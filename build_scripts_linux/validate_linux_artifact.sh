#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Uso: $0 <directorio-dist-o-paquete.deb>" >&2
    exit 2
fi

TARGET="$1"

FORBIDDEN_PATTERNS=(
    'libglib-2.0.so*'
    'libgio-2.0.so*'
    'libgobject-2.0.so*'
    'libgmodule-2.0.so*'
    'libffi.so*'
    'libsecret-1.so*'
    'libwebkit2gtk-4.1.so*'
    'libjavascriptcoregtk-4.1.so*'
)

REQUIRED_DEB_DEPENDS=(
    'gir1.2-gtk-3.0'
    'gir1.2-webkit2-4.1'
    'libgtk-3-0'
    'libwebkit2gtk-4.1-0'
    'libjavascriptcoregtk-4.1-0'
    'libgirepository-1.0-1'
    'libffi8'
    'libsecret-1-0'
)

TMP_DIR=""
LDD_OUTPUT=""
LDD_FAILURES=""
cleanup() {
    if [ -n "$TMP_DIR" ]; then
        rm -rf "$TMP_DIR"
    fi
    if [ -n "$LDD_OUTPUT" ]; then
        rm -f "$LDD_OUTPUT"
    fi
    if [ -n "$LDD_FAILURES" ]; then
        rm -f "$LDD_FAILURES"
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
            echo "[INFO] dpkg-deb --contents"
            dpkg-deb --contents "$TARGET"

            for package in "${REQUIRED_DEB_DEPENDS[@]}"; do
                if [[ "$DEPENDS" != *"$package"* ]]; then
                    echo "[ERROR] Falta dependencia Debian requerida: $package" >&2
                    exit 1
                fi
            done

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

FOUND_FORBIDDEN=0
for internal in "${INTERNAL_DIRS[@]}"; do
    echo "[INFO] Validando $internal"
    for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
        while IFS= read -r -d '' file; do
            echo "[ERROR] Biblioteca prohibida en artefacto: $file" >&2
            FOUND_FORBIDDEN=1
        done < <(find "$internal" -type f -name "$pattern" -print0)
    done

    if [ -d "$internal/gio_modules" ]; then
        echo "[ERROR] El artefacto contiene modulos GIO privados: $internal/gio_modules" >&2
        find "$internal/gio_modules" -mindepth 1 -maxdepth 1 -print >&2
        FOUND_FORBIDDEN=1
    fi
done

if [ "$FOUND_FORBIDDEN" -ne 0 ]; then
    exit 1
fi

echo "[INFO] Revisando ldd de ejecutable y extensiones nativas"
LDD_OUTPUT="$(mktemp)"
LDD_FAILURES="$(mktemp)"
while IFS= read -r -d '' native; do
    if ! ldd "$native" >> "$LDD_OUTPUT" 2>> "$LDD_FAILURES"; then
        echo "[WARN] ldd no pudo inspeccionar: $native" >&2
    fi
done < <(find "$SCAN_ROOT" -type f \( -name 'NexarFinanzas' -o -name '*.so' \) -print0)

if grep -E '_internal/.*/?(libglib-2\.0|libgio-2\.0|libgobject-2\.0|libgmodule-2\.0|libffi|libsecret-1|libwebkit2gtk-4\.1|libjavascriptcoregtk-4\.1)\.so' "$LDD_OUTPUT" >/dev/null; then
    echo "[ERROR] ldd resolvio bibliotecas prohibidas desde _internal:" >&2
    grep -E '_internal/.*/?(libglib-2\.0|libgio-2\.0|libgobject-2\.0|libgmodule-2\.0|libffi|libsecret-1|libwebkit2gtk-4\.1|libjavascriptcoregtk-4\.1)\.so' "$LDD_OUTPUT" >&2
    exit 1
fi

if [ -s "$LDD_FAILURES" ]; then
    cat "$LDD_FAILURES" >&2
fi

echo "[OK] Artefacto Linux sin copias privadas incompatibles de GLib/GIO/WebKit"
