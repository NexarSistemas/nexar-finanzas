import io
import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path

from flask import Flask
from openpyxl import load_workbook

from routes import register_routes
from tempdir_compat import make_temp_dir


EXPORT_MESSAGE = "La exportación está disponible en los planes Pro y Full."


def _create_db(config_values):
    temp_dir = make_temp_dir()
    db_path = Path(temp_dir.name) / "report_exports.sqlite3"

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT)")
    cur.execute(
        """
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY,
            date TEXT,
            type TEXT,
            category_id INTEGER,
            amount REAL,
            currency TEXT,
            method TEXT,
            account_id INTEGER,
            description TEXT
        )
        """
    )
    cur.execute("INSERT INTO categories (id, name) VALUES (1, 'Ventas')")
    cur.execute("INSERT INTO accounts (id, name) VALUES (1, 'Banco')")
    cur.execute(
        """
        INSERT INTO transactions
        (date, type, category_id, amount, currency, method, account_id, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-05-10", "income", 1, 1500.0, "ARS", "Transferencia", 1, "Cobro"),
    )
    cur.executemany(
        "INSERT INTO config (key, value) VALUES (?, ?)",
        list(config_values.items()),
    )
    conn.commit()
    conn.close()

    return temp_dir, str(db_path)


def _build_app(db_path, base_dir):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret"
    app.config["TESTING"] = True
    app.config["DB_PATH"] = db_path
    app.config["BASE_DIR"] = base_dir
    register_routes(app)
    return app


class ReportExportRoutesTests(unittest.TestCase):
    def _make_client(self, config_values):
        temp_dir, db_path = _create_db(config_values)
        self.addCleanup(temp_dir.cleanup)
        app = _build_app(db_path, temp_dir.name)
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "tester"
        return client

    def test_csv_export_still_available_for_basica(self):
        client = self._make_client({"license_tier": "BASICA"})

        response = client.get("/reports/export/csv?year=2026&month=5")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["Content-Type"])
        self.assertIn("Cobro", response.get_data(as_text=True))

    def test_excel_export_is_blocked_for_demo(self):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "demo_install_date": str(date.today() - timedelta(days=1)),
            }
        )

        response = client.get("/reports/export/excel?mode=monthly&year=2026&month=5")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/reports", response.headers["Location"])
        with client.session_transaction() as session:
            flashes = session.get("_flashes", [])
        self.assertIn(("warning", EXPORT_MESSAGE), flashes)

    def test_pdf_export_is_blocked_for_basica(self):
        client = self._make_client({"license_tier": "BASICA"})

        response = client.get("/reports/export/pdf?mode=annual&year=2026")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/reports", response.headers["Location"])
        with client.session_transaction() as session:
            flashes = session.get("_flashes", [])
        self.assertIn(("warning", EXPORT_MESSAGE), flashes)

    def test_excel_export_is_available_for_pro(self):
        client = self._make_client(
            {
                "license_tier": "PRO",
                "license_expires_at": str(date.today() + timedelta(days=7)),
            }
        )

        response = client.get("/reports/export/excel?year=2026&month=5")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            response.headers["Content-Type"],
        )
        workbook = load_workbook(io.BytesIO(response.data), data_only=True)
        sheet = workbook.active
        self.assertEqual(sheet["A1"].value, "Fecha")
        self.assertEqual(sheet["H2"].value, "Cobro")

    def test_pdf_export_is_available_for_full(self):
        client = self._make_client(
            {
                "license_tier": "FULL",
                "license_expires_at": str(date.today() + timedelta(days=7)),
            }
        )

        response = client.get("/reports/export/pdf?year=2026&month=5")

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/pdf", response.headers["Content-Type"])
        self.assertTrue(response.data.startswith(b"%PDF"))
