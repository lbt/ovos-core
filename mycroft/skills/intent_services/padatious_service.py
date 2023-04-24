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
"""Intent service wrapping Jurebes."""
from os.path import isfile
from threading import Event
from time import time as get_time, sleep

from ovos_config.config import Configuration

import jurebes
from mycroft.skills.intent_services.base import IntentMatch
from ovos_bus_client.message import Message
from ovos_utils.log import LOG


# this class is just for compat
class PadatiousIntent:
    """
    A set of data describing how a query fits into an intent
    Attributes:
        name (str): Name of matched intent
        sent (str): The query after entity extraction
        conf (float): Confidence (from 0.0 to 1.0)
        matches (dict of str -> str): Key is the name of the entity and
            value is the extracted part of the sentence
    """

    def __init__(self, name, sent, matches=None, conf=0.0):
        self.name = name
        self.sent = sent
        self.matches = matches or {}
        self.conf = conf

    def __getitem__(self, item):
        return self.matches.__getitem__(item)

    def __contains__(self, item):
        return self.matches.__contains__(item)

    def get(self, key, default=None):
        return self.matches.get(key, default)

    def __repr__(self):
        return repr(self.__dict__)


class PadatiousMatcher:
    """Matcher class to avoid redundancy in Jurebes intent matching."""

    def __init__(self, service):
        self.service = service
        self.has_result = False
        self.ret = None
        self.conf = None

    def _match_level(self, utterances, limit, lang=None):
        """Match intent and make sure a certain level of confidence is reached.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
            limit (float): required confidence level.
        """
        if not self.has_result:
            lang = lang or self.service.lang
            padatious_intent = None
            LOG.debug(f'Jurebes Matching confidence > {limit}')
            for utt in utterances:
                for variant in utt:
                    intent = self.service.calc_intent(variant, lang)
                    if intent:
                        best = padatious_intent.conf if padatious_intent else 0.0
                        if best < intent.conf:
                            padatious_intent = intent
                            padatious_intent.matches['utterance'] = utt[0]
            if padatious_intent:
                skill_id = padatious_intent.name.split(':')[0]
                self.ret = IntentMatch(
                    'Padatious', padatious_intent.name,
                    padatious_intent.matches, skill_id)
                self.conf = padatious_intent.conf
            self.has_result = True
        if self.conf and self.conf > limit:
            return self.ret

    def match_high(self, utterances, lang=None, __=None):
        """Intent matcher for high confidence.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
        """
        return self._match_level(utterances, 0.95, lang)

    def match_medium(self, utterances, lang=None, __=None):
        """Intent matcher for medium confidence.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
        """
        return self._match_level(utterances, 0.8, lang)

    def match_low(self, utterances, lang=None, __=None):
        """Intent matcher for low confidence.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
        """
        return self._match_level(utterances, 0.5, lang)


class PadatiousService:
    """Service class for Jurebes intent matching."""

    def __init__(self, bus, config):
        self.padatious_config = config
        self.bus = bus

        core_config = Configuration()
        self.lang = core_config.get("lang", "en-us")

        self.containers = {}

        self.bus.on('padatious:register_intent', self.register_intent)
        self.bus.on('padatious:register_entity', self.register_entity)
        self.bus.on('detach_intent', self.handle_detach_intent)
        self.bus.on('detach_skill', self.handle_detach_skill)
        self.bus.on('mycroft.skills.initialized', self.train)

        self.finished_training_event = Event()
        self.finished_initial_train = False

        self.train_delay = self.padatious_config['train_delay']
        self.train_time = get_time() + self.train_delay

        self.registered_intents = []
        self.registered_entities = []
        self.detached_intents = []

    def _init_lang(self, lang):
        lang = lang.lower()
        if lang not in self.containers:
            self.containers[lang] = jurebes.JurebesIntentContainer(fuzzy=self.padatious_config.get("fuzz", False))

    def _ensure_min_intents(self):
        for lang in self.containers:
            # we need at least 2 classes without capture groups to train the classifier
            # add fake intents if needed
            # TODO - maybe handle this better directly in jurebes
            n_ints = [i for i, s in self.containers[lang].intent_lines.items()
                      if not any("{" in _ for _ in s)]
            if len(n_ints) == 0:
                self.containers[lang].add_intent(":UNKNOWN_PLACEHOLDER", ["_", "-"])
            elif len(n_ints) == 1:
                self.containers[lang].add_intent(":UNKNOWN_PLACEHOLDER", ["?", "!", "."])
                self.containers[lang].add_intent(":UNKNOWN_PLACEHOLDER2", ["_", "-"])

    def train(self, message=None):
        """Perform Jurebes training.

        Args:
            message (Message): optional triggering message
        """
        self.finished_training_event.clear()

        self._ensure_min_intents()

        for lang in self.containers:
            self.containers[lang].train()

        LOG.info('Training complete.')
        self.finished_training_event.set()
        if not self.finished_initial_train:
            self.bus.emit(Message('mycroft.skills.trained'))
            self.finished_initial_train = True

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

    def __detach_intent(self, intent_name):
        """ Remove an intent if it has been registered.

        Args:
            intent_name (str): intent identifier
        """
        if intent_name not in self.detached_intents:
            self.detached_intents.append(intent_name)
        if intent_name in self.registered_intents:
            self.registered_intents.remove(intent_name)
            for lang in self.containers:
                self.containers[lang].remove_intent(intent_name)

    def handle_detach_intent(self, message):
        """Messagebus handler for detaching Jurebes intent.

        Args:
            message (Message): message triggering action
        """
        intent_name = message.data.get('intent_name')
        if intent_name in self.registered_intents:
            self.__detach_intent(intent_name)

    def handle_detach_skill(self, message):
        """Messagebus handler for detaching all intents for skill.

        Args:
            message (Message): message triggering action
        """
        skill_id = message.data['skill_id']
        remove_list = [i for i in self.registered_intents if skill_id in i]
        if len(remove_list):
            for i in remove_list:
                self.__detach_intent(i)

    def _register_object(self, message, object_name):
        """Generic method for registering a Jurebes object.

        Args:
            message (Message): trigger for action
            object_name (str): type of entry to register
        """
        file_name = message.data['file_name']
        name = message.data['name']
        lang = message.data.get('lang', self.lang).lower()

        self._init_lang(lang)  # if needed create a new intent engine for this lang

        LOG.debug('Registering Jurebes ' + object_name + ': ' + name)

        if not isfile(file_name):
            LOG.warning('Could not find file ' + file_name)
            return

        with open(file_name) as f:
            samples = [l.strip() for l in f.readlines()]

        if object_name == "intent":
            if name in self.detached_intents:
                self.detached_intents.remove(name)
            self.containers[lang].add_intent(name, samples)
        else:
            self.containers[lang].add_entity(name, samples)

        self.train_time = get_time() + self.train_delay
        self.wait_and_train()

    def register_intent(self, message):
        """Messagebus handler for registering intents.

        Args:
            message (Message): message triggering action
        """
        self.registered_intents.append(message.data['name'])
        self._register_object(message, 'intent')

    def register_entity(self, message):
        """Messagebus handler for registering entities.

        Args:
            message (Message): message triggering action
        """
        self.registered_entities.append(message.data)
        self._register_object(message, 'entity')

    def calc_intent(self, utt, lang=None):
        """Cached version of container calc_intent.

        This improves speed when called multiple times for different confidence
        levels.

        Args:
            utt (str): utterance to calculate best intent for
        """
        lang = lang or self.lang
        lang = lang.lower()
        bad_intents = self.detached_intents + [":UNKNOWN_PLACEHOLDER", ":UNKNOWN_PLACEHOLDER2"]
        if lang in self.containers:
            intent = self.containers[lang].calc_intent(utt)
            if intent and intent.intent_name not in bad_intents:
                assert isinstance(intent, jurebes.IntentMatch)
                return PadatiousIntent(name=intent.intent_name, sent=utt,
                                       matches=intent.entities,
                                       conf=intent.confidence)
