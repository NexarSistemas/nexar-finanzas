# Estado actual del sistema de licencias — Nexar Finanzas

## Planes soportados

El sistema soporta cuatro estados principales:

- `DEMO`
- `BASICA`
- `PRO`
- `FULL`

Además existe el estado operativo `DEMO_EXPIRED` para la demo vencida o para
planes mensuales vencidos sin `BASICA` previa activada.

## Backend Supabase + nexar_licencias

La activación y validación moderna usan:

- Supabase como backend remoto
- SDK `nexar_licencias`
- `license_key`
- producto `nexar-finanzas`
- `machine_id` / hardware binding
- persistencia local de estado normalizado en SQLite

No volver a documentar Google Drive ni el flujo legacy como backend principal.

## Normalización de planes

La normalización vigente está alineada con `models.py`:

- `BASIC` → `BASICA`
- `BASICO` → `BASICA`
- `BASICA` → `BASICA`
- `DEMO` → `DEMO`
- `PRO` → `PRO`
- `MENSUAL_PRO` → `PRO`
- `FULL` → `FULL`
- `MENSUAL` → `FULL`
- `MENSUAL_FULL` → `FULL`

Regla clave: `FULL` no debe degradarse ni renombrarse como `PRO`.

## Flujos válidos

Flujos aceptados actualmente:

- instalación limpia / `DEMO` → `BASICA`
- instalación limpia / `DEMO` → `PRO`
- instalación limpia / `DEMO` → `FULL`
- `BASICA` → `PRO`
- `BASICA` → `FULL`

No reintroducir la exigencia de `BASICA` previa para activar mensual.

## Regla de vencimiento

Cuando vence una licencia `PRO` o `FULL`:

- si `basica_activada == "1"` el tier efectivo pasa a `BASICA`
- si `basica_activada != "1"` el tier efectivo pasa a `DEMO_EXPIRED`

Esto evita regalar una `BASICA` a usuarios que solo compraron un mensual.

## Capacidades por plan

### DEMO

- movimientos ilimitados
- hasta 3 cuentas en total
- hasta 3 inversiones
- presupuestos ilimitados
- reportes semanal, mensual y anual
- `advanced_reports = true`
- `cashflow_analysis = true`
- `ai_insights = false`
- `export_excel = false`
- `export_pdf = false`
- `updates = false`

### BASICA

- movimientos ilimitados
- 1 cuenta por tipo
- inversiones en solo lectura
- hasta 3 presupuestos
- reportes semanal y mensual
- `advanced_reports = false`
- `cashflow_analysis = false`
- `ai_insights = false`
- `export_excel = false`
- `export_pdf = false`
- `updates = false`

### PRO

- cuentas, inversiones y presupuestos sin límites prácticos
- inversiones con escritura
- reportes semanal, mensual y anual
- `advanced_reports = false`
- `cashflow_analysis = true`
- `ai_insights = false`
- `export_excel = true`
- `export_pdf = true`
- `updates = true`

### FULL

- mismas bases operativas de PRO
- `advanced_reports = true`
- `cashflow_analysis = true`
- `ai_insights = true`
- `export_excel = true`
- `export_pdf = true`
- `updates = true`

## Funciones que no deben romperse

Mantener compatibilidad de API y contrato de datos para:

- `check_limit()`
- `is_full_version()`
- `get_demo_status()`
- `is_pro_expired()`
- `get_demo_days_remaining()`
- `get_pro_days_remaining()`
- `get_tier()`
- `normalize_license_plan()`
- `sync_license_from_remote()`

## Campos sensibles de get_demo_status()

Estos campos siguen siendo relevantes para templates, rutas o compatibilidad:

- `is_demo`
- `version`
- `limits`
- `counts`
- `tier`
- `is_expired`
- `is_basica`
- `is_pro`
- `is_full`
- `is_paid`
- `pro_expired`
- `demo_days`
- `pro_days`
- `pro_expires_soon`
- `pro_expires_tomorrow`
- `can_update`
- `can_investments_write`
- `plan_capabilities`
- `can_advanced_reports`
- `can_cashflow_analysis`
- `can_ai_insights`
- `can_export_excel`
- `can_export_pdf`

## Estado validado en el repo

- `models.py` ya distingue `PRO` y `FULL`.
- `demo_limits.py` ya define límites y capacidades de `FULL`.
- `tests/test_demo_limits.py` cubre DEMO, BASICA, PRO, FULL y vencimientos.
- La UI ya muestra `FULL` como plan independiente.
