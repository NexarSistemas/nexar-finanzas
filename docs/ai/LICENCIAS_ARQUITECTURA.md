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
- Se prefieren variables `NEXAR_LICENSES_*`.
- Se mantienen aliases legacy: `SUPABASE_URL`, `SUPABASE_KEY`,
  `SUPABASE_ANON_KEY`, `NEXAR_CACHE_FILE`, `NEXAR_CACHE_DAYS`.
- La validacion usa `validar_licencia_detalle` cuando existe y conserva fallback
  online directo contra Supabase para instalaciones empaquetadas donde el SDK no
  pueda importarse.
- El cache offline del SDK se acepta como fuente valida cuando devuelve una
  licencia `ok`.

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
