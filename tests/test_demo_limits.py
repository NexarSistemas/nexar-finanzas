import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path

from demo_limits import (
    TIER_LIMITS,
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


EXPECTED_CAPABILITIES = {
    "DEMO": {
        "advanced_reports": True,
        "cashflow_analysis": True,
        "ai_insights": False,
        "export_excel": False,
        "export_pdf": False,
    },
    "BASICA": {
        "advanced_reports": False,
        "cashflow_analysis": False,
        "ai_insights": False,
        "export_excel": False,
        "export_pdf": False,
    },
    "PRO": {
        "advanced_reports": False,
        "cashflow_analysis": True,
        "ai_insights": False,
        "export_excel": True,
        "export_pdf": True,
    },
    "FULL": {
        "advanced_reports": True,
        "cashflow_analysis": True,
        "ai_insights": True,
        "export_excel": True,
        "export_pdf": True,
    },
}


def _assert_capabilities(test_case, status, expected):
    test_case.assertEqual(status["plan_capabilities"], expected)
    for capability, enabled in expected.items():
        test_case.assertEqual(status[f"can_{capability}"], enabled)


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
        _assert_capabilities(self, status, EXPECTED_CAPABILITIES["DEMO"])

    def test_demo_expired_status_is_read_only(self):
        temp_dir, db_path = _create_db(
            {
                "license_tier": "DEMO",
                "demo_install_date": str(date.today() - timedelta(days=31)),
            }
        )
        self.addCleanup(temp_dir.cleanup)

        self.assertEqual(get_tier(db_path), "DEMO_EXPIRED")
        self.assertFalse(is_full_version(db_path))

        status = get_demo_status(db_path)
        self.assertTrue(status["is_demo"])
        self.assertFalse(status["is_paid"])
        self.assertTrue(status["is_expired"])
        self.assertTrue(status["is_read_only"])
        self.assertFalse(status["can_write_data"])
        self.assertEqual(status["expired_reason"], "demo")
        self.assertEqual(status["tier"], "DEMO_EXPIRED")
        self.assertFalse(status["can_investments_write"])
        _assert_capabilities(self, status, EXPECTED_CAPABILITIES["DEMO"])

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
        _assert_capabilities(self, status, EXPECTED_CAPABILITIES["BASICA"])

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
        _assert_capabilities(self, status, EXPECTED_CAPABILITIES["PRO"])

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
        _assert_capabilities(self, status, EXPECTED_CAPABILITIES["FULL"])

    def test_full_keeps_pro_practical_limits_with_premium_capabilities(self):
        practical_limit_keys = {
            "expenses",
            "incomes",
            "bank_accounts",
            "virtual_wallets",
            "cash_accounts",
            "accounts_total",
            "investments",
            "investments_write",
            "budgets",
            "reports_annual",
            "reports_monthly",
            "reports_weekly",
            "updates",
        }

        for key in practical_limit_keys:
            self.assertEqual(TIER_LIMITS["FULL"][key], TIER_LIMITS["PRO"][key])

        for key, expected in EXPECTED_CAPABILITIES["FULL"].items():
            self.assertEqual(TIER_LIMITS["FULL"][key], expected)

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
        status = get_demo_status(db_path)
        self.assertFalse(status["is_read_only"])
        self.assertTrue(status["can_write_data"])
        self.assertEqual(status["monthly_fallback_tier"], "BASICA")

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
        status = get_demo_status(db_path)
        self.assertFalse(status["is_read_only"])
        self.assertTrue(status["can_write_data"])
        self.assertEqual(status["monthly_fallback_tier"], "BASICA")

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
        self.assertTrue(status["is_read_only"])
        self.assertFalse(status["can_write_data"])
        self.assertEqual(status["expired_reason"], "subscription")
        self.assertEqual(status["monthly_fallback_tier"], "DEMO_EXPIRED")

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
        self.assertTrue(status["is_read_only"])
        self.assertFalse(status["can_write_data"])
        self.assertEqual(status["expired_reason"], "subscription")
        self.assertEqual(status["monthly_fallback_tier"], "DEMO_EXPIRED")


if __name__ == "__main__":
    unittest.main()
