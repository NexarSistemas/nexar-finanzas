; nexar_finanzas.nsi - Instalador NSIS para Nexar Finanzas (Windows)
;
; El instalador hace TODO automaticamente.
; El usuario final no necesita instalar nada extra:
;   - Detecta WebView2 Runtime y lo descarga/instala si falta (silencioso)
;   - Crea accesos directos en escritorio y menu inicio
;   - Registra el programa en Panel de Control > Programas

Unicode True

!define ROOT           ".."
!define APP_NAME       "Nexar Finanzas"
!define APP_VERSION    "1.10.3"
!define APP_PUBLISHER  "Nexar Sistemas"
!define APP_URL        "https://github.com/NexarSistemas"
!define APP_EXE        "NexarFinanzas.exe"
!define INSTALL_DIR    "$PROGRAMFILES64\NexarFinanzas"
!define UNINSTALL_KEY  "Software\Microsoft\Windows\CurrentVersion\Uninstall\NexarFinanzas"

; Claves de registro donde WebView2 Evergreen registra su instalacion
; (puede estar en HKLM o HKCU segun como se instalo)
!define WEBVIEW2_HKLM  "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
!define WEBVIEW2_HKLM2 "SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
!define WEBVIEW2_HKCU  "Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

Name               "${APP_NAME} v${APP_VERSION}"
OutFile            "${ROOT}\release\NexarFinanzas_v${APP_VERSION}_Setup.exe"
InstallDir         "${INSTALL_DIR}"
InstallDirRegKey   HKLM "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor      /SOLID lzma
SetCompressorDictSize 32

!include "MUI2.nsh"
!include "LogicLib.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON                   "${ROOT}\nexar_finanzas.ico"
!define MUI_UNICON                 "${ROOT}\nexar_finanzas.ico"
!define MUI_WELCOMEPAGE_TITLE      "Instalador de ${APP_NAME} v${APP_VERSION}"
!define MUI_WELCOMEPAGE_TEXT       "Este asistente instalara ${APP_NAME} en tu computadora.$\n$\nSe recomienda cerrar otras aplicaciones antes de continuar.$\n$\nSi es necesario, se instalara automaticamente un componente de Microsoft (WebView2 Runtime) requerido para la interfaz grafica."
!define MUI_FINISHPAGE_RUN         "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT    "Iniciar ${APP_NAME} ahora"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE      "${ROOT}\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Spanish"

; ── Funcion: verificar e instalar WebView2 si falta ───────────────────────────
; WebView2 Runtime es el motor que permite mostrar la interfaz nativa de la app.
; Ya viene incluido en Windows 11 y en equipos con Microsoft Edge actualizado.
; En Windows 10 sin Edge puede estar ausente — esta funcion lo resuelve solo.
Function InstallWebView2
    ; Verificar en HKLM (instalacion sistema)
    ReadRegStr $0 HKLM "${WEBVIEW2_HKLM}" "pv"
    ${If} $0 != ""
        DetailPrint "WebView2 Runtime ya instalado (v$0)."
        Return
    ${EndIf}

    ReadRegStr $0 HKLM "${WEBVIEW2_HKLM2}" "pv"
    ${If} $0 != ""
        DetailPrint "WebView2 Runtime ya instalado (v$0)."
        Return
    ${EndIf}

    ; Verificar en HKCU (instalacion por usuario)
    ReadRegStr $0 HKCU "${WEBVIEW2_HKCU}" "pv"
    ${If} $0 != ""
        DetailPrint "WebView2 Runtime ya instalado por el usuario (v$0)."
        Return
    ${EndIf}

    ; No encontrado: descargar bootstrapper de Microsoft (~2MB)
    DetailPrint "Descargando WebView2 Runtime de Microsoft..."
    DetailPrint "(Solo ocurre la primera instalacion. Por favor espera.)"
    SetDetailsPrint listonly

    StrCpy $0 "$TEMP\MicrosoftEdgeWebview2Setup.exe"

    NSISdl::download \
        "https://go.microsoft.com/fwlink/p/?LinkId=2124703" \
        "$0"
    Pop $1

    ${If} $1 != "success"
        SetDetailsPrint both
        MessageBox MB_ICONEXCLAMATION|MB_OK \
            "No se pudo descargar el componente WebView2 Runtime.$\n$\nVerifica tu conexion a internet.$\n$\nPodes instalarlo manualmente luego desde:$\nhttps://developer.microsoft.com/microsoft-edge/webview2/"
        Return
    ${EndIf}

    ; Instalar silenciosamente sin ventanas adicionales
    DetailPrint "Instalando WebView2 Runtime..."
    ExecWait '"$0" /silent /install' $1
    Delete "$0"

    ${If} $1 != 0
        SetDetailsPrint both
        MessageBox MB_ICONEXCLAMATION|MB_OK \
            "WebView2 Runtime no pudo instalarse automaticamente.$\n$\nPodes instalarlo manualmente desde:$\nhttps://developer.microsoft.com/microsoft-edge/webview2/$\n$\nLa aplicacion puede abrirse en el navegador hasta que este componente este instalado."
    ${Else}
        DetailPrint "WebView2 Runtime instalado correctamente."
    ${EndIf}

    SetDetailsPrint both
FunctionEnd

; ── Seccion principal ─────────────────────────────────────────────────────────
Section "Aplicacion principal" SecMain
    SectionIn RO

    SetOutPath "$INSTDIR"

    ; Copiar todos los archivos del build
    File /r "${ROOT}\dist\NexarFinanzas\*.*"

    ; README como .txt (abre con bloc de notas)
    File /oname=README.txt "${ROOT}\README.md"

    ; Instalar WebView2 si falta (transparente para el usuario)
    Call InstallWebView2

    ; Acceso directo en el escritorio
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_EXE}" "" \
        "$INSTDIR\${APP_EXE}" 0 \
        SW_SHOWNORMAL "" "${APP_NAME} v${APP_VERSION}"

    ; Menu inicio
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_EXE}" "" \
        "$INSTDIR\${APP_EXE}" 0 \
        SW_SHOWNORMAL "" "${APP_NAME} v${APP_VERSION}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\Desinstalar ${APP_NAME}.lnk" \
        "$INSTDIR\Uninstall.exe"

    ; Registro en Panel de Control > Programas
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayName"      "${APP_NAME}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayVersion"   "${APP_VERSION}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "Publisher"        "${APP_PUBLISHER}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "URLInfoAbout"     "${APP_URL}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "InstallLocation"  "$INSTDIR"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "UninstallString"  "$INSTDIR\Uninstall.exe"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayIcon"      "$INSTDIR\${APP_EXE}"
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify"         1
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair"         1

    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; ── Desinstalador ─────────────────────────────────────────────────────────────
Section "Uninstall"
    RMDir /r "$INSTDIR"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    RMDir /r "$SMPROGRAMS\${APP_NAME}"
    DeleteRegKey HKLM "${UNINSTALL_KEY}"
SectionEnd
