; ============================================================
; finanzas_hogar.nsi — Script NSIS para Finanzas del Hogar v1.9.2
; Genera: FinanzasHogar_v1.9.2_Setup.exe
;
; Requisitos:
;   - NSIS 3.x instalado: https://nsis.sourceforge.io
;   - El directorio dist\FinanzasHogar\ ya construido con PyInstaller
;
; Compilar:
;   makensis finanzas_hogar.nsi
; ============================================================

Unicode True

; ── Información del instalador ────────────────────────────────────────────────
!define APP_NAME        "Finanzas del Hogar"
!define APP_VERSION     "1.9.2"
!define APP_PUBLISHER   "Rolando Navarta"
!define APP_URL         "https://github.com/RolandoNavarta"
!define APP_EXE         "FinanzasHogar.exe"
!define INSTALL_DIR     "$PROGRAMFILES64\FinanzasHogar"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\FinanzasHogar"

; ── Configuración general ─────────────────────────────────────────────────────
Name                "${APP_NAME} v${APP_VERSION}"
OutFile             "FinanzasHogar_v${APP_VERSION}_Setup.exe"
InstallDir          "${INSTALL_DIR}"
InstallDirRegKey    HKLM "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor       /SOLID lzma
SetCompressorDictSize 32

; ── Páginas del instalador ────────────────────────────────────────────────────
!include "MUI2.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON                    "..\FinanzasHogar\finanzas_hogar.ico"
!define MUI_UNICON                  "..\FinanzasHogar\finanzas_hogar.ico"
!define MUI_WELCOMEPAGE_TITLE       "Instalador de ${APP_NAME} v${APP_VERSION}"
!define MUI_WELCOMEPAGE_TEXT        "Este asistente instalara ${APP_NAME} en tu computadora.$\n$\nSe recomienda cerrar otras aplicaciones antes de continuar."
!define MUI_FINISHPAGE_RUN          "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT     "Iniciar ${APP_NAME} ahora"
!define MUI_FINISHPAGE_SHOWREADME   "$INSTDIR\README.txt"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Ver novedades de la version"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE       "..\FinanzasHogar\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Spanish"

; ── Sección principal de instalación ─────────────────────────────────────────
Section "Aplicacion principal" SecMain
  SectionIn RO   ; No se puede deseleccionar

  SetOutPath "$INSTDIR"

  ; Copiar todos los archivos del build de PyInstaller
  File /r "dist\FinanzasHogar\*.*"

  ; Copiar README como .txt plano para la pantalla de finalización
  File /oname=README.txt "..\FinanzasHogar\README.md"

  ; Crear acceso directo en el escritorio
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
    "$INSTDIR\${APP_EXE}" "" \
    "$INSTDIR\${APP_EXE}" 0 \
    SW_SHOWNORMAL "" "${APP_NAME} v${APP_VERSION}"

  ; Crear carpeta y acceso directo en el menú Inicio
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
    "$INSTDIR\${APP_EXE}" "" \
    "$INSTDIR\${APP_EXE}" 0 \
    SW_SHOWNORMAL "" "${APP_NAME} v${APP_VERSION}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\Desinstalar ${APP_NAME}.lnk" \
    "$INSTDIR\Uninstall.exe"

  ; Registrar en Agregar o quitar programas
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayName"      "${APP_NAME}"
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayVersion"   "${APP_VERSION}"
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "Publisher"        "${APP_PUBLISHER}"
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "URLInfoAbout"     "${APP_URL}"
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "InstallLocation"  "$INSTDIR"
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "UninstallString"  "$INSTDIR\Uninstall.exe"
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayIcon"      "$INSTDIR\${APP_EXE}"
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify"         1
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair"         1

  ; Crear desinstalador
  WriteUninstaller "$INSTDIR\Uninstall.exe"

SectionEnd

; ── Sección de desinstalación ─────────────────────────────────────────────────
Section "Uninstall"

  ; Eliminar archivos de la aplicación
  RMDir /r "$INSTDIR"

  ; Eliminar accesos directos
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APP_NAME}"

  ; Eliminar registro de Windows
  DeleteRegKey HKLM "${UNINSTALL_KEY}"

  ; Nota: los datos del usuario en %APPDATA% se preservan

SectionEnd
