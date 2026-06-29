import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path

from demo_limits import (
    get_demo_status,
    get_pro_days_remaining,
    get_tier,
    is_full_version,
    is_pro_expired,
)
from tempdir_compat import make_temp_dir


def _create_db(config_values):
    temp_dir = make_temp_dir()
    db_path = Path(temp_dir.name) / "demo_limits.sqlite3"

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("CREATE TABLE transactions (id INTEGER PRIMARY KEY, type TEXT)")
    cur.execute(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY, type TEXT, active INTEGER)"
    )
    cur.execute("CREATE TABLE investments (id INTEGER PRIMARY KEY)")
    cur.execute("CREATE TABLE budgets (id INTEGER PRIMARY KEY)")
    cur.executemany(
        "INSERT INTO config (key, value) VALUES (?, ?)",
        list(config_values.items()),
    )
    conn.commit()
    conn.close()

    return temp_dir, str(db_path)


class DemoLimitsRuntimeTests(unittest.TestCase):
    def test_demo_active_status(self):
        temp_dir, db_path = _create_db(
            {
                "license_tier": "DEMO",
                "demo_install_date": str(date.today() - timedelta(days=10)),
            }
        )
        self.addCleanup(temp_dir.cleanup)

        self.assertEqual(get_tier(db_path), "DEMO")

        status = get_demo_status(db_path)
        self.assertTrue(status["is_demo"])
        self.assertFalse(status["is_paid"])
        self.assertEqual(status["tier"], "DEMO")

    def test_basica_active_status(self):
        temp_dir, db_path = _create_db(
            {
                "license_tier": "BASICA",
            }
        )
        self.addCleanup(temp_dir.cleanup)

        self.assertEqual(get_tier(db_path), "BASICA")
        self.assertTrue(is_full_version(db_path))

        status = get_demo_status(db_path)
        self.assertTrue(status["is_paid"])
        self.assertFalse(status["is_full"])
        self.assertEqual(status["tier"], "BASICA")

    def test_pro_active_capabilities(self):
        temp_dir, db_path = _create_db(
            {
                "license_tier": "PRO",
                "license_expires_at": str(date.today() + timedelta(days=7)),
            }
        )
        self.addCleanup(temp_dir.cleanup)

        self.assertEqual(get_tier(db_path), "PRO")
        self.assertFalse(is_pro_expired(db_path))
        self.assertEqual(get_pro_days_remaining(db_path), 7)

        status = get_demo_status(db_path)
        self.assertTrue(status["can_update"])
        self.assertTrue(status["can_investments_write"])
        self.assertTrue(status["can_export_excel"])
        self.assertTrue(status["can_export_pdf"])
        self.assertFalse(status["can_advanced_reports"])
        self.assertFalse(status["can_ai_insights"])
        self.assertEqual(status["tier"], "PRO")

    def test_full_active_capabilities(self):
        temp_dir, db_path = _create_db(
            {
                "license_tier": "FULL",
                "license_expires_at": str(date.today() + timedelta(days=7)),
            }
        )
        self.addCleanup(temp_dir.cleanup)

        self.assertEqual(get_tier(db_path), "FULL")
        self.assertFalse(is_pro_expired(db_path))
        self.assertEqual(get_pro_days_remaining(db_path), 7)

        status = get_demo_status(db_path)
        self.assertTrue(status["is_full"])
        self.assertTrue(status["is_paid"])
        self.assertTrue(status["can_ai_insights"])
        self.assertTrue(status["can_advanced_reports"])
        self.assertTrue(status["can_export_excel"])
        self.assertTrue(status["can_export_pdf"])
        self.assertEqual(status["tier"], "FULL")

    def test_pro_expired_with_basica_degrades_to_basica(self):
        temp_dir, db_path = _create_db(
            {
                "license_tier": "PRO",
                "license_expires_at": str(date.today() - timedelta(days=1)),
                "basica_activada": "1",
            }
        )
        self.addCleanup(temp_dir.cleanup)

        self.assertEqual(get_tier(db_path), "BASICA")
        self.assertTrue(is_pro_expired(db_path))

    def test_full_expired_with_basica_degrades_to_basica(self):
        temp_dir, db_path = _create_db(
            {
                "license_tier": "FULL",
                "license_expires_at": str(date.today() - timedelta(days=1)),
                "basica_activada": "1",
            }
        )
        self.addCleanup(temp_dir.cleanup)

        self.assertEqual(get_tier(db_path), "BASICA")
        self.assertTrue(is_pro_expired(db_path))

    def test_pro_expired_without_basica_becomes_demo_expired(self):
        temp_dir, db_path = _create_db(
            {
                "license_tier": "PRO",
                "license_expires_at": str(date.today() - timedelta(days=1)),
            }
        )
        self.addCleanup(temp_dir.cleanup)

        self.assertEqual(get_tier(db_path), "DEMO_EXPIRED")
        self.assertTrue(is_pro_expired(db_path))

        status = get_demo_status(db_path)
        self.assertTrue(status["is_demo"])
        self.assertFalse(status["is_paid"])
        self.assertTrue(status["is_expired"])

    def test_full_expired_without_basica_becomes_demo_expired(self):
        temp_dir, db_path = _create_db(
            {
                "license_tier": "FULL",
                "license_expires_at": str(date.today() - timedelta(days=1)),
            }
        )
        self.addCleanup(temp_dir.cleanup)

        self.assertEqual(get_tier(db_path), "DEMO_EXPIRED")
        self.assertTrue(is_pro_expired(db_path))

        status = get_demo_status(db_path)
        self.assertTrue(status["is_demo"])
        self.assertFalse(status["is_paid"])
        self.assertTrue(status["is_expired"])


if __name__ == "__main__":
    unittest.main()
