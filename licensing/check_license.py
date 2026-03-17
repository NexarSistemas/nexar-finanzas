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
      3. ~/.local/share/finanzas-hogar/          (instalación en /opt/)
    """
    # __file__ está en  <raiz>/licensing/check_license.py
    # _app_dir apunta a <raiz>/
    _app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if os.environ.get('FINANZAS_DATA_DIR'):
        base_dir = os.environ['FINANZAS_DATA_DIR']
    elif getattr(sys, 'frozen', False) and os.name == 'nt':
        base_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'FinanzasHogar')
    elif getattr(sys, 'frozen', False):
        base_dir = os.path.join(os.path.expanduser('~'), '.local', 'share', 'finanzas-hogar')
    else:
        base_dir = _app_dir if os.access(_app_dir, os.W_OK) else \
                   os.path.join(os.path.expanduser('~'), '.local', 'share', 'finanzas-hogar')
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

def check_license():
    """
    Verifica el estado de la licencia y retorna "FULL" o "DEMO".
    Solo muestra la pantalla de bienvenida la primera vez que el usuario
    abre la app sin ningún registro de licencia.
    """

    # ── Caso 1: ya activado por la interfaz web → FULL ────────────────────────
    if _is_full_in_db():
        set_full({})
        return "FULL"

    # ── Caso 2: primera vez, sin ningún registro → bienvenida ─────────────────
    try:
        from .activation_gui import WelcomeWindow
        win = WelcomeWindow()
        win.run()
    except Exception as e:
        print(f"[AVISO] No se pudo mostrar la pantalla de bienvenida: {e}")

    set_demo()
    return "DEMO"
