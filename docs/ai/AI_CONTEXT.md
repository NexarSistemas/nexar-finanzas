# AI Context — Nexar Finanzas

## Resumen del producto

Nexar Finanzas es una aplicación de escritorio para gestión financiera personal.
Corre localmente, prioriza privacidad y funcionamiento offline, y usa un
servidor Flask embebido con interfaz HTML renderizada con Jinja.

Permite registrar ingresos, gastos, cuentas, presupuestos, inversiones,
transferencias y reportes. También integra cotizaciones externas y funciones de
IA optativas configuradas por el usuario.

## Stack técnico

- Python 3.10+
- Flask
- SQLite
- HTML + Jinja2
- pywebview con fallback al navegador
- Supabase para licencias
- SDK `nexar_licencias`
- Integraciones externas: Yahoo Finance, BYMA, CAFCI, CoinGecko, dolarapi.com
- IA opcional con Anthropic API

## Estado actual

- El sistema de licencias soporta `DEMO`, `BASICA`, `PRO` y `FULL`.
- `PRO` y `FULL` son planes mensuales separados a nivel de normalización y UI.
- Ya no se requiere `BASICA` previa para activar `PRO` o `FULL`.
- Si `PRO` o `FULL` vencen:
  vuelve a `BASICA` solo si `basica_activada == "1"`;
  si no, el estado final es `DEMO_EXPIRED`.
- `demo_limits.py` ya expone capacidades por plan con flags derivados de
  `get_demo_status()`.
- Hay tests mínimos para los cuatro estados principales de licencias.

## Archivos importantes

- `app.py`: arranque de la aplicación y contexto global.
- `routes.py`: rutas HTTP y enforcement funcional.
- `models.py`: persistencia SQLite, normalización y sincronización de licencias.
- `demo_limits.py`: tiers, límites, capacidades y estado consolidado.
- `licensing/`: integración Supabase + SDK + validación de licencia.
- `tests/test_demo_limits.py`: cobertura base del comportamiento por plan.
- `README.md`: documentación pública del producto.
- `CHANGELOG.md`: historial de cambios del proyecto.
- `docs/ai/LICENCIAS_ESTADO_ACTUAL.md`: fuente rápida para decisiones sobre licencias.
- `docs/ai/PROMPTS_CODEX.md`: reglas operativas para próximas fases.

## Reglas para Codex

- Leer `README.md`, `CHANGELOG.md` y `docs/ai/*.md` antes de cambiar lógica.
- No asumir que `PRO` y `FULL` son equivalentes; revisar capacidades concretas.
- No reintroducir la regla vieja de exigir `BASICA` previa para mensual.
- No romper compatibilidad de `get_demo_status()`, `get_tier()`,
  `is_full_version()`, `is_pro_expired()` ni helpers asociados.
- No exponer secretos, claves ni variables sensibles en documentación o logs.
- No trabajar directamente sobre `main`; preparar cambios en una rama de trabajo.
