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
OutputBaseFilename=VeinServerManagement-Setup-v{#MyAppVersion}
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
Name: "{app}\Server"; Permissions: users-modify

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

[UninstallDelete]
Type: filesandordirs; Name: "{app}\Logs"
Type: filesandordirs; Name: "{app}\Runtime"
Type: filesandordirs; Name: "{app}\SteamCMD"
Type: dirifempty; Name: "{app}"

[Code]
var
  ServerChoicePage: TWizardPage;
  InstallServerRadio: TRadioButton;
  ExistingServerRadio: TRadioButton;
  ServerDirPage: TInputDirWizardPage;
  DataDirPage: TInputDirWizardPage;
  SteamCmdChoicePage: TWizardPage;
  AppSteamCmdRadio: TRadioButton;
  ExistingSteamCmdRadio: TRadioButton;
  NoSteamCmdRadio: TRadioButton;
  ExistingSteamCmdDirPage: TInputDirWizardPage;
  InstallServerBox: TNewStaticText;
  SteamCmdChoiceBox: TNewStaticText;
  InstallServer: Boolean;
  ConfigureSteamCmd: Boolean;
  UseExistingSteamCmd: Boolean;
  RemoveAppManagedServer: Boolean;
  RemoveBackups: Boolean;
  RemoveLocalConfig: Boolean;
  AppManagedServerDir: string;
  LastManagedServerDefault: string;
  LastSavesDefault: string;
  LastLogsDefault: string;

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

procedure UpdateSteamCmdChoiceState;
begin
  ConfigureSteamCmd := not NoSteamCmdRadio.Checked;
  UseExistingSteamCmd := ExistingSteamCmdRadio.Checked;
end;

procedure UpdateSteamCmdChoiceAvailability;
begin
  if not Assigned(AppSteamCmdRadio) then
    exit;

  AppSteamCmdRadio.Enabled := InstallServer;
  if (not InstallServer) and AppSteamCmdRadio.Checked then
  begin
    NoSteamCmdRadio.Checked := True;
    UpdateSteamCmdChoiceState;
  end;
end;

procedure ServerChoiceChanged(Sender: TObject);
begin
  UpdateServerChoiceState;
  if InstallServer and Assigned(AppSteamCmdRadio) then
    AppSteamCmdRadio.Checked := True
  else if Assigned(NoSteamCmdRadio) then
    NoSteamCmdRadio.Checked := True;
  UpdateSteamCmdChoiceState;
  UpdateSteamCmdChoiceAvailability;
  WizardForm.NextButton.Enabled := True;
end;

procedure SteamCmdChoiceChanged(Sender: TObject);
begin
  UpdateSteamCmdChoiceState;
  WizardForm.NextButton.Enabled := True;
end;

function CurrentAppDir(): string;
begin
  Result := WizardDirValue();
  if Result = '' then
    Result := ExpandConstant('{commonpf}\VeinServerManagement');
end;

function DefaultManagedServerDir(): string;
begin
  Result := AddBackslash(CurrentAppDir()) + 'Server';
end;

function DefaultSavesDir(): string;
begin
  Result := AddBackslash(AddBackslash(ServerDirPage.Values[0]) + 'Vein') + 'Saved\SaveGames';
end;

function DefaultLogsDir(): string;
begin
  Result := AddBackslash(AddBackslash(ServerDirPage.Values[0]) + 'Vein') + 'Saved\Logs';
end;

function DefaultAppSteamCmdDir(): string;
begin
  Result := AddBackslash(CurrentAppDir()) + 'SteamCMD';
end;

function SelectedSteamCmdExe(): string;
begin
  Result := '';
  if UseExistingSteamCmd then
    Result := AddBackslash(ExistingSteamCmdDirPage.Values[0]) + 'steamcmd.exe';
end;

procedure SyncManagedServerDefault;
var
  Current, NextDefault: string;
begin
  if not Assigned(ServerDirPage) then
    exit;

  Current := ServerDirPage.Values[0];
  NextDefault := DefaultManagedServerDir();

  if (Current = '') or
     ((LastManagedServerDefault <> '') and (CompareText(Current, LastManagedServerDefault) = 0)) or
     (CompareText(Current, ExpandConstant('{sd}\VeinServer')) = 0) then
  begin
    ServerDirPage.Values[0] := NextDefault;
  end;

  LastManagedServerDefault := NextDefault;
end;

procedure SyncDataPathDefaults;
var
  CurrentSaves, CurrentLogs, NextSaves, NextLogs: string;
begin
  if not Assigned(DataDirPage) then
    exit;

  CurrentSaves := DataDirPage.Values[0];
  CurrentLogs := DataDirPage.Values[1];
  NextSaves := DefaultSavesDir();
  NextLogs := DefaultLogsDir();

  if (CurrentSaves = '') or
     ((LastSavesDefault <> '') and (CompareText(CurrentSaves, LastSavesDefault) = 0)) then
    DataDirPage.Values[0] := NextSaves;

  if (CurrentLogs = '') or
     ((LastLogsDefault <> '') and (CompareText(CurrentLogs, LastLogsDefault) = 0)) then
    DataDirPage.Values[1] := NextLogs;

  LastSavesDefault := NextSaves;
  LastLogsDefault := NextLogs;
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
  InstallServerRadio.Height := ScaleY(26);
  InstallServerRadio.OnClick := @ServerChoiceChanged;

  ExistingServerRadio := TNewRadioButton.Create(ServerChoicePage.Surface);
  ExistingServerRadio.Parent := ServerChoicePage.Surface;
  ExistingServerRadio.Caption := 'Use an existing dedicated server folder';
  ExistingServerRadio.Checked := True;
  LayoutServerChoiceControl(ExistingServerRadio, InstallServerRadio.Top + InstallServerRadio.Height + ScaleY(10));
  ExistingServerRadio.Height := ScaleY(26);
  ExistingServerRadio.OnClick := @ServerChoiceChanged;

  InstallServerBox := TNewStaticText.Create(ServerChoicePage.Surface);
  InstallServerBox.Parent := ServerChoicePage.Surface;
  InstallServerBox.Caption :=
    'Choose an existing server folder, or let the installer download SteamCMD and install app {#SteamAppId}.';
  InstallServerBox.AutoSize := False;
  LayoutServerChoiceControl(InstallServerBox, ExistingServerRadio.Top + ExistingServerRadio.Height + ScaleY(16));
  InstallServerBox.Height := ScaleY(56);

  ServerDirPage := CreateInputDirPage(
    ServerChoicePage.ID,
    'Server Install Location',
    'Choose where the Vein dedicated server is or should be installed.',
    'Select the server root folder. SteamCMD installs use the app-managed Server folder by default. Existing servers can stay outside the app folder.',
    False,
    ''
  );
  ServerDirPage.Add('');
  LastManagedServerDefault := '';
  ServerDirPage.Values[0] := DefaultManagedServerDir();
  LastManagedServerDefault := ServerDirPage.Values[0];

  DataDirPage := CreateInputDirPage(
    ServerDirPage.ID,
    'Server Data Locations',
    'Choose where the management app should read saves and logs.',
    'These paths are used for monitoring and backups. Changing them does not move existing game save files.',
    False,
    ''
  );
  DataDirPage.Add('SaveGames folder:');
  DataDirPage.Add('Logs folder:');
  LastSavesDefault := '';
  LastLogsDefault := '';
  SyncDataPathDefaults;

  SteamCmdChoicePage := CreateCustomPage(
    DataDirPage.ID,
    'SteamCMD Location',
    'Choose whether to use app-managed SteamCMD or an existing SteamCMD install.'
  );

  AppSteamCmdRadio := TNewRadioButton.Create(SteamCmdChoicePage.Surface);
  AppSteamCmdRadio.Parent := SteamCmdChoicePage.Surface;
  AppSteamCmdRadio.Caption := 'Install or use app-managed SteamCMD inside the app folder';
  AppSteamCmdRadio.Checked := False;
  AppSteamCmdRadio.Left := ScaleX(0);
  AppSteamCmdRadio.Top := ScaleY(56);
  AppSteamCmdRadio.Width := SteamCmdChoicePage.SurfaceWidth;
  AppSteamCmdRadio.Height := ScaleY(26);
  AppSteamCmdRadio.OnClick := @SteamCmdChoiceChanged;

  ExistingSteamCmdRadio := TNewRadioButton.Create(SteamCmdChoicePage.Surface);
  ExistingSteamCmdRadio.Parent := SteamCmdChoicePage.Surface;
  ExistingSteamCmdRadio.Caption := 'Use an existing SteamCMD folder';
  ExistingSteamCmdRadio.Checked := False;
  ExistingSteamCmdRadio.Left := ScaleX(0);
  ExistingSteamCmdRadio.Top := AppSteamCmdRadio.Top + AppSteamCmdRadio.Height + ScaleY(10);
  ExistingSteamCmdRadio.Width := SteamCmdChoicePage.SurfaceWidth;
  ExistingSteamCmdRadio.Height := ScaleY(26);
  ExistingSteamCmdRadio.OnClick := @SteamCmdChoiceChanged;

  NoSteamCmdRadio := TNewRadioButton.Create(SteamCmdChoicePage.Surface);
  NoSteamCmdRadio.Parent := SteamCmdChoicePage.Surface;
  NoSteamCmdRadio.Caption := 'Do not configure SteamCMD now';
  NoSteamCmdRadio.Checked := True;
  NoSteamCmdRadio.Left := ScaleX(0);
  NoSteamCmdRadio.Top := ExistingSteamCmdRadio.Top + ExistingSteamCmdRadio.Height + ScaleY(10);
  NoSteamCmdRadio.Width := SteamCmdChoicePage.SurfaceWidth;
  NoSteamCmdRadio.Height := ScaleY(26);
  NoSteamCmdRadio.OnClick := @SteamCmdChoiceChanged;

  SteamCmdChoiceBox := TNewStaticText.Create(SteamCmdChoicePage.Surface);
  SteamCmdChoiceBox.Parent := SteamCmdChoicePage.Surface;
  SteamCmdChoiceBox.Caption :=
    'SteamCMD is portable. Use the app-managed copy for full package installs, or select an existing SteamCMD folder to avoid duplicates.';
  SteamCmdChoiceBox.AutoSize := False;
  SteamCmdChoiceBox.Left := ScaleX(0);
  SteamCmdChoiceBox.Top := NoSteamCmdRadio.Top + NoSteamCmdRadio.Height + ScaleY(20);
  SteamCmdChoiceBox.Width := SteamCmdChoicePage.SurfaceWidth - ScaleX(12);
  SteamCmdChoiceBox.Height := ScaleY(96);

  ExistingSteamCmdDirPage := CreateInputDirPage(
    SteamCmdChoicePage.ID,
    'Existing SteamCMD Folder',
    'Choose the folder that contains steamcmd.exe.',
    'The installer will use this SteamCMD to download or update the Vein dedicated server and will write the path into config.yaml.',
    False,
    ''
  );
  ExistingSteamCmdDirPage.Add('');
  UpdateServerChoiceState;
  UpdateSteamCmdChoiceState;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if Assigned(ServerDirPage) and (CurPageID = ServerDirPage.ID) and InstallServer then
    SyncManagedServerDefault;
  if Assigned(DataDirPage) and (CurPageID = DataDirPage.ID) then
    SyncDataPathDefaults;
  if Assigned(SteamCmdChoicePage) and (CurPageID = SteamCmdChoicePage.ID) then
    UpdateSteamCmdChoiceAvailability;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if Assigned(ExistingSteamCmdDirPage) and (PageID = ExistingSteamCmdDirPage.ID) then
    Result := not UseExistingSteamCmd;
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

function ValidateDataDirs: Boolean;
begin
  Result := True;
  if Trim(DataDirPage.Values[0]) = '' then
  begin
    MsgBox('Please choose the SaveGames folder used by the management app.', mbError, MB_OK);
    Result := False;
    exit;
  end;
  if Trim(DataDirPage.Values[1]) = '' then
  begin
    MsgBox('Please choose the Logs folder used by the management app.', mbError, MB_OK);
    Result := False;
    exit;
  end;
end;

function ValidateExistingSteamCmdDir: Boolean;
var
  SteamCmdExe: string;
begin
  Result := True;
  SteamCmdExe := AddBackslash(ExistingSteamCmdDirPage.Values[0]) + 'steamcmd.exe';
  if Trim(ExistingSteamCmdDirPage.Values[0]) = '' then
  begin
    MsgBox('Please choose the existing SteamCMD folder, or go Back and choose app-managed SteamCMD.', mbError, MB_OK);
    Result := False;
    exit;
  end;
  if not FileExists(SteamCmdExe) then
  begin
    MsgBox(
      'steamcmd.exe was not found in the selected folder:'#13#10#13#10 +
      SteamCmdExe,
      mbError,
      MB_OK
    );
    Result := False;
    exit;
  end;
end;

function ValidateSteamCmdChoice: Boolean;
begin
  Result := True;
  if InstallServer and (not ConfigureSteamCmd) then
  begin
    MsgBox('Choose app-managed SteamCMD or an existing SteamCMD folder to install the dedicated server.', mbError, MB_OK);
    Result := False;
    exit;
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
  end
  else if Assigned(DataDirPage) and (CurPageID = DataDirPage.ID) then
  begin
    Result := ValidateDataDirs;
  end
  else if Assigned(SteamCmdChoicePage) and (CurPageID = SteamCmdChoicePage.ID) then
  begin
    UpdateSteamCmdChoiceState;
    Result := ValidateSteamCmdChoice;
  end
  else if Assigned(ExistingSteamCmdDirPage) and (CurPageID = ExistingSteamCmdDirPage.ID) then
  begin
    Result := ValidateExistingSteamCmdDir;
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

function FileContainsText(const FileName: string; const Needle: AnsiString): Boolean;
var
  Content: AnsiString;
begin
  Result := False;
  if LoadStringFromFile(FileName, Content) then
    Result := Pos(Needle, Content) > 0;
end;

function PowerShellQuote(const Value: string): string;
begin
  Result := Value;
  StringChangeEx(Result, '''', '''''', True);
  Result := '''' + Result + '''';
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

function NormalizePathForCompare(const Value: string): string;
begin
  Result := Lowercase(Trim(Value));
  StringChangeEx(Result, '/', '\', True);
  while (Length(Result) > 3) and (Copy(Result, Length(Result), 1) = '\') do
    Delete(Result, Length(Result), 1);
end;

function IsPathInsideApp(const Value: string): Boolean;
var
  AppRoot, Candidate: string;
begin
  AppRoot := NormalizePathForCompare(ExpandConstant('{app}'));
  Candidate := NormalizePathForCompare(Value);
  Result :=
    (Candidate <> '') and
    (Candidate <> AppRoot) and
    (Pos(AppRoot + '\', Candidate) = 1);
end;

function LoadInstalledServerPath(var ServerDir: string): Boolean;
var
  RawContent: AnsiString;
begin
  Result := False;
  ServerDir := '';
  if LoadStringFromFile(ExpandConstant('{app}\Runtime\server_install_path.txt'), RawContent) then
  begin
    ServerDir := Trim(RawContent);
    Result := ServerDir <> '';
  end;
end;

procedure UpdateConfigPaths(const ServerDir, SavesDir, LogsDir, SteamCmdExe: string);
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
    if SavesDir <> '' then
      SavesPath := NormalizePathForYaml(SavesDir)
    else
      SavesPath := NormalizePathForYaml(DefaultSavesDir());
    if LogsDir <> '' then
      LogsPath := NormalizePathForYaml(LogsDir)
    else
      LogsPath := NormalizePathForYaml(DefaultLogsDir());
    LogFile := LogsPath + '/Vein.log';
    SteamCmdPath := NormalizePathForYaml(SteamCmdExe);

    ReplaceConfigValue(Content, '  server_root: "Server"', '  server_root: "' + ServerRoot + '"');
    ReplaceConfigValue(Content, '  saves_dir: "Server/Vein/Saved/SaveGames"', '  saves_dir: "' + SavesPath + '"');
    ReplaceConfigValue(Content, '  logs_dir: "Server/Vein/Saved/Logs"', '  logs_dir: "' + LogsPath + '"');
    ReplaceConfigValue(Content, '  absolute_log_file: "Server/Vein/Saved/Logs/Vein.log"', '  absolute_log_file: "' + LogFile + '"');
    if SteamCmdExe <> '' then
      ReplaceConfigValue(Content, '  steamcmd_path: "SteamCMD/steamcmd.exe"', '  steamcmd_path: "' + SteamCmdPath + '"')
    else
      ReplaceConfigValue(Content, '  steamcmd_path: "SteamCMD/steamcmd.exe"', '  steamcmd_path: ""');
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
  ServerDir, SteamCmdDir, SteamCmdExe, TempZip, ExtractDir, ExtractedSteamCmdExe, SteamCmdLog, DownloadCmd, ExtractCmd, InstallCmd: string;
  ResultCode: Integer;
begin
  ServerDir := ServerDirPage.Values[0];
  if ServerDir = '' then
    exit;
  ForceDirectories(ServerDir);

  if UseExistingSteamCmd then
  begin
    SteamCmdDir := ExistingSteamCmdDirPage.Values[0];
    SteamCmdExe := AddBackslash(SteamCmdDir) + 'steamcmd.exe';
  end
  else
  begin
    SteamCmdDir := DefaultAppSteamCmdDir();
    ForceDirectories(SteamCmdDir);
    SteamCmdExe := AddBackslash(SteamCmdDir) + 'steamcmd.exe';

    if not FileExists(SteamCmdExe) then
    begin
      TempZip := ExpandConstant('{tmp}\steamcmd.zip');
      ExtractDir := ExpandConstant('{tmp}\steamcmd_extract');
      DeleteFile(TempZip);
      DelTree(ExtractDir, True, True, True);

      SetStatus('Downloading SteamCMD from Valve...');
      DownloadCmd :=
        '$ProgressPreference=''SilentlyContinue''; ' +
        'Invoke-WebRequest -UseBasicParsing -Uri ' + PowerShellQuote('{#SteamCmdUrl}') + ' -OutFile ' + PowerShellQuote(TempZip) + '; ' +
        'if ((Get-Item ' + PowerShellQuote(TempZip) + ').Length -lt 1024) { throw ''Downloaded SteamCMD archive is too small.'' }';
      if not RunPowerShell(DownloadCmd) or (not FileExists(TempZip)) then
      begin
        MsgBox('Failed to download SteamCMD. Check your internet connection and try again.', mbError, MB_OK);
        exit;
      end;

      SetStatus('Extracting SteamCMD...');
      ExtractCmd :=
        'Add-Type -AssemblyName System.IO.Compression.FileSystem; ' +
        '[System.IO.Compression.ZipFile]::ExtractToDirectory(' + PowerShellQuote(TempZip) + ', ' + PowerShellQuote(ExtractDir) + ')';
      ExtractedSteamCmdExe := AddBackslash(ExtractDir) + 'steamcmd.exe';
      if (not RunPowerShell(ExtractCmd)) or (not FileExists(ExtractedSteamCmdExe)) then
      begin
        MsgBox('Failed to extract SteamCMD archive. The download may be blocked, incomplete, or not a valid ZIP file.', mbError, MB_OK);
        exit;
      end;

      CopyFile(ExtractedSteamCmdExe, SteamCmdExe, False);
    end;
  end;

  if not FileExists(SteamCmdExe) then
  begin
    MsgBox('SteamCMD executable not found: ' + SteamCmdExe, mbError, MB_OK);
    exit;
  end;

  SetStatus('Installing Vein dedicated server via SteamCMD. This can take several minutes...');
  SteamCmdLog := ExpandConstant('{app}\Logs\steamcmd-install.log');
  DeleteFile(SteamCmdLog);
  InstallCmd :=
    '/C ""' + SteamCmdExe + '" +@sSteamCmdForcePlatformType windows +force_install_dir "' + ServerDir + '" +login anonymous +app_update {#SteamAppId} -beta public validate +quit > "' + SteamCmdLog + '" 2>&1"';
  if (not Exec(
    ExpandConstant('{cmd}'),
    InstallCmd,
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  )) or ((ResultCode <> 0) and (not FileContainsText(SteamCmdLog, 'Success! App ''{#SteamAppId}'' fully installed.'))) then
  begin
    UpdateConfigPaths(ServerDir, DataDirPage.Values[0], DataDirPage.Values[1], SteamCmdExe);
    SaveServerInstallPath(ServerDir);
    MsgBox(
      'The management app was installed, but SteamCMD could not download the VEIN dedicated server.'#13#10#13#10 +
      'You can continue by choosing an existing server folder or rerunning the server install later.'#13#10#13#10 +
      'Installer log:'#13#10 +
      SteamCmdLog + #13#10#13#10 +
      'SteamCMD internal logs:'#13#10 +
      AddBackslash(SteamCmdDir) + 'logs',
      mbInformation,
      MB_OK
    );
    exit;
  end;

  SetStatus('Updating config paths to match the installed server...');
  UpdateConfigPaths(ServerDir, DataDirPage.Values[0], DataDirPage.Values[1], SteamCmdExe);
  SaveServerInstallPath(ServerDir);
end;

procedure ConfigureExistingServer;
var
  ServerDir, SteamCmdExe: string;
begin
  ServerDir := ServerDirPage.Values[0];
  if ServerDir = '' then
    exit;
  SetStatus('Updating config paths to match the selected server...');
  SteamCmdExe := SelectedSteamCmdExe();
  UpdateConfigPaths(ServerDir, DataDirPage.Values[0], DataDirPage.Values[1], SteamCmdExe);
  SaveServerInstallPath(ServerDir);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SaveStringToFile(ExpandConstant('{app}\version.txt'), '{#MyAppVersion}', False);
    if InstallServer then
      InstallDedicatedServer
    else
      ConfigureExistingServer;
  end;
end;

function InitializeUninstall(): Boolean;
var
  ServerDir: string;
begin
  Result := True;
  RemoveAppManagedServer := False;
  RemoveBackups := False;
  RemoveLocalConfig := False;
  AppManagedServerDir := '';

  if DirExists(ExpandConstant('{app}\Backups')) then
  begin
    RemoveBackups :=
      MsgBox(
        'Remove local Vein Server Management backups too?'#13#10#13#10 +
        ExpandConstant('{app}\Backups') + #13#10#13#10 +
        'Choose No to preserve backup files.',
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON2
      ) = IDYES;
  end;

  if DirExists(ExpandConstant('{app}\Config')) then
  begin
    RemoveLocalConfig :=
      MsgBox(
        'Remove local Vein Server Management config files too?'#13#10#13#10 +
        ExpandConstant('{app}\Config') + #13#10#13#10 +
        'Choose No to preserve local settings for a future reinstall.',
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON2
      ) = IDYES;
  end;

  if LoadInstalledServerPath(ServerDir) then
  begin
    if IsPathInsideApp(ServerDir) then
    begin
      AppManagedServerDir := ServerDir;
      RemoveAppManagedServer :=
        MsgBox(
          'The Vein dedicated server appears to be installed inside the app folder:'#13#10#13#10 +
          ServerDir + #13#10#13#10 +
          'Deleting it can permanently remove world saves, logs, SteamCMD data, and server files.'#13#10#13#10 +
          'Choose No to preserve all server data.'#13#10#13#10 +
          'Delete the app-managed Vein dedicated server folder too?',
          mbCriticalError,
          MB_YESNO or MB_DEFBUTTON2
        ) = IDYES;
    end
    else
    begin
      MsgBox(
        'The Vein dedicated server folder is outside the app install folder and will not be removed:'#13#10#13#10 +
        ServerDir + #13#10#13#10 +
        'The uninstaller will remove the management app only after stopping monitors/server processes.',
        mbInformation,
        MB_OK
      );
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and RemoveBackups then
  begin
    Log('Removing local backup folder: ' + ExpandConstant('{app}\Backups'));
    DelTree(ExpandConstant('{app}\Backups'), True, True, True);
  end;

  if (CurUninstallStep = usPostUninstall) and RemoveLocalConfig then
  begin
    Log('Removing local config folder: ' + ExpandConstant('{app}\Config'));
    DelTree(ExpandConstant('{app}\Config'), True, True, True);
  end;

  if (CurUninstallStep = usPostUninstall) and RemoveAppManagedServer and (AppManagedServerDir <> '') then
  begin
    Log('Removing app-managed Vein dedicated server folder: ' + AppManagedServerDir);
    DelTree(AppManagedServerDir, True, True, True);
  end;

  if CurUninstallStep = usPostUninstall then
    RemoveDir(ExpandConstant('{app}'));
end;
