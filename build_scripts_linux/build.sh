#!/usr/bin/env bash
set -euo pipefail

# ── Variables ─────────────────────────────────────────────────────────────────
APP_NAME="NexarFinanzas"
APP_DISPLAY="Nexar Finanzas"

# 🔥 VERSION DINÁMICA (FIX)
if [ -z "${VERSION:-}" ]; then
    if [ -z "${VERSION:-}" ]; then
    echo -e "\033[1;33m[WARN] VERSION no definida, usando ${APP_VERSION}\033[0m"
else
    APP_VERSION="$VERSION"
    echo -e "\033[0;32m[OK] VERSION desde CI: ${APP_VERSION}\033[0m"
fi

DEB_ARCH="amd64"
SPEC_FILE="build_scripts_linux/nexar_finanzas.spec"
DIST_DIR="dist/${APP_NAME}"
OUTPUT_DIR="release"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ── Ir a la raiz del proyecto ─────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo -e "${CYAN}Directorio de trabajo: $PROJECT_ROOT${NC}"
echo ""
echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}  ${APP_DISPLAY} v${APP_VERSION} - Build Linux   ${NC}"
echo -e "${CYAN}================================================${NC}"
echo ""

# ── 1. Detectar Python 3.10+ ─────────────────────────────────────────────────
echo -e "${YELLOW}[1/5] Buscando Python 3.10+...${NC}"

    if command -v python3 &>/dev/null; then
        PYTHON="python3"
    else
        echo -e "${RED}[ERROR] python3 no encontrado${NC}"
        exit 1
    fi

PY_VER=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

echo -e "${GREEN}[OK] Python $PY_VER${NC}"

# ── 2. Entorno virtual ────────────────────────────────────────────────────────
echo -e "${YELLOW}[2/5] Preparando entorno virtual...${NC}"

VENV_DIR=".venv_build"

if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON" -m venv --system-site-packages "$VENV_DIR"
fi

PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

"$PIP" install --upgrade pyinstaller --quiet

if [ -f "requirements.txt" ]; then
    "$PIP" install -r requirements.txt --quiet
fi

echo -e "${GREEN}[OK] Dependencias listas${NC}"

# ── 3. Build ──────────────────────────────────────────────────────────────────
echo -e "${YELLOW}[3/5] Compilando...${NC}"

rm -rf build dist
"$PYTHON" -m PyInstaller "$SPEC_FILE" --noconfirm

echo -e "${GREEN}[OK] Build listo${NC}"

# ── 4. Portable ───────────────────────────────────────────────────────────────
echo -e "${YELLOW}[4/5] Creando portable...${NC}"

mkdir -p "$OUTPUT_DIR"

PORTABLE_FILE="${OUTPUT_DIR}/${APP_NAME}_v${APP_VERSION}_portable_linux.tar.gz"

tar -czf "$PORTABLE_FILE" -C "dist" "$APP_NAME"

echo -e "${GREEN}[OK] $PORTABLE_FILE${NC}"

# ── 5. .deb ───────────────────────────────────────────────────────────────────
echo -e "${YELLOW}[5/5] Creando .deb...${NC}"

DEB_DIR="/tmp/${APP_NAME}_deb_build"
DEB_INSTALL_DIR="${DEB_DIR}/opt/${APP_NAME}"
DEB_FILE="${OUTPUT_DIR}/${APP_NAME}_v${APP_VERSION}_linux_${DEB_ARCH}.deb"

rm -rf "$DEB_DIR"
mkdir -p "$DEB_INSTALL_DIR" "${DEB_DIR}/DEBIAN"

cp -r "${DIST_DIR}/." "$DEB_INSTALL_DIR/"

INSTALLED_KB=$(du -sk "$DEB_INSTALL_DIR" | cut -f1)

cat > "${DEB_DIR}/DEBIAN/control" <<EOF
Package: nexar-finanzas
Version: ${APP_VERSION}
Architecture: ${DEB_ARCH}
Maintainer: Nexar Sistemas
Installed-Size: ${INSTALLED_KB}
Description: Nexar Finanzas
EOF

dpkg-deb --build "$DEB_DIR" "$DEB_FILE"

rm -rf "$DEB_DIR"

echo -e "${GREEN}[OK] $DEB_FILE${NC}"

# ── SHA256 ───────────────────────────────────────────────────────────────────
echo -e "${CYAN}Checksums:${NC}"

cd "$OUTPUT_DIR"
sha256sum * > SHA256SUMS_linux.txt

echo -e "${GREEN}Build completado${NC}"