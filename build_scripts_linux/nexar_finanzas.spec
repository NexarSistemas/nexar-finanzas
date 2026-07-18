# -*- mode: python ; coding: utf-8 -*-
# nexar_finanzas.spec - PyInstaller spec para Nexar Finanzas (Linux)
#
# SPECPATH = carpeta del .spec (build_scripts_linux/)
# ROOT     = raiz del proyecto (un nivel arriba)

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))


def collect_optional_submodules(package):
    try:
        return collect_submodules(package)
    except Exception:
        return []


added_files = [
    (os.path.join(ROOT, 'templates'),          'templates'),
    (os.path.join(ROOT, 'licensing'),          'licensing'),
    (os.path.join(ROOT, 'services.py'),        '.'),
    (os.path.join(ROOT, 'VERSION'),            '.'),
    (os.path.join(ROOT, 'LICENSE'),            '.'),
    (os.path.join(ROOT, 'nexar_finanzas.png'), '.'),
    # En Linux no se incluye el .ico (es de Windows)
]

try:
    added_files += collect_data_files('services', include_py_files=True)
except Exception:
    pass

env_file = os.path.join(ROOT, '.env.finanzas')
if os.path.exists(env_file):
    added_files.append((env_file, '.'))

hidden_imports = [
    'flask',
    'flask.templating',
    'jinja2',
    'jinja2.ext',
    'werkzeug',
    'werkzeug.serving',
    'werkzeug.routing',
    'requests',
    'requests.adapters',
    'urllib3',
    # pywebview en Linux usa Qt/PySide6 como backend principal.
    'webview',
    'webview.platforms.qt',
    'qtpy',
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',
    'PySide6.QtWebChannel',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'hmac',
    'hashlib',
    'base64',
    'licensing.hardware_id',
    'licensing.license_manager',
    'licensing.check_license',
    'licensing.crypto_verify',
    'licensing.license_storage',
    'licensing.license_api',
    'licensing.license_sdk',
    'licensing.supabase_license_api',
    'licensing.demo_state',
    'licensing.activation_gui',
    'cryptography',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.primitives.asymmetric',
    'cryptography.hazmat.primitives.hashes',
    'cryptography.hazmat.primitives.serialization',
    'cryptography.hazmat.backends',
] + collect_optional_submodules('nexar_licencias') + collect_optional_submodules('services')

a = Analysis(
    [os.path.join(ROOT, 'app.py')],
    pathex=[ROOT],
    binaries=[],
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
        # módulos exclusivos de Windows
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        # GTK/WebKitGTK no es backend principal en Linux
        'webview.platforms.gtk',
        'gi',
        'clr',
        'pythonnet',
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
    strip=True,       # strip reduce el tamaño del binario en Linux
    upx=True,
    console=False,    # sin ventana de terminal
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # En Linux no hay icon= ni version_file=
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name='NexarFinanzas',
)
