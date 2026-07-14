import os
import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from demo_limits import get_tier
from models import _write_telemetry, init_db
from tempdir_compat import make_temp_dir


def _read_config(db_path):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
        return dict(rows)
    finally:
        conn.close()


def _write_config(db_path, values):
    conn = sqlite3.connect(db_path)
    try:
        for key, value in values.items():
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
        conn.commit()
    finally:
        conn.close()


class DemoAntiReinstallTests(unittest.TestCase):
    def setUp(self):
        self.data_home = make_temp_dir()
        self.addCleanup(self.data_home.cleanup)
        self.previous_env = {
            "NEXAR_TESTING": os.environ.get("NEXAR_TESTING"),
            "XDG_DATA_HOME": os.environ.get("XDG_DATA_HOME"),
            "APPDATA": os.environ.get("APPDATA"),
            "FINANZAS_DATA_DIR": os.environ.get("FINANZAS_DATA_DIR"),
        }
        os.environ.pop("NEXAR_TESTING", None)
        os.environ["XDG_DATA_HOME"] = self.data_home.name
        os.environ["APPDATA"] = self.data_home.name
        self.addCleanup(self._restore_env)
        self.machine_patch = patch("models._generate_machine_id", return_value="TEST-HWID-001")
        self.machine_patch.start()
        self.addCleanup(self.machine_patch.stop)

    def _restore_env(self):
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _db_path(self, name):
        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        return str(Path(temp_dir.name) / name)

    def test_first_installation_starts_demo(self):
        db_path = self._db_path("first.sqlite3")

        init_db(db_path)
        cfg = _read_config(db_path)

        self.assertEqual(cfg["license_tier"], "DEMO")
        self.assertEqual(cfg["demo_install_date"], date.today().isoformat())
        self.assertEqual(get_tier(db_path), "DEMO")

    def test_second_initialization_keeps_original_demo_date(self):
        db_path = self._db_path("same.sqlite3")
        original = (date.today() - timedelta(days=7)).isoformat()

        init_db(db_path)
        _write_config(db_path, {"demo_install_date": original})
        _write_telemetry(original, "TEST-HWID-001")
        init_db(db_path)

        self.assertEqual(_read_config(db_path)["demo_install_date"], original)

    def test_recreating_sqlite_restores_demo_date_from_external_telemetry(self):
        first_db = self._db_path("deleted.sqlite3")
        original = (date.today() - timedelta(days=12)).isoformat()

        init_db(first_db)
        _write_config(first_db, {"demo_install_date": original})
        _write_telemetry(original, "TEST-HWID-001")
        init_db(first_db)

        recreated_db = self._db_path("recreated.sqlite3")
        init_db(recreated_db)

        self.assertEqual(_read_config(recreated_db)["demo_install_date"], original)

    def test_changing_database_path_restores_demo_date_for_same_device(self):
        first_db = self._db_path("folder_a.sqlite3")
        moved_db = self._db_path("folder_b.sqlite3")
        original = (date.today() - timedelta(days=20)).isoformat()

        init_db(first_db)
        _write_config(first_db, {"demo_install_date": original})
        _write_telemetry(original, "TEST-HWID-001")
        init_db(first_db)
        init_db(moved_db)

        self.assertEqual(_read_config(moved_db)["demo_install_date"], original)

    def test_expired_demo_stays_expired_after_simulated_reinstall(self):
        first_db = self._db_path("expired.sqlite3")
        expired = (date.today() - timedelta(days=31)).isoformat()

        init_db(first_db)
        _write_config(first_db, {"demo_install_date": expired})
        _write_telemetry(expired, "TEST-HWID-001")
        init_db(first_db)

        recreated_db = self._db_path("expired_recreated.sqlite3")
        init_db(recreated_db)

        self.assertEqual(_read_config(recreated_db)["demo_install_date"], expired)
        self.assertEqual(get_tier(recreated_db), "DEMO_EXPIRED")

    def test_paid_licenses_are_not_blocked_by_expired_demo_date(self):
        for plan in ("BASICA", "PRO", "FULL"):
            with self.subTest(plan=plan):
                db_path = self._db_path(f"{plan.lower()}.sqlite3")
                init_db(db_path)
                values = {
                    "license_tier": plan,
                    "license_plan": plan,
                    "demo_install_date": (date.today() - timedelta(days=90)).isoformat(),
                }
                if plan in {"PRO", "FULL"}:
                    values["license_expires_at"] = (date.today() + timedelta(days=15)).isoformat()
                _write_config(db_path, values)

                self.assertEqual(get_tier(db_path), plan)

    def test_testing_mode_does_not_write_real_telemetry(self):
        db_path = self._db_path("testing.sqlite3")
        os.environ["NEXAR_TESTING"] = "1"

        with patch("models._write_telemetry") as write_telemetry:
            init_db(db_path)

        self.assertIsNotNone(_read_config(db_path)["demo_install_date"])
        write_telemetry.assert_not_called()

    def test_temporary_remote_error_preserves_paid_local_state(self):
        from licensing import check_license

        for plan in ("BASICA", "PRO", "FULL"):
            with self.subTest(plan=plan):
                temp_dir = make_temp_dir()
                self.addCleanup(temp_dir.cleanup)
                os.environ["FINANZAS_DATA_DIR"] = temp_dir.name
                db_path = str(Path(temp_dir.name) / "database.db")
                init_db(db_path)
                values = {
                    "version": "FULL",
                    "license_tier": plan,
                    "license_plan": plan,
                    "license_key": f"NXR-FIN-{plan}",
                }
                if plan in {"PRO", "FULL"}:
                    values["license_expires_at"] = (date.today() + timedelta(days=10)).isoformat()
                _write_config(db_path, values)

                with patch(
                    "licensing.license_sdk.validate_saved_license",
                    return_value=(False, "Error validando licencia: timeout"),
                ), patch("builtins.print"):
                    result = check_license.check_license()

                cfg = _read_config(db_path)
                self.assertEqual(result, plan)
                self.assertEqual(cfg["license_tier"], plan)

    def test_structured_temporary_remote_error_preserves_paid_local_state(self):
        from licensing import check_license

        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        os.environ["FINANZAS_DATA_DIR"] = temp_dir.name
        db_path = str(Path(temp_dir.name) / "database.db")
        init_db(db_path)
        _write_config(
            db_path,
            {
                "version": "FULL",
                "license_tier": "PRO",
                "license_plan": "PRO",
                "license_key": "NXR-FIN-PRO",
                "license_expires_at": (date.today() + timedelta(days=10)).isoformat(),
            },
        )

        with patch(
            "licensing.license_sdk.validate_saved_license",
            return_value=(False, "temporary", {"reason": "timeout"}),
        ), patch("builtins.print"):
            result = check_license.check_license()

        cfg = _read_config(db_path)
        self.assertEqual(result, "PRO")
        self.assertEqual(cfg["license_tier"], "PRO")

    def test_non_validated_sdk_state_is_not_temporary_and_revokes(self):
        from licensing import check_license

        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        os.environ["FINANZAS_DATA_DIR"] = temp_dir.name
        db_path = str(Path(temp_dir.name) / "database.db")
        init_db(db_path)
        _write_config(
            db_path,
            {
                "version": "FULL",
                "license_tier": "PRO",
                "license_plan": "PRO",
                "license_key": "NXR-FIN-PRO",
                "license_expires_at": (date.today() + timedelta(days=10)).isoformat(),
            },
        )

        with patch(
            "licensing.license_sdk.validate_saved_license",
            return_value=(False, "No se pudo cargar el SDK nexar_licencias."),
        ), patch("builtins.print"):
            result = check_license.check_license()

        cfg = _read_config(db_path)
        self.assertEqual(result, "DEMO")
        self.assertEqual(cfg["license_tier"], "DEMO")

    def test_explicit_remote_rejection_keeps_revocation(self):
        from licensing import check_license

        temp_dir = make_temp_dir()
        self.addCleanup(temp_dir.cleanup)
        os.environ["FINANZAS_DATA_DIR"] = temp_dir.name
        db_path = str(Path(temp_dir.name) / "database.db")
        init_db(db_path)
        _write_config(
            db_path,
            {
                "version": "FULL",
                "license_tier": "PRO",
                "license_plan": "PRO",
                "license_key": "NXR-FIN-PRO",
                "license_expires_at": (date.today() + timedelta(days=10)).isoformat(),
            },
        )

        with patch(
            "licensing.license_sdk.validate_saved_license",
            return_value=(False, "La licencia es invalida, expiro o fue revocada."),
        ), patch("builtins.print"):
            result = check_license.check_license()

        cfg = _read_config(db_path)
        self.assertEqual(result, "DEMO")
        self.assertEqual(cfg["license_tier"], "DEMO")


if __name__ == "__main__":
    unittest.main()
