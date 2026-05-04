#define MyAppName "Jarvis Launcher"
#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#define MyAppPublisher "Jarvis Launcher"
#define MyAppExeName "JarvisLauncher.exe"

[Setup]
AppId={{8E35F730-E474-4C0E-93B4-C66BA0E957D8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\JarvisLauncher
DefaultGroupName=Jarvis Launcher
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=JarvisLauncher-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startup"; Description: "Launch Jarvis when I sign in"; GroupDescription: "Windows integration:"

[Files]
Source: "dist\JarvisLauncher.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Jarvis Launcher"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall Jarvis Launcher"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Jarvis Launcher"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "JarvisLauncher"; ValueData: """{app}\{#MyAppExeName}"" --minimized"; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Jarvis Launcher"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#MyAppExeName} /F /T >nul 2>&1"; Flags: runhidden
Filename: "{cmd}"; Parameters: "/C reg delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v JarvisLauncher /f >nul 2>&1"; Flags: runhidden

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataDir: string;
  RemoveData: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    AppDataDir := ExpandConstant('{userappdata}\JarvisLauncher');
    if DirExists(AppDataDir) then
    begin
      RemoveData := MsgBox(
        'Do you want to remove user data as well?' + #13#10 + #13#10 +
        'This includes config, logs, backups, and launch history in:' + #13#10 +
        AppDataDir + #13#10 + #13#10 +
        'Select "No" to keep your data (recommended).',
        mbConfirmation, MB_YESNO);
      if RemoveData = IDYES then
        DelTree(AppDataDir, True, True, True);
    end;
  end;
end;
