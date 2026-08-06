"""Configuración opcional de Error Monitoring con Sentry."""

import logging
import os
import sys


logger = logging.getLogger(__name__)

try:
    # Los imports estáticos permiten que PyInstaller detecte esta integración.
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
except ImportError:
    sentry_sdk = None
    FlaskIntegration = None


def _get_sentry_dependencies():
    if sentry_sdk is None or FlaskIntegration is None:
        raise RuntimeError("sentry-sdk no está disponible")

    return sentry_sdk, FlaskIntegration


def _get_environment() -> str:
    configured_environment = os.getenv("NEXAR_ENV", "").strip()
    if configured_environment:
        return configured_environment
    return "production" if getattr(sys, "frozen", False) else "development"


def _strip_personal_data(event, _hint):
    event.pop("request", None)
    event.pop("user", None)
    return event


def initialize_sentry(app_version: str) -> bool:
    """Inicializa Sentry solo cuando existe un DSN, sin bloquear el arranque."""
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    try:
        sentry_sdk, flask_integration = _get_sentry_dependencies()
        sentry_sdk.init(
            dsn=dsn,
            environment=_get_environment(),
            release=f"nexar-finanzas@{app_version}",
            integrations=[flask_integration()],
            traces_sample_rate=0,
            profiles_sample_rate=0,
            send_default_pii=False,
            include_local_variables=False,
            max_request_body_size="never",
            max_breadcrumbs=0,
            before_send=_strip_personal_data,
        )
    except Exception:
        logger.warning("Sentry no pudo inicializarse; se continúa sin monitoreo.")
        return False

    return True
