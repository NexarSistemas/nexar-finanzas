#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Uso: $0 <directorio-dist-o-paquete.deb>" >&2
    exit 2
fi

TARGET="$1"
TMP_DIR=""

cleanup() {
    if [ -n "$TMP_DIR" ]; then
        rm -rf "$TMP_DIR"
    fi
}
trap cleanup EXIT

SCAN_ROOT="$TARGET"
if [ -f "$TARGET" ]; then
    case "$TARGET" in
        *.deb)
            echo "[INFO] dpkg-deb --info"
            dpkg-deb --info "$TARGET"
            echo "[INFO] dpkg-deb -f Depends"
            DEPENDS="$(dpkg-deb -f "$TARGET" Depends)"
            echo "$DEPENDS"
            if [[ "$DEPENDS" == *"python3-gi"* || "$DEPENDS" == *"gir1.2-gtk-3.0"* || "$DEPENDS" == *"gir1.2-webkit2"* ]]; then
                echo "[ERROR] El paquete no debe depender de GTK/PyGObject como backend principal." >&2
                exit 1
            fi
            TMP_DIR="$(mktemp -d)"
            dpkg-deb -x "$TARGET" "$TMP_DIR"
            SCAN_ROOT="$TMP_DIR"
            ;;
        *)
            echo "[ERROR] Archivo no soportado: $TARGET" >&2
            exit 2
            ;;
    esac
fi

if [ ! -d "$SCAN_ROOT" ]; then
    echo "[ERROR] No existe el directorio a validar: $SCAN_ROOT" >&2
    exit 2
fi

INTERNAL_DIRS=()
while IFS= read -r -d '' dir; do
    INTERNAL_DIRS+=("$dir")
done < <(find "$SCAN_ROOT" -type d -name '_internal' -print0)

if [ "${#INTERNAL_DIRS[@]}" -eq 0 ]; then
    echo "[ERROR] No se encontro ningun directorio _internal en $SCAN_ROOT" >&2
    exit 1
fi

FOUND_ERROR=0
for internal in "${INTERNAL_DIRS[@]}"; do
    echo "[INFO] Validando backend Qt en $internal"

    if ! find "$internal" -path '*/PySide6/*' -print -quit | grep -q .; then
        echo "[ERROR] PySide6 no esta incluido en _internal." >&2
        FOUND_ERROR=1
    fi

    if ! find "$internal" \( -name 'QtWebEngineCore*' -o -name 'QtWebEngineWidgets*' \) -print -quit | grep -q .; then
        echo "[ERROR] Qt WebEngine no esta incluido en _internal." >&2
        FOUND_ERROR=1
    fi

    if find "$internal" \( -name 'libgtk-3.so*' -o -name 'libgdk-3.so*' -o -name 'libwebkit2gtk*.so*' -o -name 'libjavascriptcoregtk*.so*' \) -print -quit | grep -q .; then
        echo "[ERROR] El artefacto contiene bibliotecas GTK/WebKitGTK inesperadas:" >&2
        find "$internal" \( -name 'libgtk-3.so*' -o -name 'libgdk-3.so*' -o -name 'libwebkit2gtk*.so*' -o -name 'libjavascriptcoregtk*.so*' \) -print >&2
        FOUND_ERROR=1
    fi

    if [ -d "$internal/gi_typelibs" ] || [ -d "$internal/gio_modules" ]; then
        echo "[ERROR] El artefacto contiene typelibs/modulos GI privados; no debe inicializar GTK." >&2
        find "$internal" \( -path '*/gi_typelibs' -o -path '*/gio_modules' \) -print >&2
        FOUND_ERROR=1
    fi
done

if [ "$FOUND_ERROR" -ne 0 ]; then
    exit 1
fi

echo "[OK] Artefacto Linux validado para backend Qt/PySide6"
