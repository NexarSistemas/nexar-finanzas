# Estado actual del sistema de licencias — Nexar Finanzas

## Planes soportados

Nexar Finanzas soporta cuatro planes:

- DEMO
- BASICA
- PRO
- FULL

## Backend de licencias

El sistema usa el esquema moderno de Nexar:

- Supabase
- SDK nexar_licencias
- license_key
- producto = nexar-finanzas
- HWID / dispositivos
- cache local del SDK

Google Drive ya no debe usarse como backend principal de licencias.

## Normalización de planes

Los planes deben normalizarse así:

- BASIC → BASICA
- BASICO → BASICA
- BASICA → BASICA
- DEMO → DEMO
- PRO → PRO
- MENSUAL_PRO → PRO
- FULL → FULL
- MENSUAL → FULL
- MENSUAL_FULL → FULL

FULL no debe convertirse a PRO.

## Flujos válidos de activación

Son válidos:

- DEMO / instalación limpia → PRO
- DEMO / instalación limpia → FULL
- BASICA → PRO
- BASICA → FULL

Ya no se exige BASICA previa para activar planes mensuales.

## Regla de vencimiento mensual

Cuando vence PRO o FULL:

- Si basica_activada == "1" → vuelve a BASICA.
- Si basica_activada != "1" → pasa a DEMO_EXPIRED.

Motivo:

Un usuario que compra solo un plan mensual no debe conservar una BASICA gratuita al vencer.

## Capacidades por plan

### DEMO

- advanced_reports = true
- cashflow_analysis = true
- ai_insights = false
- export_excel = false
- export_pdf = false

### BASICA

- advanced_reports = false
- cashflow_analysis = false
- ai_insights = false
- export_excel = false
- export_pdf = false

### PRO

- advanced_reports = false
- cashflow_analysis = true
- ai_insights = false
- export_excel = true
- export_pdf = true

### FULL

- advanced_reports = true
- cashflow_analysis = true
- ai_insights = true
- export_excel = true
- export_pdf = true

## Estado implementado

Ya está implementado:

- models.py distingue PRO y FULL.
- demo_limits.py soporta FULL.
- get_demo_status() expone flags de capacidades.
- UI muestra FULL como plan separado.
- Tests mínimos cubren comportamiento de planes.

## Campos esperados en get_demo_status()

Debe conservar:

- is_demo
- version
- limits
- counts
- tier
- is_expired
- is_basica
- is_pro
- pro_expired
- demo_days
- pro_days
- pro_expires_soon
- pro_expires_tomorrow
- can_update
- can_investments_write

Debe incluir:

- is_full
- is_paid
- plan_capabilities
- can_advanced_reports
- can_cashflow_analysis
- can_ai_insights
- can_export_excel
- can_export_pdf

## Compatibilidad

No renombrar sin revisar impacto:

- check_limit()
- is_full_version()
- get_demo_status()
- is_pro_expired()
- get_demo_days_remaining()
- get_pro_days_remaining()
- get_tier()

Aunque algunas funciones digan "pro" en el nombre, deben seguir contemplando PRO y FULL por compatibilidad.
