import os
import sqlite3
import unittest
from pathlib import Path

from flask import Flask

from models import init_db
from routes import register_routes
from services import get_monthly_summary
from tempdir_compat import make_temp_dir


def _build_app(db_path, base_dir):
    repo_root = Path(__file__).resolve().parents[1]
    app = Flask(
        __name__,
        template_folder=str(repo_root / "templates"),
        static_folder=str(repo_root / "static"),
    )
    app.config.update(
        SECRET_KEY="test-secret",
        TESTING=True,
        DB_PATH=db_path,
        BASE_DIR=base_dir,
    )

    @app.context_processor
    def inject_base_context():
        return {"demo_info": {"tier": "BASICA", "is_demo": False, "is_full": False,
                               "is_pro": False, "is_expired": False, "can_update": False,
                               "pro_expired": False, "pro_expires_soon": False,
                               "pro_expires_tomorrow": False}}

    register_routes(app)
    return app


class TransferHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = make_temp_dir()
        self.addCleanup(self.temp_dir.cleanup)
        self.previous_testing = os.environ.get("NEXAR_TESTING")
        os.environ["NEXAR_TESTING"] = "1"
        self.addCleanup(self._restore_testing)
        self.db_path = str(Path(self.temp_dir.name) / "transfers.sqlite3")
        init_db(self.db_path)
        self.app = _build_app(self.db_path, self.temp_dir.name)
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "tester"

    def _restore_testing(self):
        if self.previous_testing is None:
            os.environ.pop("NEXAR_TESTING", None)
        else:
            os.environ["NEXAR_TESTING"] = self.previous_testing

    def _account_id(self, name):
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute("SELECT id FROM accounts WHERE name=?", (name,)).fetchone()[0]
        finally:
            conn.close()

    def _create_accounts(self):
        for name in ("Cuenta origen", "Cuenta destino"):
            response = self.client.post("/accounts/new", data={
                "type": "bank", "name": name, "currency": "ARS", "initial_balance": "1000",
            })
            self.assertEqual(response.status_code, 302)
        return self._account_id("Cuenta origen"), self._account_id("Cuenta destino")

    def test_empty_history_is_clear(self):
        response = self.client.get("/transfers")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Todavía no registraste transferencias entre cuentas.", response.get_data(as_text=True))

    def test_new_transfer_appears_once_with_its_details_without_affecting_global_totals(self):
        from_id, to_id = self._create_accounts()

        response = self.client.post("/transfers", data={
            "from_account_id": str(from_id), "to_account_id": str(to_id),
            "amount": "250.50", "currency": "USD", "date": "2026-08-05",
            "description": "Ahorro mensual",
        }, follow_redirects=True)

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body.count("Ahorro mensual"), 1)
        self.assertIn("Cuenta origen", body)
        self.assertIn("Cuenta destino", body)
        self.assertIn("$250.50 USD", body)
        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM transfers").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 0)
        finally:
            conn.close()
        self.assertEqual(get_monthly_summary(self.db_path, 2026, 8)["balance"], {})

    def test_history_orders_existing_transfers_by_date_descending(self):
        from_id, to_id = self._create_accounts()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany("""
                INSERT INTO transfers (from_account_id, to_account_id, amount, currency, date, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                (from_id, to_id, 100, "ARS", "2026-08-01", "Transferencia anterior"),
                (from_id, to_id, 200, "ARS", "2026-08-07", "Transferencia reciente"),
            ])
            conn.commit()
        finally:
            conn.close()

        body = self.client.get("/transfers").get_data(as_text=True)
        self.assertLess(body.index("Transferencia reciente"), body.index("Transferencia anterior"))


if __name__ == "__main__":
    unittest.main()
