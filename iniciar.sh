#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# iniciar_portable.sh — Nexar Finanzas 
# Lanzador portable para Linux / macOS
# Autor: Nexar Sistemas · 2026
#
# Uso:
#   chmod +x iniciar_portable.sh
#   ./iniciar_portable.sh
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_VERSION="1.10.5"
PORT="${PORT:-5000}"

echo ""
echo "================================================================"
echo "  Nexar Finanzas v${APP_VERSION} - Nexar Sistemas"
echo "  Modo Portable"
echo "================================================================"
echo ""

cd "$SCRIPT_DIR"

# Colores
GRN='\033[0;32m'; YEL='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GRN}[OK]${NC} $*"; }
warn() { echo -e "${YEL}[AVISO]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# ── 1. VERIFICAR PYTHON ───────────────────────────────────────────────────────
echo "[1/4] Verificando Python..."

PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    err "Python 3.10 o superior no encontrado."
    echo ""
    echo "  Instalalo con:"
    echo "    Ubuntu/Debian : sudo apt install python3 python3-pip"
    echo "    Fedora/RHEL   : sudo dnf install python3 python3-pip"
    echo "    Arch Linux    : sudo pacman -S python python-pip"
    echo "    macOS Homebrew: brew install python"
    echo "    Descarga      : https://www.python.org/downloads/"
    echo ""
    read -rp "Enter para salir..." _; exit 1
fi

PY_VER=$("$PYTHON" --version 2>&1 | awk '{print $2}')
ok "Python $PY_VER ($PYTHON)."

# ── 2. VERIFICAR PIP ──────────────────────────────────────────────────────────
echo "[2/4] Verificando pip..."

if ! "$PYTHON" -m pip --version &>/dev/null; then
    warn "pip no encontrado. Instalando..."
    if "$PYTHON" -m ensurepip --upgrade &>/dev/null 2>&1; then
        ok "pip instalado."
    else
        if   command -v apt-get &>/dev/null; then sudo apt-get install -y python3-pip &>/dev/null
        elif command -v dnf     &>/dev/null; then sudo dnf install -y python3-pip &>/dev/null
        elif command -v pacman  &>/dev/null; then sudo pacman -S --noconfirm python-pip &>/dev/null
        else err "No se pudo instalar pip. Instalalo manualmente: https://pip.pypa.io"; exit 1
        fi
    fi
fi

"$PYTHON" -m pip install --upgrade pip --quiet --disable-pip-version-check 2>/dev/null || true
ok "pip disponible."

# ── 3. INSTALAR DEPENDENCIAS ──────────────────────────────────────────────────
echo "[3/4] Verificando dependencias..."

_pip() { "$PYTHON" -m pip install "$@" --quiet --disable-pip-version-check 2>/dev/null || \
         "$PYTHON" -m pip install "$@" --quiet --disable-pip-version-check --user 2>/dev/null || true; }

echo "  Instalando paquetes del proyecto..."
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    _pip -r "$SCRIPT_DIR/requirements.txt"
else
    _pip flask requests
fi

# pywebview: en Linux necesita librerías del sistema (WebKit)
echo "  Verificando pywebview (ventana nativa)..."
if ! "$PYTHON" -c "import webview" &>/dev/null 2>&1; then
    echo "  Instalando pywebview..."

    # Dependencias de sistema para Linux
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y \
            python3-gi python3-gi-cairo \
            gir1.2-gtk-3.0 gir1.2-webkit2-4.0 \
            libgtk-3-0 \
            &>/dev/null 2>&1 || true
        # Intentar webkit2gtk-4.1 primero, luego 4.0 como fallback
        sudo apt-get install -y gir1.2-webkit2-4.1 &>/dev/null 2>&1 || \
        sudo apt-get install -y gir1.2-webkit2-4.0 &>/dev/null 2>&1 || true
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3-gobject webkit2gtk4.1 &>/dev/null 2>&1 || \
        sudo dnf install -y python3-gobject webkit2gtk3 &>/dev/null 2>&1 || true
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm python-gobject webkit2gtk &>/dev/null 2>&1 || true
    fi

    _pip pywebview

    if "$PYTHON" -c "import webview" &>/dev/null 2>&1; then
        ok "pywebview instalado."
    else
        warn "pywebview no disponible. La app usará el navegador del sistema."
    fi
else
    ok "pywebview ya disponible."
fi

# Verificar Flask mínimo
if ! "$PYTHON" -c "import flask" &>/dev/null 2>&1; then
    err "Flask no se pudo instalar. Verificá tu conexión a internet."
    exit 1
fi
ok "Dependencias listas."

# ── 4. INICIAR APLICACIÓN ─────────────────────────────────────────────────────
echo "[4/4] Iniciando aplicacion..."
echo ""
echo "  La app abrirá en una ventana propia."
echo "  Si no abre, ingresá manualmente: http://127.0.0.1:${PORT}"
echo ""
echo "================================================================"
echo ""

"$PYTHON" "$SCRIPT_DIR/app.py"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    err "La app terminó con error (código $EXIT_CODE)."
    echo "  Revisá: $SCRIPT_DIR/finanzas_error.log"
    echo ""
    read -rp "Enter para salir..." _
fi
