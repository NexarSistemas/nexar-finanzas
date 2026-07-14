import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from licensing.license_service import (
    finanzas_plan_from_sdk,
    get_license_state,
    normalize_paid_plan,
    normalize_plan,
    sdk_plan_from_finanzas,
    sync_license_from_remote,
    validate_saved_license,
)
from tempdir_compat import make_temp_dir


def _create_config_db(config_values):
    temp_dir = make_temp_dir()
    db_path = Path(temp_dir.name) / "license_service.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany(
        "INSERT INTO config (key, value) VALUES (?, ?)",
        list(config_values.items()),
    )
    conn.commit()
    conn.close()
    return temp_dir, str(db_path)


def _read_config(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT key, value FROM config").fetchall()
    conn.close()
    return dict(rows)


class LicenseServiceTests(unittest.TestCase):
    def test_normalizes_legacy_aliases_without_mixing_pro_and_full(self):
        self.assertEqual(normalize_plan("BASIC"), "BASICA")
        self.assertEqual(normalize_plan("MENSUAL_PRO"), "PRO")
        self.assertEqual(normalize_plan("MENSUAL_FULL"), "FULL")
        self.assertEqual(normalize_plan("FULL"), "FULL")
        self.assertEqual(finanzas_plan_from_sdk("MENSUAL_FULL"), "FULL")
        self.assertEqual(sdk_plan_from_finanzas("FULL"), "MENSUAL_FULL")
        self.assertEqual(sdk_plan_from_finanzas("PRO"), "PRO")
        self.assertEqual(normalize_paid_plan("DEMO"), "")

    def test_effective_state_for_expired_monthly_without_basica_is_demo_expired(self):
        temp_dir, db_path = _create_config_db(
            {
                "license_tier": "FULL",
                "license_plan": "FULL",
                "license_expires_at": str(date.today() - timedelta(days=1)),
                "basica_activada": "0",
            }
        )
        self.addCleanup(temp_dir.cleanup)

        state = get_license_state(db_path)

        self.assertEqual(state.stored_tier, "FULL")
        self.assertEqual(state.effective_tier, "DEMO_EXPIRED")
        self.assertTrue(state.subscription_expired)

    def test_effective_state_for_expired_monthly_with_basica_falls_back_to_basica(self):
        temp_dir, db_path = _create_config_db(
            {
                "license_tier": "PRO",
                "license_plan": "PRO",
                "license_expires_at": str(date.today() - timedelta(days=1)),
                "basica_activada": "1",
            }
        )
        self.addCleanup(temp_dir.cleanup)

        state = get_license_state(db_path)

        self.assertEqual(state.stored_tier, "PRO")
        self.assertEqual(state.effective_tier, "BASICA")
        self.assertTrue(state.subscription_expired)

    def test_sync_remote_keeps_full_as_real_finanzas_tier(self):
        temp_dir, db_path = _create_config_db({"basica_activada": "0"})
        self.addCleanup(temp_dir.cleanup)

        sync_license_from_remote(
            db_path,
            {
                "license_key": "NXR-FIN-FULL",
                "plan": "MENSUAL_FULL",
                "expira": str(date.today() + timedelta(days=30)),
                "max_devices": 2,
            },
        )

        cfg = _read_config(db_path)
        self.assertEqual(cfg["license_tier"], "FULL")
        self.assertEqual(cfg["license_plan"], "FULL")
        self.assertEqual(cfg["basica_activada"], "0")

    def test_sync_remote_accepts_direct_paid_plan_activation_matrix(self):
        cases = (
            ("BASICA", "BASICA", ""),
            ("PRO", "PRO", str(date.today() + timedelta(days=30))),
            ("MENSUAL_FULL", "FULL", str(date.today() + timedelta(days=30))),
        )

        for remote_plan, expected_plan, expires_at in cases:
            with self.subTest(remote_plan=remote_plan):
                temp_dir, db_path = _create_config_db({"basica_activada": "0"})
                self.addCleanup(temp_dir.cleanup)

                sync_license_from_remote(
                    db_path,
                    {
                        "license_key": f"NXR-FIN-{expected_plan}",
                        "plan": remote_plan,
                        "expira": expires_at,
                        "max_devices": 1,
                    },
                )

                cfg = _read_config(db_path)
                self.assertEqual(cfg["license_tier"], expected_plan)
                self.assertEqual(cfg["license_plan"], expected_plan)
                self.assertEqual(cfg["license_expires_at"], "" if expected_plan == "BASICA" else expires_at)
                self.assertEqual(cfg["license_key"], f"NXR-FIN-{expected_plan}")

    @patch("licensing.license_service.get_sdk_config", return_value=object())
    @patch("licensing.license_service.load_public_key", return_value="public-key")
    @patch("licensing.license_service.import_validar_licencia", return_value=None)
    @patch("licensing.license_service.import_validar_licencia_detalle")
    def test_validate_saved_license_accepts_sdk_cache_and_persists_state(
        self,
        mock_import_detalle,
        _mock_import_bool,
        _mock_public_key,
        _mock_config,
    ):
        temp_dir, db_path = _create_config_db({"license_key": "NXR-FIN-CACHE"})
        self.addCleanup(temp_dir.cleanup)
        validar_detalle = Mock(
            return_value={
                "ok": True,
                "source": "cache",
                "license": {
                    "license_key": "NXR-FIN-CACHE",
                    "plan": "FULL",
                    "expira": str(date.today() + timedelta(days=20)),
                },
            }
        )
        mock_import_detalle.return_value = validar_detalle

        ok, msg = validate_saved_license(db_path)

        self.assertTrue(ok)
        self.assertIn("correctamente", msg)
        cfg = _read_config(db_path)
        self.assertEqual(cfg["license_tier"], "FULL")
        self.assertEqual(cfg["license_key"], "NXR-FIN-CACHE")
        self.assertTrue(validar_detalle.call_args.kwargs["config"])


if __name__ == "__main__":
    unittest.main()
