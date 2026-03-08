# AI Context

Proyecto: Finanzas del Hogar  
Versión: 1.9.0  
Lenguaje: Python  
Framework: Flask  
Base de datos: SQLite  
Interfaz: HTML + Jinja templates  
Modo de ejecución: aplicación local con pywebview o navegador

## Objetivo del proyecto

Finanzas del Hogar es una aplicación local para gestión financiera personal que permite:

- registrar ingresos y gastos
- administrar cuentas
- crear presupuestos
- registrar inversiones
- ver reportes financieros
- gestionar transferencias entre cuentas
- consultar cotizaciones

La aplicación está pensada como:

- software de escritorio
- multiplataforma
- ejecutable empaquetado con PyInstaller

## Arquitectura general

Flask actúa como backend y servidor HTTP local.  
La UI se renderiza con templates Jinja.

Cuando está disponible, la aplicación se ejecuta dentro de una ventana nativa usando pywebview.

Si pywebview falla, se abre en el navegador.

## Principios del proyecto

- simplicidad
- base de datos local
- funcionamiento offline
- privacidad de datos
- fácil mantenimiento
