"""
license_api.py — Nexar Finanzas
====================================
Verifica la licencia contra Supabase usando el SDK nexar_licencias.
"""

import sys
import os
import json
import sqlite3

# Añadir el path del SDK si no está instalado como paquete
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'nexar_licencias')))
from nexar_licencias import validar_licencia

def verificar_licencia_finanzas(db_path, public_key):
    """
    Punto de entrada para Finanzas usando el nuevo SDK de Supabase.
    Lee los datos de la tabla 'config' y valida.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM config")
        cfg = {row['key']: row['value'] for row in cur.fetchall()}
        conn.close()
    except Exception as e:
        print(f"[LICENSE-ERR] No se pudo leer la DB: {e}")
        return False

    # 1. Verificar si está en modo demo
    if cfg.get('license_tier', 'DEMO') == 'DEMO':
        return True # El control de tiempo de demo es independiente

    # 2. Intentar cargar el JSON completo de la licencia
    lic_json = cfg.get('license_data_full', '{}')
    try:
        licencia_dict = json.loads(lic_json)
    except:
        # Fallback si solo tenemos los campos sueltos
        licencia_dict = {
            "license_key": cfg.get('license_key', ''),
            "public_signature": cfg.get('license_signature', '')
        }

    # 3. Validar con el SDK
    ok = validar_licencia(
        licencia_dict=licencia_dict,
        public_key=public_key,
        product_name="finanzas",
        debug=True
    )

    if not ok:
        _revocar_finanzas(db_path)
        return False

    return True

def _revocar_finanzas(db_path):
    """Degrada el tier a DEMO en caso de fallo de validación."""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # En Finanzas volvemos a DEMO si la licencia PRO/BASICA falla
        cur.execute("UPDATE config SET value = 'DEMO' WHERE key = 'license_tier'")
        cur.execute("UPDATE config SET value = '' WHERE key = 'license_expires_at'")
        conn.commit()
        conn.close()
        print("[LICENSE] Licencia revocada. Volviendo a modo DEMO.")
    except Exception as e:
        print(f"[LICENSE-ERR] Error al revocar: {e}")
