#!/usr/bin/env bash
# build.sh - Script de build para Nexar Finanzas (Linux)
# Autor: Rolando Navarta
#
# Genera dos artefactos en la carpeta release/:
#   - NexarFinanzas_vX.Y.Z_portable_linux.tar.gz   (portable)
#   - NexarFinanzas_vX.Y.Z_linux_amd64.deb          (instalador Debian/Ubuntu)
#
# Uso:
#   Ejecutar desde la carpeta raiz del proyecto (donde esta app.py):
#       bash build_scripts_linux/build.sh
#
# Requisitos del sistema (instalados una sola vez):
#   sudo apt install fakeroot dpkg python3-gi python3-gi-cairo gir1.2-webkit2-4.1

set -euo pipefail

# ── Variables ─────────────────────────────────────────────────────────────────
APP_NAME="NexarFinanzas"
APP_DISPLAY="Nexar Finanzas"
APP_VERSION="1.10.5"
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

PYTHON=""
for cmd in python3 python3.12 python3.11 python3.10; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(sys.version_info.minor)")
        if [ "$VER" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}[ERROR] Python 3.10+ no encontrado.${NC}"
    echo -e "${RED}        sudo apt install python3.10${NC}"
    exit 1
fi

PY_VER=$("$PYTHON" --version)
echo -e "${GREEN}[OK] $PY_VER ($PYTHON)${NC}"

# ── 2. Entorno virtual + dependencias ────────────────────────────────────────
echo -e "${YELLOW}[2/5] Preparando entorno virtual...${NC}"

VENV_DIR=".venv_build"

# El venv necesita --system-site-packages para que pywebview acceda
# a python3-gi (bindings GTK del sistema, no instalables con pip)
if [ ! -d "$VENV_DIR" ]; then
    echo "      Creando entorno virtual en $VENV_DIR/ ..."
    "$PYTHON" -m venv --system-site-packages "$VENV_DIR"
else
    # Si el venv existente no tiene system-site-packages, recrearlo
    if ! grep -q "include-system-site-packages = true" "$VENV_DIR/pyvenv.cfg" 2>/dev/null; then
        echo "      Recreando venv con acceso a paquetes del sistema..."
        rm -rf "$VENV_DIR"
        "$PYTHON" -m venv --system-site-packages "$VENV_DIR"
    fi
fi

PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

# Verificar que python3-gi es accesible (necesario para ventana nativa)
if ! "$PYTHON" -c "import gi" &>/dev/null; then
    echo -e "${RED}[ERROR] python3-gi no encontrado. Instalalo con:${NC}"
    echo -e "${RED}        sudo apt install python3-gi python3-gi-cairo gir1.2-webkit2-4.1${NC}"
    exit 1
fi
echo "      [OK] python3-gi accesible (pywebview usara ventana nativa GTK)."

# Siempre instalar/actualizar PyInstaller
echo "      Instalando/actualizando PyInstaller..."
"$PIP" install --upgrade pyinstaller --quiet

# Siempre instalar dependencias del proyecto
if [ -f "requirements.txt" ]; then
    echo "      Instalando dependencias desde requirements.txt..."
    "$PIP" install -r requirements.txt --quiet
else
    echo -e "${YELLOW}      Sin requirements.txt -- instalando dependencias conocidas...${NC}"
    "$PIP" install flask werkzeug jinja2 requests cryptography pywebview --quiet
fi

# Verificar flask
if ! "$PYTHON" -c "import flask" &>/dev/null; then
    echo -e "${RED}[ERROR] Flask no se pudo instalar. Revisa requirements.txt o tu conexion.${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Dependencias y PyInstaller listos (venv: $VENV_DIR).${NC}"

# ── 3. Build con PyInstaller ──────────────────────────────────────────────────
echo -e "${YELLOW}[3/5] Compilando con PyInstaller...${NC}"

rm -rf build dist
"$PYTHON" -m PyInstaller "$SPEC_FILE" --noconfirm

echo -e "${GREEN}[OK] Build completado en dist/${APP_NAME}/${NC}"

# ── 4. Portable .tar.gz ───────────────────────────────────────────────────────
echo -e "${YELLOW}[4/5] Creando portable .tar.gz...${NC}"

mkdir -p "$OUTPUT_DIR"
PORTABLE_FILE="${OUTPUT_DIR}/${APP_NAME}_v${APP_VERSION}_portable_linux.tar.gz"

tar -czf "$PORTABLE_FILE" -C "dist" "$APP_NAME"
echo -e "${GREEN}[OK] Portable: $PORTABLE_FILE${NC}"

# ── 5. Paquete .deb ───────────────────────────────────────────────────────────
echo -e "${YELLOW}[5/5] Creando paquete .deb...${NC}"

DEB_DIR="/tmp/${APP_NAME}_deb_build"
DEB_INSTALL_DIR="${DEB_DIR}/opt/${APP_NAME}"
DEB_DESKTOP_DIR="${DEB_DIR}/usr/share/applications"
DEB_ICON_DIR="${DEB_DIR}/usr/share/icons/hicolor/256x256/apps"
DEB_BIN_DIR="${DEB_DIR}/usr/local/bin"
DEB_FILE="${OUTPUT_DIR}/${APP_NAME}_v${APP_VERSION}_linux_${DEB_ARCH}.deb"

rm -rf "$DEB_DIR"
mkdir -p "$DEB_INSTALL_DIR" "$DEB_DESKTOP_DIR" "$DEB_ICON_DIR" "$DEB_BIN_DIR"
mkdir -p "${DEB_DIR}/DEBIAN"

cp -r "${DIST_DIR}/." "$DEB_INSTALL_DIR/"

if [ -f "nexar_finanzas.png" ]; then
    cp nexar_finanzas.png "${DEB_ICON_DIR}/nexar-finanzas.png"
fi

DESKTOP_SRC="build_scripts_linux/nexar_finanzas.desktop"
if [ -f "$DESKTOP_SRC" ]; then
    cp "$DESKTOP_SRC" "${DEB_DESKTOP_DIR}/nexar-finanzas.desktop"
fi

cat > "${DEB_BIN_DIR}/nexar-finanzas" <<'EOF'
#!/bin/bash
exec /opt/NexarFinanzas/NexarFinanzas "$@"
EOF
chmod 755 "${DEB_BIN_DIR}/nexar-finanzas"

INSTALLED_KB=$(du -sk "$DEB_INSTALL_DIR" | cut -f1)

# La clave para usuarios no tecnicos: el campo Depends le dice a apt que
# instale automaticamente las librerias GTK/WebKit necesarias para
# la ventana nativa. El usuario solo hace doble clic en el .deb y listo.
DEB_DEPENDS="python3-gi, python3-gi-cairo, gir1.2-webkit2-4.1, libwebkit2gtk-4.1-0"

cat > "${DEB_DIR}/DEBIAN/control" <<EOF
Package: nexar-finanzas
Version: ${APP_VERSION}
Architecture: ${DEB_ARCH}
Maintainer: Nexar Sistemas <nexarsistemas@outlook.com.ar>
Installed-Size: ${INSTALLED_KB}
Depends: ${DEB_DEPENDS}
Description: Nexar Finanzas - Gestor de finanzas del hogar
 Aplicacion de escritorio para administrar las finanzas
 personales del hogar.
Homepage: https://github.com/NexarSistemas
Section: finance
Priority: optional
EOF

# postinst: permisos, cache de iconos y entrada de menu
cat > "${DEB_DIR}/DEBIAN/postinst" <<'EOF'
#!/bin/bash
set -e
chmod +x /opt/NexarFinanzas/NexarFinanzas
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database /usr/share/applications
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f /usr/share/icons/hicolor
fi
exit 0
EOF
chmod 755 "${DEB_DIR}/DEBIAN/postinst"

# postrm: limpiar al desinstalar
cat > "${DEB_DIR}/DEBIAN/postrm" <<'EOF'
#!/bin/bash
set -e
if [ "$1" = "remove" ]; then
    rm -rf /opt/NexarFinanzas
fi
exit 0
EOF
chmod 755 "${DEB_DIR}/DEBIAN/postrm"

if command -v fakeroot &>/dev/null; then
    fakeroot dpkg-deb --build "$DEB_DIR" "$DEB_FILE"
else
    dpkg-deb --build "$DEB_DIR" "$DEB_FILE"
fi

rm -rf "$DEB_DIR"
echo -e "${GREEN}[OK] Paquete .deb: $DEB_FILE${NC}"

# ── Checksums ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}Checksums SHA256:${NC}"
SHA256_FILE="${OUTPUT_DIR}/SHA256SUMS_linux.txt"
> "$SHA256_FILE"
for f in "${OUTPUT_DIR}/"*.tar.gz "${OUTPUT_DIR}/"*.deb; do
    [ -f "$f" ] || continue
    HASH=$(sha256sum "$f" | awk '{print $1}')
    LINE="$HASH  $(basename "$f")"
    echo "  $LINE"
    echo "$LINE" >> "$SHA256_FILE"
done

echo ""
echo -e "${CYAN}================================================${NC}"
echo -e "${GREEN}  Build completado en: ${OUTPUT_DIR}/          ${NC}"
echo -e "${CYAN}================================================${NC}"
echo ""
