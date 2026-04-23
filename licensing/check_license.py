"""
check_license.py
Punto de entrada del sistema de licencias al iniciar la app.

Lógica:
  1. La BD SQLite dice version='FULL'   → FULL, sin interrupciones.
  2. Había license.json pero es inválido → DEMO silencioso.
  3. Primera vez, sin ningún registro   → pantalla de bienvenida.
"""

import os
import sys
import sqlite3

from .demo_state      import set_demo, set_full


# ── Ruta a la BD (misma lógica que app.py) ────────────────────────────────────

def _get_db_path():
    """
    Calcula la ruta a database.db usando la misma prioridad que app.py:
      1. Variable de entorno FINANZAS_DATA_DIR
      2. Directorio del script si es escribible  (modo portable)
      3. ~/.local/share/nexar-finanzas/          (instalación en /opt/)
    """
    # __file__ está en  <raiz>/licensing/check_license.py
    # _app_dir apunta a <raiz>/
    _app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if os.environ.get('FINANZAS_DATA_DIR'):
        base_dir = os.environ['FINANZAS_DATA_DIR']
    elif getattr(sys, 'frozen', False) and os.name == 'nt':
        base_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'NexarFinanzas')
    elif getattr(sys, 'frozen', False):
        base_dir = os.path.join(os.path.expanduser('~'), '.local', 'share', 'nexar-finanzas')
    else:
        base_dir = _app_dir if os.access(_app_dir, os.W_OK) else \
                   os.path.join(os.path.expanduser('~'), '.local', 'share', 'nexar-finanzas')
    return os.path.join(base_dir, 'database.db')


def _is_full_in_db():
    """
    Devuelve True si la BD SQLite registra version='FULL'.
    No lanza excepciones — si algo falla simplemente devuelve False.
    """
    try:
        db_path = _get_db_path()
        if not os.path.exists(db_path):
            return False
        conn = sqlite3.connect(db_path)
        row  = conn.execute(
            "SELECT value FROM config WHERE key='version'"
        ).fetchone()
        conn.close()
        return row is not None and row[0] == 'FULL'
    except Exception:
        return False


# ── Función principal ─────────────────────────────────────────────────────────

def _get_config_value(key: str) -> str:
    try:
        db_path = _get_db_path()
        if not os.path.exists(db_path):
            return ""
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        conn.close()
        return row[0] if row else ""
    except Exception:
        return ""


def check_license():
    """
    Verifica el estado de la licencia y retorna "FULL" o "DEMO".
    Solo muestra la pantalla de bienvenida la primera vez que el usuario
    abre la app sin ningún registro de licencia.
    """

    # ── Caso 1: ya activado por la interfaz web → FULL ────────────────────────
    if _is_full_in_db():
        if _get_config_value("license_key"):
            try:
                from .license_sdk import validate_saved_license

                ok, msg = validate_saved_license(_get_db_path(), debug=True)
                if not ok:
                    print(f"[LICENSE] {msg}")
                    try:
                        from .license_api import _revocar_finanzas

                        _revocar_finanzas(_get_db_path())
                    except Exception:
                        pass
                    if _get_config_value("basica_activada") == "1":
                        set_full({})
                        return "FULL"
                    set_demo()
                    return "DEMO"
            except Exception as e:
                print(f"[AVISO] No se pudo validar licencia guardada: {e}")
        set_full({})
        return "FULL"

    # Sin licencia activa: iniciar en DEMO sin mostrar ventanas previas.
    set_demo()
    return "DEMO"
