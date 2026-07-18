# -*- mode: python ; coding: utf-8 -*-
# nexar_finanzas.spec - PyInstaller spec para Nexar Finanzas (Linux)
#
# SPECPATH = carpeta del .spec (build_scripts_linux/)
# ROOT     = raiz del proyecto (un nivel arriba)

import fnmatch
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))


def collect_optional_submodules(package):
    try:
        return collect_submodules(package)
    except Exception:
        return []


LINUX_SYSTEM_LIBRARY_PATTERNS = (
    # GLib/GIO/GObject and util-linux closure must come from the target system.
    'libglib-2.0.so*',
    'libgio-2.0.so*',
    'libgobject-2.0.so*',
    'libgmodule-2.0.so*',
    'libffi.so*',
    'libmount.so*',
    'libblkid.so*',
    'libselinux.so*',
    'libpcre2-8.so*',
    'libzstd.so*',
    'liblzma.so*',
    'libsystemd.so*',
    'libudev.so*',
    # GTK/WebKitGTK native stack is declared as Debian dependencies.
    'libsecret-1.so*',
    'libgtk-3.so*',
    'libgdk-3.so*',
    'libgdk_pixbuf-2.0.so*',
    'libgirepository-1.0.so*',
    'libpango*.so*',
    'libatk*.so*',
    'libatspi.so*',
    'libcairo*.so*',
    'libwebkit2gtk-4.1.so*',
    'libjavascriptcoregtk-4.1.so*',
)


def _toc_entry_paths(entry):
    if isinstance(entry, (tuple, list)):
        return [str(value) for value in entry[:2] if value]
    return [str(entry)]


def _is_system_gio_module(path):
    normalized = path.replace('\\', '/')
    return (
        '/gio_modules/' in normalized
        or normalized.startswith('gio_modules/')
        or '/gdk-pixbuf/loaders/' in normalized
        or normalized.startswith('gdk-pixbuf/loaders/')
        or '/gi_typelibs/' in normalized
        or normalized.startswith('gi_typelibs/')
    )


def _is_linux_system_library(path):
    basename = os.path.basename(path)
    return any(fnmatch.fnmatchcase(basename, pattern) for pattern in LINUX_SYSTEM_LIBRARY_PATTERNS)


def _keep_linux_binary(entry):
    paths = _toc_entry_paths(entry)
    return not any(_is_linux_system_library(path) or _is_system_gio_module(path) for path in paths)


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
    # webview en Linux usa GTK o Qt según la plataforma
    'webview',
    'webview.platforms.gtk',
    'webview.platforms.qt',
    'gi',
    'gi.repository.Gdk',
    'gi.repository.GLib',
    'gi.repository.Gtk',
    'gi.repository.WebKit2',
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
        'clr',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

original_binary_count = len(a.binaries)
a.binaries = [entry for entry in a.binaries if _keep_linux_binary(entry)]
removed_binary_count = original_binary_count - len(a.binaries)
if removed_binary_count:
    print(
        "Excluidas librerias nativas del sistema Linux/GIO del bundle: "
        f"{removed_binary_count}"
    )

original_data_count = len(a.datas)
a.datas = [entry for entry in a.datas if _keep_linux_binary(entry)]
removed_data_count = original_data_count - len(a.datas)
if removed_data_count:
    print(
        "Excluidos datos/modulos GIO del sistema Linux del bundle: "
        f"{removed_data_count}"
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
