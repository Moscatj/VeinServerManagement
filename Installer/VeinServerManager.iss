#define MyAppName "Vein Server Management Suite"
#ifndef MyAppVersion
#define MyAppVersion "0.0.0-dev"
#endif
#define MyAppPublisher "Vein Server Management Contributors"
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
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallFilesDir={app}\Uninstall
WizardStyle=modern
#ifexist "{#MyAppIcon}"
SetupIconFile={#MyAppIcon}
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#MyStageDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "Backups\*,Logs\*,Runtime\*"

[Dirs]
Name: "{app}\Backups"; Permissions: users-modify
Name: "{app}\Config"; Permissions: users-modify
Name: "{app}\Logs"; Permissions: users-modify
Name: "{app}\Runtime"; Permissions: users-modify
Name: "{app}\SteamCMD"; Permissions: users-modify

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

[UninstallRun]
Filename: "{app}\VeinTools.exe"; Parameters: "uninstall-cleanup"; WorkingDir: "{app}"; StatusMsg: "Stopping Vein server and monitors..."; Flags: runhidden skipifdoesntexist; RunOnceId: "VeinServerManagement.UninstallCleanup"

[Code]
var
  ServerChoicePage: TWizardPage;
  InstallServerRadio: TRadioButton;
  ExistingServerRadio: TRadioButton;
  ServerDirPage: TInputDirWizardPage;
  InstallServerBox: TNewStaticText;
  InstallServer: Boolean;

procedure LayoutServerChoiceControl(Control: TControl; Top: Integer);
begin
  Control.Left := ScaleX(0);
  Control.Top := Top;
  Control.Width := ServerChoicePage.SurfaceWidth;
end;

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
  InstallServerRadio.Caption := 'Install or update the dedicated server with SteamCMD';
  InstallServerRadio.Checked := False;
  LayoutServerChoiceControl(InstallServerRadio, ScaleY(56));
  InstallServerRadio.OnClick := @ServerChoiceChanged;

  ExistingServerRadio := TNewRadioButton.Create(ServerChoicePage.Surface);
  ExistingServerRadio.Parent := ServerChoicePage.Surface;
  ExistingServerRadio.Caption := 'Use an existing dedicated server folder';
  ExistingServerRadio.Checked := True;
  LayoutServerChoiceControl(ExistingServerRadio, InstallServerRadio.Top + InstallServerRadio.Height + ScaleY(10));
  ExistingServerRadio.OnClick := @ServerChoiceChanged;

  InstallServerBox := TNewStaticText.Create(ServerChoicePage.Surface);
  InstallServerBox.Parent := ServerChoicePage.Surface;
  InstallServerBox.Caption :=
    'Choose an existing server folder, or let the installer download SteamCMD and install app {#SteamAppId}.';
  InstallServerBox.AutoSize := False;
  InstallServerBox.Height := ScaleY(40);
  LayoutServerChoiceControl(InstallServerBox, ExistingServerRadio.Top + ExistingServerRadio.Height + ScaleY(16));

  ServerDirPage := CreateInputDirPage(
    ServerChoicePage.ID,
    'Server Install Location',
    'Choose where the Vein dedicated server is or should be installed.',
    'Select the server root folder. Choose the parent folder that contains Vein\Binaries\Win64, not the Vein folder itself.',
    False,
    ''
  );
  ServerDirPage.Add('');
  ServerDirPage.Values[0] := ExpandConstant('{sd}\VeinServer');
  UpdateServerChoiceState;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
end;

function ValidateServerDir: Boolean;
var
  ServerDir, ExeA, ExeB, NestedExeA, NestedExeB: string;
begin
  Result := True;
  ServerDir := ServerDirPage.Values[0];
  if ServerDir = '' then
  begin
    MsgBox('Please choose the dedicated server root folder.', mbError, MB_OK);
    Result := False;
    exit;
  end;

  NestedExeA := AddBackslash(ServerDir) + 'Binaries\Win64\VeinServer.exe';
  NestedExeB := AddBackslash(ServerDir) + 'Binaries\Win64\VeinServer-Win64-Test.exe';
  if FileExists(NestedExeA) or FileExists(NestedExeB) then
  begin
    MsgBox(
      'The selected folder appears to be the inner Vein game folder.'#13#10#13#10 +
      'Choose its parent folder instead. For example, choose:'#13#10 +
      ExtractFileDir(ServerDir) + #13#10#13#10 +
      'The management suite expects the server root to contain Vein\Binaries\Win64.',
      mbError,
      MB_OK
    );
    Result := False;
    exit;
  end;

  if InstallServer then
    exit;

  if not DirExists(ServerDir) then
  begin
    MsgBox(
      'The selected server folder does not exist. Choose an existing server folder, or go Back and choose the SteamCMD install option.',
      mbError,
      MB_OK
    );
    Result := False;
    exit;
  end;

  ExeA := AddBackslash(ServerDir) + 'Vein\Binaries\Win64\VeinServer.exe';
  ExeB := AddBackslash(ServerDir) + 'Vein\Binaries\Win64\VeinServer-Win64-Test.exe';
  if (not FileExists(ExeA)) and (not FileExists(ExeB)) then
  begin
    Result := MsgBox(
      'The selected folder does not appear to contain the Vein dedicated server executable.'#13#10#13#10 +
      'Expected one of:'#13#10 +
      ExeA + #13#10 +
      ExeB + #13#10#13#10 +
      'Use this folder anyway?',
      mbConfirmation,
      MB_YESNO
    ) = IDYES;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ServerChoicePage.ID then
  begin
    UpdateServerChoiceState;
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
  Result := Value;
  StringChangeEx(Result, '\', '/', True);
end;

procedure ReplaceConfigValue(var Content: string; const Needle, InsertValue: string);
begin
  StringChangeEx(Content, Needle, InsertValue, False);
end;

procedure UpdateConfigPaths(const ServerDir, SteamCmdExe: string);
var
  RawContent: AnsiString;
  ConfigPath, Content: string;
  ServerRoot, VeinRoot, SavesPath, LogsPath, LogFile, SteamCmdPath: string;
begin
  ConfigPath := ExpandConstant('{app}\Config\config.yaml');
  if LoadStringFromFile(ConfigPath, RawContent) then
  begin
    Content := RawContent;
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
    if SteamCmdExe <> '' then
      ReplaceConfigValue(Content, '  steamcmd_path: "ENV:STEAMCMD_PATH"', '  steamcmd_path: "' + SteamCmdPath + '"');
    SaveStringToFile(ConfigPath, Content, False);
  end;
end;

procedure SaveServerInstallPath(const ServerDir: string);
begin
  SaveStringToFile(
    ExpandConstant('{app}\Runtime\server_install_path.txt'),
    ServerDir,
    False
  );
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
  SteamCmdDir := ExpandConstant('{app}\SteamCMD');
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
  SaveServerInstallPath(ServerDir);
end;

procedure ConfigureExistingServer;
var
  ServerDir: string;
begin
  ServerDir := ServerDirPage.Values[0];
  if ServerDir = '' then
    exit;
  SetStatus('Updating config paths to match the selected server...');
  UpdateConfigPaths(ServerDir, '');
  SaveServerInstallPath(ServerDir);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if InstallServer then
      InstallDedicatedServer
    else
      ConfigureExistingServer;
  end;
end;
