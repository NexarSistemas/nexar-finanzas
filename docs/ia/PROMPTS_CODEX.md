# Prompts útiles para Codex — Nexar Finanzas

## Reglas generales

Antes de modificar código:

1. Leer README.md.
2. Leer CHANGELOG.md.
3. Leer docs/ai/AI_CONTEXT.md.
4. Leer docs/ai/LICENCIAS_ESTADO_ACTUAL.md.
5. Revisar git status.
6. Confirmar rama actual.

No trabajar directamente sobre main.

## Prompt para fase de documentación

Estamos en el repo NexarSistemas/nexar-finanzas.

Objetivo:
Actualizar documentación del repo para reflejar el estado real del sistema de licencias.

Contexto:
Ya están mergeados los PRs recientes que implementaron:

- Activación de planes mensuales sin BASICA previa.
- Normalización correcta de PRO y FULL.
- Límites y capacidades para FULL en demo_limits.py.
- Tests mínimos para DEMO, BASICA, PRO y FULL.
- UI de licencias actualizada para mostrar FULL como plan independiente.

Tareas:
1. Actualizar README.md.
2. Actualizar CHANGELOG.md.
3. Crear docs/ai/AI_CONTEXT.md.
4. Crear docs/ai/LICENCIAS_ESTADO_ACTUAL.md.
5. Crear docs/ai/ROADMAP.md.
6. Crear docs/ai/PROMPTS_CODEX.md.

No implementar nuevas funciones.
No modificar lógica de negocio.
No tocar app.py, routes.py, models.py, demo_limits.py ni templates salvo que sea estrictamente necesario para corregir documentación embebida.

Validación:
- git diff --check
- revisar que no haya cambios de código productivo
- mostrar git diff resumido

Commit sugerido:
docs: actualiza contexto de licencias y roadmap
