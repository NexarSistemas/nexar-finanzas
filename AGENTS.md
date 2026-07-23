# AGENTS.md

Reglas de trabajo para IA en `nexar-finanzas`:

## Lectura obligatoria

1. Leer primero `README.md`, `docs/ai/AI_CONTEXT.md` y la documentación relacionada con la tarea.
2. Si hace falta contexto compartido, consultar `nexar-ai-context/CONTEXTO_NEXAR.md`, `repos/nexar-finanzas/CONTEXTO_REPO.md` y `standards/AI_WORKFLOW.md`; no asumir que existen dentro de este repo.
3. Revisar Issues y PR abiertas relacionadas.

## Roles y arquitectura

4. ChatGPT analiza, diseña, revisa y redacta prompts. Codex implementa, valida y ejecuta el flujo Git. Copilot/Gemini auditan o proponen salvo instrucción explícita.
5. No romper el modo offline-first, SQLite local, el flujo de licencias ni la compatibilidad desktop.
6. Validar impacto antes de tocar cotizaciones externas, activación, expiración, actualizaciones, builds o instaladores.
7. No mezclar refactorización con cambios funcionales. Reutilizar servicios y convenciones existentes.
8. Si una decisión entre `nexar-finanzas`, `nexar-admin` y `nexar_licencias` no está clara, usar `TODO(confirmar)`.

## Git y revisión

9. Nunca trabajar directamente sobre `main`. Usar ramas `feature/*`, `fix/*`, `docs/*`, `test/*` o `chore/*` y remoto SSH.
10. `main` recibe cambios solo mediante Pull Request. Estrategia predeterminada: `Squash and Merge`.
11. La primera revisión puede ser completa. Revisiones posteriores deben limitarse a `COMMIT_ANTERIOR...COMMIT_NUEVO`.
12. Si hay tests fallidos, conflictos, checks fallidos, hallazgos funcionales reales o PR no mergeable, detenerse y no mergear.
13. Si la revisión final resulta `APROBABLE`, cerrar automáticamente: Ready for Review si aplica, validación final, `Squash and Merge`, actualización de `main`, eliminación de ramas y `git status` limpio.

## Validación

14. Ejecutar primero tests focalizados. Antes del cierre ejecutar los comandos reales disponibles del repo, incluyendo como mínimo:

```bash
python -m py_compile <archivos_python_modificados>
python -m unittest discover -s tests
git diff --check
git status
```

15. Si el cambio afecta builds o instaladores, validar también los scripts y workflows correspondientes sin asumir compatibilidad entre Windows, Linux y macOS.

## Documentación y versiones

16. Mantener `README.md`, documentación, `VERSION` y `CHANGELOG.md` alineados cuando el cambio lo requiera.
17. No copiar políticas comerciales históricas a instrucciones globales sin verificar la implementación vigente, especialmente duración y compatibilidad de DEMO.
18. Crear tag y Release solo cuando la tarea indique explícitamente un cierre de versión. No hacerlo para fixes internos, revisiones post-merge o cambios documentales aislados.
19. Cerrar un Issue solo si quedó completamente resuelto.
