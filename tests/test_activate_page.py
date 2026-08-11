import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask

from demo_limits import get_demo_status
from routes import register_routes
from tempdir_compat import make_temp_dir
from licensing import supabase_license_api


def _create_db(config_values):
    temp_dir = make_temp_dir()
    db_path = Path(temp_dir.name) / "activate_page.sqlite3"

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute(
        "CREATE TABLE user (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, "
        "recovery_question TEXT, recovery_answer_hash TEXT)"
    )
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
        self.assertIn("Plan Full", html)
        self.assertNotIn("Plan Pro</div>", html)

    def test_activate_page_shows_refresh_for_pending_checkout_without_license_key(self):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
                "pending_checkout_activation_id": "HWID-DEMO-001",
                "pending_checkout_plan": "PRO",
                "pending_checkout_request_type": "alta_licencia",
                "pending_checkout_external_reference": "ALTA|HWID-DEMO-001|nexar-finanzas|PRO",
                "pending_checkout_started_at": "2026-07-06 10:30",
            }
        )

        response = client.get("/activate")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Refrescar licencia", html)
        self.assertIn("Detectamos un checkout directo iniciado", html)
        self.assertIn("HWID-DEMO-001", html)

    def test_activate_page_shows_checkout_buttons_for_demo(self):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
            }
        )

        response = client.get("/activate")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Checkout directo", html)
        self.assertIn("Plan Básica · Pagar con Mercado Pago", html)
        self.assertIn("Plan Pro · Pagar con Mercado Pago", html)
        self.assertIn("Plan Full · Pagar con Mercado Pago", html)

    @patch("routes.sync_marketing_preference", return_value=False)
    def test_setup_persists_optional_marketing_consent(self, mock_sync):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
            }
        )

        response = client.post(
            "/setup",
            data={
                "username": "admin",
                "password": "Abc1!d",
                "confirm": "Abc1!d",
                "recovery_question": "Mascota",
                "recovery_answer": "Luna",
                "email": "nuevo@example.com",
                "marketing_opt_in": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        conn = sqlite3.connect(client.application.config["DB_PATH"])
        values = dict(conn.execute("SELECT key, value FROM config").fetchall())
        conn.close()
        self.assertEqual(values["license_marketing_opt_in"], "1")
        self.assertEqual(values["license_owner_email"], "nuevo@example.com")
        mock_sync.assert_called_once()
        with client.session_transaction() as session_data:
            self.assertIn(
                ("warning", "Tu preferencia quedó guardada localmente, pero no pudo sincronizarse."),
                session_data["_flashes"],
            )

    @patch("routes.sync_marketing_preference", return_value=False)
    def test_setup_rejects_marketing_consent_without_valid_email(self, mock_sync):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
            }
        )

        response = client.post(
            "/setup",
            data={
                "username": "admin",
                "password": "Abc1!d",
                "confirm": "Abc1!d",
                "recovery_question": "Mascota",
                "recovery_answer": "Luna",
                "email": "",
                "marketing_opt_in": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Ingresá un email válido", response.get_data(as_text=True))
        conn = sqlite3.connect(client.application.config["DB_PATH"])
        row = conn.execute(
            "SELECT value FROM config WHERE key = 'license_marketing_opt_in'"
        ).fetchone()
        conn.close()
        self.assertIsNone(row)
        mock_sync.assert_not_called()

    @patch("routes.sync_marketing_preference", return_value=False)
    def test_setup_allows_demo_to_continue_without_consent(self, _mock_sync):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
            }
        )

        response = client.post(
            "/setup",
            data={
                "username": "admin",
                "password": "Abc1!d",
                "confirm": "Abc1!d",
                "recovery_question": "Mascota",
                "recovery_answer": "Luna",
            },
        )

        self.assertEqual(response.status_code, 302)
        conn = sqlite3.connect(client.application.config["DB_PATH"])
        row = conn.execute(
            "SELECT value FROM config WHERE key = 'license_marketing_opt_in'"
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], "0")

    @patch("routes.create_license_request")
    @patch("routes.sync_marketing_preference", return_value=False)
    def test_existing_user_saves_marketing_preference_without_license_request(
        self,
        mock_sync,
        mock_create_request,
    ):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
            }
        )

        response = client.post(
            "/activate",
            data={
                "action": "save_marketing_preference",
                "marketing_email": "demo@example.com",
                "marketing_opt_in": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        mock_create_request.assert_not_called()
        mock_sync.assert_called_once()
        conn = sqlite3.connect(client.application.config["DB_PATH"])
        values = dict(conn.execute("SELECT key, value FROM config").fetchall())
        conn.close()
        self.assertEqual(values["license_marketing_opt_in"], "1")
        self.assertEqual(values["license_owner_email"], "demo@example.com")
        activate_page = client.get("/activate")
        self.assertIn(
            "Preferencia guardada localmente, pero no pudo sincronizarse",
            activate_page.get_data(as_text=True),
        )

    @patch("routes.create_license_request")
    @patch("routes.sync_marketing_preference", return_value=False)
    def test_marketing_preference_rejects_opt_in_without_valid_email(
        self,
        mock_sync,
        mock_create_request,
    ):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
                "license_marketing_opt_in": "0",
                "license_owner_email": "demo@example.com",
            }
        )

        response = client.post(
            "/activate",
            data={
                "action": "save_marketing_preference",
                "marketing_email": "",
                "marketing_opt_in": "1",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Ingresá un email válido", response.get_data(as_text=True))
        mock_create_request.assert_not_called()
        mock_sync.assert_not_called()
        conn = sqlite3.connect(client.application.config["DB_PATH"])
        values = dict(conn.execute("SELECT key, value FROM config").fetchall())
        conn.close()
        self.assertEqual(values["license_marketing_opt_in"], "0")
        self.assertEqual(values["license_owner_email"], "demo@example.com")

    @patch("routes.sync_marketing_preference", return_value=False)
    def test_marketing_preference_false_persists_after_get(self, _mock_sync):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
                "license_marketing_opt_in": "1",
                "license_owner_email": "demo@example.com",
            }
        )

        response = client.post(
            "/activate",
            data={
                "action": "save_marketing_preference",
                "marketing_email": "demo@example.com",
            },
        )

        self.assertEqual(response.status_code, 302)
        response = client.get("/activate")
        html = response.get_data(as_text=True)
        self.assertNotIn('id="marketing-opt-in" value="1" checked', html)

    @patch("routes.sync_marketing_preference", return_value=False)
    def test_marketing_email_can_be_explicitly_cleared(self, _mock_sync):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
                "license_owner_email": "demo@example.com",
            }
        )

        response = client.post(
            "/activate",
            data={
                "action": "save_marketing_preference",
                "marketing_email": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        conn = sqlite3.connect(client.application.config["DB_PATH"])
        row = conn.execute(
            "SELECT value FROM config WHERE key = 'license_owner_email'"
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], "")

        response = client.get("/activate")
        self.assertNotIn('value="demo@example.com"', response.get_data(as_text=True))

    def test_marketing_preference_is_loaded_from_existing_config(self):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
                "license_marketing_opt_in": "1",
                "license_owner_email": "demo@example.com",
            }
        )

        response = client.get("/activate")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('id="marketing-opt-in" value="1" checked', html)
        self.assertIn('value="demo@example.com"', html)

    def test_marketing_preference_is_false_when_config_is_absent(self):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
            }
        )

        response = client.get("/activate")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('id="marketing-opt-in" value="1" checked', response.get_data(as_text=True))

    def test_existing_demo_does_not_offer_demo_as_a_license_request_plan(self):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
            }
        )

        response = client.get("/activate")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('<option value="DEMO"', response.get_data(as_text=True))

    def test_activate_page_shows_checkout_buttons_for_expired_demo(self):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today() - timedelta(days=31)),
            }
        )

        response = client.get("/activate")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Checkout directo", html)
        self.assertIn("Plan Básica · Pagar con Mercado Pago", html)
        self.assertIn("Plan Pro · Pagar con Mercado Pago", html)
        self.assertIn("Plan Full · Pagar con Mercado Pago", html)

    def test_activate_page_explains_expired_monthly_without_basica_as_read_only(self):
        client = self._make_client(
            {
                "license_tier": "FULL",
                "license_plan": "FULL",
                "license_key": "NXR-FIN-1234567890",
                "license_expires_at": str(date.today() - timedelta(days=1)),
                "basica_activada": "0",
            }
        )

        response = client.get("/activate")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Suscripcion vencida", html)
        self.assertIn("modo lectura", html)
        self.assertIn("Altas, ediciones y eliminaciones", html)
        self.assertIn("Plan Básica · Pagar con Mercado Pago", html)
        self.assertIn("Plan Pro · Pagar con Mercado Pago", html)
        self.assertIn("Plan Full · Pagar con Mercado Pago", html)

    @patch("routes.webbrowser.open", return_value=True)
    @patch("routes.create_checkout_preference", return_value="https://mp.test/init")
    def test_activate_checkout_open_uses_activation_flow_without_license_key(
        self,
        mock_create_checkout,
        _mock_open_browser,
    ):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
            }
        )

        response = client.post(
            "/activate/checkout/open",
            json={
                "plan": "PRO",
                "nombre": "Titular Demo",
                "email": "demo@example.com",
                "whatsapp": "2640000000",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        kwargs = mock_create_checkout.call_args.kwargs
        self.assertEqual(kwargs["tipo_solicitud"], "alta_licencia")
        self.assertEqual(kwargs["plan_destino"], "PRO")
        self.assertEqual(kwargs["email_titular"], "demo@example.com")
        self.assertEqual(kwargs["license_key"], "")
        self.assertEqual(kwargs["precio"], 0)
        self.assertTrue(kwargs["activation_id"])

        follow_up = client.get("/activate")
        html = follow_up.get_data(as_text=True)
        self.assertIn("Refrescar licencia", html)
        self.assertIn("Detectamos un checkout directo iniciado", html)

    def test_activate_checkout_requires_holder_email(self):
        client = self._make_client(
            {
                "license_tier": "BASICA",
                "license_plan": "BASICA",
                "license_key": "NXR-FIN-1234567890",
            }
        )

        response = client.post(
            "/activate/checkout",
            json={
                "plan": "PRO",
                "nombre": "Titular Basica",
                "email": "",
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("email del titular", payload["message"].lower())

    def test_activate_page_keeps_checkout_visible_without_local_price_env(self):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
            }
        )

        response = client.get("/activate")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Checkout directo", html)
        self.assertIn("Plan Básica · Pagar con Mercado Pago", html)
        self.assertNotIn("checkout online disponible en este entorno", html)

    @patch("routes.validate_saved_license", return_value=(True, "Licencia validada correctamente."))
    def test_refresh_license_with_license_key_keeps_normal_flow(self, mock_validate_saved_license):
        client = self._make_client(
            {
                "license_tier": "FULL",
                "license_plan": "FULL",
                "license_key": "NXR-FIN-1234567890",
                "pending_checkout_activation_id": "HWID-DEMO-001",
                "pending_checkout_plan": "FULL",
                "pending_checkout_request_type": "alta_licencia",
            }
        )

        response = client.post(
            "/activate",
            data={"action": "refresh_license"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        mock_validate_saved_license.assert_called_once()

        conn = sqlite3.connect(client.application.config["DB_PATH"])
        row = conn.execute(
            "SELECT value FROM config WHERE key = 'pending_checkout_activation_id'"
        ).fetchone()
        conn.close()
        self.assertEqual((row[0] if row else ""), "")

    def test_refresh_license_without_license_key_shows_safe_message_for_pending_checkout(self):
        client = self._make_client(
            {
                "license_tier": "DEMO",
                "license_plan": "DEMO",
                "demo_install_date": str(date.today()),
                "pending_checkout_activation_id": "HWID-DEMO-001",
                "pending_checkout_plan": "PRO",
                "pending_checkout_request_type": "alta_licencia",
            }
        )

        response = client.post(
            "/activate",
            data={"action": "refresh_license"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("no tiene una license_key guardada", html)
        self.assertIn("No vuelvas a pagar", html)
        self.assertIn("Activar licencia", html)

    @patch("routes.create_checkout_preference", return_value="https://mp.test/init")
    def test_activate_page_and_post_match_available_plans_for_expired_pro_with_basica(
        self,
        _mock_create_checkout,
    ):
        client = self._make_client(
            {
                "license_tier": "PRO",
                "license_plan": "PRO",
                "license_key": "NXR-FIN-1234567890",
                "license_expires_at": str(date.today() - timedelta(days=1)),
                "basica_activada": "1",
            }
        )

        response = client.get("/activate")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertNotIn("Plan Básica · Pagar con Mercado Pago", html)
        self.assertIn("Plan Pro · Pagar con Mercado Pago", html)
        self.assertIn("Plan Full · Pagar con Mercado Pago", html)

        rejected = client.post(
            "/activate/checkout",
            json={
                "plan": "BASICA",
                "nombre": "Titular Basica",
                "email": "basica@example.com",
            },
        )
        self.assertEqual(rejected.status_code, 400)

        accepted = client.post(
            "/activate/checkout",
            json={
                "plan": "PRO",
                "nombre": "Titular Basica",
                "email": "basica@example.com",
            },
        )
        self.assertEqual(accepted.status_code, 200)

    def test_about_page_shows_full_as_full_plan(self):
        client = self._make_client(
            {
                "license_tier": "FULL",
                "license_plan": "FULL",
                "license_expires_at": str(date.today() + timedelta(days=10)),
            }
        )

        response = client.get("/about")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Plan Full", html)
        self.assertNotIn("Plan Pro</span>", html)

class MarketingConsentSupabaseTests(unittest.TestCase):
    def _sync(self, marketing_opt_in=True):
        return supabase_license_api.sync_marketing_preference(
            email="demo@example.com",
            marketing_opt_in=marketing_opt_in,
            producto="nexar-finanzas",
            activation_id="HWID-DEMO-001",
        )

    @patch.dict("os.environ", {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_ANON_KEY": "anon-key"}, clear=True)
    @patch("licensing.supabase_license_api.requests.post")
    def test_marketing_opt_in_calls_the_centralized_endpoint(self, post):
        post.return_value = Mock(status_code=200, json=Mock(return_value={"ok": True}))

        self.assertTrue(self._sync(True))

        post.assert_called_once_with(
            "https://example.supabase.co/functions/v1/notify-admin",
            headers={
                "apikey": "anon-key",
                "Authorization": "Bearer anon-key",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json={
                "action": "newsletter_preference",
                "email": "demo@example.com",
                "marketing_opt_in": True,
                "producto": "nexar-finanzas",
                "activation_id": "hwid-demo-001",
            },
            timeout=8,
        )

    @patch.dict("os.environ", {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_ANON_KEY": "anon-key"}, clear=True)
    @patch("licensing.supabase_license_api.requests.post")
    def test_marketing_opt_out_calls_the_centralized_endpoint(self, post):
        post.return_value = Mock(status_code=200, json=Mock(return_value={"ok": True}))

        self.assertTrue(self._sync(False))
        self.assertFalse(post.call_args.kwargs["json"]["marketing_opt_in"])

    @patch.dict("os.environ", {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_ANON_KEY": "anon-key"}, clear=True)
    @patch("licensing.supabase_license_api.requests.post")
    def test_marketing_sync_returns_false_for_http_error(self, post):
        post.return_value = Mock(status_code=502)

        self.assertFalse(self._sync())

    @patch.dict("os.environ", {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_ANON_KEY": "anon-key"}, clear=True)
    @patch("licensing.supabase_license_api.requests.post", side_effect=TimeoutError)
    def test_marketing_sync_returns_false_for_timeout(self, _post):
        self.assertFalse(self._sync())

    @patch.dict("os.environ", {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_ANON_KEY": "anon-key"}, clear=True)
    @patch("licensing.supabase_license_api.requests.post", side_effect=RuntimeError)
    def test_marketing_sync_returns_false_for_exception(self, _post):
        self.assertFalse(self._sync())


if __name__ == "__main__":
    unittest.main()
