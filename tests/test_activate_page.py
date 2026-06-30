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
    db_path = Path(temp_dir.name) / "activate_page.sqlite3"

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("CREATE TABLE transactions (id INTEGER PRIMARY KEY, type TEXT)")
    cur.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, type TEXT, active INTEGER)")
    cur.execute("CREATE TABLE investments (id INTEGER PRIMARY KEY)")
    cur.execute("CREATE TABLE budgets (id INTEGER PRIMARY KEY)")
    cur.executemany(
        "INSERT INTO config (key, value) VALUES (?, ?)",
        list(config_values.items()),
    )
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


class ActivatePageTests(unittest.TestCase):
    def _make_client(self, config_values):
        temp_dir, db_path = _create_db(config_values)
        self.addCleanup(temp_dir.cleanup)
        app = _build_app(db_path, temp_dir.name)
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "tester"
        return client

    def test_activate_page_shows_blocked_capabilities_for_basica(self):
        client = self._make_client(
            {
                "license_tier": "BASICA",
                "license_plan": "BASICA",
                "license_activated_at": "2026-06-01",
            }
        )

        response = client.get("/activate")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Mi plan", html)
        self.assertNotIn("Plan efectivo", html)
        self.assertIn("Solo lectura", html)
        self.assertIn("Disponible en planes superiores.", html)

    def test_activate_page_shows_refresh_when_license_key_exists(self):
        client = self._make_client(
            {
                "license_tier": "FULL",
                "license_plan": "FULL",
                "license_key": "NXR-FIN-1234567890",
                "license_activated_at": "2026-06-01",
                "license_expires_at": str(date.today() + timedelta(days=10)),
            }
        )

        response = client.get("/activate")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Refrescar licencia", html)
        self.assertIn("Todas las capacidades de esta pantalla estan habilitadas", html)
        self.assertIn("NXR-FIN-", html)


if __name__ == "__main__":
    unittest.main()
