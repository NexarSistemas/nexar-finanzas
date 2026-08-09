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

    def _create_transfers(self, from_id, to_id, count):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany("""
                INSERT INTO transfers (from_account_id, to_account_id, amount, currency, date, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                (from_id, to_id, 100 + index, "ARS", "2026-08-01", f"Transferencia {index:02d}")
                for index in range(count)
            ])
            conn.commit()
        finally:
            conn.close()

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

    def test_history_query_uses_ordering_index_without_temp_b_tree(self):
        conn = sqlite3.connect(self.db_path)
        try:
            indexes = conn.execute("PRAGMA index_list('transfers')").fetchall()
            self.assertIn("idx_transfers_date_id", [index[1] for index in indexes])

            plan = conn.execute("""
                EXPLAIN QUERY PLAN
                SELECT t.id, t.amount, t.currency, t.date, t.description,
                       source.name AS from_account_name,
                       destination.name AS to_account_name
                FROM transfers t
                JOIN accounts source ON source.id = t.from_account_id
                JOIN accounts destination ON destination.id = t.to_account_id
                ORDER BY t.date DESC, t.id DESC
                LIMIT ? OFFSET ?
            """, (20, 0)).fetchall()
        finally:
            conn.close()

        plan_details = " ".join(step[3] for step in plan)
        self.assertIn("idx_transfers_date_id", plan_details)
        self.assertNotIn("USE TEMP B-TREE FOR ORDER BY", plan_details)

    def test_history_paginates_transfers_and_navigates_between_pages(self):
        from_id, to_id = self._create_accounts()
        self._create_transfers(from_id, to_id, 21)

        first_page = self.client.get("/transfers")
        first_body = first_page.get_data(as_text=True)
        self.assertEqual(first_page.status_code, 200)
        self.assertIn("Transferencia 20", first_body)
        self.assertNotIn("Transferencia 00", first_body)
        self.assertIn('href="/transfers?page=2"', first_body)

        second_page = self.client.get("/transfers?page=2")
        second_body = second_page.get_data(as_text=True)
        self.assertEqual(second_page.status_code, 200)
        self.assertIn("Transferencia 00", second_body)
        self.assertNotIn("Transferencia 20", second_body)

    def test_new_transfer_redirects_to_first_page(self):
        from_id, to_id = self._create_accounts()
        self._create_transfers(from_id, to_id, 20)

        response = self.client.post("/transfers?page=2", data={
            "from_account_id": str(from_id), "to_account_id": str(to_id),
            "amount": "250", "currency": "ARS", "date": "2026-08-02",
            "description": "Transferencia nueva",
        }, follow_redirects=True)

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Transferencia nueva", body)
        self.assertNotIn("Transferencia 00", body)


if __name__ == "__main__":
    unittest.main()
