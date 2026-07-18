# Linux Qt webview packaging

## Causa raiz

En Linux, Nexar Finanzas llamaba `webview.start()` sin seleccionar backend. En
ese escenario pywebview puede elegir GTK, lo que hace depender el arranque nativo
de PyGObject, GTK, WebKitGTK, Pango y Fontconfig del sistema o del bundle. En
instalaciones reales se reprodujo un fallo de simbolos en Pango/Fontconfig:

`libpangoft2-1.0.so.0: undefined symbol: FcConfigSetDefaultSubstitute`

Nexar Tienda ya evita esta clase de fallos usando Qt/PySide6 como backend Linux
principal de pywebview.

## Decision

Nexar Finanzas usa `gui="qt"` explicitamente solo en Linux. Windows mantiene la
seleccion normal de pywebview/WebView2.

El build Linux empaqueta:

- `pywebview[pyside6]`
- `qtpy`
- `PySide6`
- `PySide6.QtCore`
- `PySide6.QtGui`
- `PySide6.QtWidgets`
- `PySide6.QtNetwork`
- `PySide6.QtWebChannel`
- `PySide6.QtWebEngineCore`
- `PySide6.QtWebEngineWidgets`

El `.deb` deja de declarar GTK/PyGObject/WebKitGTK como dependencias principales
del backend nativo. Conserva dependencias nativas X11/OpenGL requeridas por
Qt/PySide6, alineadas con Nexar Tienda.

PyInstaller puede arrastrar bibliotecas del stack GTK/GLib/GIO como cierre
transitivo aunque el backend sea Qt. El `.spec` las filtra antes de `COLLECT`
para evitar mezcla ABI con las bibliotecas del sistema. En particular no se
empaquetan copias privadas de GLib, GIO, GObject, GModule, GThread, libffi,
libsecret, libmount, libblkid, GTK, GDK, GdkPixbuf, Pango, Fontconfig,
WebKitGTK ni JavaScriptCoreGTK. Cuando Qt necesita GLib o Fontconfig, se
resuelven desde el sistema mediante dependencias Debian.

## Diferencias con Nexar Tienda

Solo se replica la estrategia de backend Qt y empaquetado. No se copia logica de
Tienda relacionada con impresion, tickets, caja, bridges especificos ni cierre de
sesion.

## Validacion

`build_scripts_linux/validate_linux_qt_artifact.sh` falla si:

- no encuentra PySide6/Qt WebEngine dentro del artefacto;
- el `.deb` declara dependencias GTK/PyGObject/WebKitGTK como backend principal;
- aparecen bibliotecas privadas del stack GTK/GLib/GIO/Pango/Fontconfig;
- aparecen typelibs o modulos GI privados que indiquen inicializacion GTK.
