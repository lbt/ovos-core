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
"""Intent service wrapping padatious."""
from threading import Event
from time import time as get_time, sleep
from typing import List, Optional

from padacioso.opm import PadaciosoPipelinePlugin, _unmunge

from ovos_bus_client.message import Message
from ovos_utils.log import LOG, deprecated
from ovos_utils.messagebus import get_message_lang

try:
    import padatious
    from padatious.match_data import MatchData as PadatiousIntent
    from ovos_intent_plugin_padatious import PadatiousPipelinePlugin
except:
    PadatiousPipelinePlugin = None


class PadatiousMatcher:
    """Matcher class to avoid redundancy in padatious intent matching."""

    @deprecated("PadatiousMatcher class is deprecated, use padatious plugin instead", "0.1.0")
    def __init__(self, service):
        self.service = service

    def match_high(self, utterances, lang=None, message=None):
        """Intent matcher for high confidence.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
        """
        return self.service.match_high(utterances, lang, message)

    def match_medium(self, utterances, lang=None, message=None):
        """Intent matcher for medium confidence.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
        """
        return self.service.match_medium(utterances, lang, message)

    def match_low(self, utterances, lang=None, message=None):
        """Intent matcher for low confidence.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
        """
        return self.service.match_low(utterances, lang, message)


class PadatiousService:
    """Service class for padatious intent matching."""

    @deprecated("PadatiousService has been replaced by ovos-intent-plugin-padatious, "
                "use the new pipeline plugin mechanism instead of this class", "0.0.9")
    def __init__(self, bus, config):
        self.bus = bus
        self._plugin = None
        # TODO - wrap everything below into properties with deprecation warnings
        self.padatious_config = config
        self.conf_high = self.padatious_config.get("conf_high") or 0.95
        self.conf_med = self.padatious_config.get("conf_med") or 0.8
        self.conf_low = self.padatious_config.get("conf_low") or 0.5
        self.containers = {}
        self.finished_training_event = Event()
        self.finished_initial_train = False
        self.train_delay = self.padatious_config.get('train_delay', 4)
        self.train_time = get_time() + self.train_delay
        self.registered_intents = []
        self.registered_entities = []

    def bind(self, plugin):
        self._plugin = plugin
        if not isinstance(self._plugin, PadaciosoPipelinePlugin):
            LOG.debug('Using Padatious intent parser.')
        else:
            LOG.debug('Using Padacioso intent parser.')

    @property
    def plugin(self):
        # lazy loaded only if accessed, allow IntentService to pass reference of already loaded plugin
        if not self._plugin:
            if self.padatious_config.get("regex_only") or PadatiousPipelinePlugin is None:
                _plugin = PadaciosoPipelinePlugin(self.bus, self.padatious_config)
            else:
                try:
                    _plugin = PadatiousPipelinePlugin(self.bus, self.padatious_config)
                except:
                    _plugin = PadaciosoPipelinePlugin(self.bus, self.padatious_config)
            self.bind(_plugin)
        return self._plugin

    # deprecated proxies for plugin methods
    @deprecated("PadatiousService has been replaced by ovos-intent-plugin-padatious, "
                "this handler is deprecated and no longer connected to a bus event (it won't be called)", "0.0.9")
    def train(self, message=None):
        """Perform padatious training.
        Args:
            message (Message): optional triggering message
        """
        self.finished_training_event.clear()
        padatious_single_thread = self.padatious_config.get('single_thread', True)
        if message is None:
            single_thread = padatious_single_thread
        else:
            single_thread = message.data.get('single_thread',
                                             padatious_single_thread)
        self.plugin.train(single_thread=single_thread)

        LOG.info('Training complete.')
        self.finished_training_event.set()
        if not self.finished_initial_train:
            self.bus.emit(Message('mycroft.skills.trained'))
            self.finished_initial_train = True

    @deprecated("PadatiousService has been replaced by ovos-intent-plugin-padatious, "
                "this handler is deprecated and no longer connected to a bus event (it won't be called)", "0.0.9")
    def wait_and_train(self):
        """Wait for minimum time between training and start training."""
        if not self.finished_initial_train:
            return
        sleep(self.train_delay)
        if self.train_time < 0.0:
            return

        if self.train_time <= get_time() + 0.01:
            self.train_time = -1.0
            self.train()

    @deprecated("PadatiousService has been replaced by ovos-intent-plugin-padatious, "
                "this handler is deprecated and no longer connected to a bus event (it won't be called)", "0.0.9")
    def handle_detach_intent(self, message):
        """Messagebus handler for detaching padatious intent.
        Args:
            message (Message): message triggering action
        """
        munged = message.data.get('intent_name')
        name, skill_id = _unmunge(munged)  # TODO - validate - is original munging same as plugin ?
        self.plugin.detach_intent(skill_id=skill_id, intent_name=name)

    @deprecated("PadatiousService has been replaced by ovos-intent-plugin-padatious, "
                "this handler is deprecated and no longer connected to a bus event (it won't be called)", "0.0.9")
    def handle_detach_skill(self, message):
        """Messagebus handler for detaching all intents for skill.
        Args:
            message (Message): message triggering action
        """
        skill_id = message.data['skill_id']
        self.plugin.detach_skill(skill_id)

    @deprecated("PadatiousService has been replaced by ovos-intent-plugin-padatious, "
                "this handler is deprecated and no longer connected to a bus event (it won't be called)", "0.0.9")
    def register_intent(self, message):
        """Messagebus handler for registering intents.
        Args:
            message (Message): message triggering action
        """
        munged = message.data.get('name')
        name, skill_id = _unmunge(munged)  # TODO - validate - is original munging same as plugin ?
        lang = get_message_lang()
        file_name = message.data.get("file_name")
        if file_name:
            self.plugin.register_intent_from_file(skill_id=skill_id, intent_name=name,
                                                  lang=lang, file_name=file_name)
        else:
            samples = message.data.get("samples") or []
            self.plugin.register_intent(skill_id=skill_id, intent_name=name,
                                        lang=lang, samples=samples)

    @deprecated("PadatiousService has been replaced by ovos-intent-plugin-padatious, "
                "this handler is deprecated and no longer connected to a bus event (it won't be called)", "0.0.9")
    def register_entity(self, message):
        """Messagebus handler for registering entities.
        Args:
            message (Message): message triggering action
        """
        munged = message.data.get('name')
        name, skill_id = _unmunge(munged)  # TODO - validate - is original munging same as plugin ?
        lang = get_message_lang()
        file_name = message.data.get("file_name")
        if file_name:
            self.plugin.register_entity_from_file(skill_id=skill_id, entity_name=name,
                                                  lang=lang, file_name=file_name)
        else:
            samples = message.data.get("samples") or []
            self.plugin.register_entity(skill_id=skill_id, entity_name=name,
                                        lang=lang, samples=samples)

    @deprecated("PadatiousService has been replaced by ovos-intent-plugin-padatious, "
                "this handler is deprecated and no longer connected to a bus event (it won't be called)", "0.0.9")
    def calc_intent(self, utterances: List[str], lang: str = None) -> Optional[PadatiousIntent]:
        """
        Get the best intent match for the given list of utterances. Utilizes a
        thread pool for overall faster execution. Note that this method is NOT
        compatible with Padatious, but is compatible with Padacioso.
        @param utterances: list of string utterances to get an intent for
        @param lang: language of utterances
        @return:
        """
        if isinstance(utterances, str):
            utterances = [utterances]  # backwards compat when arg was a single string
        return self.plugin.match(utterances, lang)
