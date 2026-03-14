# build.ps1 — Script de build para Finanzas del Hogar v1.9.2
# Autor: Rolando Navarta
#
# Uso:
#   1. Abri PowerShell en la carpeta raiz del proyecto (donde esta app.py)
#   2. Ejecuta:  .\build_scripts\build.ps1
#
# Requisitos previos:
#   - Python 3.10+  (https://www.python.org/downloads/)
#   - NSIS 3.x      (https://nsis.sourceforge.io)  — solo para el instalador .exe
#   - pip install pyinstaller

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$APP_NAME    = "FinanzasHogar"
$APP_VERSION = "1.9.2"
$SPEC_FILE   = "build_scripts\finanzas_hogar.spec"
$NSI_FILE    = "build_scripts\finanzas_hogar.nsi"
$DIST_DIR    = "dist\$APP_NAME"
$OUTPUT_DIR  = "release"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Finanzas del Hogar v$APP_VERSION — Build Script" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Detectar Python ────────────────────────────────────────────────────────
Write-Host "[1/5] Buscando Python..." -ForegroundColor Yellow

$PYTHON = $null

# Intentar py launcher (forma recomendada en Windows)
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $ver = py --version 2>&1
    if ($ver -match "Python 3\.(\d+)") {
        $minor = [int]$Matches[1]
        if ($minor -ge 10) { $PYTHON = "py" }
    }
}

# Intentar python directo
if (-not $PYTHON -and (Get-Command "python" -ErrorAction SilentlyContinue)) {
    $ver = python --version 2>&1
    if ($ver -match "Python 3\.(\d+)") {
        $minor = [int]$Matches[1]
        if ($minor -ge 10) { $PYTHON = "python" }
    }
}

# Buscar en rutas conocidas
if (-not $PYTHON) {
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

if (-not $PYTHON) {
    Write-Host "[ERROR] Python 3.10+ no encontrado." -ForegroundColor Red
    Write-Host "        Descargalo en: https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

$pyVer = & $PYTHON --version 2>&1
Write-Host "[OK] $pyVer ($PYTHON)" -ForegroundColor Green

# ── 2. Instalar/verificar PyInstaller ─────────────────────────────────────────
Write-Host "[2/5] Verificando PyInstaller..." -ForegroundColor Yellow

$pyiCheck = & $PYTHON -c "import PyInstaller; print(PyInstaller.__version__)" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "      Instalando PyInstaller..." -ForegroundColor Yellow
    & $PYTHON -m pip install pyinstaller --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] No se pudo instalar PyInstaller." -ForegroundColor Red
        exit 1
    }
}
Write-Host "[OK] PyInstaller disponible." -ForegroundColor Green

# ── 3. Build con PyInstaller ──────────────────────────────────────────────────
Write-Host "[3/5] Compilando con PyInstaller..." -ForegroundColor Yellow

# Limpiar build anterior
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist")  { Remove-Item "dist"  -Recurse -Force }

& $PYTHON -m PyInstaller $SPEC_FILE --noconfirm 2>&1 | Tee-Object -Variable pyiOutput
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] PyInstaller falló." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Build completado en dist\$APP_NAME\" -ForegroundColor Green

# ── 4. Crear instalador con NSIS ──────────────────────────────────────────────
Write-Host "[4/5] Buscando NSIS para crear instalador..." -ForegroundColor Yellow

$MAKENSIS = $null
$nsisCandidates = @(
    "C:\Program Files (x86)\NSIS\makensis.exe",
    "C:\Program Files\NSIS\makensis.exe"
)
foreach ($c in $nsisCandidates) {
    if (Test-Path $c) { $MAKENSIS = $c; break }
}
if (-not $MAKENSIS -and (Get-Command "makensis" -ErrorAction SilentlyContinue)) {
    $MAKENSIS = "makensis"
}

if (-not $MAKENSIS) {
    Write-Host "[AVISO] NSIS no encontrado. Se omite la generacion del instalador .exe." -ForegroundColor Yellow
    Write-Host "        Instalalo en: https://nsis.sourceforge.io" -ForegroundColor Yellow
} else {
    & $MAKENSIS $NSI_FILE 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] NSIS falló al crear el instalador." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Instalador creado: FinanzasHogar_v${APP_VERSION}_Setup.exe" -ForegroundColor Green
}

# ── 5. Empaquetar release ─────────────────────────────────────────────────────
Write-Host "[5/5] Empaquetando release..." -ForegroundColor Yellow

if (-not (Test-Path $OUTPUT_DIR)) { New-Item -ItemType Directory $OUTPUT_DIR | Out-Null }

# ZIP portable (sin instalador)
$portableZip = "$OUTPUT_DIR\FinanzasHogar_v${APP_VERSION}_portable_windows.zip"
if (Test-Path $DIST_DIR) {
    Compress-Archive -Path "$DIST_DIR\*" -DestinationPath $portableZip -Force
    Write-Host "[OK] Portable: $portableZip" -ForegroundColor Green
}

# Mover instalador si se generó
$setupExe = "FinanzasHogar_v${APP_VERSION}_Setup.exe"
if (Test-Path $setupExe) {
    Move-Item $setupExe "$OUTPUT_DIR\" -Force
    Write-Host "[OK] Instalador: $OUTPUT_DIR\$setupExe" -ForegroundColor Green
}

# Generar SHA256
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
Write-Host "  Build completado en: $OUTPUT_DIR\" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
