from unittest import TestCase, mock

from ovos_config.locations import get_xdg_config_save_path, get_xdg_data_save_path, get_xdg_cache_save_path
from ovos_backend_client.identity import IdentityManager
from ovos_workshop.filesystem import FileSystemAccess


class TestXdg(TestCase):

    @mock.patch('ovos_config.meta.get_xdg_base')
    def test_base_folder(self, mock_folder):
        mock_folder.return_value = "testcroft"
        self.assertTrue(get_xdg_config_save_path().endswith("/testcroft"))
        self.assertTrue(get_xdg_data_save_path().endswith("/testcroft"))
        self.assertTrue(get_xdg_cache_save_path().endswith("/testcroft"))

    def test_identity(self):
        self.assertTrue(IdentityManager.IDENTITY_FILE.startswith(get_xdg_config_save_path()))
        self.assertTrue(IdentityManager.IDENTITY_FILE.endswith("/identity/identity2.json"))
        self.assertTrue(IdentityManager.OLD_IDENTITY_FILE not in IdentityManager.IDENTITY_FILE)

    def test_filesystem(self):
        self.assertTrue(FileSystemAccess("test").path.startswith(get_xdg_data_save_path()))

    def test_remote_config(self):
        self.assertTrue(str(REMOTE_CACHE).startswith(get_xdg_cache_save_path()))
