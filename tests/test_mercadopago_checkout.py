import unittest
from unittest.mock import MagicMock, patch

from services.mercadopago_checkout import (
    MercadoPagoCheckoutError,
    build_external_reference,
    create_checkout_preference,
    get_price_for_plan,
    plan_supports_checkout,
)


class MercadoPagoCheckoutTests(unittest.TestCase):
    def test_plan_supports_checkout_only_for_paid_plans(self):
        self.assertTrue(plan_supports_checkout("BASICA"))
        self.assertTrue(plan_supports_checkout("PRO"))
        self.assertTrue(plan_supports_checkout("FULL"))
        self.assertFalse(plan_supports_checkout("DEMO"))
        self.assertFalse(plan_supports_checkout(""))

    def test_get_price_for_plan_returns_zero_without_local_env(self):
        self.assertEqual(get_price_for_plan("BASICA"), 0)
        self.assertEqual(get_price_for_plan("PRO"), 0)
        self.assertEqual(get_price_for_plan("FULL"), 0)

    def test_build_external_reference_requires_activation_id_for_alta(self):
        with self.assertRaises(MercadoPagoCheckoutError):
            build_external_reference(
                producto="nexar-finanzas",
                plan_destino="PRO",
                tipo_solicitud="alta_licencia",
                activation_id="",
            )

    def test_build_external_reference_requires_license_key_for_change(self):
        with self.assertRaises(MercadoPagoCheckoutError):
            build_external_reference(
                producto="nexar-finanzas",
                plan_destino="FULL",
                tipo_solicitud="cambio_plan",
                license_key="",
            )

    @patch("services.mercadopago_checkout.requests.post")
    def test_create_checkout_preference_sends_payload_for_activation_without_local_price(self, mock_post):
        response = MagicMock()
        response.status_code = 200
        response.content = b'{"init_point":"https://mp.test/init"}'
        response.json.return_value = {"init_point": "https://mp.test/init"}
        mock_post.return_value = response

        init_point = create_checkout_preference(
            producto="nexar-finanzas",
            plan_destino="PRO",
            external_reference="ALTA|HWID-123|nexar-finanzas|PRO",
            license_key="",
            email_titular="demo@example.com",
            activation_id="HWID-123",
            tipo_solicitud="alta_licencia",
        )

        self.assertEqual(init_point, "https://mp.test/init")
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["producto"], "nexar-finanzas")
        self.assertEqual(payload["plan_destino"], "PRO")
        self.assertEqual(payload["precio"], 0)
        self.assertEqual(payload["external_reference"], "ALTA|HWID-123|nexar-finanzas|PRO")
        self.assertEqual(payload["license_key"], "")
        self.assertEqual(payload["activation_id"], "HWID-123")
        self.assertEqual(payload["tipo_solicitud"], "alta_licencia")
        self.assertEqual(payload["email"], "demo@example.com")

    @patch("services.mercadopago_checkout.requests.post")
    def test_create_checkout_preference_sends_payload_for_plan_change(self, mock_post):
        response = MagicMock()
        response.status_code = 200
        response.content = b'{"init_point":"https://mp.test/init"}'
        response.json.return_value = {"init_point": "https://mp.test/init"}
        mock_post.return_value = response

        init_point = create_checkout_preference(
            producto="nexar-finanzas",
            plan_destino="FULL",
            external_reference="NXR-FIN-123456|nexar-finanzas|FULL",
            license_key="NXR-FIN-123456",
            email_titular="cliente@example.com",
            activation_id="HWID-999",
            tipo_solicitud="cambio_plan",
        )

        self.assertEqual(init_point, "https://mp.test/init")
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["license_key"], "NXR-FIN-123456")
        self.assertEqual(payload["activation_id"], "HWID-999")
        self.assertEqual(payload["tipo_solicitud"], "cambio_plan")
        self.assertEqual(payload["external_reference"], "NXR-FIN-123456|nexar-finanzas|FULL")


if __name__ == "__main__":
    unittest.main()
