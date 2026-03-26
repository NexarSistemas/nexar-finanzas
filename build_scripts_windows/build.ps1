# build.ps1 - Script de build para Nexar Finanzas (Windows)
# Autor: Rolando Navarta
#
# Genera dos artefactos en la carpeta release\:
#   - NexarFinanzas_vX.Y.Z_portable_windows.zip  (portable con launcher)
#   - NexarFinanzas_vX.Y.Z_Setup.exe             (instalador NSIS)
#
# Uso:
#   Ejecutar desde la carpeta raiz del proyecto (donde esta app.py):
#       .\build_scripts_windows\build.ps1
#
# Requisitos para el desarrollador:
#   - Python 3.10+  https://www.python.org/downloads/
#   - NSIS 3.x      https://nsis.sourceforge.io  (solo para el instalador)
#
# El usuario final NO necesita instalar nada extra.
# WebView2 Runtime se instala automaticamente si falta.

$ErrorActionPreference = "Stop"

$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $PROJECT_ROOT
Write-Host "Directorio de trabajo: $PROJECT_ROOT"

$APP_NAME    = "NexarFinanzas"
$APP_VERSION = "1.10.2"           # <── actualizar en cada release
$SPEC_FILE   = "build_scripts_windows\nexar_finanzas_windows.spec"
$ISS_FILE    = "build_scripts_windows\installer.iss"
$DIST_DIR    = "dist\$APP_NAME"
$OUTPUT_DIR  = "release"
$VENV_DIR    = ".venv_build"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Nexar Finanzas v$APP_VERSION - Build Windows  " -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Detectar Python 3.10+ ─────────────────────────────────────────────────
Write-Host "[1/5] Buscando Python 3.10+..." -ForegroundColor Yellow

$PYTHON = ""

if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $ver = (py --version 2>&1).ToString()
    if ($ver -match "Python 3[.]([0-9]+)") {
        if ([int]$Matches[1] -ge 10) { $PYTHON = "py" }
    }
}

if (($PYTHON -eq "") -and (Get-Command "python" -ErrorAction SilentlyContinue)) {
    $ver = (python --version 2>&1).ToString()
    if ($ver -match "Python 3[.]([0-9]+)") {
        if ([int]$Matches[1] -ge 10) { $PYTHON = "python" }
    }
}

if ($PYTHON -eq "") {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $PYTHON = $c; break }
    }
}

if ($PYTHON -eq "") {
    Write-Host "[ERROR] Python 3.10+ no encontrado." -ForegroundColor Red
    Write-Host "        Descargalo en: https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

$pyVer = (& $PYTHON --version 2>&1).ToString()
Write-Host "[OK] $pyVer ($PYTHON)" -ForegroundColor Green

# ── 2. Entorno virtual + dependencias ────────────────────────────────────────
Write-Host "[2/5] Preparando entorno virtual..." -ForegroundColor Yellow

# Crear venv si no existe
if (-not (Test-Path $VENV_DIR)) {
    Write-Host "      Creando entorno virtual en $VENV_DIR\ ..."
    & $PYTHON -m venv $VENV_DIR
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] No se pudo crear el entorno virtual." -ForegroundColor Red
        exit 1
    }
}

# Usar el Python y pip del venv a partir de aqui
$PYTHON = "$VENV_DIR\Scripts\python.exe"
$PIP    = "$VENV_DIR\Scripts\pip.exe"

# Actualizar pip primero (evita warnings y errores de compatibilidad)
Write-Host "      Actualizando pip..."
& $PYTHON -m pip install --upgrade pip --quiet

# Siempre instalar/actualizar PyInstaller
Write-Host "      Instalando/actualizando PyInstaller..."
& $PIP install --upgrade pyinstaller --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] No se pudo instalar PyInstaller." -ForegroundColor Red
    exit 1
}

# Siempre instalar dependencias del proyecto
if (Test-Path "requirements.txt") {
    Write-Host "      Instalando dependencias desde requirements.txt..."
    & $PIP install -r requirements.txt --quiet
} else {
    Write-Host "      Sin requirements.txt -- instalando dependencias conocidas..." -ForegroundColor Yellow
    & $PIP install flask werkzeug jinja2 requests cryptography pywebview pythonnet --quiet
}

# Verificar flask (la mas critica)
& $PYTHON -c "import flask" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Flask no se pudo instalar. Revisa requirements.txt o tu conexion." -ForegroundColor Red
    exit 1
}

# Verificar pythonnet (necesario para ventana nativa en Windows)
& $PYTHON -c "import clr" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      pythonnet no disponible, instalando..." -ForegroundColor Yellow
    & $PIP install pythonnet --quiet
    & $PYTHON -c "import clr" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[AVISO] pythonnet no pudo instalarse. La ventana nativa puede no funcionar." -ForegroundColor Yellow
        Write-Host "        Intenta: pip install pythonnet==3.0.3" -ForegroundColor Yellow
    }
}

Write-Host "[OK] Dependencias y PyInstaller listos (venv: $VENV_DIR)." -ForegroundColor Green

# ── 3. Build con PyInstaller ──────────────────────────────────────────────────
Write-Host "[3/5] Compilando con PyInstaller..." -ForegroundColor Yellow

if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist")  { Remove-Item "dist"  -Recurse -Force }

& $PYTHON -m PyInstaller $SPEC_FILE --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] PyInstaller fallo." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Build completado en dist\$APP_NAME\" -ForegroundColor Green

# ── 4. Portable .zip con launcher ────────────────────────────────────────────
Write-Host "[4/5] Creando portable .zip..." -ForegroundColor Yellow

if (-not (Test-Path $OUTPUT_DIR)) { New-Item -ItemType Directory $OUTPUT_DIR | Out-Null }

# Launcher .bat para el portable.
# Verifica si WebView2 esta instalado; si no, lo descarga e instala silenciosamente.
# Despues lanza la app. El usuario solo hace doble clic en este archivo.
$launcherContent = @'
@echo off
setlocal

:: Launcher de Nexar Finanzas (portable)
:: Verifica WebView2 Runtime e instala si es necesario, luego lanza la app.
:: El usuario no necesita hacer nada mas que doble clic.

:: Buscar WebView2 en las ubicaciones de registro conocidas
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
if %errorlevel% equ 0 goto :launch

reg query "HKCU\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
if %errorlevel% equ 0 goto :launch

reg query "HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
if %errorlevel% equ 0 goto :launch

:: WebView2 no encontrado — descargarlo e instalarlo silenciosamente
echo.
echo  Instalando componente requerido (WebView2 Runtime)...
echo  Esto solo ocurre la primera vez. Por favor espera.
echo.

set "INSTALLER=%TEMP%\MicrosoftEdgeWebview2Setup.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile '%INSTALLER%' -UseBasicParsing"

if not exist "%INSTALLER%" (
    echo.
    echo  [Aviso] No se pudo descargar WebView2.
    echo  Verifica tu conexion a internet.
    echo  La aplicacion intentara abrirse de todas formas.
    echo.
    goto :launch
)

"%INSTALLER%" /silent /install
del "%INSTALLER%" >nul 2>&1

:launch
start "" "%~dp0NexarFinanzas.exe"
endlocal
'@

# Guardar el launcher en la carpeta dist antes de comprimir
$launcherPath = "$DIST_DIR\Iniciar NexarFinanzas.bat"
[System.IO.File]::WriteAllText($launcherPath, $launcherContent, [System.Text.Encoding]::ASCII)

# Esperar un momento para que el sistema libere file handles
Start-Sleep -Seconds 2

$portableZip = "$OUTPUT_DIR\${APP_NAME}_v${APP_VERSION}_portable_windows.zip"
Compress-Archive -Path "$DIST_DIR\*" -DestinationPath $portableZip -Force
Write-Host "[OK] Portable: $portableZip" -ForegroundColor Green

# ── 5. Instalador con Inno Setup ─────────────────────────────────────────────
Write-Host "[5/5] Buscando Inno Setup para crear instalador..." -ForegroundColor Yellow

$ISCC = ""

# Rutas típicas
$innoCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

foreach ($c in $innoCandidates) {
    if (Test-Path $c) { $ISCC = $c; break }
}

# También intentar si está en PATH
if (($ISCC -eq "") -and (Get-Command "iscc" -ErrorAction SilentlyContinue)) {
    $ISCC = "iscc"
}

if ($ISCC -eq "") {
    Write-Host "[AVISO] Inno Setup no encontrado. Se omite el instalador." -ForegroundColor Yellow
    Write-Host "        Instalalo en: https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow
} else {
    & $ISCC "/DMyAppVersion=$APP_VERSION" $ISS_FILE
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Inno Setup fallo." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Instalador generado en dist_installer\" -ForegroundColor Green
}

# ── Checksums SHA256 ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Checksums SHA256:" -ForegroundColor Cyan
$sha256File = "$OUTPUT_DIR\SHA256SUMS_windows.txt"
"" | Set-Content $sha256File
Get-ChildItem "$OUTPUT_DIR\*" -Include "*.zip","*.exe" | ForEach-Object {
    $hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower()
    $line = "$hash  $($_.Name)"
    Write-Host "  $line"
    $line | Add-Content $sha256File
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Build completado en: $OUTPUT_DIR\"              -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
