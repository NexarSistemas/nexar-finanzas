import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path

from flask import Flask

from demo_limits import get_demo_status
from routes import register_routes
from tempdir_compat import make_temp_dir


def _create_db(config_values):
    temp_dir = make_temp_dir()
    db_path = Path(temp_dir.name) / "expired_read_only.sqlite3"

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY, type TEXT, active INTEGER, current_balance REAL)"
    )
    cur.execute(
        "CREATE TABLE transactions (id INTEGER PRIMARY KEY, type TEXT, account_id INTEGER)"
    )
    cur.execute(
        "CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT, type TEXT, active INTEGER, es_necesario INTEGER)"
    )
    cur.execute("CREATE TABLE investments (id INTEGER PRIMARY KEY)")
    cur.execute("CREATE TABLE budgets (id INTEGER PRIMARY KEY, year INTEGER, month INTEGER)")
    cur.executemany(
        "INSERT INTO config (key, value) VALUES (?, ?)",
        list(config_values.items()),
    )
    cur.execute(
        "INSERT INTO accounts (id, type, active, current_balance) VALUES (1, 'bank', 1, 1000)"
    )
    cur.execute("INSERT INTO transactions (id, type, account_id) VALUES (1, 'expense', 1)")
    cur.execute(
        "INSERT INTO categories (id, name, type, active, es_necesario) VALUES (1, 'Test', 'expense', 1, 1)"
    )
    cur.execute("INSERT INTO investments (id) VALUES (1)")
    cur.execute("INSERT INTO budgets (id, year, month) VALUES (1, 2026, 7)")
    conn.commit()
    conn.close()

    return temp_dir, str(db_path)


def _build_app(db_path, base_dir):
    repo_root = Path(__file__).resolve().parents[1]
    app = Flask(
        __name__,
        template_folder=str(repo_root / "templates"),
    )
    app.config["SECRET_KEY"] = "test-secret"
    app.config["TESTING"] = True
    app.config["DB_PATH"] = db_path
    app.config["BASE_DIR"] = base_dir

    @app.context_processor
    def inject_base_context():
        return {
            "demo_info": get_demo_status(db_path),
            "update_info": {"available": False},
            "app_version": "test",
            "app_name": "Nexar Finanzas",
            "license_mode": "test",
            "changelog": [],
        }

    register_routes(app)
    return app


class ExpiredLicenseReadOnlyTests(unittest.TestCase):
    def _make_client(self, config_values):
        temp_dir, db_path = _create_db(config_values)
        self.addCleanup(temp_dir.cleanup)
        app = _build_app(db_path, temp_dir.name)
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "tester"
        return client

    def _scalar(self, client, query):
        conn = sqlite3.connect(client.application.config["DB_PATH"])
        try:
            return conn.execute(query).fetchone()[0]
        finally:
            conn.close()

    def test_expired_monthly_without_basica_blocks_destructive_financial_changes(self):
        client = self._make_client(
            {
                "license_tier": "PRO",
                "license_plan": "PRO",
                "license_expires_at": str(date.today() - timedelta(days=1)),
                "basica_activada": "0",
            }
        )

        requests = [
            ("post", "/accounts/1/delete", {}),
            ("post", "/transactions/1/delete", {}),
            ("post", "/categories/1/delete", {}),
            ("post", "/budgets/1/delete", {}),
            ("post", "/investments/1/delete", {}),
            ("post", "/categories/1/toggle-necesario", {}),
            ("post", "/categories/new", {"name": "Nueva", "type": "expense"}),
        ]

        for method, path, data in requests:
            response = getattr(client, method)(path, data=data)
            self.assertEqual(response.status_code, 302, path)

        self.assertEqual(self._scalar(client, "SELECT active FROM accounts WHERE id=1"), 1)
        self.assertEqual(self._scalar(client, "SELECT COUNT(*) FROM transactions WHERE id=1"), 1)
        self.assertEqual(self._scalar(client, "SELECT active FROM categories WHERE id=1"), 1)
        self.assertEqual(self._scalar(client, "SELECT es_necesario FROM categories WHERE id=1"), 1)
        self.assertEqual(self._scalar(client, "SELECT COUNT(*) FROM categories"), 1)
        self.assertEqual(self._scalar(client, "SELECT COUNT(*) FROM budgets WHERE id=1"), 1)
        self.assertEqual(self._scalar(client, "SELECT COUNT(*) FROM investments WHERE id=1"), 1)

    def test_expired_monthly_with_basica_keeps_basica_write_behavior(self):
        client = self._make_client(
            {
                "license_tier": "FULL",
                "license_plan": "FULL",
                "license_expires_at": str(date.today() - timedelta(days=1)),
                "basica_activada": "1",
            }
        )

        response = client.post("/categories/1/toggle-necesario")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._scalar(client, "SELECT es_necesario FROM categories WHERE id=1"), 0)


if __name__ == "__main__":
    unittest.main()
