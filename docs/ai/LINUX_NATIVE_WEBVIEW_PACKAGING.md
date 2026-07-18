# Linux native webview packaging

## Causa raiz

El build Linux usa PyInstaller con `--system-site-packages` para que el entorno
de build vea PyGObject y los typelibs de GTK/WebKitGTK. Desde `v1.10.14` el spec
tambien declara imports explicitos de `gi.repository.*` para habilitar la ventana
nativa de pywebview.

Ese flujo es correcto para empaquetar el modulo Python `gi`, pero puede hacer que
PyInstaller recoja copias privadas del stack nativo GLib/GIO/GObject/libffi y
modulos `gio_modules` del sistema de build. En una maquina limpia esas copias se
cargan antes que las bibliotecas del sistema instaladas por APT y pueden mezclarse
con WebKitGTK/JavascriptCoreGTK de `/usr/lib`, provocando errores ABI como
simbolos faltantes en `libsecret-1.so.0` o `libjavascriptcoregtk-4.1.so.0`.

## Regla de empaquetado

El `.deb` debe incluir Python embebido, Flask, pywebview, PyGObject como modulo
Python, SDK de licencias, templates, static y recursos propios.

El `.deb` no debe incluir copias privadas de estas bibliotecas nativas:

- `libglib-2.0.so*`
- `libgio-2.0.so*`
- `libgobject-2.0.so*`
- `libgmodule-2.0.so*`
- `libffi.so*`
- `libsecret-1.so*`
- `libwebkit2gtk-4.1.so*`
- `libjavascriptcoregtk-4.1.so*`
- `_internal/gio_modules/*`

GTK, GLib, GIO, WebKitGTK, JavaScriptCoreGTK, libsecret y typelibs se resuelven
desde paquetes Debian instalados por APT.

## Dependencias Debian

El control del `.deb` declara dependencias graficas nativas, sin pedir al usuario
que instale Python ni pip:

- `gir1.2-gtk-3.0`
- `gir1.2-webkit2-4.1`
- `libgtk-3-0`
- `libwebkit2gtk-4.1-0`
- `libjavascriptcoregtk-4.1-0`
- `libgirepository-1.0-1`
- `libffi8`
- `libsecret-1-0`
- bibliotecas X11/OpenGL requeridas por GTK/WebKitGTK

APT debe resolver e instalar automaticamente esas dependencias al instalar el
paquete con `apt install ./NexarFinanzas_vX.Y.Z_linux_amd64.deb`.

## Validacion automatica

`build_scripts_linux/validate_linux_artifact.sh` falla si el directorio `dist`
o el `.deb` contienen bibliotecas prohibidas o `gio_modules` privados. Para
paquetes `.deb`, tambien imprime y valida:

- `dpkg-deb --info`
- `dpkg-deb --contents`
- `dpkg-deb -f ... Depends`
- `find` sobre `_internal`
- `ldd` sobre el ejecutable y extensiones `.so`

## Base de build y matriz

El workflow Linux usa `ubuntu-24.04`, que es la base mas antigua soportada para
el paquete WebKitGTK 4.1 en este proyecto.

Matriz requerida antes de publicar release:

| Plataforma | Instalacion limpia | Terminal | Menu | pywebview | X11 | Wayland | Actualizacion v1.13.0 | Datos locales | Reinstalacion |
|---|---|---|---|---|---|---|---|---|---|
| Ubuntu 24.04 | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) |
| Ubuntu posterior disponible | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) |
| Debian estable | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) | TODO(confirmar) |

No crear tag ni release hasta validar el `.deb` real en esos entornos.
