import unittest
from mycroft.skills.intent_services.padatious_service import PadatiousService
from ovos_bus_client.message import Message
from ovos_utils.messagebus import FakeBus


class UtteranceIntentMatchingTest(unittest.TestCase):
    def get_service(self, fuzzy=False):
        intent_service = PadatiousService(FakeBus(),
                                          {"train_delay": 1,
                                           "fuzz": fuzzy,
                                           "single_thread": True,
                                           })
        # register test intents
        filename = "/tmp/test.intent"
        with open(filename, "w") as f:
            f.write("this is a test\ntest the intent\nexecute test")
        rxfilename = "/tmp/test2.intent"
        with open(rxfilename, "w") as f:
            f.write("tell me about {thing}\nwhat is {thing}")
        data = {'file_name': filename, 'lang': 'en-US', 'name': 'test'}
        intent_service.register_intent(Message("padatious:register_intent", data))
        data = {'file_name': rxfilename, 'lang': 'en-US', 'name': 'test2'}
        intent_service.register_intent(Message("padatious:register_intent", data))
        intent_service.train()

        return intent_service

    def test_padatious_intent(self):
        intent_service = self.get_service()

        # exact match
        intent = intent_service.calc_intent("this is a test", "en-US")
        self.assertEqual(intent.name, "test")

        # fuzzy match
        intent = intent_service.calc_intent("this test", "en-US")
        self.assertEqual(intent.name, "test")
        self.assertTrue(intent.conf >= 0.6)

        # regex match
        intent = intent_service.calc_intent("tell me about Mycroft", "en-US")
        self.assertEqual(intent.name, "test2")
        self.assertEqual(intent.matches, {'thing': 'mycroft'})

        # fuzzy regex match - fail
        intent = intent_service.calc_intent("tell me everything about Mycroft", "en-US")
        self.assertIsNone(intent)

    def test_fuzzy_intent(self):
        intent_service = self.get_service(fuzzy=True)

        # exact match
        intent = intent_service.calc_intent("this is a test", "en-US")
        self.assertEqual(intent.name, "test")

        # fuzzy match
        intent = intent_service.calc_intent("this test", "en-US")
        self.assertEqual(intent.name, "test")
        self.assertTrue(intent.conf >= 0.6)

        # regex match
        intent = intent_service.calc_intent("tell me about Mycroft", "en-US")
        self.assertEqual(intent.name, "test2")
        self.assertEqual(intent.matches, {'thing': 'mycroft'})

        # fuzzy regex match - no fail
        intent = intent_service.calc_intent("tell me everything about Mycroft", "en-US")
        self.assertEqual(intent.name, "test2")
        self.assertEqual(intent.matches, {'thing': 'mycroft'})
        self.assertTrue(intent.conf <= 0.9)
