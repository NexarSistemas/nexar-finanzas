from __future__ import annotations

import logging
import os

import requests


DEFAULT_NEXAR_PAGOS_API = "https://nexar-pagos.netlify.app/.netlify/functions"
REQUEST_TIMEOUT_SECONDS = 12

logger = logging.getLogger(__name__)


class MercadoPagoCheckoutError(RuntimeError):
    """Error controlado del flujo de checkout."""


def _normalize_checkout_plan(plan: str) -> str:
    raw = str(plan or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "BASIC": "BASICA",
        "BASICO": "BASICA",
        "MENSUAL_PRO": "PRO",
        "MENSUAL_FULL": "FULL",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in {"BASICA", "PRO", "FULL"} else ""


def _mask_license_key(license_key: str) -> str:
    value = str(license_key or "").strip()
    if not value:
        return ""
    if len(value) <= 6:
        return f"{value[:1]}***{value[-1:]}"
    return f"{value[:3]}***{value[-3:]}"


def get_nexar_pagos_api_base() -> str:
    return (
        os.getenv("NEXAR_PAGOS_API", DEFAULT_NEXAR_PAGOS_API).strip().rstrip("/")
        or DEFAULT_NEXAR_PAGOS_API
    )


def get_price_for_plan(plan_destino: str) -> int:
    plan = _normalize_checkout_plan(plan_destino)
    if not plan:
        raise MercadoPagoCheckoutError("El plan solicitado no admite checkout online.")
    return 0


def plan_supports_checkout(plan_destino: str) -> bool:
    return bool(_normalize_checkout_plan(plan_destino))


def build_external_reference(
    *,
    producto: str,
    plan_destino: str,
    tipo_solicitud: str,
    license_key: str = "",
    activation_id: str = "",
) -> str:
    license_value = str(license_key or "").strip()
    activation_value = str(activation_id or "").strip()
    product_value = str(producto or "").strip()
    plan_value = _normalize_checkout_plan(plan_destino)
    request_type = str(tipo_solicitud or "").strip().lower()

    if request_type not in {"alta_licencia", "cambio_plan"}:
        raise MercadoPagoCheckoutError("No se pudo resolver el tipo de checkout.")
    if not product_value:
        raise MercadoPagoCheckoutError("No se pudo resolver el producto de la licencia.")
    if not plan_supports_checkout(plan_value):
        raise MercadoPagoCheckoutError("El plan solicitado no admite checkout online.")

    if request_type == "alta_licencia":
        if not activation_value:
            raise MercadoPagoCheckoutError(
                "No se encontro un ID de activacion valido para iniciar el checkout."
            )
        return f"ALTA|{activation_value}|{product_value}|{plan_value}"

    if not license_value:
        raise MercadoPagoCheckoutError(
            "No se encontro una licencia valida para iniciar el checkout."
        )
    return f"{license_value}|{product_value}|{plan_value}"


def create_checkout_preference(
    *,
    producto: str,
    plan_destino: str,
    precio: int = 0,
    external_reference: str,
    license_key: str,
    email_titular: str,
    activation_id: str = "",
    tipo_solicitud: str = "cambio_plan",
) -> str:
    plan = _normalize_checkout_plan(plan_destino)
    email = str(email_titular or "").strip().lower()
    reference = str(external_reference or "").strip()
    api_base = get_nexar_pagos_api_base()
    request_type = str(tipo_solicitud or "").strip().lower() or "cambio_plan"

    if not plan_supports_checkout(plan):
        raise MercadoPagoCheckoutError("El plan solicitado no admite checkout online.")
    if not email:
        raise MercadoPagoCheckoutError(
            "Necesitas cargar un email del titular antes de continuar."
        )
    if not reference:
        raise MercadoPagoCheckoutError(
            "No se pudo generar la referencia del checkout."
        )

    payload = {
        "producto": str(producto or "").strip(),
        "plan_destino": plan,
        "precio": int(precio or 0),
        "external_reference": reference,
        "license_key": str(license_key or "").strip(),
        "activation_id": str(activation_id or "").strip(),
        "tipo_solicitud": request_type,
        "email": email,
    }

    request_url = f"{api_base}/create-preference"
    logger.info(
        "Checkout Mercado Pago: creando preferencia tipo=%s producto=%s plan=%s licencia=%s activation_id=%s",
        request_type,
        payload["producto"],
        plan,
        _mask_license_key(payload["license_key"]),
        payload["activation_id"][:12],
    )

    try:
        response = requests.post(request_url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.Timeout as exc:
        raise MercadoPagoCheckoutError(
            "El servicio de pagos tardo demasiado en responder."
        ) from exc
    except requests.ConnectionError as exc:
        raise MercadoPagoCheckoutError(
            "No se pudo conectar con el servicio de pagos."
        ) from exc
    except requests.RequestException as exc:
        raise MercadoPagoCheckoutError(
            "No se pudo iniciar el checkout en este momento."
        ) from exc

    try:
        body = response.json() if response.content else {}
    except ValueError:
        body = {}

    if response.status_code >= 400:
        detail = str(body.get("detalle") or body.get("error") or "").strip()
        raise MercadoPagoCheckoutError(
            detail or "El servicio de pagos no pudo crear la preferencia."
        )

    init_point = str(body.get("init_point") or "").strip()
    if not init_point:
        raise MercadoPagoCheckoutError(
            "La preferencia de pago no devolvio un enlace valido."
        )

    logger.info(
        "Checkout Mercado Pago preferencia creada tipo=%s plan=%s licencia=%s activation_id=%s",
        request_type,
        plan,
        _mask_license_key(payload["license_key"]),
        payload["activation_id"][:12],
    )
    return init_point
