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

# build.ps1 - Nexar Finanzas (Windows CI/CD listo)

$ErrorActionPreference = "Stop"

$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $PROJECT_ROOT

$APP_NAME    = "NexarFinanzas"
$APP_VERSION = "1.10.2"
$SPEC_FILE   = "build_scripts_windows\nexar_finanzas.spec"
$ISS_FILE    = "build_scripts_windows\installer.iss"
$DIST_DIR    = "dist$APP_NAME"
$OUTPUT_DIR  = "release"
$VENV_DIR    = ".venv_build"

Write-Host ""
Write-Host "================================================"
Write-Host "  Nexar Finanzas v$APP_VERSION - Build Windows  "
Write-Host "================================================"
Write-Host ""

# ── 1. Python (forzado) ──────────────────────────────────────

Write-Host "[1/5] Usando Python del entorno..." -ForegroundColor Yellow

$PYTHON = "python"

$pyVer = (& $PYTHON --version 2>&1).ToString()
Write-Host "[OK] $pyVer ($PYTHON)" -ForegroundColor Green

# ── 2. Entorno virtual ───────────────────────────────────────

Write-Host "[2/5] Preparando entorno virtual..." -ForegroundColor Yellow

if (-not (Test-Path $VENV_DIR)) {
& $PYTHON -m venv $VENV_DIR
}

$PYTHON = "$VENV_DIR\Scripts\python.exe"
$PIP    = "$VENV_DIR\Scripts\pip.exe"

& $PYTHON -m pip install --upgrade pip
& $PIP install --upgrade pyinstaller

if (Test-Path "requirements.txt") {
& $PIP install -r requirements.txt
} else {
& $PIP install flask pywebview pythonnet
}

Write-Host "[OK] Dependencias listas" -ForegroundColor Green

# ── 3. Build PyInstaller ─────────────────────────────────────

Write-Host "[3/5] Compilando..." -ForegroundColor Yellow

if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist")  { Remove-Item "dist"  -Recurse -Force }

& $PYTHON -m PyInstaller $SPEC_FILE --noconfirm

if ($LASTEXITCODE -ne 0) {
Write-Host "[ERROR] PyInstaller fallo" -ForegroundColor Red
exit 1
}

Write-Host "[OK] EXE generado" -ForegroundColor Green

# ── 4. Portable ZIP ──────────────────────────────────────────

Write-Host "[4/5] Creando portable..." -ForegroundColor Yellow

if (-not (Test-Path $OUTPUT_DIR)) {
New-Item -ItemType Directory $OUTPUT_DIR | Out-Null
}

$portableZip = "$OUTPUT_DIR${APP_NAME}_v${APP_VERSION}_portable_windows.zip"

Compress-Archive -Path "$DIST_DIR*" -DestinationPath $portableZip -Force

Write-Host "[OK] Portable generado" -ForegroundColor Green

# ── 5. Instalador Inno Setup ─────────────────────────────────

Write-Host "[5/5] Generando instalador..." -ForegroundColor Yellow

$ISCC = ""

$paths = @(
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
"C:\Program Files\Inno Setup 6\ISCC.exe"
)

foreach ($p in $paths) {
if (Test-Path $p) {
$ISCC = $p
break
}
}

if ($ISCC -eq "") {
Write-Host "[ERROR] Inno Setup no encontrado" -ForegroundColor Red
exit 1
}

Write-Host "Version enviada a Inno: $APP_VERSION"

$arguments = @(
"/DMyAppVersion=$APP_VERSION",
$ISS_FILE
)

& $ISCC @arguments

if ($LASTEXITCODE -ne 0) {
Write-Host "[ERROR] Inno Setup fallo" -ForegroundColor Red
exit 1
}

Write-Host "[OK] Instalador generado" -ForegroundColor Green

Write-Host ""
Write-Host "✔ BUILD COMPLETO"
Write-Host ""
