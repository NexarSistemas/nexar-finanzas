# Arquitectura unificada de licencias

## Objetivo

Nexar Finanzas consume el SDK `nexar_licencias`, pero mantiene una fachada local
para adaptar nombres, persistencia SQLite y compatibilidad historica del producto.
La regla es: rutas, templates y arranque no deben depender de detalles internos
del SDK ni duplicar reglas criticas de plan.

## Fuente de verdad local

La fuente de verdad local esta centralizada en `licensing/license_service.py`.

Responsabilidades:

- normalizar planes de Finanzas: `DEMO`, `BASICA`, `PRO`, `FULL`;
- adaptar aliases legacy del ecosistema: `BASIC`, `BASICO`, `MENSUAL_PRO`,
  `MENSUAL`, `MENSUAL_FULL`;
- adaptar `MENSUAL_FULL` del SDK a `FULL` dentro de Finanzas;
- resolver tier efectivo con vencimientos y fallback offline/local;
- persistir en SQLite la licencia validada online o desde cache;
- construir `SDKConfig` usando variables `NEXAR_LICENSES_*` y aliases legacy;
- exponer una API estable para activacion, refresh, HWID y producto.

Campos SQLite relevantes:

- `license_tier`: plan guardado de la licencia local.
- `license_plan`: plan comercial normalizado.
- `license_expires_at`: vencimiento de `PRO` o `FULL`.
- `license_key`: clave activada.
- `license_data_full`: payload remoto/cache para auditoria local.
- `license_last_check`: fecha del ultimo refresh exitoso.
- `basica_activada`: derecho permanente base adquirido previamente.
- `demo_install_date`: fecha local de primera ejecucion demo.

## Anti-reinstall de DEMO

La proteccion local contra reinstalacion de la DEMO vive en `models.py` y usa
un archivo externo a la base financiera principal:

- Windows: `%APPDATA%\NexarFinanzas\telemetry.bin`.
- Linux/Mac: `$XDG_DATA_HOME/NexarFinanzas/telemetry.bin` o
  `~/.local/share/NexarFinanzas/telemetry.bin`.

`telemetry.bin` guarda la fecha original de inicio de DEMO codificada con un
salt derivado del `machine_id`. No contiene secretos ni datos financieros. Su
proposito es que borrar o recrear `database.db`, mover la carpeta de la app o
reinstalar la aplicacion en la misma cuenta del sistema operativo no reinicie el
periodo de 30 dias.

Orden de precedencia al inicializar:

- si `telemetry.bin` existe y corresponde al `machine_id`, restaura
  `demo_install_date` en SQLite;
- si SQLite tiene `demo_install_date` pero falta `telemetry.bin`, recrea el
  archivo externo con esa fecha, para migraciones o instalaciones previas;
- si no existe ninguno, registra la fecha actual como primera instalacion real.

En `NEXAR_TESTING=1` no se lee ni escribe telemetria real. Los tests que simulan
produccion deben redirigir `XDG_DATA_HOME`/`APPDATA` a un temporal controlado.

Relaciones entre identificadores:

- `machine_id`: hash local simple usado por `models.py` para vincular
  `telemetry.bin` al equipo.
- HWID/product HWID: lo resuelve `license_service.get_current_hwid()` mediante
  el SDK `nexar_licencias` cuando esta disponible y es el identificador usado
  para activacion y licencias pagas.
- `activation_id`: la UI de activacion usa el product HWID; el helper
  `generate_activation_id()` queda para solicitudes manuales con detalles del
  equipo.
- cache del SDK: cachea licencias pagas validadas y permite continuidad
  offline; no es la fuente de inicio de DEMO.
- validacion remota: actualmente aplica a licencias `BASICA`, `PRO` y `FULL`.
  No existe todavia un registro remoto de inicio de DEMO para bloquear una DEMO
  despues de reinstalar el sistema operativo.

Escenarios protegidos:

- primera instalacion real: inicia DEMO de 30 dias;
- segunda inicializacion: conserva la fecha original;
- borrar o recrear SQLite: restaura la fecha desde `telemetry.bin`;
- cambiar la ruta de la base o carpeta de instalacion: conserva la DEMO porque
  la telemetria esta fuera de la carpeta de la app;
- reinstalar la aplicacion en la misma cuenta del sistema operativo: conserva
  la fecha original;
- DEMO vencida: sigue vencida tras reinstalacion simulada;
- licencias `BASICA`, `PRO` y `FULL`: no se bloquean por una DEMO vencida local.

Limitaciones conocidas:

- Cambiar a otro usuario del sistema operativo puede iniciar otra DEMO si ese
  usuario no comparte la ruta de datos donde vive `telemetry.bin`.
- Reinstalar completamente el sistema operativo puede iniciar otra DEMO si se
  pierde la telemetria local y no existe validacion remota de DEMO.
- El mecanismo no depende de la ruta de instalacion ni solo de SQLite, pero
  sigue siendo local. Para cerrar esos dos escenarios hace falta soporte remoto
  en Nexar Licencias/Supabase para registrar el inicio de DEMO por HWID/producto.

Ante fallas temporales de validacion remota, el arranque conserva una licencia
paga local vigente en vez de revocarla automaticamente. Las revocaciones quedan
reservadas para rechazos explicitos del servidor o del SDK.

## Estado efectivo

`license_service.get_license_state(db_path)` devuelve:

- `stored_tier`: tier guardado.
- `active_plan`: plan comercial guardado.
- `effective_tier`: tier realmente habilitado para la app.
- `subscription_expired`: `PRO` o `FULL` vencido.
- `demo_expired`: demo vencida.

Reglas:

- `DEMO` vence despues de 30 dias y pasa a `DEMO_EXPIRED`.
- `BASICA` no vence.
- `PRO` vencido vuelve a `BASICA` solo si `basica_activada == "1"`.
- `FULL` vencido vuelve a `BASICA` solo si `basica_activada == "1"`.
- `PRO` o `FULL` vencido sin `BASICA` pasa a `DEMO_EXPIRED`.
- `FULL` no es alias interno de `PRO`; es un tier real de Finanzas.

## Integracion con el SDK

La integracion con `nexar_licencias` se hace desde `license_service.py`.

- Se usa `SDKConfig` cuando el SDK esta disponible.
- `requirements.txt` fija el SDK a una release concreta de `nexar_licencias`;
  no debe apuntar a `main` ni a una carpeta editable local.
- Se prefieren variables `NEXAR_LICENSES_*`.
- Se mantienen aliases legacy: `SUPABASE_URL`, `SUPABASE_KEY`,
  `SUPABASE_ANON_KEY`, `NEXAR_CACHE_FILE`, `NEXAR_CACHE_DAYS`.
- La validacion usa `validar_licencia_detalle` cuando existe y conserva fallback
  online directo contra Supabase para instalaciones empaquetadas donde el SDK no
  pueda importarse.
- El cache offline del SDK se acepta como fuente valida cuando devuelve una
  licencia `ok`.
- El codigo del SDK no se autoactualiza por separado dentro de una instalacion
  existente de Finanzas. Politica de actualizacion:
  nueva release de `nexar_licencias` -> actualizar la referencia en
  `requirements.txt` -> ejecutar tests -> generar nuevos builds -> publicar una
  nueva version de Nexar Finanzas.
- Los datos de licencia y estado remoto pueden sincronizarse con Supabase; eso
  no implica actualizar automaticamente el codigo Python del SDK ya empaquetado.

## Empaquetado del SDK

Los builds Windows y Linux instalan `requirements.txt` dentro del entorno de
build antes de ejecutar PyInstaller. La dependencia privada de
`nexar_licencias` se obtiene por SSH desde GitHub usando una deploy key de solo
lectura configurada como secreto de GitHub Actions.

Los specs de PyInstaller recolectan los submodulos de `nexar_licencias` con
`collect_optional_submodules('nexar_licencias')`. Por eso el SDK queda dentro del
directorio `dist/NexarFinanzas` y viaja tanto en el portable como en el
instalador `.exe` y el paquete `.deb`. El `.deb` no declara `nexar_licencias`
como dependencia Debian: el usuario final no debe instalar Python, pip ni el SDK
manualmente.

## Compatibilidad

Estos wrappers se mantienen para no romper rutas, templates ni tests existentes:

- `demo_limits.get_tier()`
- `demo_limits.get_demo_status()`
- `demo_limits.is_full_version()`
- `demo_limits.is_pro_expired()`
- `models.normalize_license_plan()`
- `models.sync_license_from_remote()`
- `licensing/license_sdk.py`

Los wrappers delegan en `licensing/license_service.py`.

## Fronteras de responsabilidad

- `routes.py`: coordina acciones HTTP y consume la fachada.
- `demo_limits.py`: arma limites, capacidades y conteos para UI/enforcement.
- `models.py`: inicializa SQLite y conserva migraciones historicas.
- `supabase_license_api.py`: fallback online y solicitudes manuales.
- `nexar_licencias`: validacion SDK, configuracion, cache offline y contrato
  reusable entre productos Nexar.
