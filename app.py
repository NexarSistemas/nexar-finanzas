# -*- coding: utf-8 -*-
"""
app.py
Punto de entrada principal — Finanzas del Hogar v1.6.0
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

# ─── Log de errores a archivo ─────────────────────────────────────────────────
def _setup_logging():
    # Prioridad de ubicacion del log:
    # 1. Directorio del .exe (PyInstaller)
    # 2. ~/.local/share/finanzas-hogar/ (instalacion .deb, usuario sin permisos en /opt)
    # 3. Directorio del script (modo desarrollo)
    if getattr(sys, 'frozen', False):
        log_dir = os.path.dirname(sys.executable)
    else:
        # Verificar si el directorio del script es escribible
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if os.access(script_dir, os.W_OK):
            log_dir = script_dir
        else:
            # Fallback al directorio de datos del usuario
            log_dir = os.path.join(
                os.environ.get('HOME', os.path.expanduser('~')),
                '.local', 'share', 'finanzas-hogar'
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
        # Ultimo recurso: log solo en consola
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
        )
        log_path = '(consola)'
    return log_path

_LOG_PATH = _setup_logging()

# ─── Rutas del sistema (portable + PyInstaller frozen) ────────────────────────

def _get_app_dir() -> str:
    """Directorio del .exe o del script según el modo de ejecución."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _get_internal_dir() -> str:
    """Directorio de recursos (templates). En frozen apunta a _MEIPASS."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

_APP_DIR      = _get_app_dir()
_INTERNAL_DIR = _get_internal_dir()

# Permite redirigir datos a otro directorio via variable de entorno
BASE_DIR = os.environ.get('FINANZAS_DATA_DIR', _APP_DIR)

if BASE_DIR != _APP_DIR:
    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'backups'), exist_ok=True)

DB_PATH = os.path.join(BASE_DIR, 'database.db')

# ─── Liberar puerto si quedó ocupado ──────────────────────────────────────────
def _liberar_puerto(puerto: int = 5000):
    import subprocess, platform, signal

    sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    sock.settimeout(0.5)
    en_uso = sock.connect_ex(('127.0.0.1', puerto)) == 0
    sock.close()
    if not en_uso:
        return

    print(f"  ⚠ Puerto {puerto} ocupado. Liberando proceso anterior…")
    sistema = platform.system()
    try:
        if sistema == 'Windows':
            resultado = subprocess.run(
                ['netstat', '-ano'], capture_output=True, text=True, timeout=5
            )
            for linea in resultado.stdout.splitlines():
                if f':{puerto}' in linea and 'LISTEN' in linea:
                    pid = linea.split()[-1]
                    subprocess.run(['taskkill', '/F', '/PID', pid],
                                   capture_output=True, timeout=3)
                    print(f"  ✓ Proceso {pid} terminado.")
                    break
        else:
            pids = []
            for cmd in [['fuser', f'{puerto}/tcp'], ['lsof', '-ti', f'tcp:{puerto}']]:
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    pids = r.stdout.strip().split()
                    if pids:
                        break
                except FileNotFoundError:
                    continue
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    print(f"  ✓ Proceso {pid} terminado.")
                except (ProcessLookupError, ValueError):
                    pass
        time.sleep(0.8)
    except Exception as e:
        logging.warning(f"No se pudo liberar el puerto: {e}")

_liberar_puerto(5000)

# ─── Inicializar Flask ────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=os.path.join(_INTERNAL_DIR, 'templates'),
)

app.secret_key = os.environ.get(
    'FLASK_SECRET_KEY',
    'FinanzasHogar_2026_SessionKey_Change_In_Prod_XK9Z'
)

app.config['DB_PATH']  = DB_PATH
app.config['BASE_DIR'] = BASE_DIR
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

APP_VERSION = '1.6.0'

# ─── Base de datos ────────────────────────────────────────────────────────────
from models import init_db
init_db(DB_PATH)

# ─── Rutas ────────────────────────────────────────────────────────────────────
from routes import register_routes
register_routes(app)

# ─── Backup automático ────────────────────────────────────────────────────────
import services as _svc
_svc.verificar_backup_automatico(DB_PATH, BASE_DIR)

# ─── Manejadores de error ─────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404,
                           message="Página no encontrada"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', code=500,
                           message="Error interno del servidor"), 500

# ─── Variables globales en templates ──────────────────────────────────────────
@app.context_processor
def inject_globals():
    from demo_limits import get_demo_status
    demo_info = get_demo_status(DB_PATH) if 'user_id' in session else {}
    return {
        'demo_info':   demo_info,
        'app_version': APP_VERSION,
        'app_name':    'Finanzas del Hogar',
    }

# ─── Punto de entrada ─────────────────────────────────────────────────────────
if __name__ == '__main__':

    PORT = 5000
    URL  = f'http://127.0.0.1:{PORT}'

    print("=" * 55)
    print(f"  💰 Finanzas del Hogar v{APP_VERSION}")
    print("  Creado por Rolando Navarta")
    print("=" * 55)
    print(f"  Base de datos: {DB_PATH}")
    print("=" * 55)

    # ── Flask en hilo secundario ──────────────────────────────────────────────
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

    # Esperar a que Flask levante (máx 10 segundos)
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

    # ── Intentar pywebview — ventana nativa sin navegador ────────────────────
    _webview_ok = False
    try:
        import webview
        print("  Abriendo ventana nativa...")
        logging.info("Iniciando pywebview.")

        window = webview.create_window(
            title       = f'Finanzas del Hogar v{APP_VERSION}',
            url         = URL,
            width       = 1280,
            height      = 800,
            min_size    = (900, 600),
            resizable   = True,
            text_select = False,
        )
        # Guardar referencia global para poder cerrar la ventana desde routes
        app.config['WEBVIEW_WINDOW'] = window

        # Bloquea hasta que el usuario cierra la ventana
        webview.start(debug=False, http_server=False)
        _webview_ok = True

    except ImportError:
        logging.warning("pywebview no instalado — fallback al navegador.")
        print("  [AVISO] pywebview no disponible. Abriendo en navegador...")

    except Exception as e:
        logging.error(f"pywebview falló: {e}\n{traceback.format_exc()}")
        print(f"  [AVISO] pywebview falló ({e}). Abriendo en navegador...")

    # ── Fallback al navegador — SOLO si pywebview falló ──────────────────────
    if not _webview_ok:
        import webbrowser
        webbrowser.open(URL)
        print(f"  Navegador abierto en: {URL}")
        print("  Cerrá esta ventana para detener la app.")
        print("  (o presioná Ctrl+C)")
        try:
            flask_thread.join()
        except KeyboardInterrupt:
            print("\n  Cerrando...")

    os._exit(0)
