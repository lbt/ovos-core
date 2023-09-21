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
"""Mycroft's intent service, providing intent parsing since forever!"""
from mycroft.metrics import report_timing
# compat imports
from mycroft.skills.intent_services.adapt_service import AdaptService
from mycroft.skills.intent_services.padatious_service import PadatiousService
from ovos_bus_client.message import Message
from ovos_bus_client.session import SessionManager
from ovos_core.intent_services import IntentService as _IS
from ovos_utils.log import LOG, log_deprecation, deprecated


class IntentService(_IS):
    """contains only junk code that logs deprecation warnings to not break downstream api"""

    def __init__(self, bus):
        self.bus = bus
        self.pipeline_plugins = {}
        self._converse = None
        self._common_qa = None
        self._fallback = None
        self._adapt_service = None
        self._padatious_service = None
        self._padacioso_service = None

    # deprecated properties / handlers
    # convenience properties around default pipeline components / backwards compat
    @property
    def active_skills(self):
        log_deprecation("self.active_skills is deprecated! use Session instead", "0.0.9")
        session = SessionManager.get()
        return session.active_skills

    @active_skills.setter
    def active_skills(self, val):
        log_deprecation("self.active_skills is deprecated! use Session instead", "0.0.9")
        session = SessionManager.get()
        session.active_skills = []
        for skill_id, ts in val:
            session.activate_skill(skill_id)

    @property
    def converse(self):
        log_deprecation("self.converse has been deprecated, "
                        "pipeline plugin object references can be found under self.pipeline_plugins", "0.1.0")
        if self._converse is None:
            self._converse = self.pipeline_plugins.get("converse")
        return self._converse

    @property
    def common_qa(self):
        log_deprecation("self.common_qa has been deprecated, "
                        "pipeline plugin object references can be found under self.pipeline_plugins", "0.1.0")
        if self._common_qa is None:
            self._common_qa = self.pipeline_plugins.get("common_qa")
        return self._common_qa

    @property
    def fallback(self):
        log_deprecation("self.fallback has been deprecated, "
                        "pipeline plugin object references can be found under self.pipeline_plugins", "0.1.0")
        if self._fallback is None:
            self._fallback = self.pipeline_plugins.get("fallback")
        return self._fallback

    @property
    def adapt_service(self):
        log_deprecation("self.adapt_service has been deprecated, "
                        "get plugin object reference via self.pipeline_plugins.get('adapt')", "0.1.0")
        if self._adapt_service is None:
            _p = self.pipeline_plugins.get("adapt")
            self._adapt_service = AdaptService(self.bus)
            self._adapt_service.bind(_p)
        return self._adapt_service

    @property
    def padacioso_service(self):
        log_deprecation("self.padacioso has been deprecated, "
                        "get plugin object reference via self.pipeline_plugins.get('padacioso')", "0.1.0")
        if self._padacioso_service is None:
            _p = self.pipeline_plugins.get("padacioso")
            self._padacioso_service = PadatiousService(self.bus, config={"regex_only": True})
            self._padacioso_service.bind(_p)
        return self._padacioso_service

    @property
    def padatious_service(self):
        log_deprecation("self.padatious has been deprecated, "
                        "get plugin object reference via self.pipeline_plugins.get('padatious')", "0.1.0")
        if self._padatious_service is None:
            _p = self.pipeline_plugins.get("padatious")
            self._padatious_service = PadatiousService(self.bus)
            self._padatious_service.bind(_p)
        return self._padatious_service

    @property
    def skill_names(self):
        log_deprecation("self.skill_names has been deprecated and is always an empty dict,"
                        " skill names no longer in use, reference skill_id directly", "0.0.8")
        return {}

    @property
    def registered_intents(self):
        log_deprecation("self.registered_intents has been deprecated, moved to AdaptService,"
                        "pipeline plugin object references can be found under self.pipeline_plugins", "0.1.0")
        return self.adapt_service.registered_intents

    @property
    def registered_vocab(self):
        log_deprecation("self.registered_vocab has been deprecated, moved to AdaptService,"
                        "pipeline plugin object references can be found under self.pipeline_plugins", "0.1.0")
        return self.adapt_service.registered_vocab

    @deprecated("skill names have been replaced across the whole ecosystem with skill_ids, "
                "this handler is no longer connected to the messagebus", "0.0.8")
    def update_skill_name_dict(self, message):
        """Messagebus handler, updates dict of id to skill name conversions."""
        pass

    @deprecated("skill names have been replaced across the whole ecosystem with skill_ids, "
                "get_skill_name is no longer necessary", "0.0.8")
    def get_skill_name(self, skill_id):
        """Get skill name from skill ID.

        Args:
            skill_id: a skill id as encoded in Intent handlers.

        Returns:
            (str) Skill name or the skill id if the skill wasn't found
        """
        return skill_id

    @deprecated("handle_register_intent moved to AdaptService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def handle_register_vocab(self, message):
        """Register adapt vocabulary.

        Args:
            message (Message): message containing vocab info
        """
        pass

    @deprecated("handle_register_intent moved to AdaptService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def handle_register_intent(self, message):
        """Register adapt intent.

        Args:
            message (Message): message containing intent info
        """
        pass

    @deprecated("handle_detach_intent moved to AdaptService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def handle_detach_intent(self, message):
        """Remover adapt intent.

        Args:
            message (Message): message containing intent info
        """
        pass

    @deprecated("handle_detach_skill moved to AdaptService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def handle_detach_skill(self, message):
        """Remove all intents registered for a specific skill.

        Args:
            message (Message): message containing intent info
        """
        pass

    @deprecated("handle_get_adapt moved to AdaptService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def handle_get_adapt(self, message):
        """handler getting the adapt response for an utterance.

        Args:
            message (Message): message containing utterance
        """
        pass

    @deprecated("handle_adapt_manifest moved to AdaptService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def handle_adapt_manifest(self, message):
        """Send adapt intent manifest to caller.

        Argument:
            message: query message to reply to.
        """
        pass

    @deprecated("handle_vocab_manifest moved to AdaptService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def handle_vocab_manifest(self, message):
        """Send adapt vocabulary manifest to caller.

        Argument:
            message: query message to reply to.
        """
        pass

    @deprecated("handle_get_padatious moved to PadatiousService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def handle_get_padatious(self, message):
        """messagebus handler for perfoming padatious parsing.

        Args:
            message (Message): message triggering the method
        """
        pass

    @deprecated("handle_padatious_manifest moved to PadatiousService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def handle_padatious_manifest(self, message):
        """Messagebus handler returning the registered padatious intents.

        Args:
            message (Message): message triggering the method
        """
        pass

    @deprecated("handle_entity_manifest moved to PadatiousService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def handle_entity_manifest(self, message):
        """Messagebus handler returning the registered padatious entities.

        Args:
            message (Message): message triggering the method
        """
        pass

    @deprecated("do_converse moved to ConverseService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def do_converse(self, utterances, skill_id, lang, message):
        """DEPRECATED: do not use, method only for api backwards compatibility

        Logs a warning and calls ConverseService.converse

        Args:
            utterances (list of tuples): utterances paired with normalized
                                         versions.
            skill_id: skill to query.
            lang (str): current language
            message (Message): message containing interaction info.
        """
        # NOTE: can not delete method for backwards compat with upstream
        LOG.warning("self.do_converse has been deprecated!\n"
                    "use self.converse.converse instead")
        return self.converse.converse(utterances, skill_id, lang, message)

    @deprecated("do_converse moved to ConverseService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def handle_converse_error(self, message):
        """DEPRECATED: do not use, method only for api backwards compatibility
        Logs a warning
        """
        # NOTE: can not delete method for backwards compat with upstream
        LOG.warning("handle_converse_error has been deprecated!")

    @deprecated("do_converse moved to ConverseService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def remove_active_skill(self, skill_id):
        """DEPRECATED: do not use, method only for api backwards compatibility

        Logs a warning and calls ConverseService.deactivate_skill

        Args:
            skill_id (str): skill to remove
        """
        # NOTE: can not delete method for backwards compat with upstream
        LOG.warning("self.remove_active_skill has been deprecated!\n"
                    "use self.converse.deactivate_skill instead")
        self.converse.deactivate_skill(skill_id)

    @deprecated("do_converse moved to ConverseService, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def add_active_skill(self, skill_id):
        """DEPRECATED: do not use, method only for api backwards compatibility

        Logs a warning and calls ConverseService.activate_skill

        Args:
            skill_id (str): identifier of skill to be added.
        """
        # NOTE: can not delete method for backwards compat with upstream
        LOG.warning("self.add_active_skill has been deprecated!\n"
                    "use self.converse.activate_skill instead")
        self.converse.activate_skill(skill_id)

    @deprecated("send_metrics/selene has been deprecated, overriding this method has no effect, "
                "it has been disconnected from the bus event", "0.0.8")
    def send_metrics(self, intent, context, stopwatch):
        """Send timing metrics to the backend.

        NOTE: This only applies to those with Opt In.

        Args:
            intent (IntentMatch or None): intet match info
            context (dict): context info about the interaction
            stopwatch (StopWatch): Timing info about the skill parsing.
        """
        ident = context['ident'] if 'ident' in context else None
        # Determine what handled the intent
        if intent and intent.intent_service == 'Converse':
            intent_type = f'{intent.skill_id}:converse'
        elif intent and intent.intent_service == 'Fallback':
            intent_type = 'fallback'
        elif intent and intent.intent_service == 'CommonQuery':
            intent_type = 'common_qa'
        elif intent:  # Handled by an other intent parser
            # Recreate skill name from skill id
            parts = intent.intent_type.split(':')
            intent_type = self.get_skill_name(parts[0])
            if len(parts) > 1:
                intent_type = ':'.join([intent_type] + parts[1:])
        else:  # No intent was found
            intent_type = 'intent_failure'

        report_timing(ident, 'intent_service', stopwatch,
                      {'intent_type': intent_type})
