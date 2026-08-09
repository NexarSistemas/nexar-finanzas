import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask

import routes
import update_checker


def _release_response(stable_names=True, tag_name="v9.9.9"):
    response = Mock()
    response.raise_for_status.return_value = None
    windows_asset = (
        "Nexar_Finanzas_Windows_Setup.exe"
        if stable_names else "NexarFinanzas_v9.9.9_setup.exe"
    )
    linux_asset = (
        "Nexar_Finanzas_Linux_amd64.deb"
        if stable_names else "NexarFinanzas_v9.9.9_linux_amd64.deb"
    )
    response.json.return_value = {
        "tag_name": tag_name,
        "html_url": "https://github.com/NexarSistemas/nexar-finanzas/releases/tag/v9.9.9",
        "assets": [
            {
                "name": windows_asset,
                "browser_download_url": f"https://example.test/{windows_asset}",
            },
            {
                "name": linux_asset,
                "browser_download_url": f"https://example.test/{linux_asset}",
            },
            {
                "name": "NexarFinanzas_v9.9.9_macos_x86_64.dmg",
                "browser_download_url": "https://example.test/NexarFinanzas_v9.9.9_macos_x86_64.dmg",
            },
            {
                "name": "NexarFinanzas_v9.9.9_macos_x86_64.zip",
                "browser_download_url": "https://example.test/NexarFinanzas_v9.9.9_macos_x86_64.zip",
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
        self.assertEqual(info["asset_name"], "Nexar_Finanzas_Windows_Setup.exe")
        self.assertEqual(info["asset_url"], "https://example.test/Nexar_Finanzas_Windows_Setup.exe")
        self.assertEqual(info["latest"], "9.9.9")
        self.assertNotIn(".deb", info["asset_name"])

    def test_linux_selects_only_linux_asset(self):
        info = self._check_release_for("Linux")
        self.assertEqual(info["asset_kind"], "linux")
        self.assertEqual(info["asset_name"], "Nexar_Finanzas_Linux_amd64.deb")
        self.assertEqual(info["asset_url"], "https://example.test/Nexar_Finanzas_Linux_amd64.deb")
        self.assertNotIn(".exe", info["asset_name"])

    def test_versioned_release_assets_remain_compatible(self):
        with (
            patch.object(update_checker.platform, "system", return_value="Windows"),
            patch.object(update_checker.requests, "get", return_value=_release_response(False)),
        ):
            info = update_checker.check_latest_release("1.0.0")

        self.assertEqual(info["asset_name"], "NexarFinanzas_v9.9.9_setup.exe")
        self.assertEqual(info["latest"], "9.9.9")

    def test_release_version_is_normalized_from_tag_and_invalid_tags_are_rejected(self):
        self.assertEqual(update_checker.normalize_release_version("v09.009.0009"), "9.9.9")
        self.assertEqual(update_checker.normalize_release_version("v9.9.9-beta"), "")
        with (
            patch.object(update_checker.platform, "system", return_value="Windows"),
            patch.object(update_checker.requests, "get", return_value=_release_response(tag_name="v9.9.9-beta")),
        ):
            self.assertEqual(update_checker.check_latest_release("1.0.0"), {"available": False})

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

    def test_stable_installers_use_downloaded_release_version_and_are_safe(self):
        app = Flask(__name__)
        with tempfile.TemporaryDirectory() as tmp:
            update_dir = Path(tmp) / "updates"
            update_dir.mkdir()
            app.config.update(BASE_DIR=tmp, APP_VERSION="1.0.0")

            for platform_name, installer in (
                ("windows", "Nexar_Finanzas_Windows_Setup.exe"),
                ("linux", "Nexar_Finanzas_Linux_amd64.deb"),
            ):
                installer_path = update_dir / installer
                installer_path.touch()
                (update_dir / f"{installer}.version").write_text("v9.9.9", encoding="utf-8")
                with app.app_context(), patch.object(routes, "get_update_platform", return_value=platform_name):
                    self.assertEqual(routes._installer_version(installer, "v9.9.9"), "9.9.9")
                    self.assertEqual(routes._update_file(installer), installer_path)
                    self.assertEqual(routes._update_list()[0]["version"], "9.9.9")
                    with self.assertRaises(FileNotFoundError):
                        routes._update_file(f"../{installer}")
                    with self.assertRaises(FileNotFoundError):
                        routes._update_file("otro-installer.exe")

            legacy_installer = update_dir / "NexarFinanzas_v9.9.9_setup.exe"
            legacy_installer.touch()
            with app.app_context(), patch.object(routes, "get_update_platform", return_value="windows"):
                self.assertEqual(routes._installer_version(legacy_installer.name), "9.9.9")
                self.assertEqual(routes._update_file(legacy_installer.name), legacy_installer)


if __name__ == "__main__":
    unittest.main()
