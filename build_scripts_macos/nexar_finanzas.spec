# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))


def optional_data(package):
    try:
        return collect_data_files(package, include_py_files=True)
    except Exception:
        return []


def optional_submodules(package):
    try:
        return collect_submodules(package)
    except Exception:
        return []


datas = [
    (os.path.join(ROOT, 'templates'), 'templates'),
    (os.path.join(ROOT, 'licensing'), 'licensing'),
    (os.path.join(ROOT, 'services.py'), '.'),
    (os.path.join(ROOT, 'VERSION'), '.'),
    (os.path.join(ROOT, 'LICENSE'), '.'),
    (os.path.join(ROOT, 'nexar_finanzas.png'), '.'),
] + optional_data('services') + optional_data('webview')

env_file = os.path.join(ROOT, '.env.finanzas')
if os.path.exists(env_file):
    datas.append((env_file, '.'))

hiddenimports = [
    'flask', 'flask.templating', 'jinja2', 'werkzeug', 'werkzeug.serving',
    'requests', 'requests.adapters', 'urllib3', 'webview', 'webview.platforms.cocoa',
    'hmac', 'hashlib', 'base64',
    'licensing.hardware_id', 'licensing.license_manager', 'licensing.check_license',
    'licensing.crypto_verify', 'licensing.license_storage', 'licensing.license_api',
    'licensing.license_sdk', 'licensing.supabase_license_api', 'licensing.demo_state',
    'licensing.activation_gui', 'cryptography',
] + optional_submodules('nexar_licencias') + optional_submodules('services')

a = Analysis(
    [os.path.join(ROOT, 'app.py')],
    pathex=[ROOT], binaries=[], datas=datas, hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'cv2', 'test',
              'unittest', 'pydoc', 'webview.platforms.gtk', 'webview.platforms.qt',
              'webview.platforms.winforms', 'gi', 'PySide6', 'qtpy', 'clr', 'pythonnet'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='NexarFinanzas',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, target_arch=None, codesign_identity=None, entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='NexarFinanzas')
app = BUNDLE(
    coll,
    name='NexarFinanzas.app',
    bundle_identifier='com.nexarsistemas.nexarfinanzas',
    version=os.environ.get('VERSION', '0.0.0'),
    info_plist={'CFBundleDisplayName': 'Nexar Finanzas', 'NSHighResolutionCapable': True},
)
