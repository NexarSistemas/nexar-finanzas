# Matriz de estados de licencias

## Proposito

Este documento consolida los estados, transiciones, capacidades y casos de
prueba del sistema de licencias de Nexar Finanzas. Es una referencia funcional y
tecnica para futuras fases; no reemplaza la arquitectura base de
`LICENCIAS_ARQUITECTURA.md` ni el resumen operativo de
`LICENCIAS_ESTADO_ACTUAL.md`.

Alcance de esta version:

- planes comerciales vigentes: `DEMO`, `BASICA`, `PRO`, `FULL`;
- estado operativo adicional: `DEMO_EXPIRED`;
- activacion manual, checkout, refresh, vencimientos y validacion remota;
- anti-reinstall local de DEMO;
- cobertura automatizada existente y brechas manuales.

## Terminologia

| Termino | Significado |
|---|---|
| Plan comercial | Plan vendido o mostrado al usuario: `DEMO`, `BASICA`, `PRO`, `FULL`. |
| Tier guardado | Valor persistido en SQLite en `license_tier`. |
| Plan activo | Valor normalizado de `license_plan`; representa el plan comercial guardado. |
| Tier efectivo | Resultado de `license_service.get_license_state(...).effective_tier`, usado por la app para permisos. |
| Estado remoto | Resultado que devuelve Supabase/SDK para una licencia: valida, expirada, revocada, inexistente, limite de dispositivos, etc. |
| Estado local | Configuracion persistida en SQLite y, para DEMO, `telemetry.bin`. |
| Estado vencido | DEMO con mas de 30 dias o `PRO`/`FULL` con `license_expires_at` anterior a hoy. |
| Modo lectura | Estado donde se conservan datos pero se bloquean altas, ediciones y eliminaciones financieras. |
| Derecho BASICA | `basica_activada == "1"`; permite fallback a `BASICA` cuando vence un plan mensual. |
| Error temporal | Falla de transporte/timeout validando una licencia guardada. Conserva el tier efectivo local vigente. |
| Rechazo explicito | Respuesta del SDK/backend que invalida la licencia; revoca segun politica local. |

## Fuentes de verdad

| Area | Fuente |
|---|---|
| Normalizacion y estado efectivo | `licensing/license_service.py` |
| Capacidades y limites | `demo_limits.py` |
| Persistencia inicial y anti-reinstall | `models.py` |
| Arranque y validacion conservadora | `licensing/check_license.py` |
| Activacion manual y refresh | `routes.py`, `licensing/license_service.py` |
| Checkout | `routes.py`, `services/mercadopago_checkout.py` |
| UI de Mi Plan | `templates/activate.html`, helpers en `routes.py` |
| Contexto funcional | `README.md`, `docs/ai/LICENCIAS_ESTADO_ACTUAL.md` |

## Estados comerciales y tecnicos

| Estado | Tipo | Vigente como plan comercial | Descripcion |
|---|---|---:|---|
| `DEMO` | Comercial y tecnico | Si | Prueba de 30 dias desde `demo_install_date`. |
| `DEMO_EXPIRED` | Tecnico operativo | No | DEMO vencida o mensual vencido sin `BASICA`; activa modo lectura. |
| `BASICA` | Comercial y tecnico | Si | Plan pago permanente, sin vencimiento. |
| `PRO` | Comercial y tecnico | Si | Plan mensual con vencimiento. |
| `FULL` | Comercial y tecnico | Si | Plan mensual premium, separado de `PRO`. |

Aliases normalizados, no planes comerciales vigentes:

| Alias | Normaliza a | Uso |
|---|---|---|
| `BASIC` | `BASICA` | Compatibilidad historica/ecosistema. |
| `BASICO` | `BASICA` | Compatibilidad historica/ecosistema. |
| `MENSUAL_PRO` | `PRO` | Alias tecnico del ecosistema. |
| `MENSUAL` | `FULL` | Alias legacy que actualmente se adapta a `FULL`. |
| `MENSUAL_FULL` | `FULL` | Plan del SDK para `FULL`. |

## Persistencia local

Campos SQLite relevantes:

| Campo | Proposito |
|---|---|
| `license_tier` | Tier guardado: `DEMO`, `BASICA`, `PRO`, `FULL`. |
| `license_plan` | Plan comercial normalizado. |
| `license_expires_at` | Vencimiento ISO para `PRO` y `FULL`; vacio para `BASICA`. |
| `license_key` | Clave activada. |
| `license_signature` | Firma si el payload remoto/SDK la provee. |
| `license_data_full` | Payload remoto/cache serializado para auditoria local. |
| `license_last_check` | Fecha del ultimo refresh exitoso. |
| `license_max_devices` | Maximo remoto de equipos cuando aplica. |
| `basica_activada` | Derecho permanente a fallback `BASICA`. |
| `demo_install_date` | Fecha local de primera DEMO. |
| `machine_id` | Hash local usado por `telemetry.bin`. |
| `pending_checkout_*` | Estado local de checkout directo pendiente. |

Persistencia externa a SQLite:

- `telemetry.bin`: fecha original de DEMO fuera de la base financiera.
- cache del SDK `nexar_licencias`: fuente offline valida para licencias pagas
  cuando `validar_licencia_detalle` devuelve `ok`.

## Matriz de transiciones

| Estado inicial | Evento | Condicion | Estado efectivo resultante | Persistencia | Escritura permitida | Accion disponible |
|---|---|---|---|---|---|---|
| Sin DB/telemetria | Primera ejecucion | Sin antecedentes locales | `DEMO` | Crea SQLite, `demo_install_date`, `machine_id`, `telemetry.bin` | Si, con limites DEMO | Activar/comprar `BASICA`, `PRO`, `FULL` |
| `DEMO` | Pasan 31 dias | `demo_install_date` > 30 dias | `DEMO_EXPIRED` | No elimina datos | No | Activar/comprar `BASICA`, `PRO`, `FULL` |
| `DEMO` | Compra/activacion `BASICA` | Licencia valida | `BASICA` | `license_tier=BASICA`, `basica_activada=1` | Si, limites BASICA | Upgrade a `PRO` o `FULL` |
| `DEMO` o limpia | Compra/activacion `PRO` | Licencia valida | `PRO` | `license_tier=PRO`, `license_expires_at` | Si | Renovar `PRO` o upgrade a `FULL` |
| `DEMO` o limpia | Compra/activacion `FULL` | Licencia valida | `FULL` | `license_tier=FULL`, `license_expires_at` | Si | Renovar `FULL` |
| Cualquier plan | Activacion manual | `validate_license_key` ok | Plan devuelto por SDK/Supabase | Sincroniza SQLite y cache SDK si aplica | Segun tier efectivo | Refresh/renovar/cambiar plan |
| Checkout iniciado sin `license_key` | Refresh post-pago | No hay licencia local aun | Sin cambio local | Mantiene `pending_checkout_*` | Segun tier previo | Mostrar mensaje seguro: no volver a pagar |
| Checkout con `license_key` | Refresh post-pago | `validate_saved_license` ok | Plan devuelto por SDK/cache | Limpia `pending_checkout_*` | Segun tier efectivo | Continuar o renovar |
| `BASICA` | Upgrade | Checkout/activacion `PRO` valida | `PRO` | Guarda `PRO`, conserva `basica_activada=1` | Si | Renovar o upgrade a `FULL` |
| `BASICA` | Upgrade | Checkout/activacion `FULL` valida | `FULL` | Guarda `FULL`, conserva `basica_activada=1` | Si | Renovar `FULL` |
| `PRO` | Upgrade | Checkout/activacion `FULL` valida | `FULL` | Guarda `FULL` | Si | Renovar `FULL` |
| `FULL` | Cambio a `PRO` | No expuesto como downgrade normal en UI; posible operacion administrativa remota | `PRO` si remoto devuelve `PRO` | Sync remoto reescribe `license_tier=PRO` | Si | Renovar/upgrade segun nuevo plan |
| `PRO` | Renovacion `PRO` | Remoto devuelve `PRO` con nueva fecha | `PRO` | Actualiza `license_expires_at` | Si | Seguir operando |
| `FULL` | Renovacion `FULL` | Remoto devuelve `FULL`/`MENSUAL_FULL` con nueva fecha | `FULL` | Actualiza `license_expires_at` | Si | Seguir operando |
| `PRO`/`FULL` | Vencimiento mensual | `basica_activada == "1"` | `BASICA` | No borra datos; tier efectivo deriva de fecha | Si, limites BASICA | Renovar mensual |
| `PRO`/`FULL` | Vencimiento mensual | `basica_activada != "1"` | `DEMO_EXPIRED` | No borra datos | No | Renovar o activar plan |
| `BASICA` | Paso del tiempo | Sin vencimiento | `BASICA` | Sin cambios | Si, limites BASICA | Upgrade |
| Plan pago local | Validacion correcta | SDK/Supabase ok | Plan remoto sincronizado | Actualiza SQLite/cache | Segun tier efectivo | Operar normalmente |
| `BASICA` local | Error temporal remoto | Timeout/transporte estructurado o mensaje temporal | `BASICA` | No modifica ni revoca | Si, limites BASICA | Reintentar luego |
| `PRO` local | Error temporal remoto | Timeout/transporte estructurado o mensaje temporal | `PRO` | No modifica ni revoca | Si | Reintentar luego |
| `FULL` local | Error temporal remoto | Timeout/transporte estructurado o mensaje temporal | `FULL` | No modifica ni revoca | Si | Reintentar luego |
| Plan pago local | SDK/config/cache no disponible | No hay validacion ni cache valida | Revocacion segun politica actual | Degrada a `BASICA` si `basica_activada=1`; si no, `DEMO` | Segun resultado | Configurar/validar licencia |
| Plan pago local | Rechazo explicito | Expirada, revocada, no existe, limite dispositivos | Revocacion segun politica actual | Degrada a `BASICA` si `basica_activada=1`; si no, `DEMO` | Segun resultado | Contactar soporte/reactivar |
| `DEMO` con `telemetry.bin` | Borrado/recreacion SQLite | Mismo usuario/equipo | DEMO con fecha original o `DEMO_EXPIRED` | Restaura `demo_install_date` desde `telemetry.bin` | Segun dias restantes | Activar/comprar |
| Cualquier DB | Cambio de carpeta app/base | Misma telemetria de usuario/equipo | Conserva DEMO original | `telemetry.bin` fuera de carpeta app | Segun tier | Operar/activar |
| Mismo usuario/equipo | Reinstalacion local | `telemetry.bin` conserva fecha | Conserva DEMO original | Restaura SQLite | Segun tier | Operar/activar |
| Otro usuario SO | Cambio de usuario | No comparte `telemetry.bin` | Puede iniciar nueva DEMO | Limitacion local | Si hasta vencer | Requiere registro remoto DEMO para cerrar |
| Equipo reinstalado | Reinstalacion SO | Se pierde telemetria local | Puede iniciar nueva DEMO | Limitacion local | Si hasta vencer | Requiere registro remoto DEMO para cerrar |

## Transiciones no permitidas o no expuestas

| Transicion | Estado |
|---|---|
| `PRO` -> `BASICA` por checkout normal | No expuesta salvo vencimiento con `basica_activada=1` o decision administrativa remota. |
| `FULL` -> `PRO` por UI normal | No expuesta como downgrade; puede ocurrir si backend/admin devuelve `PRO`. |
| `DEMO_EXPIRED` -> escritura sin activar | No permitida; modo lectura. |
| Falta SDK/config/cache -> conservar pago editable localmente | No permitida por politica actual. |
| Aliases historicos como planes visibles | No permitido; se normalizan a planes vigentes. |

## Matriz de vencimientos

| Caso | Resultado |
|---|---|
| `DEMO` vencida | `DEMO_EXPIRED` -> datos conservados -> modo lectura -> activacion/renovacion disponible. |
| `PRO` vencido + `basica_activada == "1"` | Tier efectivo `BASICA`. |
| `FULL` vencido + `basica_activada == "1"` | Tier efectivo `BASICA`. |
| `PRO` vencido + `basica_activada != "1"` | `DEMO_EXPIRED` -> modo lectura. |
| `FULL` vencido + `basica_activada != "1"` | `DEMO_EXPIRED` -> modo lectura. |
| `BASICA` | No vence. |

## Matriz de capacidades

Valores tomados de `demo_limits.TIER_LIMITS` y `get_demo_status()`.

| Capacidad | DEMO | DEMO_EXPIRED | BASICA | PRO | FULL |
|---|---:|---:|---:|---:|---:|
| Movimientos | Ilimitados | Solo lectura | Ilimitados | Ilimitados | Ilimitados |
| Cuentas | 3 en total | Solo lectura | 1 por tipo | Ilimitadas | Ilimitadas |
| Presupuestos | Ilimitados | Solo lectura | 3 | Ilimitados | Ilimitados |
| Inversiones | Hasta 3, escritura | Solo lectura | Solo lectura | Ilimitadas, escritura | Ilimitadas, escritura |
| Reportes semanal/mensual | Si | Si | Si | Si | Si |
| Reporte anual | Si | Si | No | Si | Si |
| Flujo de caja | Si | Si | No | Si | Si |
| Reportes avanzados | Si | Si | No | No | Si |
| IA integrada con API key | Disponible en la app | Disponible en lectura | Disponible | Disponible | Disponible |
| Insights IA premium | No | No | No | No | Si |
| Exportacion Excel | No | No | No | Si | Si |
| Exportacion PDF | No | No | No | Si | Si |
| Actualizaciones | No | No | No | Si | Si |
| Escritura de datos financieros | Si | No | Si | Si | Si |
| Modo lectura forzado | No | Si | No | No | No |

Notas:

- `DEMO_EXPIRED` reutiliza limites base de `DEMO` para visualizacion, pero
  `can_write_data` y `can_investments_write` quedan en `False`.
- `BASICA` no bloquea lectura de inversiones existentes, pero no permite nuevas
  operaciones de inversion.
- `FULL` conserva limites practicos de `PRO` y habilita capacidades premium:
  reportes avanzados e insights IA.

## Validacion local y remota

| Resultado de validacion | Comportamiento |
|---|---|
| Correcta | Se sincroniza el plan devuelto, vencimiento, clave, payload y cache local si aplica. |
| Cache SDK valida | Se acepta como licencia `ok` y se persiste en SQLite para continuidad offline. |
| Error temporal estructurado | Conserva exactamente el tier local efectivo: `BASICA`, `PRO` o `FULL`. |
| Error temporal por mensaje | Fallback de compatibilidad basado en prefijos de mensaje; es fragil y debe preferirse metadata estructurada cuando el SDK la exponga. |
| SDK no disponible/config faltante/sin cache | No se clasifica como temporal; no se acepta automaticamente un estado pago editable localmente. |
| Rechazo explicito | Revoca segun politica actual: fallback a `BASICA` si existe derecho; si no, `DEMO`. |

Mensajes temporales reconocidos hoy en `check_license.py`:

- `Error validando licencia:`
- `No se pudo validar online:`

Razones estructuradas temporales reconocidas hoy:

- `network_error`
- `timeout`
- `temporary_error`
- `transport_error`

Razones no temporales documentadas:

- `sin_cache`
- `missing_config`
- `sdk_unavailable`

## Reinstalacion y anti-reinstall

La DEMO usa `telemetry.bin` fuera de SQLite. Ver detalles en
`LICENCIAS_ARQUITECTURA.md`.

| Escenario | Resultado actual |
|---|---|
| Primera instalacion sin antecedentes | Inicia DEMO de 30 dias. |
| Reinstalacion con `telemetry.bin` | Conserva fecha original. |
| SQLite eliminada o recreada | Restaura `demo_install_date` desde `telemetry.bin`. |
| Cambio de carpeta de instalacion/base | Conserva fecha original para el mismo usuario/equipo. |
| `NEXAR_TESTING=1` | No lee ni escribe telemetria real. |
| Cambio de usuario del SO | Limitado: puede iniciar otra DEMO si no comparte telemetria. |
| Reinstalacion completa del SO | Limitado: puede iniciar otra DEMO si se pierde telemetria. |

Los dos ultimos escenarios dependen de un registro remoto de DEMO por
HWID/producto. Esa limitacion mantiene abierto el Issue #63.

## Cobertura automatizada

| Escenario critico | Test actual | Estado |
|---|---|---|
| DEMO activa | `tests/test_demo_limits.py::test_demo_active_status` | Cubierto |
| DEMO vencida | `tests/test_demo_limits.py::test_demo_expired_status_is_read_only` | Cubierto |
| BASICA permanente | `tests/test_demo_limits.py::test_basica_active_status` | Cubierto |
| PRO activo | `tests/test_demo_limits.py::test_pro_active_capabilities` | Cubierto |
| FULL activo | `tests/test_demo_limits.py::test_full_active_capabilities` | Cubierto |
| PRO vencido con BASICA previa | `tests/test_demo_limits.py::test_pro_expired_with_basica_degrades_to_basica` | Cubierto |
| FULL vencido con BASICA previa | `tests/test_demo_limits.py::test_full_expired_with_basica_degrades_to_basica` | Cubierto |
| PRO vencido sin BASICA previa | `tests/test_demo_limits.py::test_pro_expired_without_basica_becomes_demo_expired` | Cubierto |
| FULL vencido sin BASICA previa | `tests/test_demo_limits.py::test_full_expired_without_basica_becomes_demo_expired` | Cubierto |
| Activacion directa BASICA/PRO/FULL desde remoto | `tests/test_license_service.py::test_sync_remote_accepts_direct_paid_plan_activation_matrix` | Cubierto |
| Normalizacion de aliases | `tests/test_license_service.py::test_normalizes_legacy_aliases_without_mixing_pro_and_full` | Cubierto |
| Cache SDK valida | `tests/test_license_service.py::test_validate_saved_license_accepts_sdk_cache_and_persists_state` | Cubierto |
| Checkout disponible para DEMO vencida | `tests/test_activate_page.py::test_activate_page_shows_checkout_buttons_for_expired_demo` | Cubierto |
| Checkout alta sin license_key | `tests/test_activate_page.py::test_activate_checkout_open_uses_activation_flow_without_license_key` | Cubierto |
| Refresh post-pago con license_key | `tests/test_activate_page.py::test_refresh_license_with_license_key_keeps_normal_flow` | Cubierto |
| Refresh post-pago sin license_key | `tests/test_activate_page.py::test_refresh_license_without_license_key_shows_safe_message_for_pending_checkout` | Cubierto |
| Modo lectura bloquea escritura | `tests/test_expired_license_read_only.py::test_expired_monthly_without_basica_blocks_destructive_financial_changes` | Cubierto |
| No se eliminan datos por vencimiento | `tests/test_expired_license_read_only.py::test_expired_monthly_without_basica_blocks_destructive_financial_changes` | Cubierto |
| Mensual vencido con BASICA conserva escritura BASICA | `tests/test_expired_license_read_only.py::test_expired_monthly_with_basica_keeps_basica_write_behavior` | Cubierto |
| Error temporal conserva BASICA | `tests/test_demo_anti_reinstall.py::test_temporary_remote_error_preserves_paid_local_state` | Cubierto |
| Error temporal conserva PRO | `tests/test_demo_anti_reinstall.py::test_temporary_remote_error_preserves_paid_local_state` | Cubierto |
| Error temporal conserva FULL | `tests/test_demo_anti_reinstall.py::test_temporary_remote_error_preserves_paid_local_state` | Cubierto |
| Error temporal estructurado | `tests/test_demo_anti_reinstall.py::test_structured_temporary_remote_error_preserves_paid_local_state` | Cubierto |
| Rechazo explicito revoca | `tests/test_demo_anti_reinstall.py::test_explicit_remote_rejection_keeps_revocation` | Cubierto |
| SDK no disponible no es temporal | `tests/test_demo_anti_reinstall.py::test_non_validated_sdk_state_is_not_temporary_and_revokes` | Cubierto |
| Borrar SQLite no reinicia DEMO | `tests/test_demo_anti_reinstall.py::test_recreating_sqlite_restores_demo_date_from_external_telemetry` | Cubierto |
| Cambiar ruta no reinicia DEMO | `tests/test_demo_anti_reinstall.py::test_changing_database_path_restores_demo_date_for_same_device` | Cubierto |
| DEMO vencida sigue vencida tras reinstalacion simulada | `tests/test_demo_anti_reinstall.py::test_expired_demo_stays_expired_after_simulated_reinstall` | Cubierto |
| `NEXAR_TESTING=1` no toca telemetria real | `tests/test_demo_anti_reinstall.py::test_testing_mode_does_not_write_real_telemetry` y `tests/test_models_init_db.py::test_init_db_does_not_write_telemetry_in_testing_mode` | Cubierto |
| FULL se muestra como FULL | `tests/test_activate_page.py::test_activate_page_shows_refresh_when_license_key_exists`, `tests/test_activate_page.py::test_about_page_shows_full_as_full_plan` | Cubierto |
| Exportacion Excel PRO | `tests/test_report_exports.py::test_excel_export_is_available_for_pro` | Cubierto |
| Exportacion PDF FULL | `tests/test_report_exports.py::test_pdf_export_is_available_for_full` | Cubierto |
| Bloqueo export DEMO/BASICA | `tests/test_report_exports.py::test_excel_export_is_blocked_for_demo`, `tests/test_report_exports.py::test_pdf_export_is_blocked_for_basica` | Cubierto |

## Pruebas manuales o funcionales

| Escenario | Motivo |
|---|---|
| Solicitud manual real a Supabase | Requiere credenciales y backend externo. |
| Aprobacion desde Nexar Admin | Pertenece a otro repositorio/producto. |
| Checkout Mercado Pago end-to-end | Depende de Nexar Pagos/Mercado Pago y credenciales externas. |
| Renovacion real PRO/FULL post-pago | Depende de integracion con Nexar Pagos y backend de licencias. |
| Cambio `FULL` -> `PRO` administrativo | No esta expuesto en UI; depende del estado devuelto por backend/admin. |
| Cambio de usuario del SO | Requiere entorno del sistema operativo. |
| Reinstalacion completa del SO | No es simulable de forma confiable en unittest local. |

## Limitaciones conocidas

- Issue #63 sigue abierto: falta registro remoto de DEMO por HWID/producto para
  cubrir cambio de usuario del SO y reinstalacion completa del SO.
- La deteccion por prefijos de mensaje para errores temporales es un fallback de
  compatibilidad; la forma preferida es metadata estructurada del SDK.
- `check_license()` conserva el tier local ante errores temporales, pero no debe
  aceptar estados pagos locales cuando faltan SDK/configuracion/cache.
- `FULL` -> `PRO` no es flujo de downgrade de usuario en Finanzas; si ocurre,
  debe venir de una decision administrativa/backend.

## Dependencias con otros repositorios

| Dependencia | Necesaria para |
|---|---|
| `nexar_licencias` | Metadata estructurada de errores, cache offline, validacion y HWID/product HWID. |
| Supabase/Nexar Licencias | Registro remoto de licencias pagas y futuro registro remoto de DEMO. |
| Nexar Admin | Aprobacion, revocacion, cambios administrativos y eventuales downgrades. |
| Nexar Pagos | Checkout, renovaciones y cambios de plan post-pago. |

## Reglas para futuros planes

1. Agregar el plan en `license_service.py` y su normalizacion.
2. Definir si es permanente o mensual.
3. Agregar limites y capacidades en `demo_limits.TIER_LIMITS`.
4. Documentar fallback ante vencimiento.
5. Agregar tests de estado efectivo, capacidades, vencimiento y UI.
6. Evitar aliases visibles como planes comerciales.
7. Mantener `DEMO_EXPIRED` como estado tecnico de modo lectura, no como plan.
8. Si el nuevo plan depende de backend externo, documentar el contrato antes de
   cambiar rutas o templates.
