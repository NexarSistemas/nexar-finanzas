#!/usr/bin/env bash
set -euo pipefail

APP_NAME="NexarFinanzas"
APP_VERSION="${VERSION:-$(tr -d '[:space:]' < VERSION)}"
SPEC_FILE="build_scripts_macos/nexar_finanzas.spec"
VENV_DIR=".venv_build"
OUTPUT_DIR="release"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

[[ "$APP_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "ERROR: versión inválida: $APP_VERSION"; exit 1; }
[[ "$(uname -s)" == "Darwin" ]] || { echo "ERROR: este script solo puede ejecutarse en macOS"; exit 1; }
[[ "$(uname -m)" == "x86_64" ]] || { echo "ERROR: el build macOS MVP requiere un runner Intel x86_64"; exit 1; }
command -v ditto >/dev/null || { echo "ERROR: no se encontró ditto"; exit 1; }
command -v hdiutil >/dev/null || { echo "ERROR: no se encontró hdiutil"; exit 1; }
command -v lipo >/dev/null || { echo "ERROR: no se encontró lipo"; exit 1; }

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip pyinstaller
"$VENV_DIR/bin/pip" install -r requirements-build.txt

if [[ -z "${SUPABASE_URL:-}" || -z "${SUPABASE_ANON_KEY:-}" || -z "${SECRET_KEY:-}" ]]; then
  echo "ERROR: faltan SUPABASE_URL, SUPABASE_ANON_KEY o SECRET_KEY"
  exit 1
fi

cat > .env.finanzas <<EOF
LICENSE_PRODUCT=nexar-finanzas
SUPABASE_URL=${SUPABASE_URL}
SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
SECRET_KEY=${SECRET_KEY}
EOF

rm -rf build dist "$OUTPUT_DIR"
"$VENV_DIR/bin/python" -m PyInstaller "$SPEC_FILE" --noconfirm

APP_PATH="dist/${APP_NAME}.app"
[[ -d "$APP_PATH/Contents/MacOS" ]] || { echo "ERROR: PyInstaller no generó ${APP_NAME}.app"; exit 1; }
APP_EXECUTABLE="$APP_PATH/Contents/MacOS/$APP_NAME"
[[ -f "$APP_EXECUTABLE" ]] || { echo "ERROR: no se encontró el ejecutable macOS"; exit 1; }
[[ "$(lipo -archs "$APP_EXECUTABLE")" == "x86_64" ]] || {
  echo "ERROR: el ejecutable macOS no es exclusivamente x86_64"
  exit 1
}
mkdir -p "$OUTPUT_DIR"
cp -R "$APP_PATH" "$OUTPUT_DIR/"

ZIP_FILE="$OUTPUT_DIR/${APP_NAME}_v${APP_VERSION}_macos.zip"
DMG_FILE="$OUTPUT_DIR/${APP_NAME}_v${APP_VERSION}_macos.dmg"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_FILE"

DMG_SOURCE="$(mktemp -d)"
trap 'rm -rf "$DMG_SOURCE"' EXIT
cp -R "$APP_PATH" "$DMG_SOURCE/"
ln -s /Applications "$DMG_SOURCE/Applications"
hdiutil create -volname "Nexar Finanzas ${APP_VERSION}" -srcfolder "$DMG_SOURCE" -ov -format UDZO "$DMG_FILE"

(cd "$OUTPUT_DIR" && shasum -a 256 "${APP_NAME}_v${APP_VERSION}_macos.zip" "${APP_NAME}_v${APP_VERSION}_macos.dmg" > SHA256SUMS_macos.txt)
echo "Build macOS sin firma generado en $OUTPUT_DIR"
