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
from queue import Queue

from mycroft import MYCROFT_ROOT_PATH
from mycroft.audio.service import PlaybackService
from mycroft.messagebus import Message
from ovos_config import Configuration
from ovos_utils.process_utils import ProcessState

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
        self.assertTrue(ProcessState.NOT_STARTED <= speech.status.state < ProcessState.ALIVE)
        speech.run()
        self.assertTrue(speech.status.state >= ProcessState.ALIVE)
        self.assertTrue(tts_factory_mock.create.called)
        self.assertTrue(speech.tts.init.called)

        bus.on.assert_any_call('mycroft.stop', speech.handle_stop)
        bus.on.assert_any_call('mycroft.audio.speech.stop',
                               speech.handle_stop)
        bus.on.assert_any_call('speak', speech.handle_speak)

        self.assertTrue(speech.status.state > ProcessState.STOPPING)
        speech.shutdown()
        self.assertTrue(speech.status.state <= ProcessState.STOPPING)
        self.assertFalse(speech.is_alive())

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

    @mock.patch('mycroft.audio.service.TTS')
    def test_queue(self, mock_TTS, tts_factory_mock, config_mock):
        mock_TTS.queue = Queue()
        setup_mocks(config_mock, tts_factory_mock)
        bus = mock.Mock()
        speech = PlaybackService(bus=bus)

        with self.assertRaises(ValueError):
            msg = Message("", {})
            speech.handle_queue_audio(msg)

        with self.assertRaises(FileNotFoundError):
            msg = Message("", {"filename": "no_exist.mp3"})
            speech.handle_queue_audio(msg)

        f = f"{MYCROFT_ROOT_PATH}/mycroft/res/snd/start_listening.wav"
        msg = Message("", {"filename": f})
        speech.handle_queue_audio(msg)
        data = mock_TTS.queue.get()
        self.assertEqual(data[0], "wav")
        self.assertEqual(data[1], f)
        self.assertEqual(data[-1], False)

    @mock.patch('mycroft.audio.service.report_timing')
    def test_speak(self, mock_timing, tts_factory_mock, config_mock):

        setup_mocks(config_mock, tts_factory_mock)
        bus = mock.Mock()
        speech = PlaybackService(bus=bus)
        speech.execute_tts = mock.Mock()

        msg = Message("speak", {"utterance": "hello world"})

        # test message.context.destination
        msg.context["destination"] = "external"
        speech.handle_speak(msg)
        self.assertFalse(speech.execute_tts.called)
        self.assertFalse(mock_timing.called)

        msg.context["destination"] = "audio"
        speech.handle_speak(msg)
        self.assertTrue(speech.execute_tts.called)
        self.assertTrue(mock_timing.called)

        msg.context.pop("destination")
        speech.handle_speak(msg)
        self.assertTrue(speech.execute_tts.called)
        self.assertTrue(mock_timing.called)


if __name__ == "__main__":
    unittest.main()
