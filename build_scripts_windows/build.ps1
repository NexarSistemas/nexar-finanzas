# build.ps1 - Script de build para Nexar Finanzas (Windows)
# Autor: Rolando Navarta
#
# Genera dos artefactos en la carpeta release\:
#   - NexarFinanzas_vX.Y.Z_portable_windows.zip  (portable con launcher)
#   - NexarFinanzas_vX.Y.Z_setup.exe             (instalador Inno Setup)
#
# Uso:
#   Ejecutar desde la carpeta raiz del proyecto (donde esta app.py):
#       .\build_scripts_windows\build.ps1
#
# Requisitos para el desarrollador:
#   - Python 3.10+  https://www.python.org/downloads/
#   - Inno Setup 6  https://jrsoftware.org/isinfo.php  (solo para el instalador)
#
# El usuario final NO necesita instalar nada extra.
# WebView2 Runtime se instala automaticamente si falta.

$ErrorActionPreference = "Stop"

$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $PROJECT_ROOT

$APP_NAME = "NexarFinanzas"

$APP_VERSION = Get-Content "VERSION"
$APP_VERSION = $APP_VERSION.Trim()

$SPEC_FILE   = "build_scripts_windows\nexar_finanzas.spec"
$ISS_FILE    = "build_scripts_windows\installer.iss"
$DIST_DIR    = "dist\$APP_NAME"
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

# FIX: separador \ entre $OUTPUT_DIR y $APP_NAME para que el path sea valido
$portableZip = "$OUTPUT_DIR\${APP_NAME}_v${APP_VERSION}_portable_windows.zip"

Compress-Archive -Path "$DIST_DIR\*" -DestinationPath $portableZip -Force

Write-Host "[OK] Portable generado: $portableZip" -ForegroundColor Green

# ── 5. Instalador Inno Setup ─────────────────────────────────

Write-Host "[5/5] Generando instalador..." -ForegroundColor Yellow

$ISCC = ""

$paths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
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

# Mover el installer desde dist_installer\ a release\ para centralizar artefactos
$installerSrc = "build_scripts_windows\dist_installer\${APP_NAME}_v${APP_VERSION}_setup.exe"
$installerDst = "$OUTPUT_DIR\${APP_NAME}_v${APP_VERSION}_setup.exe"

if (Test-Path $installerSrc) {
    Move-Item $installerSrc $installerDst -Force
    Write-Host "[OK] Installer movido a $OUTPUT_DIR" -ForegroundColor Green
} else {
    Write-Host "[AVISO] No se encontro el installer en $installerSrc" -ForegroundColor Yellow
}

# ── SHA256 ───────────────────────────────────────────────────

Write-Host ""
Write-Host "Checksums SHA256:" -ForegroundColor Cyan

$sha256File = "$OUTPUT_DIR\SHA256SUMS_windows.txt"
"" | Out-File $sha256File -Encoding UTF8

Get-ChildItem "$OUTPUT_DIR\*.zip", "$OUTPUT_DIR\*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
    $hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower()
    $line = "$hash  $($_.Name)"
    Write-Host "  $line"
    $line | Add-Content $sha256File -Encoding UTF8
}

Write-Host ""
Write-Host "[OK] BUILD COMPLETO"
Write-Host ""
