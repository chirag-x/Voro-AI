[Setup]
AppName=Voro
AppVersion=1.3.0
DefaultDirName={pf}\Voro
DefaultGroupName=Voro
OutputDir=installer
OutputBaseFilename=Voro_Setup
SetupIconFile=logo.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Voro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Voro"; Filename: "{app}\Voro.exe"; IconFilename: "{app}\logo.ico"
Name: "{group}\{cm:UninstallProgram,Voro}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Voro"; Filename: "{app}\Voro.exe"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\Voro.exe"; Description: "{cm:LaunchProgram,Voro}"; Flags: nowait postinstall skipifsilent
