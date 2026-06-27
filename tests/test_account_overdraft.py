import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from models import init_db
from routes import register_routes


def _build_app(db_path, base_dir):
    repo_root = Path(__file__).resolve().parents[1]
    app = Flask(
        __name__,
        template_folder=str(repo_root / "templates"),
        static_folder=str(repo_root / "static"),
    )
    app.config["SECRET_KEY"] = "test-secret"
    app.config["TESTING"] = True
    app.config["DB_PATH"] = db_path
    app.config["BASE_DIR"] = base_dir

    @app.context_processor
    def inject_base_context():
        return {
            "demo_info": {
                "tier": "BASICA",
                "is_demo": False,
                "is_full": False,
                "is_pro": False,
                "is_expired": False,
                "can_update": False,
                "pro_expired": False,
                "pro_expires_soon": False,
                "pro_expires_tomorrow": False,
            }
        }

    register_routes(app)
    return app


class AccountOverdraftRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = str(Path(self.temp_dir.name) / "overdraft.sqlite3")
        init_db(self.db_path)
        self.app = _build_app(self.db_path, self.temp_dir.name)
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "tester"

    def _fetchone(self, query, params=()):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(query, params).fetchone()
        conn.close()
        return row

    def _fetchval(self, query, params=()):
        row = self._fetchone(query, params)
        return row[0] if row else None

    def test_bank_without_overdraft_rejects_negative_initial_balance(self):
        response = self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco sin descubierto",
                "currency": "ARS",
                "initial_balance": "-1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._fetchval("SELECT COUNT(*) FROM accounts WHERE name=?", ("Banco sin descubierto",)), 0)

    def test_bank_with_overdraft_accepts_negative_initial_balance_within_limit(self):
        response = self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco descubierto",
                "currency": "ARS",
                "initial_balance": "-35000",
                "permite_descubierto": "1",
                "limite_descubierto": "100000",
            },
        )

        account = self._fetchone(
            """
            SELECT initial_balance, current_balance, permite_descubierto, limite_descubierto
            FROM accounts WHERE name=?
            """,
            ("Banco descubierto",),
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(account)
        self.assertEqual(account["initial_balance"], -35000)
        self.assertEqual(account["current_balance"], -35000)
        self.assertEqual(account["permite_descubierto"], 1)
        self.assertEqual(account["limite_descubierto"], 100000)

    def test_bank_with_overdraft_rejects_initial_balance_below_limit(self):
        response = self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco excedido",
                "currency": "ARS",
                "initial_balance": "-120000",
                "permite_descubierto": "1",
                "limite_descubierto": "100000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._fetchval("SELECT COUNT(*) FROM accounts WHERE name=?", ("Banco excedido",)), 0)

    def test_non_bank_keeps_previous_negative_balance_rule(self):
        response = self.client.post(
            "/accounts/new",
            data={
                "type": "cash",
                "name": "Caja principal",
                "currency": "ARS",
                "initial_balance": "-10",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._fetchval("SELECT COUNT(*) FROM accounts WHERE name=?", ("Caja principal",)), 0)

    def test_expense_is_allowed_while_staying_within_overdraft_limit(self):
        self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco operativo",
                "currency": "ARS",
                "initial_balance": "0",
                "permite_descubierto": "1",
                "limite_descubierto": "100000",
            },
        )
        account_id = self._fetchval("SELECT id FROM accounts WHERE name=?", ("Banco operativo",))

        response = self.client.post(
            "/transactions/new",
            data={
                "type": "expense",
                "amount": "35000",
                "currency": "ARS",
                "account_id": str(account_id),
                "method": "debit",
                "date": "2026-06-27",
            },
        )

        balance = self._fetchval("SELECT current_balance FROM accounts WHERE id=?", (account_id,))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(balance, -35000)

    def test_expense_is_rejected_if_it_exceeds_overdraft_limit(self):
        self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco limite",
                "currency": "ARS",
                "initial_balance": "0",
                "permite_descubierto": "1",
                "limite_descubierto": "100000",
            },
        )
        account_id = self._fetchval("SELECT id FROM accounts WHERE name=?", ("Banco limite",))

        response = self.client.post(
            "/transactions/new",
            data={
                "type": "expense",
                "amount": "120000",
                "currency": "ARS",
                "account_id": str(account_id),
                "method": "debit",
                "date": "2026-06-27",
            },
        )

        balance = self._fetchval("SELECT current_balance FROM accounts WHERE id=?", (account_id,))
        tx_count = self._fetchval("SELECT COUNT(*) FROM transactions WHERE account_id=?", (account_id,))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(balance, 0)
        self.assertEqual(tx_count, 0)

    def test_income_reduces_used_overdraft(self):
        self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco en descubierto",
                "currency": "ARS",
                "initial_balance": "-50000",
                "permite_descubierto": "1",
                "limite_descubierto": "100000",
            },
        )
        account_id = self._fetchval("SELECT id FROM accounts WHERE name=?", ("Banco en descubierto",))

        response = self.client.post(
            "/transactions/new",
            data={
                "type": "income",
                "amount": "15000",
                "currency": "ARS",
                "account_id": str(account_id),
                "method": "transfer",
                "date": "2026-06-27",
            },
        )

        balance = self._fetchval("SELECT current_balance FROM accounts WHERE id=?", (account_id,))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(balance, -35000)


if __name__ == "__main__":
    unittest.main()
