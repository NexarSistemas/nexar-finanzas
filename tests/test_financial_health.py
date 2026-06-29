import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from services.financial_health import get_financial_health_summary
from models import init_db
from routes import register_routes


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
            },
            "update_info": {"available": False},
            "app_version": "test",
            "app_name": "Nexar Finanzas",
            "license_mode": "BASICA",
            "changelog": [],
        }

    register_routes(app)
    return app


class FinancialHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp_dir.cleanup)
        previous_testing = os.environ.get("NEXAR_TESTING")
        os.environ["NEXAR_TESTING"] = "1"
        self.addCleanup(self._restore_testing_env, previous_testing)
        self.db_path = str(Path(self.temp_dir.name) / "financial_health.sqlite3")
        init_db(self.db_path)

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _restore_testing_env(previous_value):
        if previous_value is None:
            os.environ.pop("NEXAR_TESTING", None)
        else:
            os.environ["NEXAR_TESTING"] = previous_value

    def test_summary_returns_safe_defaults_without_data(self):
        summary = get_financial_health_summary(self.db_path)

        self.assertEqual(summary["score"], 8)
        self.assertEqual(summary["status"], "Critica")
        self.assertEqual(summary["income"], 0.0)
        self.assertEqual(summary["expenses"], 0.0)
        self.assertEqual(summary["net_savings"], 0.0)
        self.assertEqual(summary["savings_rate"], 0.0)
        self.assertEqual(summary["liquidity"], 0.0)
        self.assertIn("Todavia no hay movimientos en el periodo actual para calcular tendencias.", summary["alerts"])
        self.assertIn("No hay presupuestos cargados para evaluar control basico de gastos.", summary["alerts"])

    def test_summary_calculates_monthly_metrics_and_budget_alerts(self):
        conn = self._connect()
        conn.execute(
            "INSERT INTO accounts (name, type, currency, initial_balance, current_balance, active) VALUES (?, ?, ?, ?, ?, 1)",
            ("Banco principal", "bank", "ARS", 50000, 50000),
        )
        conn.execute(
            "INSERT INTO categories (name, type, active, es_necesario) VALUES (?, 'income', 1, 1)",
            ("Ventas Salud",),
        )
        conn.execute(
            "INSERT INTO categories (name, type, active, es_necesario) VALUES (?, 'expense', 1, 1)",
            ("Servicios Salud",),
        )
        income_category_id = conn.execute(
            "SELECT id FROM categories WHERE name='Ventas Salud' AND type='income'"
        ).fetchone()["id"]
        expense_category_id = conn.execute(
            "SELECT id FROM categories WHERE name='Servicios Salud' AND type='expense'"
        ).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO transactions (type, amount, currency, category_id, account_id, method, date, description)
            VALUES ('income', 100000, 'ARS', ?, 1, 'transfer', date('now'), 'Cobro')
            """,
            (income_category_id,),
        )
        conn.execute(
            """
            INSERT INTO transactions (type, amount, currency, category_id, account_id, method, date, description)
            VALUES ('expense', 60000, 'ARS', ?, 1, 'debit', date('now'), 'Pago')
            """,
            (expense_category_id,),
        )
        conn.execute(
            """
            INSERT INTO budgets (category_id, amount, month, year)
            VALUES (?, 50000, CAST(strftime('%m', 'now') AS INTEGER), CAST(strftime('%Y', 'now') AS INTEGER))
            """,
            (expense_category_id,),
        )
        conn.commit()
        conn.close()

        summary = get_financial_health_summary(self.db_path)

        self.assertEqual(summary["income"], 100000.0)
        self.assertEqual(summary["expenses"], 60000.0)
        self.assertEqual(summary["net_savings"], 40000.0)
        self.assertEqual(summary["savings_rate"], 40.0)
        self.assertEqual(summary["liquidity"], 50000.0)
        self.assertEqual(summary["score"], 78)
        self.assertEqual(summary["status"], "Buena")
        self.assertIn("Hay 1 presupuesto(s) del mes por encima del limite.", summary["alerts"])

    def test_route_renders_financial_health_page(self):
        app = _build_app(self.db_path, self.temp_dir.name)
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "tester"

        response = client.get("/salud-financiera")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Salud financiera", html)
        self.assertIn("Puntaje general", html)


if __name__ == "__main__":
    unittest.main()
