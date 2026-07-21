# Estado operativo — 21 de julio de 2026

## Rol del repositorio

Aplicación de escritorio para gestión financiera personal, con operación local sobre SQLite, ventana nativa y licenciamiento integrado al ecosistema Nexar.

## Estado confirmado

- Repositorio activo; versión documentada: `1.13.1`.
- La aplicación funciona offline para la gestión cotidiana y utiliza validación online/cache para licencias.
- La DEMO de Nexar Finanzas dura 30 días; esta regla es propia del producto y no debe confundirse con los 14 días de Nexar Comercio.
- BASICA es permanente; PRO y FULL son mensuales.
- Una instalación limpia puede activar directamente PRO o FULL sin pasar por BASICA.
- El repositorio incluye cuentas con descubierto autorizado, reportes, inversiones, presupuestos, cotizaciones, backups y actualizaciones para planes habilitados.
- La protección anti-reinstalación de DEMO y el estado de licencia deben mantenerse fuera de la sola base SQLite.

## Decisiones vigentes

- La base SQLite contiene datos del usuario; las actualizaciones deben preservar datos, historial y licencia.
- Los builds oficiales incluyen dependencias necesarias para la ventana nativa y conservan fallback al navegador.
- La IA es opcional, usa una clave configurada localmente y no forma parte del núcleo obligatorio de licencias.

## Integraciones

- `nexar_licencias`: validación compartida y continuidad offline.
- `nexar-admin`: aprobación y operación administrativa de licencias.
- `nexar-pagos`: backend de checkout cuando el flujo comercial automático esté conectado.
- `nexar-ai-context`: arquitectura y decisiones transversales.
