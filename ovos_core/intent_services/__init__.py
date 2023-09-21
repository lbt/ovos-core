# Copyright 2017 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from ovos_config.config import Configuration
from ovos_config.locale import setup_locale

from ovos_bus_client.message import Message
from ovos_bus_client.session import SessionManager
from ovos_core.intent_services.commonqa_service import CommonQAService
from ovos_core.intent_services.converse_service import ConverseService
from ovos_core.intent_services.fallback_service import FallbackService
from ovos_core.transformers import MetadataTransformersService, UtteranceTransformersService
from ovos_plugin_manager.templates.pipeline import PipelineStagePlugin
from ovos_utils.log import LOG, deprecated, log_deprecation
from ovos_utils.messagebus import get_message_lang
from ovos_utils.metrics import Stopwatch


class IntentService:
    """OpenVoiceOS intent service. parses utterances using a variety of systems.

    The intent service also provides the internal API for registering and
    querying the intent service.
    """

    def __init__(self, bus):
        self.bus = bus
        config = Configuration()

        self.pipeline_plugins = self.load_pipeline_plugins()
        self.utterance_plugins = UtteranceTransformersService(bus, config=config)
        self.metadata_plugins = MetadataTransformersService(bus, config=config)

        # Intents API
        self.bus.on('intent.service.intent.get', self.handle_get_intent)

        # Pipeline API
        self.bus.on('recognizer_loop:utterance', self.handle_utterance)

        # Context related handlers
        self.bus.on('intent.service:add_context', self.handle_add_context)
        self.bus.on('intent.service:remove_context', self.handle_remove_context)
        self.bus.on('intent.service:clear_context', self.handle_clear_context)

        # backwards compat namespace - TODO deprecate 0.2.0
        self.bus.on('add_context', self.handle_add_context)
        self.bus.on('remove_context', self.handle_remove_context)
        self.bus.on('clear_context', self.handle_clear_context)

    @property
    def pipeline(self):
        # List of functions to use to match the utterance with intent, listed in priority order.
        config = Configuration().get("intents") or {}
        return config.get("pipeline", [
            "converse",
            "padacioso_high",
            "adapt",
            "common_qa",
            "fallback_high",
            "padacioso_medium",
            "fallback_medium",
            "padacioso_low",
            "fallback_low"
        ])

    def load_pipeline_plugins(self):
        plugins = {}  # TODO in OPM
        loaded_plugins = {}
        for plug_name, plug in plugins.items():
            matchers = [plug.matcher_id,
                        plug.matcher_id + "_low",
                        plug.matcher_id + "_medium",
                        plug.matcher_id + "_high"]
            if any(m in self.pipeline for m in matchers):
                try:
                    # TODO - read plugin config
                    conf = {}
                    loaded_plugins[plug_name] = plug(self.bus, conf)
                except Exception as e:
                    LOG.error(f"failed to load plugin {plug_name}:{e}")
                    continue
        return loaded_plugins

    @property
    def pipeline_matchers(self):
        matchers = []
        for m in self.pipeline:
            matcher_id = m.replace("_high", "").replace("_medium", "").replace("_low", "")
            if matcher_id not in self.pipeline_plugins:
                LOG.error(f"{matcher_id} not installed, skipping pipeline stage!")
                continue

            plugin = self.pipeline_plugins[matcher_id]

            if m.endswith("_high"):
                matchers.append(plugin.match_high)
            elif m.endswith("_medium"):
                matchers.append(plugin.match_medium)
            elif m.endswith("_low"):
                matchers.append(plugin.match_low)
            else:
                matchers.append(plugin.match)
        return matchers

    # service implementation
    def _handle_transformers(self, message):
        """
        Pipe utterance through transformer plugins to get more metadata.
        Utterances may be modified by any parser and context overwritten
        """
        lang = get_message_lang(message)  # per query lang or default Configuration lang
        original = utterances = message.data.get('utterances', [])
        message.context["lang"] = lang
        utterances, message.context = self.utterance_plugins.transform(utterances, message.context)
        if original != utterances:
            message.data["utterances"] = utterances
            LOG.debug(f"utterances transformed: {original} -> {utterances}")
        message.context = self.metadata_plugins.transform(message.context)
        return message

    @staticmethod
    def disambiguate_lang(message):
        """ disambiguate language of the query via pre-defined context keys
        1 - stt_lang -> tagged in stt stage  (STT used this lang to transcribe speech)
        2 - request_lang -> tagged in source message (wake word/request volunteered lang info)
        3 - detected_lang -> tagged by transformers  (text classification, free form chat)
        4 - config lang (or from message.data)
        """
        cfg = Configuration()
        default_lang = get_message_lang(message)
        valid_langs = set([cfg.get("lang", "en-us")] + cfg.get("secondary_langs'", []))
        lang_keys = ["stt_lang",
                     "request_lang",
                     "detected_lang"]
        for k in lang_keys:
            if k in message.context:
                v = message.context[k]
                if v in valid_langs:
                    if v != default_lang:
                        LOG.info(f"replaced {default_lang} with {k}: {v}")
                    return v
                else:
                    LOG.warning(f"ignoring {k}, {v} is not in enabled languages: {valid_langs}")

        return default_lang

    def get_pipeline(self, no_side_effects=False):
        """return a list of matcher functions ordered by priority
        utterances will be sent to each matcher in order until one can handle the utterance
        the list can be configured in mycroft.conf under intents.pipeline,
        in the future plugins will be supported for users to define their own pipeline"""
        matchers = []
        for m in self.pipeline:
            matcher_id = m.replace("_high", "").replace("_medium", "").replace("_low", "")
            if matcher_id not in self.pipeline_plugins:
                LOG.error(f"{matcher_id} not installed, skipping pipeline stage!")
                continue

            plugin = self.pipeline_plugins[matcher_id]
            if no_side_effects and isinstance(plugin, PipelineStagePlugin):
                continue

            if m.endswith("_high"):
                matchers.append(plugin.match_high)
            elif m.endswith("_medium"):
                matchers.append(plugin.match_medium)
            elif m.endswith("_low"):
                matchers.append(plugin.match_low)
            else:
                matchers.append(plugin.match)
        return matchers

    def handle_utterance(self, message):
        """Main entrypoint for handling user utterances

        Monitor the messagebus for 'recognizer_loop:utterance', typically
        generated by a spoken interaction but potentially also from a CLI
        or other method of injecting a 'user utterance' into the system.

        Utterances then work through this sequence to be handled:
        1) UtteranceTransformers can modify the utterance and metadata in message.context
        2) MetadataTransformers can modify the metadata in message.context
        3) Language is extracted from message
        4) Active skills attempt to handle using converse()
        5) Padatious high match intents (conf > 0.95)
        6) Adapt intent handlers
        7) CommonQuery Skills
        8) High Priority Fallbacks
        9) Padatious near match intents (conf > 0.8)
        10) General Fallbacks
        11) Padatious loose match intents (conf > 0.5)
        12) Catch all fallbacks including Unknown intent handler

        If all these fail the complete_intent_failure message will be sent
        and a generic error sound played.

        Args:
            message (Message): The messagebus data
        """
        try:

            # Get utterance utterance_plugins additional context
            message = self._handle_transformers(message)

            # tag language of this utterance
            lang = self.disambiguate_lang(message)
            try:
                setup_locale(lang)
            except Exception as e:
                LOG.exception(f"Failed to set lingua_franca default lang to {lang}")

            utterances = message.data.get('utterances', [])

            stopwatch = Stopwatch()

            # match
            match = None
            with stopwatch:
                # Loop through the matching functions until a match is found.
                for match_func in self.get_pipeline():
                    match = match_func(utterances, lang, message)
                    if match:
                        break
            LOG.debug(f"intent matching took: {stopwatch.time}")
            if match:
                message.data["utterance"] = match.utterance

                if match.skill_id:
                    # update converse session
                    session = SessionManager.get(message)
                    session.activate_skill(match.skill_id)

                    message.context["skill_id"] = match.skill_id
                    # If the service didn't report back the skill_id it
                    # takes on the responsibility of making the skill "active"

                # Launch skill if not handled by the match function
                if match.intent_type:
                    # keep all original message.data and update with intent
                    # match, mycroft-core only keeps "utterances"
                    data = dict(message.data)
                    data.update(match.intent_data)
                    reply = message.reply(match.intent_type, data)
                    self.bus.emit(reply)

            else:
                # Nothing was able to handle the intent
                # Ask politely for forgiveness for failing in this vital task
                self.send_complete_intent_failure(message)

            return match, message.context, stopwatch

        except Exception as err:
            LOG.exception(err)

    def send_complete_intent_failure(self, message):
        """Send a message that no skill could handle the utterance.

        Args:
            message (Message): original message to forward from
        """
        sound = Configuration().get('sounds', {}).get('error', "snd/error.mp3")
        self.bus.emit(message.forward('mycroft.audio.play_sound', {"uri": sound}))
        self.bus.emit(message.forward('complete_intent_failure'))

    def handle_add_context(self, message):
        """Add context

        Args:
            message: data contains the 'context' item to add
                     optionally can include 'word' to be injected as
                     an alias for the context item.
        """
        entity = {'confidence': 1.0}
        context = message.data.get('context')
        word = message.data.get('word') or ''
        origin = message.data.get('origin') or ''
        # if not a string type try creating a string from it
        if not isinstance(word, str):
            word = str(word)
        entity['data'] = [(word, context)]
        entity['match'] = word
        entity['key'] = word
        entity['origin'] = origin
        sess = SessionManager.get(message)
        sess.context.inject_context(entity)

    def handle_remove_context(self, message):
        """Remove specific context

        Args:
            message: data contains the 'context' item to remove
        """
        context = message.data.get('context')
        if context:
            sess = SessionManager.get(message)
            sess.context.remove_context(context)

    def handle_clear_context(self, message):
        """Clears all keywords from context """
        sess = SessionManager.get(message)
        sess.context.clear_context()

    def handle_get_intent(self, message):
        """Get intent from pipeline

        Args:
            message (Message): message containing utterance
        """
        utterance = message.data["utterance"]
        lang = get_message_lang(message)

        # Loop through the matching functions until a match is found.
        for match_func in self.get_pipeline(no_side_effects=True):
            match = match_func([utterance], lang, message)
            if match:
                if match.intent_type:
                    intent_data = match.intent_data
                    intent_data["intent_name"] = match.intent_type
                    intent_data["intent_service"] = match.intent_service
                    intent_data["skill_id"] = match.skill_id
                    intent_data["handler"] = match_func.__name__
                    self.bus.emit(message.reply("intent.service.intent.reply",
                                                {"intent": intent_data}))
                return

        # signal intent failure
        self.bus.emit(message.reply("intent.service.intent.reply",
                                    {"intent": None}))
