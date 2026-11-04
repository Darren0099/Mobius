; User-level Mobius installer. Build Mobius.exe first.
#define AppName "Mobius"
#define AppVersion "0.7.0"
#define AppExe "Mobius.exe"

[Setup]
AppId={{2E3E507E-6F84-4628-B1DE-48AF4ABF8A72}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Mobius
DefaultDirName={localappdata}\Programs\Mobius
DefaultGroupName=Mobius
OutputDir=installer
OutputBaseFilename=Mobius-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a Desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "dist\Mobius.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Mobius"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\Mobius"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch Mobius"; Flags: nowait postinstall skipifsilent
