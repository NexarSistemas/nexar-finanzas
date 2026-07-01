# AGENTS.md

Reglas de trabajo para IA en `nexar-finanzas`:

1. Leer primero `README.md` y `docs/ai/AI_CONTEXT.md`.
2. Si hace falta contexto compartido del ecosistema Nexar, consultar el repo externo `nexar-ai-context`; no asumir que existe dentro de este repo.
3. Copilot solo audita, resume riesgos o propone cambios. Codex aplica cambios y revisa el diff final.
4. No romper el modo offline-first ni el flujo de licencias.
5. Validar impacto antes de tocar cotizaciones externas, activacion, expiracion o actualizaciones.
6. Mantener compatibilidad desktop/local.
7. Si una decision entre `nexar-finanzas`, `nexar-admin` y `nexar_licencias` no esta clara, dejar `TODO(confirmar)`.
