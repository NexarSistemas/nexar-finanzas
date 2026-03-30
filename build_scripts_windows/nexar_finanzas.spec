# -*- mode: python ; coding: utf-8 -*-
# nexar_finanzas_windows.spec - PyInstaller spec para Nexar Finanzas (Windows)
#
# SPECPATH = carpeta del .spec (build_scripts_windows\)
# ROOT     = raiz del proyecto (un nivel arriba)

import os
import glob
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

# ── Archivos del proyecto ─────────────────────────────────────────────────────
added_files = [
    (os.path.join(ROOT, 'templates'),          'templates'),
    (os.path.join(ROOT, 'licensing'),          'licensing'),
    (os.path.join(ROOT, 'VERSION'),            '.'),
    (os.path.join(ROOT, 'LICENSE'),            '.'),
    (os.path.join(ROOT, 'nexar_finanzas.ico'), '.'),
    (os.path.join(ROOT, 'nexar_finanzas.png'), '.'),
]

# pywebview necesita sus archivos JS/HTML internos para renderizar la ventana
try:
    added_files += collect_data_files('webview')
except Exception:
    pass

# pythonnet necesita sus archivos de datos internos (clases .NET)
try:
    added_files += collect_data_files('pythonnet')
except Exception:
    pass

# ── Binaries: DLLs de pythonnet/.NET ────────────────────────────────────────
# pythonnet necesita las DLLs de .NET Runtime empaquetadas dentro del .exe.
# collect_dynamic_libs a veces falla silenciosamente, por eso buscamos
# manualmente en el venv las DLLs conocidas como respaldo.
binaries = []

# Metodo 1: hook automatico (puede fallar silenciosamente)
try:
    from PyInstaller.utils.hooks import collect_dynamic_libs
    binaries += collect_dynamic_libs('pythonnet')
except Exception:
    pass

# Metodo 2: busqueda manual de DLLs de pythonnet en el venv
# Cubre el caso en que el metodo 1 no encuentra nada
_venv_site = os.path.join(ROOT, '.venv_build', 'Lib', 'site-packages')
for _pattern in ['Python.Runtime.dll', 'Python.Runtime.*.dll', 'clr*.pyd']:
    for _dll in glob.glob(os.path.join(_venv_site, 'pythonnet', _pattern)):
        binaries.append((_dll, '.'))
    for _dll in glob.glob(os.path.join(_venv_site, _pattern)):
        binaries.append((_dll, '.'))

# ── Hidden imports ────────────────────────────────────────────────────────────
hidden_imports = [
    # Flask y dependencias web
    'flask',
    'flask.templating',
    'flask.cli',
    'jinja2',
    'jinja2.ext',
    'werkzeug',
    'werkzeug.serving',
    'werkzeug.routing',
    'werkzeug.middleware',
    # HTTP
    'requests',
    'requests.adapters',
    'urllib3',
    'urllib3.util',
    # pywebview y backend Windows (WinForms + WebView2)
    'webview',
    'webview.platforms.winforms',
    # pythonnet (clr) para WinForms — necesario para ventana nativa
    'clr',
    'clr._extras',
    'System',
    'System.Windows.Forms',
    'System.Threading',
    'System.Runtime.InteropServices',
    # stdlib usados por la app
    'hmac',
    'hashlib',
    'base64',
    'ctypes',
    'ctypes.wintypes',
    # Modulos de licenciamiento
    'licensing.hardware_id',
    'licensing.license_manager',
    'licensing.check_license',
    'licensing.crypto_verify',
    'licensing.license_storage',
    'licensing.license_api',
    'licensing.demo_state',
    'licensing.activation_gui',
    # Criptografia
    'cryptography',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.primitives.asymmetric',
    'cryptography.hazmat.primitives.hashes',
    'cryptography.hazmat.primitives.serialization',
    'cryptography.hazmat.backends',
]

a = Analysis(
    [os.path.join(ROOT, 'app.py')],
    pathex=[ROOT],
    binaries=binaries,
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'test',
        'unittest',
        'pydoc',
        # Modulos exclusivos de Linux — no deben incluirse en el build de Windows
        'webview.platforms.gtk',
        'webview.platforms.qt',
        'gi',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NexarFinanzas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                  # sin ventana de consola negra
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, 'nexar_finanzas.ico'),
    version_file=os.path.join(SPECPATH, 'version_info.txt'),
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NexarFinanzas',
)
