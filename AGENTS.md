# AGENTS.md

Reglas de trabajo para IA en `nexar-finanzas`:

1. Leer primero `README.md` y `nexar-ai-context/CONTEXTO_NEXAR.md`.
2. `nexar-ai-context` es la fuente central para contexto compartido y estandares.
3. Copilot solo audita, resume riesgos o propone cambios. Codex aplica cambios y revisa el diff final.
4. No romper el modo offline-first ni el flujo de licencias.
5. Validar impacto antes de tocar cotizaciones externas, activacion, expiracion o actualizaciones.
6. Mantener compatibilidad desktop/local.
7. Si una decision entre `nexar-finanzas`, `nexar-admin` y `nexar_licencias` no esta clara, dejar `TODO(confirmar)`.
