from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
VENDORED_SDK_PACKAGE = BASE_DIR / "nexar_licencias"
SIBLING_SDK_REPO_PATH = BASE_DIR.parent / "nexar_licencias"
PUBLIC_KEY_PATHS = [
    BASE_DIR / "keys" / "public_key.asc",
    BASE_DIR / "keys" / "public_key.pem",
]

PLAN_DEMO = "DEMO"
PLAN_DEMO_EXPIRED = "DEMO_EXPIRED"
PLAN_BASICA = "BASICA"
PLAN_PRO = "PRO"
PLAN_FULL = "FULL"
PAID_PLANS = {PLAN_BASICA, PLAN_PRO, PLAN_FULL}
MONTHLY_PLANS = {PLAN_PRO, PLAN_FULL}

PLAN_ALIASES = {
    "BASIC": PLAN_BASICA,
    "BASICO": PLAN_BASICA,
    "BASICA": PLAN_BASICA,
    "DEMO": PLAN_DEMO,
    "DEMO_EXPIRED": PLAN_DEMO_EXPIRED,
    "PRO": PLAN_PRO,
    "MENSUAL_PRO": PLAN_PRO,
    "FULL": PLAN_FULL,
    "MENSUAL": PLAN_FULL,
    "MENSUAL_FULL": PLAN_FULL,
}

SDK_FULL_PLAN = "MENSUAL_FULL"


@dataclass(frozen=True)
class LicenseRecord:
    stored_tier: str = PLAN_DEMO
    license_plan: str = PLAN_DEMO
    expires_at: str = ""
    demo_install_date: str = ""
    basica_activada: bool = False
    license_key: str = ""
    raw_config: dict[str, str] | None = None


@dataclass(frozen=True)
class LicenseState:
    stored_tier: str
    active_plan: str
    effective_tier: str
    expires_at: str
    demo_install_date: str
    basica_activada: bool
    license_key: str
    subscription_expired: bool
    demo_expired: bool
    source: str = "local"


def normalize_plan(plan: str | None, default: str = PLAN_BASICA) -> str:
    raw = (plan or default).strip().upper().replace("-", "_").replace(" ", "_")
    return PLAN_ALIASES.get(raw, default)


def normalize_paid_plan(plan: str | None) -> str:
    normalized = normalize_plan(plan, default="")
    return normalized if normalized in PAID_PLANS else ""


def sdk_plan_from_finanzas(plan: str | None) -> str:
    normalized = normalize_plan(plan)
    return SDK_FULL_PLAN if normalized == PLAN_FULL else normalized


def finanzas_plan_from_sdk(plan: str | None) -> str:
    return normalize_plan(plan)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "si", "on"}


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def read_config(db_path: str) -> dict[str, str]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
        return {row["key"]: row["value"] for row in rows}
    finally:
        conn.close()


def write_config(db_path: str, values: dict[str, Any]) -> None:
    conn = sqlite3.connect(db_path)
    try:
        for key, value in values.items():
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, "" if value is None else str(value)),
            )
        conn.commit()
    finally:
        conn.close()


def read_license_record(db_path: str) -> LicenseRecord:
    try:
        cfg = read_config(db_path)
    except Exception:
        cfg = {}

    stored_tier = normalize_plan(cfg.get("license_tier"), default=PLAN_DEMO)
    active_plan = normalize_plan(
        cfg.get("license_plan") or cfg.get("license_tier"),
        default=stored_tier,
    )
    return LicenseRecord(
        stored_tier=stored_tier,
        license_plan=active_plan,
        expires_at=str(cfg.get("license_expires_at", "") or ""),
        demo_install_date=str(cfg.get("demo_install_date", "") or ""),
        basica_activada=_as_bool(cfg.get("basica_activada")),
        license_key=str(cfg.get("license_key", "") or "").strip(),
        raw_config=cfg,
    )


def resolve_license_state(record: LicenseRecord, today: date | None = None) -> LicenseState:
    current_day = today or date.today()
    stored_tier = normalize_plan(record.stored_tier, default=PLAN_DEMO)
    active_plan = normalize_plan(record.license_plan, default=stored_tier)
    expires_on = _parse_iso_date(record.expires_at)
    install_on = _parse_iso_date(record.demo_install_date)

    subscription_expired = bool(stored_tier in MONTHLY_PLANS and expires_on and current_day > expires_on)
    demo_expired = bool(stored_tier == PLAN_DEMO and install_on and (current_day - install_on).days > 30)

    effective_tier = stored_tier
    if subscription_expired:
        effective_tier = PLAN_BASICA if record.basica_activada else PLAN_DEMO_EXPIRED
    elif demo_expired:
        effective_tier = PLAN_DEMO_EXPIRED

    return LicenseState(
        stored_tier=stored_tier,
        active_plan=active_plan,
        effective_tier=effective_tier,
        expires_at=record.expires_at,
        demo_install_date=record.demo_install_date,
        basica_activada=record.basica_activada,
        license_key=record.license_key,
        subscription_expired=subscription_expired,
        demo_expired=demo_expired,
    )


def get_license_state(db_path: str) -> LicenseState:
    return resolve_license_state(read_license_record(db_path))


def sync_license_from_remote(db_path: str, license_data: dict) -> None:
    data = dict(license_data or {})
    plan = normalize_plan(data.get("plan") or data.get("tier") or data.get("license_plan"))
    tier = plan
    expires_at = data.get("expira") or data.get("expires_at") or ""
    license_key = data.get("license_key") or ""
    max_devices = data.get("max_devices") or data.get("max_machines") or 1

    try:
        cfg = read_config(db_path)
    except Exception:
        cfg = {}
    basica_activada = _as_bool(cfg.get("basica_activada")) or tier == PLAN_BASICA

    values = {
        "version": "DEMO" if tier == PLAN_DEMO else "FULL",
        "license_tier": tier,
        "license_plan": plan,
        "license_expires_at": "" if tier == PLAN_BASICA else expires_at,
        "license_key": license_key,
        "license_signature": data.get("public_signature") or data.get("signature") or "",
        "license_type": "supabase",
        "license_activated_at": data.get("activated_at") or data.get("created_at") or date.today().isoformat(),
        "license_last_check": date.today().isoformat(),
        "license_max_devices": max_devices,
        "license_data_full": json.dumps(data, ensure_ascii=False, sort_keys=True),
        "basica_activada": "1" if basica_activada else "0",
    }
    write_config(db_path, values)


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


def _env_first(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def get_license_product() -> str:
    return _env_first("NEXAR_LICENSES_PRODUCT", "LICENSE_PRODUCT") or "nexar-finanzas"


def get_sdk_config(overrides: dict[str, Any] | None = None):
    module = _import_module("nexar_licencias")
    sdk_config_cls = getattr(module, "SDKConfig")
    values = {
        "validation_url": _env_first("NEXAR_LICENSES_VALIDATION_URL", "SUPABASE_URL"),
        "supabase_key": _env_first("NEXAR_LICENSES_SUPABASE_KEY", "SUPABASE_KEY", "SUPABASE_ANON_KEY"),
    }
    values.update(overrides or {})
    return sdk_config_cls.from_env(**{k: v for k, v in values.items() if v})


def load_public_key() -> str | None:
    env_key = _env_first("NEXAR_LICENSES_PUBLIC_KEY", "PUBLIC_KEY")
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


def _save_sdk_cache(license_data: dict, config=None) -> None:
    if not license_data:
        return
    save_cache = None
    try:
        cache_module = _import_module("nexar_licencias.cache")
        save_cache = getattr(cache_module, "save_cache", None)
        if callable(save_cache):
            save_cache(license_data, config=config)
    except TypeError:
        try:
            if callable(save_cache):
                save_cache(license_data)
        except Exception:
            pass
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
        sync_license_from_remote(db_path, license_data)
        return True, ""
    except Exception as ex:
        return False, f"Licencia valida, pero no se pudo guardar la activacion: {ex}"


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


def validate_license_key(license_key: str, db_path: str | None = None, debug: bool = False, config=None) -> tuple[bool, str]:
    license_key = (license_key or "").strip()
    if not license_key:
        return False, "Ingresa una licencia valida."

    validar_detalle = import_validar_licencia_detalle()
    validar_licencia = import_validar_licencia()
    sdk_config = config
    if sdk_config is None and (validar_detalle is not None or validar_licencia is not None):
        try:
            sdk_config = get_sdk_config()
        except Exception:
            sdk_config = None

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
                config=sdk_config,
            )
            ok = bool(result.get("ok"))
            license_data = result.get("license") or {}
        else:
            ok = bool(validar_licencia(
                {"license_key": license_key},
                load_public_key(),
                get_license_product(),
                debug=debug,
                config=sdk_config,
            ))
            license_data = {"license_key": license_key}
    except TypeError:
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
    except Exception as ex:
        return False, f"Error validando licencia: {ex}"

    if not ok:
        reason = result.get("reason") if validar_detalle is not None else ""
        if reason in {"sin_cache", "firma_invalida", "signature_error"}:
            fallback_ok, fallback_msg, fallback_data = _activate_license_without_sdk(license_key)
            if fallback_ok and fallback_data:
                ok = True
                license_data = fallback_data
                _save_sdk_cache(license_data, config=sdk_config)
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

    _save_sdk_cache(license_data, config=sdk_config)

    ok_sync, sync_msg = _sync_license_data(db_path, license_data)
    if not ok_sync:
        return False, sync_msg

    return True, "Licencia validada correctamente."


def validate_saved_license(db_path: str, debug: bool = False, config=None) -> tuple[bool, str]:
    try:
        license_key = read_config(db_path).get("license_key", "")
    except Exception:
        license_key = ""

    if not license_key:
        return False, "No hay licencia guardada."

    return validate_license_key(license_key, db_path=db_path, debug=debug, config=config)
