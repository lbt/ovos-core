# Copyright 2019 Mycroft AI Inc.
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
from unittest import skip
from unittest.mock import Mock, patch

from ovos_bus_client.message import Message
from ovos_core.skill_manager import SkillManager
from ovos_workshop.skill_launcher import SkillLoader
from ..base import MycroftUnitTestBase


class TestSkillManager(MycroftUnitTestBase):
    mock_package = 'mycroft.skills.skill_manager.'

    def setUp(self):
        super().setUp()
        self._mock_skill_updater()
        self._mock_skill_settings_downloader()
        self.skill_manager = SkillManager(self.message_bus_mock)
        self._mock_skill_loader_instance()

    def _mock_skill_settings_downloader(self):
        settings_download_patch = patch(
            self.mock_package + 'SkillSettingsDownloader',
            spec=True
        )
        self.addCleanup(settings_download_patch.stop)
        self.settings_download_mock = settings_download_patch.start()

    def _mock_skill_updater(self):
        skill_updater_patch = patch(
            self.mock_package + 'SkillUpdater',
            spec=True
        )
        self.addCleanup(skill_updater_patch.stop)
        self.skill_updater_mock = skill_updater_patch.start()

    def _mock_skill_loader_instance(self):
        self.skill_dir = self.temp_dir.joinpath('test_skill')
        self.skill_loader_mock = Mock(spec=SkillLoader)
        self.skill_loader_mock.instance = Mock()
        self.skill_loader_mock.instance.default_shutdown = Mock()
        self.skill_loader_mock.instance.converse = Mock()
        self.skill_loader_mock.instance.converse.return_value = True
        self.skill_loader_mock.skill_id = 'test_skill'
        self.skill_manager.skill_loaders = {
            str(self.skill_dir): self.skill_loader_mock
        }

    def test_instantiate(self):
        expected_result = [
            'skillmanager.list',
            'skillmanager.deactivate',
            'skillmanager.keep',
            'skillmanager.activate',
            'mycroft.skills.initialized',
            'mycroft.skills.trained',
            'mycroft.network.connected',
            'mycroft.internet.connected',
            'mycroft.gui.available',
            'mycroft.network.disconnected',
            'mycroft.internet.disconnected',
            'mycroft.gui.unavailable',
            'mycroft.skills.is_alive',
            'mycroft.skills.is_ready',
            'mycroft.skills.all_loaded'
        ]

        self.assertListEqual(expected_result,
                             self.message_bus_mock.event_handlers)

    def test_unload_removed_skills(self):
        self.skill_manager._unload_removed_skills()

        self.assertDictEqual({}, self.skill_manager.skill_loaders)
        self.skill_loader_mock.unload.assert_called_once_with()

    def test_send_skill_list(self):
        self.skill_loader_mock.active = True
        self.skill_loader_mock.loaded = True
        self.skill_manager.send_skill_list(None)

        self.assertListEqual(
            ['mycroft.skills.list'],
            self.message_bus_mock.message_types
        )
        message_data = self.message_bus_mock.message_data[-1]
        self.assertIn('test_skill', message_data.keys())
        skill_data = message_data['test_skill']
        self.assertDictEqual(dict(active=True, id='test_skill'), skill_data)

    def test_stop(self):
        self.skill_manager.stop()

        self.assertTrue(self.skill_manager._stop_event.is_set())
        instance = self.skill_loader_mock.instance
        instance.default_shutdown.assert_called_once_with()

    @skip("TODO - refactor test")
    def test_handle_paired(self):
        self.skill_updater_mock.next_download = 0
        self.skill_manager.handle_paired(None)
        updater = self.skill_manager.skill_updater
        updater.post_manifest.assert_called_once_with(
            reload_skills_manifest=True)

    def test_deactivate_skill(self):
        message = Message("test.message", {'skill': 'test_skill'})
        message.response = Mock()
        self.skill_manager.deactivate_skill(message)
        self.skill_loader_mock.deactivate.assert_called_once()
        message.response.assert_called_once()

    @patch("ovos_utils.log.LOG.exception")
    def test_deactivate_skill_exception(self, mock_exception_logger):
        message = Message("test.message", {'skill': 'test_skill'})
        message.response = Mock()
        self.skill_loader_mock.deactivate.side_effect = Exception()
        self.skill_manager.deactivate_skill(message)
        self.skill_loader_mock.deactivate.assert_called_once()
        message.response.assert_called_once()
        mock_exception_logger.assert_called_once_with('Failed to deactivate test_skill')

    def test_deactivate_except(self):
        message = Message("test.message", {'skill': 'test_skill'})
        message.response = Mock()
        self.skill_loader_mock.active = True
        foo_skill_loader = Mock(spec=SkillLoader)
        foo_skill_loader.skill_id = 'foo'
        foo2_skill_loader = Mock(spec=SkillLoader)
        foo2_skill_loader.skill_id = 'foo2'
        test_skill_loader = Mock(spec=SkillLoader)
        test_skill_loader.skill_id = 'test_skill'
        self.skill_manager.skill_loaders['foo'] = foo_skill_loader
        self.skill_manager.skill_loaders['foo2'] = foo2_skill_loader
        self.skill_manager.skill_loaders['test_skill'] = test_skill_loader

        self.skill_manager.deactivate_except(message)
        foo_skill_loader.deactivate.assert_called_once()
        foo2_skill_loader.deactivate.assert_called_once()
        self.assertFalse(test_skill_loader.deactivate.called)

    def test_activate_skill(self):
        message = Message("test.message", {'skill': 'test_skill'})
        message.response = Mock()
        test_skill_loader = Mock(spec=SkillLoader)
        test_skill_loader.skill_id = 'test_skill'
        test_skill_loader.active = False

        self.skill_manager.skill_loaders = {}
        self.skill_manager.skill_loaders['test_skill'] = test_skill_loader

        self.skill_manager.activate_skill(message)
        test_skill_loader.activate.assert_called_once()
        message.response.assert_called_once()

    @patch("ovos_utils.log.LOG.exception")
    def test_activate_skill_exception(self, mock_exception_logger):
        message = Message("test.message", {'skill': 'test_skill'})
        message.response = Mock()
        test_skill_loader = Mock(spec=SkillLoader)
        test_skill_loader.activate.side_effect = Exception()
        test_skill_loader.skill_id = 'test_skill'
        test_skill_loader.active = False

        self.skill_manager.skill_loaders = {}
        self.skill_manager.skill_loaders['test_skill'] = test_skill_loader

        self.skill_manager.activate_skill(message)
        test_skill_loader.activate.assert_called_once()
        message.response.assert_called_once()
        mock_exception_logger.assert_called_once_with('Couldn\'t activate skill test_skill')
