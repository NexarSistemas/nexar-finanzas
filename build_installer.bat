@echo off
rem build_installer.bat - Lanzador de build para Finanzas del Hogar v1.9.2
rem Ejecutar desde la carpeta raiz del proyecto (donde esta app.py)
PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_scripts\build.ps1"
