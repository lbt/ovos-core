import os
import re
from os.path import dirname
from threading import Event

import ovos_core.intent_services
from ovos_bus_client.message import Message
from ovos_bus_client.session import SessionManager
from ovos_config.config import Configuration
from ovos_utils import flatten_list
from ovos_utils.log import LOG


class StopService:
    """Intent Service thats handles stopping skills."""

    def __init__(self, bus):
        self.bus = bus
        self._voc_cache = {}
        self.load_resource_files()

    def load_resource_files(self):
        base = f"{dirname(dirname(__file__))}/locale"
        for lang in os.listdir(base):
            lang2 = lang.split("-")[0].lower()
            self._voc_cache[lang2] = {}
            for f in os.listdir(f"{base}/{lang}"):
                with open(f"{base}/{lang}/{f}") as fi:
                    lines = [l for l in fi.read().split("\n")
                             if l.strip() and not l.startswith("#")]
                    n = f.split(".", 1)[0]
                    self._voc_cache[lang2][n] = lines

    @property
    def config(self):
        """
        Returns:
            converse_config (dict): config for converse handling options
        """
        return Configuration().get("skills", {}).get("stop") or {}

    @property
    def active_skills(self):
        session = SessionManager.get()
        return session.active_skills

    @active_skills.setter
    def active_skills(self, val):
        session = SessionManager.get()
        session.active_skills = []
        for skill_id, ts in val:
            session.activate_skill(skill_id)

    def get_active_skills(self, message=None):
        """Active skill ids ordered by converse priority
        this represents the order in which converse will be called

        Returns:
            active_skills (list): ordered list of skill_ids
        """
        session = SessionManager.get(message)
        return [skill[0] for skill in session.active_skills]

    def _collect_stop_skills(self, message):
        """use the messagebus api to determine which skills can stop
        This includes all skills and external applications"""

        want_stop = []
        skill_ids = []

        active_skills = self.get_active_skills(message)

        if not active_skills:
            return want_stop

        event = Event()

        def handle_ack(msg):
            nonlocal event
            skill_id = msg.data["skill_id"]

            # validate the stop pong
            if all((skill_id not in want_stop,
                    msg.data.get("can_handle", True),
                    skill_id in active_skills)):
                want_stop.append(skill_id)

            if skill_id not in skill_ids:  # track which answer we got
                skill_ids.append(skill_id)

            if all(s in skill_ids for s in active_skills):
                # all skills answered the ping!
                event.set()

        self.bus.on("skill.stop.pong", handle_ack)

        # ask skills if they want to converse
        for skill_id in active_skills:
            self.bus.emit(message.forward(f"{skill_id}.stop.ping",
                                          {"skill_id": skill_id}))

        # wait for all skills to acknowledge they want to converse
        event.wait(timeout=0.5)

        self.bus.remove("skill.stop.pong", handle_ack)
        return want_stop or active_skills

    def stop_skill(self, skill_id, message):
        """Call skill and ask if they want to process the utterance.

        Args:
            skill_id: skill to query.
            message (Message): message containing interaction info.

        Returns:
            handled (bool): True if handled otherwise False.
        """
        converse_msg = message.reply(f"{skill_id}.stop.request")
        result = self.bus.wait_for_response(converse_msg, 'skill.stop.response')
        if result and 'error' in result.data:
            error_msg = result.data['error']
            LOG.error(f"{skill_id}: {error_msg}")
            return False
        elif result is not None:
            return result.data.get('result', False)

    def match_stop(self, utterances, lang, message):
        """If utterance is an exact match for "stop" , run before intent stage

        Args:
            utterances (list):  list of utterances
            lang (string):      4 letter ISO language code
            message (Message):  message to use to generate reply

        Returns:
            IntentMatch if handled otherwise None.
        """
        # we call flatten in case someone is sending the old style list of tuples
        utterances = flatten_list(utterances)
        return self._match(message, utterances[0], lang, exact=True)

    def match_stop_low(self, utterances, lang, message):
        """ before fallback_low , if "stop" is in the utterance

        Args:
            utterances (list):  list of utterances
            lang (string):      4 letter ISO language code
            message (Message):  message to use to generate reply

        Returns:
            IntentMatch if handled otherwise None.
        """
        # we call flatten in case someone is sending the old style list of tuples
        utterances = flatten_list(utterances)
        return self._match(message, utterances[0], lang, exact=False)

    def _match(self, message, utterance, lang, exact=True):

        is_stop = self.voc_match(utterance, 'stop', exact=exact, lang=lang)
        is_global_stop = self.voc_match(utterance, 'global_stop', exact=True, lang=lang) or \
                         (is_stop and not len(self.active_skills))

        # TODO - approximate conf based on utterance_remainder
        conf = 0.8 if exact else 0.5
        if len(self.active_skills) > 0:
            conf += 0.1

        if is_global_stop:
            self.bus.emit(message.reply("mycroft.stop", {}))
            return ovos_core.intent_services.IntentMatch('Stop', "global_stop", {"conf": conf},
                                                         "stop.openvoiceos", utterance)

        if is_stop:
            # check if any skill can stop
            for skill_id in self._collect_stop_skills(message):
                if self.stop_skill(skill_id, message):
                    return ovos_core.intent_services.IntentMatch('Stop', "stop", {"conf": conf},
                                                                 skill_id, utterance)
        return None

    def voc_match(self, utt: str, voc_filename: str, lang: str,
                  exact: bool = False):
        """
        Determine if the given utterance contains the vocabulary provided.

        By default the method checks if the utterance contains the given vocab
        thereby allowing the user to say things like "yes, please" and still
        match against "Yes.voc" containing only "yes". An exact match can be
        requested.

        The method first checks in the current Skill's .voc files and secondly
        in the "res/text" folder of mycroft-core. The result is cached to
        avoid hitting the disk each time the method is called.

        Args:
            utt (str): Utterance to be tested
            voc_filename (str): Name of vocabulary file (e.g. 'yes' for
                                'res/text/en-us/yes.voc')
            lang (str): Language code, defaults to self.lang
            exact (bool): Whether the vocab must exactly match the utterance

        Returns:
            bool: True if the utterance has the given vocabulary it
        """
        lang = lang.split("-")[0].lower()
        if lang not in self._voc_cache:
            return False

        _vocs = self._voc_cache[lang].get(voc_filename) or []

        if utt and _vocs:
            if exact:
                # Check for exact match
                return any(i.strip() == utt
                           for i in _vocs)
            else:
                # Check for matches against complete words
                return any([re.match(r'.*\b' + i + r'\b.*', utt)
                            for i in _vocs])
        return False


if __name__ == "__main__":
    from ovos_utils.fakebus import FakeBus
    s = StopService(FakeBus())
    m = s.match_stop(["where is the nearest bus stop"], "en", Message(""))
    # None
    print(m)
    m = s.match_stop(["stop"], "en", Message(""))
    # IntentMatch(intent_service='Stop', intent_type='global_stop',
    #             intent_data={'conf': 0.8}, skill_id='stop.openvoiceos', utterance='stop')
    print(m)
    m = s.match_stop_low(["stop that right now"], "en", Message(""))
    # IntentMatch(intent_service='Stop', intent_type='global_stop', intent_data={'conf': 0.5},
    #             skill_id='stop.openvoiceos', utterance='stop that right now')
    print(m)
    m = s.match_stop_low(["where is the nearest bus stop"], "en", Message(""))
    # IntentMatch(intent_service='Stop', intent_type='global_stop', intent_data={'conf': 0.5},
    #             skill_id='stop.openvoiceos', utterance='where is the nearest bus stop')
    print(m)