# -*- coding: utf-8 -*-
"""
app.py
Punto de entrada principal — Nexar Finanzas v1.10.1
Modo de visualización: pywebview (ventana nativa) con fallback
al navegador SOLO si pywebview falla o no está disponible.
"""

import os
import sys
import logging
import traceback
import threading
import time
import socket as _socket
from flask import Flask, render_template, session, redirect, url_for

# ─────────────────────────────────────────────────────────────
# SISTEMA DE LICENCIAS
# ─────────────────────────────────────────────────────────────

LICENSE_MODE = "DEMO"

try:
    from licensing.check_license import check_license
    from licensing.demo_state import LICENSE_MODE as _LICENSE_MODE

    def _check_license():
        global LICENSE_MODE
        try:
            LICENSE_MODE = check_license()
        except Exception as e:
            print("[AVISO] Error verificando licencia:", e)
            LICENSE_MODE = "DEMO"

except Exception as e:

    print("[AVISO] Sistema de licencias no disponible:", e)

    def _check_license():
        global LICENSE_MODE
        LICENSE_MODE = "DEMO"


# ─── Log de errores a archivo ─────────────────────────────────

def _setup_logging():
    if getattr(sys, 'frozen', False):
        log_dir = os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if os.access(script_dir, os.W_OK):
            log_dir = script_dir
        else:
            log_dir = os.path.join(
                os.environ.get('HOME', os.path.expanduser('~')),
                '.local', 'share', 'nexar-finanzas'
            )
            os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, 'finanzas_error.log')
    try:
        logging.basicConfig(
            filename=log_path,
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
            encoding='utf-8',
        )
    except (PermissionError, OSError):
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
        )
        log_path = '(consola)'
    return log_path


_LOG_PATH = _setup_logging()


# ─── Rutas del sistema ────────────────────────────────────────

def _get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _get_internal_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


_APP_DIR = _get_app_dir()
_INTERNAL_DIR = _get_internal_dir()

# Calcular directorio de datos del usuario segun el entorno:
#   - Variable de entorno FINANZAS_DATA_DIR  → usarla siempre que este definida
#   - .exe compilado en Windows              → %APPDATA%\NexarFinanzas
#   - .exe compilado en Linux/Mac            → ~/.local/share/nexar-finanzas
#   - Desarrollo / portable                  → directorio del script si es escribible,
#                                              sino ~/.local/share/nexar-finanzas
if os.environ.get('FINANZAS_DATA_DIR'):
    BASE_DIR = os.environ['FINANZAS_DATA_DIR']
elif getattr(sys, 'frozen', False) and os.name == 'nt':
    BASE_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'NexarFinanzas')
elif getattr(sys, 'frozen', False):
    BASE_DIR = os.path.join(os.path.expanduser('~'), '.local', 'share', 'nexar-finanzas')
else:
    BASE_DIR = _APP_DIR if os.access(_APP_DIR, os.W_OK) else \
               os.path.join(os.path.expanduser('~'), '.local', 'share', 'nexar-finanzas')

if BASE_DIR != _APP_DIR:
    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'backups'), exist_ok=True)

# ─── Migración automática de datos (nexar-finanzas → nexar-finanzas) ─────

def _migrate_data_if_needed():
    """
    Si existen datos en ~/.local/share/nexar-finanzas/, migrar a nexar-finanzas/
    Solo ejecuta si BASE_DIR es 'nexar-finanzas' y no está ya migrado.
    """
    if 'nexar-finanzas' not in BASE_DIR:
        return  # No es necesario migrar si la ruta no es la nueva
    
    old_data_dir = os.path.join(
        os.path.expanduser('~'), '.local', 'share', 'nexar-finanzas'
    )
    
    # Si no existe el directorio viejo, no hay nada que migrar
    if not os.path.exists(old_data_dir):
        return
    
    # Marcar que ya se migró
    migration_marker = os.path.join(BASE_DIR, '.migrated_from_finanzas_hogar')
    if os.path.exists(migration_marker):
        return  # Ya se migró antes
    
    try:
        import shutil
        
        # Copiar database.db si existe
        old_db = os.path.join(old_data_dir, 'database.db')
        if os.path.exists(old_db) and not os.path.exists(os.path.join(BASE_DIR, 'database.db')):
            shutil.copy2(old_db, os.path.join(BASE_DIR, 'database.db'))
            logging.info(f"✓ Database migrada de {old_data_dir}")
        
        # Copiar backups si existen
        old_backups = os.path.join(old_data_dir, 'backups')
        if os.path.exists(old_backups):
            new_backups = os.path.join(BASE_DIR, 'backups')
            if not os.path.exists(new_backups):
                os.makedirs(new_backups)
            for backup_file in os.listdir(old_backups):
                src = os.path.join(old_backups, backup_file)
                dst = os.path.join(new_backups, backup_file)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
            logging.info(f"✓ Backups migrados de {old_data_dir}")
        
        # Crear marcador de migración
        with open(migration_marker, 'w') as f:
            f.write("Migración completada de nexar-finanzas a nexar-finanzas\n")
        
        logging.info("✓ Migración de datos completada exitosamente")
    except Exception as e:
        logging.error(f"⚠ Error durante migración de datos: {e}")


_migrate_data_if_needed()

DB_PATH = os.path.join(BASE_DIR, 'database.db')


# ─── Selección dinámica de puerto ─────────────────────────────

def _encontrar_puerto(preferido=5000):

    sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)

    try:
        sock.bind(('127.0.0.1', preferido))
        sock.close()
        return preferido
    except OSError:
        sock.close()

    sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 0))
    puerto_libre = sock.getsockname()[1]
    sock.close()

    logging.info(f"Puerto 5000 ocupado. Usando puerto alternativo: {puerto_libre}")
    return puerto_libre


# ─── Inicializar Flask ────────────────────────────────────────

app = Flask(
    __name__,
    template_folder=os.path.join(_INTERNAL_DIR, 'templates'),
    static_folder=os.path.join(_INTERNAL_DIR, 'static'),
)

app.secret_key = os.environ.get(
    'FLASK_SECRET_KEY',
    'NexarFinanzas_2026_SessionKey_Change_In_Prod_XK9Z'
)

app.config['DB_PATH'] = DB_PATH
app.config['BASE_DIR'] = BASE_DIR
app.config['APP_DIR'] = _APP_DIR  # FIX v1.10.2
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

APP_VERSION = '1.10.2'


# ─── Base de datos ────────────────────────────────────────────

from models import init_db
init_db(DB_PATH)


# ─── Rutas ────────────────────────────────────────────────────

from routes import register_routes
register_routes(app)


# ─── Backup automático ────────────────────────────────────────

import services as _svc
_svc.verificar_backup_automatico(DB_PATH, BASE_DIR)


# ─── Manejo de errores ────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404,
                           message="Página no encontrada"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', code=500,
                           message="Error interno del servidor"), 500


# ─── Variables globales para templates ────────────────────────

@app.context_processor
def inject_globals():
    from demo_limits import get_demo_status
    demo_info = get_demo_status(DB_PATH) if 'user_id' in session else {}

    return {
        'demo_info': demo_info,
        'app_version': APP_VERSION,
        'app_name': 'Nexar Finanzas',
        'license_mode': LICENSE_MODE
    }


# ─── Punto de entrada ─────────────────────────────────────────

if __name__ == '__main__':

    print("=" * 55)
    print(f"  💰 Nexar Finanzas v{APP_VERSION}")
    print("  Creado por Nexar Sistemas")
    print("=" * 55)

    # ── Verificación de licencia ──────────────────────────────
    print("  Verificando licencia...")

    _check_license()

    if LICENSE_MODE == "DEMO":
        print("  ⚠ Ejecutando en MODO DEMO")
    else:
        print("  ✔ Licencia válida")

    # ── Puerto ────────────────────────────────────────────────

    PORT = _encontrar_puerto(preferido=5000)
    URL = f'http://127.0.0.1:{PORT}'

    print(f"  Base de datos : {DB_PATH}")

    if PORT != 5000:
        print(f"  Puerto        : {PORT} (5000 ocupado)")
    else:
        print(f"  Puerto        : {PORT}")

    print("=" * 55)

    # ── Flask en hilo secundario ──────────────────────────────

    def _run_flask():
        app.run(
            debug=False,
            host='127.0.0.1',
            port=PORT,
            threaded=True,
            use_reloader=False,
        )

    flask_thread = threading.Thread(target=_run_flask, daemon=True)
    flask_thread.start()

    # Esperar que Flask levante

    print("  Iniciando servidor", end='', flush=True)

    for _ in range(20):
        try:
            s = _socket.create_connection(('127.0.0.1', PORT), timeout=0.5)
            s.close()
            print(" ✓")
            break
        except OSError:
            print(".", end='', flush=True)
            time.sleep(0.5)
    else:
        print("\n  [ERROR] El servidor Flask no respondió.")
        logging.critical("Flask no levantó en 10 segundos.")
        sys.exit(1)

    # ── Ventana nativa ────────────────────────────────────────

    _webview_ok = False

    try:

        import webview

        print("  Abriendo ventana nativa...")
        logging.info("Iniciando pywebview.")

        window = webview.create_window(
            title=f'Nexar Finanzas v{APP_VERSION}',
            url=URL,
            width=1280,
            height=800,
            min_size=(900, 600),
            resizable=True,
            text_select=False,
        )

        app.config['WEBVIEW_WINDOW'] = window
        webview.start(debug=False, http_server=False)

        _webview_ok = True

    except ImportError:

        logging.warning("pywebview no instalado — fallback al navegador.")
        print("  [AVISO] pywebview no disponible. Abriendo en navegador...")

    except Exception as e:

        logging.error(f"pywebview falló: {e}\n{traceback.format_exc()}")
        print(f"  [AVISO] pywebview falló ({e}). Abriendo en navegador...")

    # ── Fallback navegador ────────────────────────────────────

    if not _webview_ok:

        import webbrowser

        webbrowser.open(URL)

        print(f"  Navegador abierto en: {URL}")
        print("  Cerrá esta ventana para detener la app.")

        try:
            flask_thread.join()
        except KeyboardInterrupt:
            print("\n  Cerrando...")

    os._exit(0)