from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
VENDORED_SDK_PACKAGE = BASE_DIR / "nexar_licencias"
SIBLING_SDK_REPO_PATH = BASE_DIR.parent / "nexar_licencias"
PUBLIC_KEY_PATHS = [
    BASE_DIR / "keys" / "public_key.asc",
    BASE_DIR / "keys" / "public_key.pem",
]


def _ensure_sdk_path() -> None:
    candidates = []
    if VENDORED_SDK_PACKAGE.exists():
        candidates.append(BASE_DIR)
    if SIBLING_SDK_REPO_PATH.exists():
        candidates.append(SIBLING_SDK_REPO_PATH)

    for path in candidates:
        sdk_path = str(path)
        if sdk_path not in sys.path:
            sys.path.append(sdk_path)


def _import_module(module_name: str):
    _ensure_sdk_path()
    return importlib.import_module(module_name)


def import_validar_licencia():
    try:
        module = _import_module("nexar_licencias")
        return getattr(module, "validar_licencia", None)
    except Exception:
        return None


def import_validar_licencia_detalle():
    try:
        module = _import_module("nexar_licencias")
        return getattr(module, "validar_licencia_detalle", None)
    except Exception:
        return None


def get_license_product() -> str:
    return os.getenv("LICENSE_PRODUCT", "nexar-finanzas").strip() or "nexar-finanzas"


def load_public_key() -> str | None:
    env_key = os.getenv("PUBLIC_KEY", "").strip()
    if env_key:
        return env_key

    for path in PUBLIC_KEY_PATHS:
        try:
            content = path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception:
            continue
    return None


def get_current_hwid() -> str:
    try:
        device_module = _import_module("nexar_licencias.device")
        get_product_hwid = getattr(device_module, "get_product_hwid", None)
        if callable(get_product_hwid):
            return str(get_product_hwid(get_license_product()))
        return str(device_module.get_hwid())
    except Exception:
        try:
            from licensing.hardware_id import get_hardware_id

            return get_hardware_id()
        except Exception:
            return ""


def _save_sdk_cache(license_data: dict) -> None:
    if not license_data:
        return
    try:
        cache_module = _import_module("nexar_licencias.cache")
        save_cache = getattr(cache_module, "save_cache", None)
        if callable(save_cache):
            save_cache(license_data)
    except Exception:
        pass


def _activate_license_without_sdk(license_key: str) -> tuple[bool, str, dict[str, Any] | None]:
    try:
        from licensing.supabase_license_api import activate_license

        return activate_license(
            license_key,
            get_current_hwid(),
            get_license_product(),
        )
    except Exception as ex:
        return False, f"No se pudo validar online: {ex}", None


def _sync_license_data(db_path: str | None, license_data: dict) -> tuple[bool, str]:
    if not db_path:
        return True, ""

    try:
        import models

        plan = models.normalize_license_plan(
            license_data.get("plan") or license_data.get("tier") or license_data.get("license_plan")
        )
        cfg = models.get_config(db_path)
        if plan == "MENSUAL_FULL" and cfg.get("basica_activada", "0") != "1":
            return False, "Para activar Mensual Full primero tenes que activar una licencia Basica en esta instalacion."
        models.sync_license_from_remote(db_path, license_data)
        return True, ""
    except Exception as ex:
        return False, f"Licencia valida, pero no se pudo guardar la activacion: {ex}"


def validate_license_key(license_key: str, db_path: str | None = None, debug: bool = False) -> tuple[bool, str]:
    license_key = (license_key or "").strip()
    if not license_key:
        return False, "Ingresa una licencia valida."

    validar_detalle = import_validar_licencia_detalle()
    validar_licencia = import_validar_licencia()
    if validar_detalle is None and validar_licencia is None:
        fallback_ok, fallback_msg, fallback_data = _activate_license_without_sdk(license_key)
        if fallback_ok and fallback_data:
            ok_sync, sync_msg = _sync_license_data(db_path, fallback_data)
            if not ok_sync:
                return False, sync_msg
            return True, fallback_msg
        return False, fallback_msg or "No se pudo cargar el SDK nexar_licencias."

    result = {}
    try:
        if validar_detalle is not None:
            result = validar_detalle(
                {"license_key": license_key},
                load_public_key(),
                get_license_product(),
                debug=debug,
            )
            ok = bool(result.get("ok"))
            license_data = result.get("license") or {}
        else:
            ok = bool(validar_licencia(
                {"license_key": license_key},
                load_public_key(),
                get_license_product(),
                debug=debug,
            ))
            license_data = {"license_key": license_key}
    except Exception as ex:
        return False, f"Error validando licencia: {ex}"

    if not ok:
        reason = result.get("reason") if validar_detalle is not None else ""
        if reason == "sin_cache":
            fallback_ok, fallback_msg, fallback_data = _activate_license_without_sdk(license_key)
            if fallback_ok and fallback_data:
                ok = True
                license_data = fallback_data
                _save_sdk_cache(license_data)
            else:
                return False, fallback_msg

    if not ok:
        reason = result.get("reason") if validar_detalle is not None else ""
        messages = {
            "expirada": "La licencia expiro. Pedi la renovacion al desarrollador.",
            "revocada": "La licencia fue revocada o esta desactivada.",
            "limite_dispositivos": "La licencia alcanzo el limite de dispositivos. Pedi reset o mas equipos al desarrollador.",
            "no_se_pudo_vincular_dispositivo": "La licencia existe, pero no se pudo vincular este equipo. Intenta de nuevo o pedi reset al desarrollador.",
            "no_existe": "No existe una licencia activa con esa clave para este producto.",
            "sin_cache": "No se pudo validar online y no hay cache offline para esta licencia.",
        }
        return False, messages.get(reason, "La licencia es invalida, expiro o fue revocada.")

    _save_sdk_cache(license_data)

    ok_sync, sync_msg = _sync_license_data(db_path, license_data)
    if not ok_sync:
        return False, sync_msg

    return True, "Licencia validada correctamente."


def validate_saved_license(db_path: str, debug: bool = False) -> tuple[bool, str]:
    try:
        import models

        license_key = models.get_config(db_path).get("license_key", "")
    except Exception:
        license_key = ""

    if not license_key:
        return False, "No hay licencia guardada."

    return validate_license_key(license_key, db_path=db_path, debug=debug)
