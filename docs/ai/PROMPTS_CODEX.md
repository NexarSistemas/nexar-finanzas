# Prompts útiles para Codex — Nexar Finanzas

## Reglas generales

Antes de modificar código:

1. Leer `README.md`.
2. Leer `CHANGELOG.md`.
3. Leer `docs/ai/AI_CONTEXT.md`.
4. Leer `docs/ai/LICENCIAS_ESTADO_ACTUAL.md`.
5. Revisar `git status`.
6. Confirmar rama actual.

No trabajar directamente sobre `main`.
No asumir que la documentación vieja sigue vigente.
Si hay contradicción entre docs históricas y el código actual, tomar como fuente
de verdad el estado implementado y los tests.

## Prompt base para próximas fases

Estamos en el repo `NexarSistemas/nexar-finanzas`.

Objetivo:
Trabajar sobre la siguiente fase del sistema sin perder compatibilidad con el
estado real de licencias.

Contexto mínimo que ya debe asumirse:

- existen los planes `DEMO`, `BASICA`, `PRO` y `FULL`
- `PRO` y `FULL` son planes mensuales separados
- ya no se exige `BASICA` previa para activar mensual
- `FULL` no debe normalizarse como `PRO`
- si `PRO` o `FULL` vencen, vuelven a `BASICA` solo cuando
  `basica_activada == "1"`; si no, quedan en `DEMO_EXPIRED`
- `get_demo_status()` expone capacidades por plan y no debe romperse

Restricciones base:

- no cambiar nombres ni contratos de funciones sensibles sin revisar impacto
- no exponer secretos, tokens o variables sensibles
- mantener documentación y código consistentes
- si la fase actual es solo documental, no tocar lógica productiva

## Recordatorio operativo

- no trabajar en `main`
- abrir rama de trabajo antes de cambios relevantes
- validar con `git diff --check`
- revisar que los cambios correspondan a la fase pedida
- resumir al final archivos modificados y alcance real
