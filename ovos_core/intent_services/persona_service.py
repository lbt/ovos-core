import os
from ovos_persona import PersonaService
from ovos_utils.intents import IntentBuilder
from ovos_utils.log import LOG
from ovos_utils.xdg_utils import xdg_data_home
from ovos_workshop.app import OVOSAbstractApplication
from ovos_workshop.decorators import intent_handler

import ovos_core.intent_services


class PersonaPipeline(OVOSAbstractApplication):

    def __init__(self, bus):
        super().__init__(bus=bus, skill_id="persona-openvoiceos")
        # add persona .json files here
        personas_folder = f"{xdg_data_home()}/personas"
        os.makedirs(personas_folder, exist_ok=True)
        self.persona = PersonaService(personas_folder)
        self.active_persona = None

        self.add_event("ovos.persona.register", self.handle_register_persona)
        self.add_event("ovos.persona.deregister", self.handle_deregister_persona)
        self.add_event("ovos.persona.enable", self.handle_enable_persona)
        self.add_event("ovos.persona.disable", self.handle_disable_persona)
        self.add_event("ovos.persona.ask", self.handle_persona_request)

    # bus api to manage personas
    def handle_register_persona(self, message):
        name = message.data.get("name")
        persona = message.data.get("persona")
        self.persona.register_persona(name, persona)

    def handle_deregister_persona(self, message):
        name = message.data.get("name")
        self.persona.deregister_persona(name)

    def handle_enable_persona(self, message):
        self.active_persona = message.data.get("name")
        # TODO set active_persona in message Session
        self.set_context("ActivePersona", self.active_persona)

    def handle_disable_persona(self, message):
        self.active_persona = None
        # TODO reset active_persona in message Session
        self.remove_context("ActivePersona")

    def handle_persona_request(self, message):
        # TODO active persona from Session
        utterance = message.data['utterance']
        answer = self.persona.chatbox_ask(utterance, self.active_persona, self.lang)
        self.bus.emit(message.response(data={"utterance": answer, "lang": self.lang}))

    # active skills timeout
    def handle_deactivate(self, message):
        """ skill is no longer considered active by the intent service
        converse method will not be called, skills might want to reset state here
        """
        if self.active_persona:
            LOG.info(f"converse timed out, deactivating: {self.active_persona}")
            self.handle_disable_persona(message)

    # converse matcher
    def match_converse(self, utterances, lang, message):
        if self.active_persona:
            # check if user exited the persona loop
            if self.voc_match(utterances[0], "Release", exact=True):
                match = ovos_core.intent_services.IntentMatch('PersonaConverse',
                                                              "persona.deactivate",
                                                              {"persona": self.active_persona},
                                                              self.skill_id,
                                                              utterances[0])
                self.handle_disable_persona(message)
                return match
            return self.match(message.data["utterances"], lang, message)
        return None

    # pipeline matcher
    def match(self, utterances, lang, message):
        # TODO persona from Session
        persona = self.active_persona or self.config_core.get("default_persona")
        if persona is None:
            return None
        answer = self.persona.chatbox_ask(utterances[0], persona, lang)
        if not answer:
            return None
        self.speak(answer)
        return ovos_core.intent_services.IntentMatch('Persona',
                                                     "persona.match",
                                                     {"persona": persona},
                                                     self.skill_id,
                                                     utterances[0])
