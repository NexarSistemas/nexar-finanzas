import os
import unittest
from unittest.mock import Mock, patch

import sentry_monitoring


class SentryMonitoringTests(unittest.TestCase):
    def test_does_not_initialize_without_dsn(self):
        with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False), patch(
            "sentry_monitoring._get_sentry_dependencies"
        ) as dependencies:
            initialized = sentry_monitoring.initialize_sentry("1.13.2")

        self.assertFalse(initialized)
        dependencies.assert_not_called()

    def test_initializes_with_dsn_and_safe_options(self):
        sentry_sdk = Mock()
        flask_integration = Mock(return_value="flask-integration")

        with patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://public@example.ingest.sentry.io/1", "NEXAR_ENV": "test"},
            clear=False,
        ), patch(
            "sentry_monitoring._get_sentry_dependencies",
            return_value=(sentry_sdk, flask_integration),
        ):
            initialized = sentry_monitoring.initialize_sentry("1.13.2")

        self.assertTrue(initialized)
        sentry_sdk.init.assert_called_once_with(
            dsn="https://public@example.ingest.sentry.io/1",
            environment="test",
            release="nexar-finanzas@1.13.2",
            integrations=["flask-integration"],
            default_integrations=False,
            traces_sample_rate=0,
            profiles_sample_rate=0,
            send_default_pii=False,
            include_local_variables=False,
            max_request_body_size="never",
            max_breadcrumbs=0,
            before_send=sentry_monitoring._strip_personal_data,
        )

    def test_sdk_failure_does_not_block_application_start(self):
        with patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://public@example.ingest.sentry.io/1"},
            clear=False,
        ), patch(
            "sentry_monitoring._get_sentry_dependencies",
            side_effect=RuntimeError("SDK unavailable"),
        ):
            self.assertFalse(sentry_monitoring.initialize_sentry("1.13.2"))

    def test_strips_request_and_user_data(self):
        event = {
            "request": {"data": {"amount": "100"}, "cookies": {"session": "secret"}},
            "user": {"id": "123"},
        }

        self.assertEqual(sentry_monitoring._strip_personal_data(event, {}), {})

    def test_uses_contextual_environment_fallback(self):
        with patch.dict(os.environ, {"NEXAR_ENV": ""}, clear=False), patch.object(
            sentry_monitoring.sys, "frozen", False, create=True
        ):
            self.assertEqual(sentry_monitoring._get_environment(), "development")

        with patch.dict(os.environ, {"NEXAR_ENV": ""}, clear=False), patch.object(
            sentry_monitoring.sys, "frozen", True, create=True
        ):
            self.assertEqual(sentry_monitoring._get_environment(), "production")


if __name__ == "__main__":
    unittest.main()
