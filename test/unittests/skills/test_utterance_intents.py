import unittest
from mycroft.skills.intent_services.padatious_service import PadatiousService
from ovos_bus_client.message import Message
from ovos_utils.messagebus import FakeBus


class UtteranceIntentMatchingTest(unittest.TestCase):
    def get_service(self, fuzzy=False, xtra_intents=False):
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

        if xtra_intents:
            filename3 = "/tmp/test3.intent"
            with open(filename3, "w") as f:
                f.write("turn on the light\nlights on")
            filename4 = "/tmp/test4.intent"
            with open(filename4, "w") as f:
                f.write("turn off the light\nlights off")
            data = {'file_name': filename3, 'lang': 'en-US', 'name': 'test3'}
            intent_service.register_intent(Message("padatious:register_intent", data))
            data = {'file_name': filename4, 'lang': 'en-US', 'name': 'test4'}
            intent_service.register_intent(Message("padatious:register_intent", data))

        intent_service.train()

        return intent_service

    def test_not_enough_intents(self):
        intent_service = self.get_service()

        # exact match
        intent = intent_service.calc_intent("this is a test", "en-US")
        self.assertEqual(intent.name, "test")

        # regex match
        intent = intent_service.calc_intent("tell me about Mycroft", "en-US")
        self.assertEqual(intent.name, "test2")
        self.assertEqual(intent.matches, {'thing': 'mycroft'})

        # not in training set - fail  (not enough intents to train classifier)
        intent = intent_service.calc_intent("this test", "en-US")
        self.assertIsNone(intent)

        # not in training set - regex fail
        intent = intent_service.calc_intent("tell me everything about Mycroft", "en-US")
        self.assertIsNone(intent)

    def test_fuzzy_intent(self):
        intent_service = self.get_service(fuzzy=True)

        # exact match
        intent = intent_service.calc_intent("this is a test", "en-US")
        self.assertEqual(intent.name, "test")

        # not in training set - fuzzy match (padacioso gets it now)
        intent = intent_service.calc_intent("this test", "en-US")
        self.assertEqual(intent.name, "test")
        self.assertTrue(intent.conf >= 0.6)

        # regex match
        intent = intent_service.calc_intent("tell me about Mycroft", "en-US")
        self.assertEqual(intent.name, "test2")
        self.assertEqual(intent.matches, {'thing': 'mycroft'})

        # not in training set - fuzzy regex match (padacioso gets it now)
        intent = intent_service.calc_intent("tell me everything about Mycroft", "en-US")
        self.assertEqual(intent.name, "test2")
        self.assertEqual(intent.matches, {'thing': 'mycroft'})
        self.assertTrue(intent.conf <= 0.9)

    def test_padatious_intent(self):
        intent_service = self.get_service(xtra_intents=True)

        # exact match
        intent = intent_service.calc_intent("this is a test", "en-US")
        self.assertEqual(intent.name, "test")

        # regex match
        intent = intent_service.calc_intent("tell me about Mycroft", "en-US")
        self.assertEqual(intent.name, "test2")
        self.assertEqual(intent.matches, {'thing': 'mycroft'})

        # not in training set (classifier get's it now)
        intent = intent_service.calc_intent("this test", "en-US")
        self.assertEqual(intent.name, "test")
        self.assertTrue(intent.conf >= 0.5)

        # not in training set - fuzzy regex match - fail  (wrong without fuzzy flag)
        intent = intent_service.calc_intent("tell me everything about Mycroft", "en-US")
        self.assertEqual(intent.name, "test")  # should be test2
        self.assertTrue(intent.conf >= 0.5)

    def test_padatious_fuzzy_intent(self):
        intent_service = self.get_service(xtra_intents=True, fuzzy=True)

        # exact match
        intent = intent_service.calc_intent("this is a test", "en-US")
        self.assertEqual(intent.name, "test")

        # regex match
        intent = intent_service.calc_intent("tell me about Mycroft", "en-US")
        self.assertEqual(intent.name, "test2")
        self.assertEqual(intent.matches, {'thing': 'mycroft'})

        # not in training set
        intent = intent_service.calc_intent("this test", "en-US")
        self.assertEqual(intent.name, "test")

        # not in training set - fuzzy regex match  (gets it right with fuzzy flag)
        intent = intent_service.calc_intent("tell me everything about Mycroft", "en-US")
        self.assertEqual(intent.name, "test2")
        self.assertTrue(intent.conf >= 0.5)
