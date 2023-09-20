# Copyright 2020 Mycroft AI Inc.
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
"""An intent parsing service using the Adapt parser."""
from adapt.context import ContextManagerFrame
from adapt.engine import IntentDeterminationEngine
from ovos_utils.intents import AdaptIntent, IntentBuilder, Intent
from ovos_config.config import Configuration
from ovos_bus_client.message import Message, dig_for_message
from ovos_bus_client.session import IntentContextManager as ContextManager, \
    SessionManager
from ovos_intent_plugin_adapt import AdaptPipelinePlugin
from ovos_utils.log import deprecated, log_deprecation
from ovos_utils.messagebus import get_message_lang, get_mycroft_bus


class AdaptService:
    """ this class provides methods that were deprecated in 0.0.8 ,
    it's sole purpose is to log warnings and direct users to use the plugin that replaced this implementation

    Methods here were present in ovos-core 0.0.7 and will be fully removed by ovos-core 0.0.9"""

    @deprecated("AdaptService has been replaced by ovos-intent-plugin-adapt, "
                "use the new pipeline plugin mechanism instead of this class", "0.0.9")
    def __init__(self, bus=None, config=None):
        self.bus = bus or get_mycroft_bus()  # backwards compat, bus was optional
        core_config = Configuration()
        config = config or core_config.get("context", {})
        self._plugin = AdaptPipelinePlugin(self.bus, config)

    def bind(self, plugin):
        self._plugin = plugin
        self._plugin.bus.on('intent.service.adapt.get', self.handle_get_adapt)
        self._plugin.bus.on('intent.service.adapt.manifest.get', self.handle_adapt_manifest)
        self._plugin.bus.on('intent.service.adapt.vocab.manifest.get', self.handle_vocab_manifest)

    @property
    def plugin(self):
        # lazy loaded only if accessed, allow IntentService to pass reference of already loaded plugin
        if not self._plugin:
            _plugin = AdaptPipelinePlugin(self.bus)
            self.bind(_plugin)
        return self._plugin

    # deprecated proxies for plugin methods
    @deprecated("AdaptService has been replaced by ovos-intent-plugin-adapt, "
                "this handler is deprecated and no longer connected to a bus event (it won't be called)", "0.0.9")
    def register_vocab(self, start_concept, end_concept,
                       alias_of, regex_str, lang):
        """Register Vocabulary. DEPRECATED

        This method should not be used, it has been replaced by
        register_vocabulary().
        """
        self.register_vocabulary(start_concept, end_concept, alias_of,
                                 regex_str, lang)

    @deprecated("AdaptService has been replaced by ovos-intent-plugin-adapt, "
                "this handler is deprecated and no longer connected to a bus event (it won't be called)", "0.0.9")
    def register_vocabulary(self, entity_value, entity_type,
                            alias_of, regex_str, lang):
        """Register skill vocabulary as adapt entity.

        This will handle both regex registration and registration of normal
        keywords. if the "regex_str" argument is set all other arguments will
        be ignored.

        Argument:
            entity_value: the natural langauge word
            entity_type: the type/tag of an entity instance
            alias_of: entity this is an alternative for
        """
        m = dig_for_message() or Message("")  # to dig skill_id in message.context
        m = m.forward("register_vocab", {"entity_type": entity_type,
                                         "entity_value": entity_value,
                                         "regex": regex_str,
                                         "alias_of": alias_of,
                                         "lang": lang or self.plugin})
        self.plugin._handle_adapt_vocab(m)

    @deprecated("AdaptService has been replaced by ovos-intent-plugin-adapt, "
                "this handler is deprecated and no longer connected to a bus event (it won't be called)", "0.0.9")
    def register_intent(self, intent):
        """Register new intent with adapt engine.

        Args:
            intent (IntentParser): IntentParser to register
        """
        m = dig_for_message() or Message("")  # to dig skill_id in message.context
        m = m.forward("register_intent", {"name": intent.name,
                                          "requires": intent.requires,
                                          "optional": intent.optional,
                                          "at_least_one": intent.at_least_one})
        self.plugin.handle_register_keyword_intent(m)

    @deprecated("AdaptService has been replaced by ovos-intent-plugin-adapt, "
                "this handler is deprecated and no longer connected to a bus event (it won't be called)", "0.0.9")
    def detach_skill(self, skill_id):
        """Remove all intents for skill.

        Args:
            skill_id (str): skill to process
        """
        self.plugin.detach_skill(skill_id)

    @deprecated("AdaptService has been replaced by ovos-intent-plugin-adapt, "
                "this handler is deprecated and no longer connected to a bus event (it won't be called)", "0.0.9")
    def detach_intent(self, intent_name):
        """Detach a single intent

        Args:
            intent_name (str): Identifier for intent to remove.
        """
        m = dig_for_message() or Message("")  # to dig skill_id in message.context
        skill_id = m.data.get("skill_id") or m.context.get("skill_id")
        self.plugin.detach_intent(skill_id=skill_id, intent_name=intent_name)

    # deprecated bus api handlers - moved from IntentService for deprecation
    def handle_get_adapt(self, message):
        """handler getting the adapt response for an utterance.

        Args:
            message (Message): message containing utterance
        """
        utterance = message.data["utterance"]
        lang = get_message_lang(message)
        intent = self.plugin.match_intent([utterance], lang, message)
        intent_data = intent.intent_data if intent else None
        self.plugin.bus.emit(message.reply("intent.service.adapt.reply",
                                           {"intent": intent_data}))

    def handle_adapt_manifest(self, message):
        """Send adapt intent manifest to caller.

        Argument:
            message: query message to reply to.
        """
        self.plugin.bus.emit(message.reply("intent.service.adapt.manifest",
                                           {"intents": self.registered_intents}))

    def handle_vocab_manifest(self, message):
        """Send adapt vocabulary manifest to caller.

        Argument:
            message: query message to reply to.
        """
        self.plugin.bus.emit(message.reply("intent.service.adapt.vocab.manifest",
                                           {"vocab": self.registered_vocab}))

    # deprecated properties / backwards compat syntax
    @property
    def registered_vocab(self):
        log_deprecation("self.registered_vocab has been deprecated and is unused,"
                        " use the adapt plugin directly instead", "0.0.8")
        return []

    @registered_vocab.setter
    def registered_vocab(self, val):
        log_deprecation("self.registered_vocab has been deprecated and is unused, "
                        "use the adapt plugin directly instead", "0.0.8")

    @property
    def registered_intents(self):
        lang = get_message_lang()
        return [parser.__dict__ for parser in self.plugin.engines[lang].intent_parsers]

    @property
    def context_keywords(self):
        log_deprecation("self.context_keywords has been deprecated and is unused,"
                        " use self.config.get('keywords', []) instead", "0.1.0")
        return self.plugin.config.get('keywords', [])

    @context_keywords.setter
    def context_keywords(self, val):
        log_deprecation("self.context_keywords has been deprecated and is unused, "
                        "edit mycroft.conf instead, setter will be ignored", "0.1.0")

    @property
    def context_max_frames(self):
        log_deprecation("self.context_keywords has been deprecated and is unused, "
                        "use self.config.get('max_frames', 3) instead", "0.1.0")
        return self.plugin.config.get('max_frames', 3)

    @context_max_frames.setter
    def context_max_frames(self, val):
        log_deprecation("self.context_max_frames has been deprecated and is unused, "
                        "edit mycroft.conf instead, setter will be ignored", "0.1.0")

    @property
    def context_timeout(self):
        log_deprecation("self.context_timeout has been deprecated and is unused,"
                        " use self.config.get('timeout', 2) instead", "0.1.0")
        return self.plugin.config.get('timeout', 2)

    @context_timeout.setter
    def context_timeout(self, val):
        log_deprecation("self.context_timeout has been deprecated and is unused,"
                        " edit mycroft.conf instead, setter will be ignored", "0.1.0")

    @property
    def context_greedy(self):
        log_deprecation("self.context_greedy has been deprecated and is unused, "
                        "use self.config.get('greedy', False) instead", "0.1.0")
        return self.plugin.config.get('greedy', False)

    @context_greedy.setter
    def context_greedy(self, val):
        log_deprecation("self.context_greedy has been deprecated and is unused,"
                        " edit mycroft.conf instead, setter will be ignored", "0.1.0")

    @property
    def context_manager(self):
        log_deprecation("context_manager has been deprecated, use Session.context instead", "0.1.0")
        sess = SessionManager.get()
        return sess.context

    @context_manager.setter
    def context_manager(self, val):
        log_deprecation("context_manager has been deprecated, use Session.context instead", "0.1.0")

        assert isinstance(val, ContextManager)
        sess = SessionManager.get()
        sess.context = val

    @deprecated("update_context has been deprecated, use Session.context.update_context instead", "0.1.0")
    def update_context(self, intent):
        """Updates context with keyword from the intent.

        NOTE: This method currently won't handle one_of intent keywords
              since it's not using quite the same format as other intent
              keywords. This is under investigation in adapt, PR pending.

        Args:
            intent: Intent to scan for keywords
        """
        sess = SessionManager.get()
        ents = [tag['entities'][0] for tag in intent['__tags__'] if 'entities' in tag]
        sess.context.update_context(ents)


def _entity_skill_id(skill_id):
    """Helper converting a skill id to the format used in entities.

    Arguments:
        skill_id (str): skill identifier

    Returns:
        (str) skill id on the format used by skill entities
    """
    skill_id = skill_id[:-1]
    skill_id = skill_id.replace('.', '_')
    skill_id = skill_id.replace('-', '_')
    return skill_id


def _is_old_style_keyword_message(message):
    """Simple check that the message is not using the updated format.
    TODO: Remove in v22.02
    Args:
        message (Message): Message object to check
    Returns:
        (bool) True if this is an old messagem, else False
    """
    return ('entity_value' not in message.data and 'start' in message.data)


def _update_keyword_message(message):
    """Make old style keyword registration message compatible.
    Copies old keys in message data to new names.
    Args:
        message (Message): Message to update
    """
    message.data['entity_value'] = message.data['start']
    message.data['entity_type'] = message.data['end']
