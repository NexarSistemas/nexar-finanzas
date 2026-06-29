import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from models import (
    account_financial_snapshot,
    account_overdraft_alert_level,
    account_overdraft_report,
    account_overdraft_usage_percent,
    init_db,
)
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
        previous_testing = os.environ.get("NEXAR_TESTING")
        os.environ["NEXAR_TESTING"] = "1"
        self.addCleanup(self._restore_testing_env, previous_testing)
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

    @staticmethod
    def _restore_testing_env(previous_value):
        if previous_value is None:
            os.environ.pop("NEXAR_TESTING", None)
        else:
            os.environ["NEXAR_TESTING"] = previous_value

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
            follow_redirects=True,
        )

        balance = self._fetchval("SELECT current_balance FROM accounts WHERE id=?", (account_id,))
        tx_count = self._fetchval("SELECT COUNT(*) FROM transactions WHERE account_id=?", (account_id,))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(balance, 0)
        self.assertEqual(tx_count, 0)
        body = response.get_data(as_text=True)
        self.assertIn('no tiene margen de descubierto suficiente', body)
        self.assertIn('Autorizado: $100,000.00', body)
        self.assertIn('Usado al confirmar: $120,000.00', body)
        self.assertIn('Disponible: $0.00', body)

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

    def test_edit_rejects_disabling_overdraft_while_account_is_negative(self):
        self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco negativo",
                "currency": "ARS",
                "initial_balance": "-25000",
                "permite_descubierto": "1",
                "limite_descubierto": "80000",
            },
        )
        account_id = self._fetchval("SELECT id FROM accounts WHERE name=?", ("Banco negativo",))

        response = self.client.post(
            f"/accounts/{account_id}/edit",
            data={
                "type": "bank",
                "name": "Banco negativo",
                "currency": "ARS",
                "limite_descubierto": "80000",
                "cbu_cvu": "",
                "alias": "",
            },
            follow_redirects=True,
        )

        account = self._fetchone(
            "SELECT permite_descubierto, limite_descubierto FROM accounts WHERE id=?",
            (account_id,),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(account["permite_descubierto"], 1)
        self.assertEqual(account["limite_descubierto"], 80000)
        body = response.get_data(as_text=True)
        self.assertIn('No podés desactivar el descubierto mientras la cuenta siga en descubierto.', body)
        self.assertIn('Descubierto utilizado: $25,000.00.', body)

    def test_edit_rejects_lowering_limit_below_used_overdraft(self):
        self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco con uso",
                "currency": "ARS",
                "initial_balance": "-40000",
                "permite_descubierto": "1",
                "limite_descubierto": "90000",
            },
        )
        account_id = self._fetchval("SELECT id FROM accounts WHERE name=?", ("Banco con uso",))

        response = self.client.post(
            f"/accounts/{account_id}/edit",
            data={
                "type": "bank",
                "name": "Banco con uso",
                "currency": "ARS",
                "permite_descubierto": "1",
                "limite_descubierto": "30000",
                "cbu_cvu": "",
                "alias": "",
            },
            follow_redirects=True,
        )

        account = self._fetchone(
            "SELECT permite_descubierto, limite_descubierto FROM accounts WHERE id=?",
            (account_id,),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(account["permite_descubierto"], 1)
        self.assertEqual(account["limite_descubierto"], 90000)
        body = response.get_data(as_text=True)
        self.assertIn('No podés reducir el límite de descubierto a $30,000.00', body)
        self.assertIn('la cuenta ya está usando $40,000.00.', body)

    def test_overdraft_snapshot_reports_usage_percentage_and_alert_levels(self):
        moderate = {
            "type": "bank",
            "current_balance": -80000,
            "permite_descubierto": 1,
            "limite_descubierto": 100000,
        }
        high = {
            "type": "bank",
            "current_balance": -95000,
            "permite_descubierto": 1,
            "limite_descubierto": 100000,
        }
        limit = {
            "type": "bank",
            "current_balance": -100000,
            "permite_descubierto": 1,
            "limite_descubierto": 100000,
        }

        moderate_snapshot = account_financial_snapshot(moderate)
        self.assertEqual(account_overdraft_usage_percent(moderate), 80.0)
        self.assertEqual(account_overdraft_alert_level(moderate), "moderate")
        self.assertEqual(moderate_snapshot["alerta_descubierto_texto"], "Advertencia moderada")

        high_snapshot = account_financial_snapshot(high)
        self.assertEqual(account_overdraft_usage_percent(high), 95.0)
        self.assertEqual(account_overdraft_alert_level(high), "high")
        self.assertEqual(high_snapshot["alerta_descubierto_texto"], "Advertencia alta")

        limit_snapshot = account_financial_snapshot(limit)
        self.assertEqual(account_overdraft_usage_percent(limit), 100.0)
        self.assertEqual(account_overdraft_alert_level(limit), "limit")
        self.assertEqual(limit_snapshot["alerta_descubierto_texto"], "Límite alcanzado")

    def test_overdraft_snapshot_keeps_margin_separate_from_positive_funds(self):
        snapshot = account_financial_snapshot({
            "type": "bank",
            "current_balance": 25000,
            "permite_descubierto": 1,
            "limite_descubierto": 100000,
        })

        self.assertEqual(snapshot["descubierto_usado"], 0.0)
        self.assertEqual(snapshot["margen_disponible"], 100000.0)

    def test_overdraft_report_aggregates_basic_metrics(self):
        report = account_overdraft_report([
            {
                "name": "Banco A",
                "type": "bank",
                "currency": "ARS",
                "current_balance": 150000,
                "permite_descubierto": 1,
                "limite_descubierto": 100000,
            },
            {
                "name": "Banco B",
                "type": "bank",
                "currency": "ARS",
                "current_balance": -40000,
                "permite_descubierto": 1,
                "limite_descubierto": 100000,
            },
            {
                "name": "Billetera",
                "type": "virtual_wallet",
                "currency": "ARS",
                "current_balance": 30000,
                "permite_descubierto": 0,
                "limite_descubierto": 0,
            },
        ])

        self.assertEqual(report["cuentas_en_descubierto_total"], 1)
        self.assertEqual(report["cuenta_mayor_descubierto"]["name"], "Banco B")
        self.assertEqual(report["cuenta_mayor_descubierto"]["descubierto_usado"], 40000.0)
        self.assertEqual(len(report["overdraft_accounts"]), 1)
        self.assertEqual(report["overdraft_accounts"][0]["name"], "Banco B")
        self.assertEqual(report["overdraft_accounts"][0]["margen_disponible"], 60000.0)

        ars = report["by_currency"][0]
        self.assertEqual(ars["currency"], "ARS")
        self.assertEqual(ars["saldo_neto_total"], 140000.0)
        self.assertEqual(ars["fondos_positivos_disponibles"], 180000.0)
        self.assertEqual(ars["descubierto_utilizado_total"], 40000.0)
        self.assertEqual(ars["margen_descubierto_total"], 160000.0)
        self.assertEqual(ars["cuentas_en_descubierto"], 1)
        self.assertEqual(ars["mayor_descubierto_usado_por_cuenta"], 40000.0)
        self.assertEqual(ars["cuenta_mayor_descubierto"], "Banco B")

    def test_accounts_list_shows_overdraft_indicator_percentage_and_alert(self):
        self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco alerta",
                "currency": "ARS",
                "initial_balance": "-96000",
                "permite_descubierto": "1",
                "limite_descubierto": "100000",
            },
        )

        response = self.client.get("/accounts")

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("En descubierto", body)
        self.assertIn("96%", body)
        self.assertIn("Advertencia alta", body)
        self.assertIn("El descubierto permite que una cuenta bancaria siga operando temporalmente", body)

    def test_accounts_list_does_not_duplicate_global_overdraft_report(self):
        self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco Fondo",
                "currency": "ARS",
                "initial_balance": "150000",
                "permite_descubierto": "1",
                "limite_descubierto": "100000",
            },
        )
        self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco Giro",
                "currency": "ARS",
                "initial_balance": "-40000",
                "permite_descubierto": "1",
                "limite_descubierto": "100000",
            },
        )

        response = self.client.get("/accounts")

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Resumen de saldos y descubierto", body)
        self.assertNotIn("Fondos positivos disponibles", body)
        self.assertNotIn("Descubierto utilizado total", body)
        self.assertIn("Banco Giro", body)
        self.assertIn("Descubierto bancario", body)

    def test_reports_shows_basic_overdraft_report_metrics_and_table(self):
        self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco Fondo",
                "currency": "ARS",
                "initial_balance": "150000",
                "permite_descubierto": "1",
                "limite_descubierto": "100000",
            },
        )
        self.client.post(
            "/accounts/new",
            data={
                "type": "bank",
                "name": "Banco Giro",
                "currency": "ARS",
                "initial_balance": "-40000",
                "permite_descubierto": "1",
                "limite_descubierto": "100000",
            },
        )

        response = self.client.get("/reports")

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Liquidez y descubierto", body)
        self.assertIn("Saldo neto total", body)
        self.assertIn("$110,000.00", body)
        self.assertIn("Fondos positivos disponibles", body)
        self.assertIn("$150,000.00", body)
        self.assertIn("Descubierto utilizado total", body)
        self.assertIn("$40,000.00", body)
        self.assertIn("Margen total disponible", body)
        self.assertIn("$160,000.00", body)
        self.assertIn("Cantidad de cuentas en descubierto", body)
        self.assertIn("Mayor descubierto usado por cuenta", body)
        self.assertIn("Cuenta", body)
        self.assertIn("Usado", body)
        self.assertIn("Límite", body)
        self.assertIn("Disponible", body)
        self.assertIn("Banco Giro", body)
        self.assertIn("$60,000.00", body)
        self.assertIn("no tratar financiamiento bancario como dinero propio disponible", body)


if __name__ == "__main__":
    unittest.main()
