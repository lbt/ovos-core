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
import unittest
import unittest.mock as mock

from ovos_config import Configuration
from mycroft.audio.service import PlaybackService
from mycroft.messagebus import Message
from mycroft.tts.remote_tts import RemoteTTSTimeoutException

"""Tests for speech dispatch service."""


tts_mock = mock.Mock()


def setup_mocks(config_mock, tts_factory_mock, fallback="A"):
    """Do the common setup for the mocks."""
    c = Configuration.get()
    c["tts"] = {"module": "A", "fallback_module": fallback}
    config_mock.return_value = c

    tts_factory_mock.create.return_value = tts_mock
    config_mock.reset_mock()
    tts_factory_mock.reset_mock()
    tts_mock.reset_mock()


@mock.patch('mycroft.audio.service.Configuration')
@mock.patch('mycroft.audio.service.TTSFactory')
class TestSpeech(unittest.TestCase):
    def test_life_cycle(self, tts_factory_mock, config_mock):
        """Ensure the init and shutdown behaves as expected."""
        setup_mocks(config_mock, tts_factory_mock)
        bus = mock.Mock()
        speech = PlaybackService(bus=bus)
        speech.daemon = True
        speech.run()

        self.assertTrue(tts_factory_mock.create.called)
        bus.on.assert_any_call('mycroft.stop', speech.handle_stop)
        bus.on.assert_any_call('mycroft.audio.speech.stop',
                               speech.handle_stop)
        bus.on.assert_any_call('speak', speech.handle_speak)

        speech.shutdown()
        self.assertFalse(speech.is_alive())
        # TODO TTS.playback is now a singleton, this test does not reach it anymore when using mock
        #self.assertTrue(tts_mock.playback.stop.called)
        #self.assertTrue(tts_mock.playback.join.called)

    @mock.patch('mycroft.audio.service.check_for_signal')
    def test_stop(self, check_for_signal_mock, tts_factory_mock, config_mock):
        """Ensure the stop handler signals stop correctly."""
        setup_mocks(config_mock, tts_factory_mock)
        bus = mock.Mock()
        config_mock.get.return_value = {'tts': {'module': 'test'}}
        speech = PlaybackService(bus=bus)

        speech._last_stop_signal = 0
        check_for_signal_mock.return_value = False
        speech.handle_stop(Message('mycroft.stop'))
        self.assertEqual(speech._last_stop_signal, 0)

        check_for_signal_mock.return_value = True
        speech.handle_stop(Message('mycroft.stop'))
        self.assertNotEqual(speech._last_stop_signal, 0)
        speech.shutdown()

    def test_fallback_tts_creation(self, tts_factory_mock, config_mock):
        """Ensure the init and shutdown behaves as expected."""
        setup_mocks(config_mock, tts_factory_mock, fallback="B")
        bus = mock.Mock()
        speech = PlaybackService(bus=bus)
        speech.fallback_tts = None
        speech._get_tts_fallback()
        self.assertIsNotNone(speech.fallback_tts)
        self.assertTrue(speech.fallback_tts.init.called)

    def test_no_fallback_tts(self, tts_factory_mock, config_mock):
        """Ensure the init and shutdown behaves as expected."""
        setup_mocks(config_mock, tts_factory_mock)
        bus = mock.Mock()

        _real = PlaybackService._get_tts_fallback
        _real2 = PlaybackService.execute_fallback_tts
        PlaybackService._get_tts_fallback = mock.Mock()
        PlaybackService.execute_fallback_tts = mock.Mock()
        PlaybackService.tts = mock.Mock()
        speech = PlaybackService(bus=bus)
        self.assertTrue(tts_factory_mock.create.called)
        self.assertFalse(speech._get_tts_fallback.called)

        speech.execute_tts("hello", "123")
        self.assertTrue(speech.tts.execute.called)
        self.assertFalse(speech.execute_fallback_tts.called)

        PlaybackService._get_tts_fallback = _real
        PlaybackService.execute_fallback_tts = _real2

    def test_fallback_tts(self, tts_factory_mock, config_mock):
        """Ensure the init and shutdown behaves as expected."""
        setup_mocks(config_mock, tts_factory_mock, fallback="B")
        bus = mock.Mock()
        _real = PlaybackService._get_tts_fallback
        PlaybackService._get_tts_fallback = mock.Mock()

        speech = PlaybackService(bus=bus)
        self.assertTrue(tts_factory_mock.create.called)
        self.assertTrue(speech._get_tts_fallback.called)

        PlaybackService._get_tts_fallback = _real

    def test_fallback_tts_execute(self, tts_factory_mock, config_mock):
        """Ensure the init and shutdown behaves as expected."""
        setup_mocks(config_mock, tts_factory_mock, fallback="B")
        bus = mock.Mock()

        class FailingTTS:
            def execute(*args, **kwargs):
                raise RuntimeError("oops")

        speech = PlaybackService(bus=bus)
        speech.tts = FailingTTS()

        speech.execute_tts("hello", "123")
        self.assertTrue(speech.fallback_tts.execute.called)


if __name__ == "__main__":
    unittest.main()
