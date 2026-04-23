@echo off
setlocal EnableDelayedExpansion
title Nexar Finanzas v1.10.16

echo.
echo ================================================================
echo   Nexar Finanzas v1.10.16 - Nexar Sistemas
echo   Modo Portable
echo ================================================================
echo.

cd /d "%~dp0"

:: 1. VERIFICAR PYTHON
echo [1/4] Verificando Python...

python --version >nul 2>&1
if errorlevel 1 goto :no_python

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_FULL=%%v
for /f "tokens=1,2 delims=." %%a in ("%PY_FULL%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 goto :python_viejo
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 goto :python_viejo

echo [OK] Python %PY_FULL% detectado.
goto :check_pip

:no_python
echo.
echo [ERROR] Python no esta instalado.
echo.
echo   Descargalo en: https://www.python.org/downloads/
echo   Instala la version 3.10 o superior.
echo   IMPORTANTE: marca "Add Python to PATH" al instalar.
echo.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:python_viejo
echo.
echo [ERROR] Python %PY_FULL% es muy antiguo. Se requiere 3.10 o superior.
echo   Descargalo en: https://www.python.org/downloads/
echo.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:: 2. VERIFICAR PIP
:check_pip
echo [2/4] Verificando pip...
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo   Instalando pip...
    python -m ensurepip --upgrade >nul 2>&1
    python -m pip install --upgrade pip --quiet >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar pip.
        pause
        exit /b 1
    )
)
echo [OK] pip disponible.

:: 3. INSTALAR DEPENDENCIAS
echo [3/4] Verificando dependencias...

python -m pip install --upgrade pip --quiet --disable-pip-version-check >nul 2>&1

echo   Instalando paquetes del proyecto...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check >nul 2>&1

echo   Verificando pywebview...
python -c "import webview" >nul 2>&1
if errorlevel 1 (
    echo   Instalando pywebview...
    python -m pip install pywebview --quiet --disable-pip-version-check >nul 2>&1
    python -c "import webview" >nul 2>&1
    if errorlevel 1 (
        echo   [AVISO] pywebview no pudo instalarse.
        echo           La app se abrira en el navegador del sistema.
    ) else (
        echo   [OK] pywebview instalado.
    )
) else (
    echo   [OK] pywebview disponible.
)

python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Flask no se pudo instalar.
    echo         Verifica tu conexion a internet e intentalo de nuevo.
    pause
    exit /b 1
)
echo [OK] Dependencias listas.

:: 4. INICIAR APLICACION
echo [4/4] Iniciando aplicacion...
echo.
echo   La app abrira en una ventana propia.
echo   Si no abre, ingresa manualmente: http://127.0.0.1:5000
echo.
echo ================================================================
echo.

python app.py

if errorlevel 1 (
    echo.
    echo [ERROR] La app termino con un error.
    echo         Revisa finanzas_error.log en esta carpeta.
    echo.
    pause
)
