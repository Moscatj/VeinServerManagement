#define MyAppName "Vein Server Management Suite"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "Red Head Software"
#define MyAppExeName "VeinManager.exe"
#define MyStageDir "..\\dist\\VeinServerManager"
#define MyAppIcon "assets\\VeinServerManager.ico"
#define MyAppShortcutIcon "VeinServerManager.ico"
#define SteamCmdUrl "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
#define SteamAppId "2131400"

[Setup]
AppId={{2D6A61E2-0A8B-4F6B-9F8B-9912879D7499}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={commonpf}\VeinServerManagement
DefaultGroupName={#MyAppName}
OutputDir=..\dist\installer
OutputBaseFilename=VeinServerManagement-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayName={#MyAppName}
WizardStyle=modern
#ifexist "{#MyAppIcon}"
SetupIconFile={#MyAppIcon}
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#MyStageDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Vein Server Manager"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppShortcutIcon}"
Name: "{group}\Open Config Folder"; Filename: "{app}\Config"; WorkingDir: "{app}\Config"
Name: "{group}\Docs"; Filename: "{app}\Docs"; WorkingDir: "{app}\Docs"
Name: "{group}\Uninstall Vein Server Management"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Vein Server Manager"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppShortcutIcon}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Vein Server Manager"; Flags: nowait postinstall skipifsilent

[Code]
var
  ServerChoicePage: TWizardPage;
  InstallServerRadio: TRadioButton;
  ExistingServerRadio: TRadioButton;
  ServerDirPage: TInputDirWizardPage;
  InstallServerBox: TNewStaticText;
  InstallServer: Boolean;

procedure UpdateServerChoiceState;
begin
  InstallServer := InstallServerRadio.Checked;
end;

procedure ServerChoiceChanged(Sender: TObject);
begin
  UpdateServerChoiceState;
  WizardForm.NextButton.Enabled := True;
end;

procedure InitializeWizard;
begin
  ServerChoicePage := CreateCustomPage(
    wpSelectDir,
    'Dedicated Server Files',
    'Install the Vein dedicated server with SteamCMD?'
  );

  InstallServerRadio := TNewRadioButton.Create(ServerChoicePage.Surface);
  InstallServerRadio.Parent := ServerChoicePage.Surface;
  InstallServerRadio.Caption :=
    'Install or update the Vein dedicated server using SteamCMD (Windows only)';
  InstallServerRadio.Checked := False;
  InstallServerRadio.OnClick := @ServerChoiceChanged;

  ExistingServerRadio := TNewRadioButton.Create(ServerChoicePage.Surface);
  ExistingServerRadio.Parent := ServerChoicePage.Surface;
  ExistingServerRadio.Caption :=
    'Skip (I already have the dedicated server installed)';
  ExistingServerRadio.Checked := True;
  ExistingServerRadio.Top := InstallServerRadio.Top + InstallServerRadio.Height + ScaleY(8);
  ExistingServerRadio.OnClick := @ServerChoiceChanged;

  InstallServerBox := TNewStaticText.Create(ServerChoicePage.Surface);
  InstallServerBox.Parent := ServerChoicePage.Surface;
  InstallServerBox.Caption :=
    'The installer can optionally download SteamCMD from Valve and install app {#SteamAppId}.';
  InstallServerBox.AutoSize := False;
  InstallServerBox.Width := ServerChoicePage.SurfaceWidth;
  InstallServerBox.Top := ExistingServerRadio.Top + ExistingServerRadio.Height + ScaleY(8);

  ServerDirPage := CreateInputDirPage(
    ServerChoicePage.ID,
    'Server Install Location',
    'Choose where the Vein dedicated server should be installed.',
    'Select an existing folder or create a new one. It must be writable.'
  );
  ServerDirPage.Add('');
  ServerDirPage.Values[0] := ExpandConstant('{sd}\VeinServer');
  ServerDirPage.Visible := False;
  UpdateServerChoiceState;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if Assigned(ServerDirPage) and (PageID = ServerDirPage.ID) then
    Result := not InstallServer;
end;

function ValidateServerDir: Boolean;
begin
  Result := True;
  if InstallServer then
  begin
    if ServerDirPage.Values[0] = '' then
    begin
      MsgBox('Please choose a folder for the dedicated server files.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ServerChoicePage.ID then
  begin
    Result := ValidateServerDir;
  end
  else if Assigned(ServerDirPage) and (CurPageID = ServerDirPage.ID) then
  begin
    Result := ValidateServerDir;
  end;
end;

procedure SetStatus(const Msg: string);
begin
  WizardForm.StatusLabel.Caption := Msg;
  Log(Msg);
end;

function RunPowerShell(const Command: string): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(
    'powershell.exe',
    '-NoLogo -NonInteractive -ExecutionPolicy Bypass -Command ' + AddQuotes(Command),
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
  Result := Result and (ResultCode = 0);
end;

function NormalizePathForYaml(const Value: string): string;
begin
  Result := StringChange(Value, '\', '/');
end;

procedure ReplaceConfigValue(var Content: string; const Needle, InsertValue: string);
begin
  StringChangeEx(Content, Needle, InsertValue, False);
end;

procedure UpdateConfigPaths(const ServerDir, SteamCmdExe: string);
var
  ConfigPath, Content: string;
  ServerRoot, VeinRoot, SavesPath, LogsPath, LogFile, SteamCmdPath: string;
begin
  ConfigPath := ExpandConstant('{app}\Config\config.yaml');
  if LoadStringFromFile(ConfigPath, Content) then
  begin
    ServerRoot := NormalizePathForYaml(ServerDir);
    VeinRoot := NormalizePathForYaml(AddBackslash(ServerDir) + 'Vein');
    SavesPath := NormalizePathForYaml(AddBackslash(AddBackslash(ServerDir) + 'Vein') + 'Saved\SaveGames');
    LogsPath := NormalizePathForYaml(AddBackslash(AddBackslash(ServerDir) + 'Vein') + 'Saved\Logs');
    LogFile := NormalizePathForYaml(AddBackslash(AddBackslash(ServerDir) + 'Vein') + 'Saved\Logs\Vein.log');
    SteamCmdPath := NormalizePathForYaml(SteamCmdExe);

    ReplaceConfigValue(Content, '  server_root: ".."', '  server_root: "' + ServerRoot + '"');
    ReplaceConfigValue(Content, '  saves_dir: "../Vein/Saved/SaveGames"', '  saves_dir: "' + SavesPath + '"');
    ReplaceConfigValue(Content, '  logs_dir: "../Vein/Saved/Logs"', '  logs_dir: "' + LogsPath + '"');
    ReplaceConfigValue(Content, '  absolute_log_file: "../Vein/Saved/Logs/Vein.log"', '  absolute_log_file: "' + LogFile + '"');
    ReplaceConfigValue(Content, '  steamcmd_path: "C:/SteamCMD/steamcmd.exe"', '  steamcmd_path: "' + SteamCmdPath + '"');
    SaveStringToFile(ConfigPath, Content, False);
  end;
end;

procedure InstallDedicatedServer;
var
  ServerDir, SteamCmdDir, SteamCmdExe, TempZip, DownloadCmd, ExtractCmd, InstallCmd: string;
  ResultCode: Integer;
begin
  ServerDir := ServerDirPage.Values[0];
  if ServerDir = '' then
    exit;
  ForceDirectories(ServerDir);
  SteamCmdDir := AddBackslash(ServerDir) + 'SteamCMD';
  ForceDirectories(SteamCmdDir);

  TempZip := ExpandConstant('{tmp}\steamcmd.zip');
  DeleteFile(TempZip);

  SetStatus('Downloading SteamCMD from Valve...');
  DownloadCmd :=
    '$ProgressPreference="SilentlyContinue"; Invoke-WebRequest -Uri "{#SteamCmdUrl}" -OutFile "' + TempZip + '"';
  if not RunPowerShell(DownloadCmd) or (not FileExists(TempZip)) then
  begin
    MsgBox('Failed to download SteamCMD. Check your internet connection and try again.', mbError, MB_OK);
    exit;
  end;

  SetStatus('Extracting SteamCMD...');
  ExtractCmd := 'Expand-Archive -Path "' + TempZip + '" -DestinationPath "' + SteamCmdDir + '" -Force';
  if not RunPowerShell(ExtractCmd) then
  begin
    MsgBox('Failed to extract SteamCMD archive.', mbError, MB_OK);
    exit;
  end;

  SteamCmdExe := AddBackslash(SteamCmdDir) + 'steamcmd.exe';
  if not FileExists(SteamCmdExe) then
  begin
    MsgBox('SteamCMD executable not found after extraction.', mbError, MB_OK);
    exit;
  end;

  SetStatus('Installing Vein dedicated server via SteamCMD...');
  InstallCmd :=
    '+force_install_dir "' + ServerDir + '" +login anonymous +app_update {#SteamAppId} validate +quit';
  if not Exec(
    SteamCmdExe,
    InstallCmd,
    '',
    SW_SHOW,
    ewWaitUntilTerminated,
    ResultCode
  ) or (ResultCode <> 0) then
  begin
    MsgBox('SteamCMD installation failed. Check the log window for details.', mbError, MB_OK);
    exit;
  end;

  SetStatus('Updating config paths to match the installed server...');
  UpdateConfigPaths(ServerDir, SteamCmdExe);
  SaveStringToFile(
    ExpandConstant('{app}\Runtime\server_install_path.txt'),
    ServerDir,
    False
  );
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssInstall) and InstallServer then
  begin
    InstallDedicatedServer;
  end;
end;
