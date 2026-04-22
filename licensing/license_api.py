"""
Compatibilidad para integraciones que todavia importan license_api.py.

El flujo nuevo usa licensing.license_sdk y licensing.supabase_license_api,
igual que Nexar Tienda/Almacen.
"""

from __future__ import annotations

import sqlite3

from .license_sdk import validate_saved_license


def verificar_licencia_finanzas(db_path, public_key=None):
    ok, _msg = validate_saved_license(db_path, debug=True)
    if not ok:
        _revocar_finanzas(db_path)
    return ok


def _revocar_finanzas(db_path):
    """Degrada a DEMO, salvo que exista Basica activada previamente."""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        row = cur.execute("SELECT value FROM config WHERE key='basica_activada'").fetchone()
        basica_activada = row is not None and row[0] == "1"
        if basica_activada:
            cur.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('version', 'FULL')")
            cur.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('license_tier', 'BASICA')")
            cur.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('license_plan', 'BASICA')")
        else:
            cur.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('version', 'DEMO')")
            cur.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('license_tier', 'DEMO')")
            cur.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('license_plan', 'DEMO')")
        cur.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('license_expires_at', '')")
        conn.commit()
        conn.close()
        print("[LICENSE] Licencia revocada. Volviendo al plan disponible.")
    except Exception as e:
        print(f"[LICENSE-ERR] Error al revocar: {e}")
