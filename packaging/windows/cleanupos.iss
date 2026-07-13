; CleanupOs — Inno Setup stub (Inno Setup 6.x)
;
; This is a packaging skeleton only. Fill AppVersion, Source paths, and
; Authenticode SignTool settings before a real release build.
;
; Do NOT commit built installers or signing certificates to the repository.
;
; Safety: the installed app must keep the hardcoded denylist
; (core/safety/denylist.py). Never ship a build that loads forbidden-path
; lists from user config.

#define MyAppName "CleanupOs"
#define MyAppVersion "2.0.0-dev"
#define MyAppPublisher "YukaC"
#define MyAppURL "https://github.com/YukaC/cleanupDiskW11"
#define MyAppExeName "CleanupOs.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
; OutputDir=dist\installer
; OutputBaseFilename=CleanupOs-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; PrivilegesRequired=admin
; SignTool=signtool

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Replace Source with the PyInstaller (or equivalent) output directory.
; Source: "dist\CleanupOs\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
