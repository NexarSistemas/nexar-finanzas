# Roadmap — Nexar Finanzas

## Estado actual

El repo ya tiene mergeados los cambios principales de licencias:

- activación mensual sin `BASICA` previa
- separación real entre `PRO` y `FULL`
- capacidades de `FULL` en `demo_limits.py`
- tests base para `DEMO`, `BASICA`, `PRO` y `FULL`
- UI de licencias mostrando `FULL` como plan independiente

## Fase actual

Fase enfocada en documentación y alineación de contexto técnico:

- actualizar `README.md`
- actualizar `CHANGELOG.md`
- consolidar contexto de trabajo en `docs/ai`
- dejar reglas claras para futuras intervenciones de Codex

En esta fase no se deben introducir cambios de lógica productiva.

## Próximas fases posibles

### 1. UI de licencias

- mejorar textos y ayudas en activación
- revisar consistencia visual de badges, banners y mensajes de vencimiento
- aclarar diferencias reales entre `PRO` y `FULL`

### 2. Gating por capacidades

- usar `plan_capabilities` como fuente única
- reducir lógica dispersa por nombres de plan
- endurecer tests para evitar regresiones

### 3. Exportaciones

- consolidar gating de Excel y PDF
- revisar UX de errores y mensajes cuando el plan no habilita exportación
- validar consistencia entre backend, templates y documentación

### 4. Reportes avanzados FULL

- profundizar funciones exclusivas de `FULL`
- ampliar análisis comparativos y financieros
- separar claramente reportes estándar vs avanzados

### 5. IA financiera

- definir capacidades premium relacionadas con IA
- evaluar uso de `ai_insights` en reportes, clasificación y asistente
- mantener costos y privacidad claramente comunicados

### 6. Release formal

- empaquetar estos cambios documentales en una release ordenada
- revisar versión, changelog y notas de publicación
- verificar que README, tests y UI cuenten la misma historia
