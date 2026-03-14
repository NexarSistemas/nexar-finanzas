# Changelog — Finanzas del Hogar

Todos los cambios notables de este proyecto se documentan aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).
Se utiliza [Versionado Semántico](https://semver.org/lang/es/).

---

## [1.9.2] — 2026-03-14

### Corregido
- Pantalla de activación: el ID de máquina (hardware ID) ahora se muestra correctamente en modo DEMO, con botón para copiar al portapapeles. Este dato es necesario para solicitar una licencia.

---

## [1.9.1] — 2026-03-09

### Mejorado
- Licencia MIT visible en Acerca de: sección colapsable al final de la página, sin interferir con la interfaz.

---

## [1.9.0] — 2026-03-05

### Corregido
- **Ventana en blanco al cerrar sin sesión activa**: al hacer logout y luego
  "Cerrar app", el servidor ahora se cierra correctamente sin dejar la ventana
  de pywebview colgada. Causa: `shutdown_confirm` tenía `@login_required`,
  que redirigía al login en lugar de ejecutar el cierre cuando no había sesión.
- **Cancelar en pantalla de cierre**: el botón ahora redirige al dashboard si
  hay sesión activa, o al login si el usuario ya cerró sesión.

### Mejorado
- **Aviso de costo de API de IA** (sin popup, notificación permanente):
  - En **Configuración → Inteligencia Artificial**: alerta visible antes del
    campo de clave API explicando que la obtención de la clave es gratuita
    pero el uso tiene costo a cargo del usuario, con enlace a precios.
  - En el **chat flotante (header)**: texto pequeño permanente bajo el
    subtítulo indicando "API gratuita · uso con costo (Anthropic)".
  - En la **pantalla "sin configurar"** del chat: aviso destacado antes del
    botón de configurar, explicando el modelo de costos.

### Modificado
- `routes.py`: removido `@login_required` de `shutdown_confirm`; comentario
  explicativo de la decisión de diseño.
- `templates/shutdown.html`: botón Cancelar condicional (dashboard/login
  según estado de sesión); bloque `auth_content` para acceso sin sesión.
- `templates/settings.html`: `alert-warning` de costo en sección IA.
- `templates/base.html`: aviso de costo en header del chat y en pantalla
  "sin configurar".
- `templates/help.html`: bloque v1.9.0 al tope del acordeón.
- `templates/about.html`: entrada v1.9.0 en historial.
- `app.py`, `VERSION`, `README.md`, `iniciar.bat`, `iniciar.sh`: v1.9.0.

---

## [1.8.0] — 2026-03-05

### Agregado
- **Recuperación de contraseña por pregunta secreta**: nuevo flujo de 2 pasos
  accesible desde el link "¿Olvidaste tu contraseña?" en el login.
- **Setup inicial**: ahora solicita pregunta y respuesta de seguridad al crear
  la cuenta de administrador por primera vez.
- **Configuración → Pregunta de seguridad**: sección nueva para configurar o
  cambiar la pregunta en cualquier momento (requiere contraseña actual para
  confirmar el cambio).
- Nueva ruta `GET/POST /forgot-password` con pasos: verificar respuesta → nueva
  contraseña.
- Nuevo template `forgot_password.html` con validación en tiempo real y
  botón mostrar/ocultar contraseña.
- Migración automática de base de datos: agrega columnas `recovery_question` y
  `recovery_answer_hash` a instalaciones existentes sin pérdida de datos.

### Modificado
- `models.py`: tabla `user` con nuevos campos `recovery_question` y
  `recovery_answer_hash`; migración segura con `ALTER TABLE` si la columna
  no existe.
- `routes.py`: rutas `/forgot-password`, `/setup` y `/settings` actualizadas.
- `templates/login.html`: link "¿Olvidaste tu contraseña?" debajo del botón.
- `templates/setup.html`: campos de pregunta/respuesta de seguridad.
- `templates/settings.html`: nueva tarjeta "Pregunta de seguridad".
- `templates/help.html`: bloque v1.8.0 al tope del acordeón.
- `templates/about.html`: entrada v1.8.0 en historial de versiones.
- `app.py`: `APP_VERSION` actualizado a `1.8.0`.
- `VERSION`, `README.md`, `iniciar.bat`, `iniciar.sh`: versión actualizada.

### Seguridad
- La respuesta secreta se almacena hasheada con SHA-256 (igual que la contraseña).
- La sesión de recuperación usa un token temporal en la sesión Flask, sin
  persistencia en base de datos.
- La respuesta se normaliza a minúsculas antes de hashear (no distingue
  mayúsculas/minúsculas para el usuario).

---

## [1.7.0] — 2026-03-04

### Agregado
- **Puerto dinámico**: la aplicación detecta automáticamente si el puerto 5000
  está ocupado y, en ese caso, solicita al sistema operativo un puerto libre
  alternativo. Ya no se requiere terminar procesos anteriores para poder
  iniciar la app.
- Nueva función interna `_encontrar_puerto(preferido)` en `app.py` que
  centraliza toda la lógica de selección de puerto.
- El banner de inicio ahora muestra el puerto real utilizado e informa si fue
  asignado automáticamente.

### Eliminado
- Función `_liberar_puerto()`: ya no es necesario matar procesos para liberar
  el puerto 5000; la lógica de fallback dinámico la reemplaza por completo.

### Modificado
- `app.py`: `APP_VERSION` actualizado a `1.7.0`.
- `iniciar.bat` / `iniciar.sh`: referencias de versión actualizadas a `1.7.0`.
- `README.md`: encabezado de versión actualizado a `1.7.0`.
- `VERSION`: actualizado a `1.7.0`.

---

## [1.6.0] — (versión anterior)

Versión inicial documentada. Puerto fijo 5000 con función `_liberar_puerto()`
para terminar procesos que lo tuvieran ocupado.
