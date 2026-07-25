import json
import os
import sqlite3
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock, patch

from licensing.license_cache import (
    atomic_save_license_cache,
    atomic_write_json,
    ensure_license_cache_directory,
    get_license_cache_path,
    get_user_data_dir,
    migrate_legacy_license_cache,
)
from licensing.license_service import validate_license_key
from tempdir_compat import make_temp_dir


@dataclass(frozen=True)
class _FakeSDKConfig:
    cache_file: Path
    cache_dir: Path | None = None

    @property
    def resolved_cache_file(self):
        if self.cache_dir is None or self.cache_file.is_absolute():
            return self.cache_file
        return self.cache_dir / self.cache_file


def _create_config_db(directory: Path) -> Path:
    db_path = directory / "license.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()
    return db_path


class LicenseCachePathTests(unittest.TestCase):
    def test_linux_uses_xdg_data_home(self):
        path = get_license_cache_path(
            system="Linux",
            environ={"XDG_DATA_HOME": "/tmp/xdg"},
            home=Path("/home/user"),
        )
        self.assertEqual(path, Path("/tmp/xdg/NexarFinanzas/license_cache.json"))

    def test_linux_falls_back_to_local_share(self):
        path = get_license_cache_path(system="Linux", environ={}, home=Path("/home/user"))
        self.assertEqual(path, Path("/home/user/.local/share/NexarFinanzas/license_cache.json"))

    def test_linux_ignores_relative_xdg_data_home(self):
        path = get_license_cache_path(
            system="Linux",
            environ={"XDG_DATA_HOME": "relative/data"},
            home=Path("/home/user"),
        )
        self.assertEqual(path, Path("/home/user/.local/share/NexarFinanzas/license_cache.json"))
        self.assertTrue(path.is_absolute())

    def test_windows_uses_local_app_data(self):
        path = get_license_cache_path(
            system="Windows",
            environ={"LOCALAPPDATA": r"C:\Users\User\AppData\Local"},
            home=Path("/unused"),
        )
        self.assertEqual(path, Path(r"C:\Users\User\AppData\Local") / "NexarFinanzas" / "license_cache.json")

    def test_macos_uses_application_support(self):
        path = get_license_cache_path(system="Darwin", environ={}, home=Path("/Users/user"))
        self.assertEqual(
            path,
            Path("/Users/user/Library/Application Support/NexarFinanzas/license_cache.json"),
        )

    def test_creates_parent_directory(self):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        destination = Path(temp_dir.name) / "nested" / "NexarFinanzas" / "license_cache.json"

        result = ensure_license_cache_directory(destination)

        self.assertEqual(result, destination)
        self.assertTrue(destination.parent.is_dir())

    def test_cache_is_independent_from_current_working_directory(self):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        unwritable_cwd = root / "readonly-install"
        data_home = root / "user-data"
        unwritable_cwd.mkdir()
        original_cwd = Path.cwd()
        os.chmod(unwritable_cwd, 0o500)
        try:
            os.chdir(unwritable_cwd)
            destination = get_license_cache_path(
                system="Linux",
                environ={"XDG_DATA_HOME": str(data_home)},
                home=root,
            )
            atomic_save_license_cache({"license_key": "NXR-FIN"}, destination=destination)
        finally:
            os.chdir(original_cwd)
            os.chmod(unwritable_cwd, 0o700)

        self.assertTrue(destination.is_file())
        self.assertFalse((unwritable_cwd / "license_cache.json").exists())

    def test_migrates_valid_legacy_cache(self):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        legacy = root / "legacy" / "license_cache.json"
        destination = root / "data" / "license_cache.json"
        legacy.parent.mkdir()
        payload = {
            "data": {"license_key": "NXR-FIN-VALID", "product": "nexar-finanzas"},
            "last_check": "2026-07-24T10:00:00",
        }
        legacy.write_text(json.dumps(payload), encoding="utf-8")

        migrated = migrate_legacy_license_cache(destination, legacy_paths=[legacy])

        self.assertTrue(migrated)
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), payload)
        self.assertTrue(legacy.exists())

    def test_migrates_cache_from_legacy_environment_override_to_canonical_path(self):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        legacy = root / "custom-cache" / "finanzas.json"
        destination = root / "user-data" / "NexarFinanzas" / "license_cache.json"
        legacy.parent.mkdir()
        payload = {
            "data": {"license_key": "NXR-FIN-ENV", "product": "nexar-finanzas"},
            "last_check": "2026-07-24T10:00:00",
        }
        legacy.write_text(json.dumps(payload), encoding="utf-8")

        with patch.dict(os.environ, {"NEXAR_CACHE_FILE": str(legacy)}, clear=True):
            migrated = migrate_legacy_license_cache(destination)

        self.assertTrue(migrated)
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), payload)
        self.assertTrue(legacy.exists())

    def test_resolves_relative_environment_override_only_as_legacy_source(self):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        legacy_dir = root / "legacy-config"
        legacy = legacy_dir / "custom-cache.json"
        destination = root / "user-data" / "NexarFinanzas" / "license_cache.json"
        legacy_dir.mkdir()
        payload = {
            "data": {"license_key": "NXR-FIN-RELATIVE", "product": "nexar-finanzas"},
            "last_check": "2026-07-24T10:00:00",
        }
        legacy.write_text(json.dumps(payload), encoding="utf-8")

        with patch.dict(
            os.environ,
            {
                "NEXAR_LICENSES_CACHE_DIR": str(legacy_dir),
                "NEXAR_CACHE_FILE": "custom-cache.json",
            },
            clear=True,
        ):
            migrated = migrate_legacy_license_cache(destination)

        self.assertTrue(migrated)
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), payload)
        self.assertTrue(legacy.exists())
        self.assertNotEqual(destination, legacy)

    def test_does_not_overwrite_existing_cache(self):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        legacy = root / "legacy" / "license_cache.json"
        destination = root / "data" / "license_cache.json"
        legacy.parent.mkdir()
        destination.parent.mkdir()
        legacy.write_text('{"data": {"license_key": "OLD"}}', encoding="utf-8")
        destination.write_text('{"data": {"license_key": "NEW"}}', encoding="utf-8")

        migrated = migrate_legacy_license_cache(destination, legacy_paths=[legacy])

        self.assertFalse(migrated)
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8"))["data"]["license_key"], "NEW")

    def test_ignores_corrupt_legacy_cache(self):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        legacy = root / "license_cache.json"
        destination = root / "data" / "license_cache.json"
        legacy.write_text("{broken", encoding="utf-8")

        migrated = migrate_legacy_license_cache(destination, legacy_paths=[legacy])

        self.assertFalse(migrated)
        self.assertFalse(destination.exists())

    def test_does_not_migrate_nexar_tienda_cache(self):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        legacy = root / "NexarTienda" / "license_cache.json"
        destination = root / "NexarFinanzas" / "license_cache.json"
        legacy.parent.mkdir()
        legacy.write_text(
            json.dumps({"data": {"license_key": "NXR-TIENDA", "product": "nexar-tienda"}}),
            encoding="utf-8",
        )

        migrated = migrate_legacy_license_cache(destination, legacy_paths=[legacy])

        self.assertFalse(migrated)
        self.assertFalse(destination.exists())

    def test_atomic_write_keeps_previous_cache_when_replace_fails(self):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        destination = Path(temp_dir.name) / "license_cache.json"
        original = {"data": {"license_key": "ORIGINAL"}}
        destination.write_text(json.dumps(original), encoding="utf-8")

        with patch("licensing.license_cache.os.replace", side_effect=PermissionError("read only")):
            with self.assertRaises(PermissionError):
                atomic_write_json(destination, {"data": {"license_key": "NEW"}})

        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), original)
        self.assertEqual(list(destination.parent.glob(f".{destination.name}.*.tmp")), [])

    @patch("licensing.license_service.load_public_key", return_value="public-key")
    @patch("licensing.license_service.import_validar_licencia", return_value=None)
    @patch("licensing.license_service.import_validar_licencia_detalle")
    def test_cache_write_failure_is_fail_closed(
        self,
        mock_import_detail,
        _mock_import_boolean,
        _mock_public_key,
    ):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        db_path = _create_config_db(root)
        canonical = root / "data" / "license_cache.json"
        config = _FakeSDKConfig(canonical)
        license_data = {
            "license_key": "NXR-FIN-VALID",
            "plan": "BASICA",
            "product": "nexar-finanzas",
        }
        canonical.parent.mkdir(parents=True)
        canonical.write_text(
            json.dumps({"data": license_data, "last_check": "2026-07-23T10:00:00"}),
            encoding="utf-8",
        )

        def validate_detail(*_args, **kwargs):
            cache_path = kwargs["config"].resolved_cache_file
            cache_path.write_text(
                json.dumps({"data": license_data, "last_check": "2026-07-24T10:00:00"}),
                encoding="utf-8",
            )
            return {"ok": True, "source": "online", "license": license_data}

        mock_import_detail.return_value = Mock(side_effect=validate_detail)

        with patch("licensing.license_cache.os.replace", side_effect=PermissionError("read only")):
            ok, message = validate_license_key(
                "NXR-FIN-VALID",
                db_path=str(db_path),
                config=config,
            )

        self.assertFalse(ok)
        self.assertIn("no se pudo guardar", message.lower())
        conn = sqlite3.connect(db_path)
        stored = conn.execute("SELECT value FROM config WHERE key='license_tier'").fetchone()
        conn.close()
        self.assertIsNone(stored)

    @patch("licensing.license_service.load_public_key", return_value="public-key")
    @patch("licensing.license_service._activate_license_without_sdk")
    @patch("licensing.license_service.import_validar_licencia", return_value=None)
    @patch("licensing.license_service.import_validar_licencia_detalle")
    def test_legacy_validator_uses_http_fallback_and_canonical_atomic_writer(
        self,
        mock_import_detail,
        _mock_import_boolean,
        mock_activate_without_sdk,
        _mock_public_key,
    ):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        db_path = _create_config_db(root)
        canonical = root / "data" / "license_cache.json"
        config = _FakeSDKConfig(canonical)
        license_data = {
            "license_key": "NXR-FIN-LEGACY",
            "plan": "BASICA",
            "product": "nexar-finanzas",
        }

        validator = Mock(side_effect=TypeError("unexpected keyword argument 'config'"))
        mock_import_detail.return_value = validator
        mock_activate_without_sdk.return_value = (True, "Licencia activada.", license_data)

        original_cwd = Path.cwd()
        try:
            os.chdir(root)
            ok, message = validate_license_key(
                "NXR-FIN-LEGACY",
                db_path=str(db_path),
                config=config,
            )
        finally:
            os.chdir(original_cwd)

        self.assertTrue(ok, message)
        self.assertEqual(validator.call_count, 1)
        mock_activate_without_sdk.assert_called_once_with("NXR-FIN-LEGACY")
        self.assertFalse((root / "license_cache.json").exists())
        cached = json.loads(canonical.read_text(encoding="utf-8"))
        self.assertEqual(cached["data"], license_data)
        conn = sqlite3.connect(db_path)
        stored = conn.execute("SELECT value FROM config WHERE key='license_tier'").fetchone()
        conn.close()
        self.assertEqual(stored[0], "BASICA")

    @patch("licensing.license_service.load_public_key", return_value="public-key")
    @patch("licensing.license_service._activate_license_without_sdk")
    @patch("licensing.license_service.import_validar_licencia", return_value=None)
    @patch("licensing.license_service.import_validar_licencia_detalle")
    def test_sin_cache_http_fallback_preserves_custom_cache_destination(
        self,
        mock_import_detail,
        _mock_import_boolean,
        mock_activate_without_sdk,
        _mock_public_key,
    ):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        canonical = root / "custom-data" / "license_cache.json"
        config = _FakeSDKConfig(canonical)
        license_data = {
            "license_key": "NXR-FIN-FALLBACK",
            "plan": "PRO",
            "product": "nexar-finanzas",
        }
        mock_import_detail.return_value = Mock(
            return_value={"ok": False, "reason": "sin_cache"}
        )
        mock_activate_without_sdk.return_value = (True, "Licencia activada.", license_data)

        ok, message = validate_license_key("NXR-FIN-FALLBACK", config=config)

        self.assertTrue(ok, message)
        self.assertEqual(
            json.loads(canonical.read_text(encoding="utf-8"))["data"],
            license_data,
        )
        mock_activate_without_sdk.assert_called_once_with("NXR-FIN-FALLBACK")


if __name__ == "__main__":
    unittest.main()
