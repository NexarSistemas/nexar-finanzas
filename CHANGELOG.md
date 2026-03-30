# Changelog — Nexar Finanzas

Todos los cambios notables de este proyecto se documentan aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).
Se utiliza [Versionado Semántico](https://semver.org/lang/es/).

---

## [1.10.4] - 2026-03-30

### 🛠️ CI/CD
- Pipeline de release estabilizado
- Generación de SHA256 única para artefactos
- Firma GPG integrada en releases
- Upload de assets robusto y sin duplicados
- Eliminación previa de assets para evitar conflictos
- Uso de `gh cli` con uploads idempotentes (`--clobber`)
- Prevención de race conditions en releases

### 🔧 Chores
- Ajustes en `.gitignore`

### 🐛 Fixes
- Correcciones en workflows de build y release

## [1.10.3] — 2026-03-28

### Mejorado
- **Pipeline de build y release automatizado**: integración completa con GitHub Actions para generación de paquetes Linux y Windows.
- **Generación automática de SHA256** para todos los artefactos de distribución.
- **Firma digital GPG** de binarios (`.sig`) para verificación de integridad y autenticidad.
- **Release automática basada en CHANGELOG**: el sistema detecta la versión desde este archivo y genera la release en GitHub sin intervención manual.

### Técnico
- Unificación del flujo CI/CD entre Nexar Finanzas y Nexar Almacén.
- Preparación del proyecto para distribución profesional (instaladores + portable + firma).

## [1.10.2] - 2026-03-21

### Fixed
- **Sistema de actualización**: Los archivos del update ahora se escriben en `APP_DIR`
  (directorio del código) en lugar de `BASE_DIR` (directorio de datos). En instalaciones
  `.deb` estos directorios son distintos, lo que causaba que las actualizaciones no se
  aplicaran. (`routes.py` + `app.py`)
  
## [1.10.1] — 2026-03-21

### Corregido
- **Renovación Pro sin interrupciones**: el formulario para pegar el token de
  renovación ahora aparece en la pantalla de Activación cuando el Plan Pro está
  **activo**, no solo cuando ya venció. Permite al usuario renovar antes del
  vencimiento sin perder ni un día de servicio.

---

## [1.10.0] — 2026-03-20

### Agregado
- **Sistema de licencias por tiers (DEMO / BÁSICA / PRO)**: reemplazo completo del sistema binario DEMO/FULL anterior.
  - **DEMO**: 30 días desde la primera ejecución, funcionalidad casi completa con límites suaves.
  - **BÁSICA**: pago único permanente. Movimientos ilimitados, 1 cuenta por tipo, inversiones en solo lectura, hasta 3 presupuestos, reportes semanal + mensual.
  - **PRO**: suscripción mensual. Acceso completo, actualizaciones incluidas, soporte WhatsApp.
- **Activación por Token Base64 + RSA**: nuevo sistema de activación offline con firma digital RSA (PKCS1v15 + SHA256). Reemplaza los códigos HMAC anteriores para clientes nuevos.
- **Anti-reinstall (`telemetry.bin`)**: la fecha de inicio de la demo se guarda fuera de la base de datos en `~/.local/share/NexarFinanzas/telemetry.bin` (Linux) o `%APPDATA%\NexarFinanzas	elemetry.bin` (Windows). Sobrevive al borrado de la BD.
- **Detección de hardware ID (`machine_id`)**: se genera y persiste en la BD para vincular licencias al equipo.
- **Pantalla de activación rediseñada**: campo token largo (textarea), tabla comparativa de planes, botón WhatsApp con ID pre-cargado, formulario de upgrade PRO desde BÁSICA.
- **Badge de plan en navbar**: muestra DEMO (con días restantes), BÁSICA o PRO con estilos diferenciados.
- **Banner de plan en contenido**: aviso rojo para DEMO vencida, amarillo para DEMO activa con días, verde suave para BÁSICA con botón upgrade. PRO sin banner.
- **Aviso PRO vencido** en pie del sidebar con link directo a renovar.

### Modificado
- `activation.py`: soporte dual — Token Base64+RSA para clientes nuevos + HMAC legacy para códigos existentes (compatibilidad total).
- `demo_limits.py`: reescrito con `TIER_LIMITS`, `get_tier()`, `is_pro_expired()`, `get_demo_days_remaining()`, `check_tier_limit()`. API original (`check_limit`, `is_full_version`, `get_demo_status`) preservada para compatibilidad.
- `models.py`: nuevos campos `license_tier`, `license_expires_at`, `demo_install_date`, `machine_id` en `init_db()`. Anti-reinstall integrado.
- `routes.py`: enforcement de tier en cuentas (por tipo), inversiones (solo lectura en BÁSICA), presupuestos (máx 3 en BÁSICA), reportes (sin anual en BÁSICA), actualizaciones (solo PRO). Ruta `/activate` acepta tokens en cualquier estado de activación (permite upgrade BÁSICA→PRO).
- `base.html`: badge de 4 estados, candado visual en inversiones sidebar, banner diferenciado por tier.
- `requirements.txt`: agregada dependencia `cryptography>=41.0.0` para verificación RSA.

### Migración automática
- Usuarios con código HMAC activo (`version=FULL`) son migrados silenciosamente a `tier=BASICA` al primer arranque. Sin intervención del usuario.

---
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
