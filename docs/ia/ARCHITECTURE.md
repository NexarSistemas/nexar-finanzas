# Architecture

Arquitectura tipo MVC simplificada.

## Backend

Flask

Componentes principales:

app.py
    punto de entrada

routes.py
    define endpoints

services.py
    lógica de negocio

models.py
    esquema de base de datos SQLite

ai_service.py
    integración futura con servicios de IA

licensing/
    control de licencias con Supabase + SDK nexar_licencias

## Frontend

Templates HTML usando Jinja:

templates/
    dashboard
    cuentas
    transacciones
    inversiones
    reportes

## Base de datos

SQLite

database.db

Inicializada automáticamente en:

models.init_db()
