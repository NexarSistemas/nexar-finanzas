#!/usr/bin/env bash
set -euo pipefail

# ── Variables ─────────────────────────────────────────────────────────────────
APP_NAME="NexarFinanzas"
APP_DISPLAY="Nexar Finanzas"

# 🔥 MEJORA EN VERSIONADO: Limpieza absoluta
if [ -n "${VERSION:-}" ]; then
    APP_VERSION=$(echo "$VERSION" | tr -d '[:space:]')
    echo -e "\033[0;32m[OK] VERSION desde CI: ${APP_VERSION}\033[0m"
elif [ -f "VERSION" ]; then
    APP_VERSION=$(tr -d '[:space:]' < VERSION)
    echo -e "\033[0;32m[OK] VERSION desde archivo: ${APP_VERSION}\033[0m"
else
    echo -e "\033[0;31m[ERROR] No se encontró el archivo VERSION\033[0m"
    exit 1
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

# ── 2. Entorno virtual (OPTIMIZADO) ───────────────────────────────────────────
echo -e "${YELLOW}[2/5] Preparando entorno virtual...${NC}"
VENV_DIR=".venv_build"

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${CYAN}Creando entorno nuevo...${NC}"
    "$PYTHON" -m venv "$VENV_DIR"
    # Solo instalamos si el entorno es nuevo
    "$VENV_DIR/bin/pip" install --upgrade pip pyinstaller
    if [ -f "requirements.txt" ]; then
        "$VENV_DIR/bin/pip" install -r requirements.txt
    fi
else
    echo -e "${GREEN}[INFO] Usando entorno existente para ahorrar tiempo.${NC}"
fi

PYTHON="$VENV_DIR/bin/python"

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_ANON_KEY:-}" ] || [ -z "${SECRET_KEY:-}" ]; then
    echo -e "${RED}[ERROR] Faltan SUPABASE_URL, SUPABASE_ANON_KEY o SECRET_KEY para empaquetar licencias${NC}"
    exit 1
fi

cat > .env.finanzas <<EOF
LICENSE_PRODUCT=nexar-finanzas
SUPABASE_URL=${SUPABASE_URL}
SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
SECRET_KEY=${SECRET_KEY}
EOF

echo -e "${GREEN}[OK] Configuracion publica de licencias generada${NC}"

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
mkdir -p "${DEB_DIR}/usr/local/bin"
mkdir -p "${DEB_DIR}/usr/share/applications"
mkdir -p "${DEB_DIR}/usr/share/pixmaps"

cp -r "${DIST_DIR}/." "$DEB_INSTALL_DIR/"

if [ -f "${DEB_INSTALL_DIR}/_internal/nexar_finanzas.png" ]; then
    cp "${DEB_INSTALL_DIR}/_internal/nexar_finanzas.png" "${DEB_DIR}/usr/share/pixmaps/nexar-finanzas.png"
else
    echo -e "${YELLOW}[WARN] No se encontró ícono nexar_finanzas.png; el .deb se generará sin ícono de menú.${NC}"
fi

if [ -f "build_scripts_linux/nexar_finanzas.desktop" ]; then
    cp "build_scripts_linux/nexar_finanzas.desktop" "${DEB_DIR}/usr/share/applications/nexar-finanzas.desktop"
else
    cat > "${DEB_DIR}/usr/share/applications/nexar-finanzas.desktop" <<DESKTOP_EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Nexar Finanzas
Comment=Gestor de finanzas del hogar
Exec=/usr/local/bin/nexarfinanzas
Path=/opt/NexarFinanzas
Icon=nexar-finanzas
Terminal=false
Categories=Finance;Office;
Keywords=finanzas;dinero;presupuesto;hogar;
StartupNotify=true
StartupWMClass=NexarFinanzas
DESKTOP_EOF
fi

cat > "${DEB_DIR}/usr/local/bin/nexarfinanzas" <<'WRAPPER_EOF'
#!/usr/bin/env bash
unset GSETTINGS_SCHEMA_DIR

if [ -n "${XDG_DATA_DIRS:-}" ]; then
    export XDG_DATA_DIRS="/usr/local/share:/usr/share:${XDG_DATA_DIRS}"
else
    export XDG_DATA_DIRS="/usr/local/share:/usr/share"
fi

cd /opt/NexarFinanzas
exec ./NexarFinanzas "$@"
WRAPPER_EOF

chmod +x "${DEB_DIR}/usr/local/bin/nexarfinanzas"
chmod +x "${DEB_INSTALL_DIR}/NexarFinanzas"

INSTALLED_KB=$(du -sk "$DEB_INSTALL_DIR" "${DEB_DIR}/usr" | awk '{total += $1} END {print total}')

cat > "${DEB_DIR}/DEBIAN/control" <<EOF
Package: nexar-finanzas
Version: ${APP_VERSION}
Architecture: ${DEB_ARCH}
Maintainer: Nexar Sistemas
Installed-Size: ${INSTALLED_KB}
Depends: libegl1, libgl1, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxkbcommon-x11-0
Section: misc
Priority: optional
Description: Nexar Finanzas
 Gestor de finanzas del hogar.
EOF

cat > "${DEB_DIR}/DEBIAN/postinst" <<'POSTINST_EOF'
#!/usr/bin/env bash
set -e

chmod +x /usr/local/bin/nexarfinanzas
chmod +x /opt/NexarFinanzas/NexarFinanzas
chmod -R a+rX /opt/NexarFinanzas

update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache /usr/share/pixmaps 2>/dev/null || true

echo ""
echo "Nexar Finanzas instalado correctamente."
echo "Ejecutar: nexarfinanzas"
echo "O buscar 'Nexar Finanzas' en el menú de apps."

exit 0
POSTINST_EOF
chmod +x "${DEB_DIR}/DEBIAN/postinst"

cat > "${DEB_DIR}/DEBIAN/postrm" <<'POSTRM_EOF'
#!/usr/bin/env bash
set -e
update-desktop-database /usr/share/applications 2>/dev/null || true
exit 0
POSTRM_EOF
chmod +x "${DEB_DIR}/DEBIAN/postrm"

dpkg-deb --build "$DEB_DIR" "$DEB_FILE"

rm -rf "$DEB_DIR"

echo -e "${GREEN}[OK] $DEB_FILE${NC}"

# ── SHA256 ───────────────────────────────────────────────────────────────────
echo -e "${CYAN}Checksums:${NC}"

cd "$OUTPUT_DIR"
sha256sum * > SHA256SUMS_linux.txt

echo -e "${GREEN}Build completado${NC}"
