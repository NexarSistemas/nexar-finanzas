#define MyAppVersion "0.0.0"
#define MyAppExeName "NexarFinanzas.exe"

[Setup]
AppName=Nexar Finanzas
AppVersion={#MyAppVersion}
AppPublisher=Nexar Sistemas
DefaultDirName={pf}\NexarFinanzas
DefaultGroupName=Nexar Finanzas
OutputDir=dist_installer
OutputBaseFilename=NexarFinanzas_v{#MyAppVersion}_setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

; Permite instalación sin admin si querés cambiar luego
PrivilegesRequired=lowest

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; Copia TODO lo que generó PyInstaller
Source: "dist\NexarFinanzas\*"; DestDir: "{app}"; Flags: recursesubdirs

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Opciones:"; Flags: unchecked

[Icons]
Name: "{group}\Nexar Finanzas"; Filename: "{app}\NexarFinanzas.exe"
Name: "{commondesktop}\Nexar Finanzas"; Filename: "{app}\NexarFinanzas.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir Nexar Finanzas"; Flags: nowait postinstall skipifsilent
