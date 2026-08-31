#define MyAppName "Artboard Cutter"
#include "version.iss"
#define MyAppPublisher "Artboard Cutter"
#define MyAppExeName "ArtboardCutter.exe"

[Setup]
AppId={{A75D242E-FE4F-4F65-A90D-12F43A7EA644}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Artboard Cutter
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=ArtboardCutter-{#MyAppVersion}-Setup
SetupIconFile=..\assets\artboard_cutter.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesAssociations=yes
LicenseFile=..\LICENSE
AppPublisherURL=https://github.com/0Thirteenth0/Arboard
AppSupportURL=https://github.com/0Thirteenth0/Arboard/issues
AppUpdatesURL=https://github.com/0Thirteenth0/Arboard/releases/latest

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\NOTICE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Registry]
Root: HKA; Subkey: "Software\Classes\.artboard-job"; ValueType: string; ValueName: ""; ValueData: "ArtboardCutter.Job"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\ArtboardCutter.Job"; ValueType: string; ValueName: ""; ValueData: "Artboard Cutter Job"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\ArtboardCutter.Job\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\ArtboardCutter.Job\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
