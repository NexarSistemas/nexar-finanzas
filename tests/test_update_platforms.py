import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask

import routes
import update_checker


def _release_response():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "tag_name": "v9.9.9",
        "html_url": "https://github.com/NexarSistemas/nexar-finanzas/releases/tag/v9.9.9",
        "assets": [
            {
                "name": "NexarFinanzas_v9.9.9_setup.exe",
                "browser_download_url": "https://example.test/NexarFinanzas_v9.9.9_setup.exe",
            },
            {
                "name": "NexarFinanzas_v9.9.9_linux_amd64.deb",
                "browser_download_url": "https://example.test/NexarFinanzas_v9.9.9_linux_amd64.deb",
            },
            {
                "name": "NexarFinanzas_v9.9.9_macos.dmg",
                "browser_download_url": "https://example.test/NexarFinanzas_v9.9.9_macos.dmg",
            },
            {
                "name": "NexarFinanzas_v9.9.9_macos.zip",
                "browser_download_url": "https://example.test/NexarFinanzas_v9.9.9_macos.zip",
            },
        ],
    }
    return response


class UpdatePlatformTests(unittest.TestCase):
    def _check_release_for(self, system):
        with (
            patch.object(update_checker.platform, "system", return_value=system),
            patch.object(update_checker.requests, "get", return_value=_release_response()),
        ):
            return update_checker.check_latest_release("1.0.0")

    def test_windows_selects_only_windows_asset(self):
        info = self._check_release_for("Windows")
        self.assertEqual(info["asset_kind"], "windows")
        self.assertTrue(info["asset_name"].endswith("_setup.exe"))
        self.assertNotIn(".deb", info["asset_name"])

    def test_linux_selects_only_linux_asset(self):
        info = self._check_release_for("Linux")
        self.assertEqual(info["asset_kind"], "linux")
        self.assertTrue(info["asset_name"].endswith("_linux_amd64.deb"))
        self.assertNotIn(".exe", info["asset_name"])

    def test_darwin_detects_update_without_selecting_an_installer(self):
        info = self._check_release_for("Darwin")
        self.assertTrue(info["available"])
        self.assertEqual(info["platform"], "macos")
        self.assertEqual(info["install_mode"], "manual")
        self.assertEqual(info["asset_name"], "")
        self.assertEqual(info["asset_url"], "")
        self.assertNotIn("apt", info["install_message"].lower())
        self.assertIn("manualmente", info["install_message"].lower())

    def test_unknown_platform_does_not_fall_back_to_linux(self):
        info = self._check_release_for("FreeBSD")
        self.assertEqual(info["platform"], "unsupported")
        self.assertEqual(info["asset_name"], "")
        self.assertEqual(info["asset_url"], "")

    def test_darwin_lists_no_deb_or_exe_and_generates_no_apt_command(self):
        app = Flask(__name__)
        with tempfile.TemporaryDirectory() as tmp:
            update_dir = Path(tmp) / "updates"
            update_dir.mkdir()
            (update_dir / "NexarFinanzas_v9.9.9_linux_amd64.deb").touch()
            (update_dir / "NexarFinanzas_v9.9.9_setup.exe").touch()
            app.config.update(BASE_DIR=tmp, APP_VERSION="1.0.0")
            with app.app_context(), patch.object(routes, "get_update_platform", return_value="macos"):
                self.assertEqual(routes._update_list(), [])
                with self.assertRaises(FileNotFoundError):
                    routes._update_file("NexarFinanzas_v9.9.9_linux_amd64.deb")


if __name__ == "__main__":
    unittest.main()
