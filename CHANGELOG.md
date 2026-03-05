# Changelog — Finanzas del Hogar

Todos los cambios notables de este proyecto se documentan aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).
Se utiliza [Versionado Semántico](https://semver.org/lang/es/).

---

## [1.7.0] — 2026-03-04

### Agregado
- **Puerto dinámico**: la aplicación detecta automáticamente si el puerto 5000
  está ocupado y, en ese caso, solicita al sistema operativo un puerto libre
  alternativo. Ya no se requiere terminar procesos anteriores para poder
  iniciar la app.
- Nueva función interna `_encontrar_puerto(preferido)` en `app.py` que
  centraliza toda la lógica de selección de puerto.
- El banner de inicio ahora muestra el puerto real utilizado e informa si fue
  asignado automáticamente.

### Eliminado
- Función `_liberar_puerto()`: ya no es necesario matar procesos para liberar
  el puerto 5000; la lógica de fallback dinámico la reemplaza por completo.

### Modificado
- `app.py`: `APP_VERSION` actualizado a `1.7.0`.
- `iniciar.bat` / `iniciar.sh`: referencias de versión actualizadas a `1.7.0`.
- `README.md`: encabezado de versión actualizado a `1.7.0`.
- `VERSION`: actualizado a `1.7.0`.

---

## [1.6.0] — (versión anterior)

Versión inicial documentada. Puerto fijo 5000 con función `_liberar_puerto()`
para terminar procesos que lo tuvieran ocupado.
