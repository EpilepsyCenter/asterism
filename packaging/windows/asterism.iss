; Inno Setup script for the ASTERISM Windows installer.
;   iscc /DVersion=0.1.1 packaging\windows\asterism.iss     (after pyinstaller)
; Installs for the current user (no administrator rights needed), adds a Start menu entry,
; opens .asterism files with ASTERISM and offers it for .prism / .pzfx, with an uninstaller.

#ifndef Version
  #define Version "0.1.1"
#endif

[Setup]
AppId={{8D7AF439-95A7-4FFC-AD91-E7E075746090}
AppName=ASTERISM
AppVersion={#Version}
AppPublisher=ASTERISM contributors
AppPublisherURL=https://github.com/EpilepsyCenter/asterism
AppSupportURL=https://github.com/EpilepsyCenter/asterism/issues
AppUpdatesURL=https://github.com/EpilepsyCenter/asterism/releases
DefaultDirName={autopf}\ASTERISM
DefaultGroupName=ASTERISM
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ChangesAssociations=yes
OutputDir=..\..\dist
OutputBaseFilename=ASTERISM-{#Version}-windows-setup
SetupIconFile=..\..\asterism\app\assets\asterism.ico
UninstallDisplayIcon={app}\ASTERISM.exe
LicenseFile=..\..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\ASTERISM\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\ASTERISM"; Filename: "{app}\ASTERISM.exe"
Name: "{autodesktop}\ASTERISM"; Filename: "{app}\ASTERISM.exe"; Tasks: desktopicon

[Registry]
; .asterism projects open in ASTERISM
Root: HKA; Subkey: "Software\Classes\.asterism"; ValueType: string; ValueName: ""; ValueData: "ASTERISM.Project"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\ASTERISM.Project"; ValueType: string; ValueName: ""; ValueData: "ASTERISM Project"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\ASTERISM.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\ASTERISM.exe,0"
Root: HKA; Subkey: "Software\Classes\ASTERISM.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\ASTERISM.exe"" ""%1"""
; Prism files: offered under "Open with" (Prism stays the default if installed)
Root: HKA; Subkey: "Software\Classes\.prism\OpenWithProgids"; ValueType: string; ValueName: "ASTERISM.Project"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.pzfx\OpenWithProgids"; ValueType: string; ValueName: "ASTERISM.Project"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\ASTERISM.exe\SupportedTypes"; ValueType: string; ValueName: ".asterism"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\ASTERISM.exe\SupportedTypes"; ValueType: string; ValueName: ".prism"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\ASTERISM.exe\SupportedTypes"; ValueType: string; ValueName: ".pzfx"; ValueData: ""

[Run]
Filename: "{app}\ASTERISM.exe"; Description: "Start ASTERISM"; Flags: nowait postinstall skipifsilent
; in-app updates run this installer silently: start ASTERISM again afterwards
Filename: "{app}\ASTERISM.exe"; Flags: nowait skipifnotsilent
