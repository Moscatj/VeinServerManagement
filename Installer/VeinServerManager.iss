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
CloseApplications=yes
RestartApplications=no
CloseApplicationsFilter=VeinManager.exe,VeinTools.exe
#ifexist "{#MyAppIcon}"
SetupIconFile={#MyAppIcon}
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#MyStageDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "Backups\*,Logs\*,Runtime\*,Config\config.yaml"
Source: "{#MyStageDir}\Config\config.yaml"; DestDir: "{app}\Config"; Flags: onlyifdoesntexist uninsneveruninstall

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
  InstallIntentPage: TWizardPage;
  PrimaryIntentRadio: TRadioButton;
  AlternateIntentRadio: TRadioButton;
  InstallIntentBox: TNewStaticText;
  ServerChoicePage: TWizardPage;
  InstallServerRadio: TRadioButton;
  ExistingServerRadio: TRadioButton;
  ServerDirPage: TInputDirWizardPage;
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
  ExistingAppInstall: Boolean;
  ExistingAppVersion: string;
  PreviousServerDir: string;
  PreviousSteamCmdExe: string;
  SetupNewServer: Boolean;
  PreserveExistingServerConfig: Boolean;

procedure LayoutIntentControl(Control: TControl; Top: Integer);
begin
  Control.Left := ScaleX(0);
  Control.Top := Top;
  Control.Width := InstallIntentPage.SurfaceWidth;
end;

procedure LayoutServerChoiceControl(Control: TControl; Top: Integer);
begin
  Control.Left := ScaleX(0);
  Control.Top := Top;
  Control.Width := ServerChoicePage.SurfaceWidth;
end;

procedure UpdateServerChoiceState;
begin
  if ExistingAppInstall and (not SetupNewServer) then
  begin
    InstallServer := InstallServerRadio.Checked;
    PreserveExistingServerConfig := ExistingServerRadio.Checked;
  end;
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

function CurrentAppDir(): string; forward;
function DefaultManagedServerDir(): string; forward;
function NormalizePathForCompare(const Value: string): string; forward;

function DefaultSeparateServerDir(): string;
var
  BaseDir: string;
  Suffix: Integer;
begin
  BaseDir := AddBackslash(CurrentAppDir()) + 'Server-New';
  Result := BaseDir;
  Suffix := 2;
  while DirExists(Result) do
  begin
    Result := BaseDir + '-' + IntToStr(Suffix);
    Suffix := Suffix + 1;
  end;
end;

procedure ApplyIntentState;
begin
  if ExistingAppInstall then
    SetupNewServer := AlternateIntentRadio.Checked
  else
    SetupNewServer := PrimaryIntentRadio.Checked;

  PreserveExistingServerConfig := ExistingAppInstall and (not SetupNewServer);
  if SetupNewServer then
    InstallServer := True
  else if ExistingAppInstall then
    InstallServer := Assigned(InstallServerRadio) and InstallServerRadio.Checked
  else
    InstallServer := False;

  if Assigned(ServerDirPage) then
  begin
    if ExistingAppInstall and SetupNewServer then
      ServerDirPage.Values[0] := DefaultSeparateServerDir()
    else if (PreviousServerDir <> '') then
      ServerDirPage.Values[0] := PreviousServerDir
    else
      ServerDirPage.Values[0] := DefaultManagedServerDir();
    LastManagedServerDefault := ServerDirPage.Values[0];
  end;

  if Assigned(AppSteamCmdRadio) then
  begin
    if InstallServer and (PreviousSteamCmdExe <> '') and FileExists(PreviousSteamCmdExe) then
    begin
      ExistingSteamCmdRadio.Checked := True;
      ExistingSteamCmdDirPage.Values[0] := ExtractFileDir(PreviousSteamCmdExe);
      AppSteamCmdRadio.Checked := False;
      NoSteamCmdRadio.Checked := False;
    end
    else if InstallServer then
    begin
      AppSteamCmdRadio.Checked := True;
      ExistingSteamCmdRadio.Checked := False;
      NoSteamCmdRadio.Checked := False;
    end
    else
    begin
      NoSteamCmdRadio.Checked := True;
      AppSteamCmdRadio.Checked := False;
      ExistingSteamCmdRadio.Checked := False;
    end;
    UpdateSteamCmdChoiceState;
    UpdateSteamCmdChoiceAvailability;
  end;
end;

procedure InstallIntentChanged(Sender: TObject);
begin
  ApplyIntentState;
  WizardForm.NextButton.Enabled := True;
end;

procedure ServerChoiceChanged(Sender: TObject);
begin
  UpdateServerChoiceState;
  if InstallServer and Assigned(AppSteamCmdRadio) then
  begin
    if (PreviousSteamCmdExe <> '') and FileExists(PreviousSteamCmdExe) and
       Assigned(ExistingSteamCmdRadio) and Assigned(ExistingSteamCmdDirPage) then
    begin
      ExistingSteamCmdRadio.Checked := True;
      ExistingSteamCmdDirPage.Values[0] := ExtractFileDir(PreviousSteamCmdExe);
    end
    else
      AppSteamCmdRadio.Checked := True;
  end
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

function LoadTrimmedFile(const FileName: string; var Value: string): Boolean;
var
  RawContent: AnsiString;
begin
  Result := LoadStringFromFile(FileName, RawContent);
  if Result then
  begin
    Value := Trim(RawContent);
    Result := Value <> '';
  end;
end;

function ReadYamlScalar(const FileName, Key: string; var Value: string): Boolean;
var
  Lines: TArrayOfString;
  I, Separator: Integer;
  Line: string;
begin
  Result := False;
  Value := '';
  if not LoadStringsFromFile(FileName, Lines) then
    exit;

  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    Line := Trim(Lines[I]);
    Separator := Pos(':', Line);
    if (Separator > 0) and (CompareText(Trim(Copy(Line, 1, Separator - 1)), Key) = 0) then
    begin
      Value := Trim(Copy(Line, Separator + 1, MaxInt));
      if (Length(Value) >= 2) and (Value[1] = '"') and (Value[Length(Value)] = '"') then
        Value := Copy(Value, 2, Length(Value) - 2);
      Result := Value <> '';
      exit;
    end;
  end;
end;

procedure DetectExistingInstall;
var
  AppDir, ConfigPath, Candidate: string;
begin
  AppDir := CurrentAppDir();
  ExistingAppInstall :=
    FileExists(AddBackslash(AppDir) + '{#MyAppExeName}') or
    FileExists(AddBackslash(AppDir) + 'VeinTools.exe') or
    FileExists(AddBackslash(AppDir) + 'version.txt') or
    FileExists(AddBackslash(AppDir) + 'Config\config.yaml');
  ExistingAppVersion := '';
  PreviousServerDir := '';
  PreviousSteamCmdExe := '';

  if not ExistingAppInstall then
    exit;

  LoadTrimmedFile(AddBackslash(AppDir) + 'version.txt', ExistingAppVersion);
  if ExistingAppVersion = '' then
    ExistingAppVersion := 'unknown';
  LoadTrimmedFile(AddBackslash(AppDir) + 'Runtime\server_install_path.txt', PreviousServerDir);
  ConfigPath := AddBackslash(AppDir) + 'Config\config.yaml';
  if ReadYamlScalar(ConfigPath, 'steamcmd_path', Candidate) then
  begin
    StringChangeEx(Candidate, '/', '\', True);
    if FileExists(Candidate) then
      PreviousSteamCmdExe := Candidate
    else if FileExists(AddBackslash(AppDir) + Candidate) then
      PreviousSteamCmdExe := AddBackslash(AppDir) + Candidate;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  ToolPath: string;
begin
  Result := '';
  if not ExistingAppInstall then
    exit;

  ToolPath := AddBackslash(CurrentAppDir()) + 'VeinTools.exe';
  if FileExists(ToolPath) then
    Exec(
      ToolPath,
      'stop-all-monitors',
      CurrentAppDir(),
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    );
end;

procedure SyncManagedServerDefault;
var
  Current, NextDefault: string;
begin
  if not Assigned(ServerDirPage) then
    exit;

  Current := ServerDirPage.Values[0];
  if ExistingAppInstall and SetupNewServer then
    NextDefault := DefaultSeparateServerDir()
  else
    NextDefault := DefaultManagedServerDir();

  if (Current = '') or
     ((LastManagedServerDefault <> '') and (CompareText(Current, LastManagedServerDefault) = 0)) or
     (CompareText(Current, ExpandConstant('{sd}\VeinServer')) = 0) then
  begin
    ServerDirPage.Values[0] := NextDefault;
  end;

  LastManagedServerDefault := NextDefault;
end;

procedure InitializeWizard;
begin
  DetectExistingInstall;

  InstallIntentPage := CreateCustomPage(
    wpWelcome,
    'Choose What Setup Should Do',
    'Select the installation goal for this computer.'
  );

  PrimaryIntentRadio := TNewRadioButton.Create(InstallIntentPage.Surface);
  PrimaryIntentRadio.Parent := InstallIntentPage.Surface;
  if ExistingAppInstall then
    PrimaryIntentRadio.Caption :=
      'Update or repair the existing installation (recommended)'
  else
    PrimaryIntentRadio.Caption :=
      'Install the management app and a new Vein dedicated server (recommended)';
  PrimaryIntentRadio.Checked := True;
  LayoutIntentControl(PrimaryIntentRadio, ScaleY(48));
  PrimaryIntentRadio.Height := ScaleY(28);
  PrimaryIntentRadio.OnClick := @InstallIntentChanged;

  AlternateIntentRadio := TNewRadioButton.Create(InstallIntentPage.Surface);
  AlternateIntentRadio.Parent := InstallIntentPage.Surface;
  if ExistingAppInstall then
    AlternateIntentRadio.Caption :=
      'Update the management app and set up a new server in a different folder'
  else
    AlternateIntentRadio.Caption :=
      'Install the management app and connect it to an existing Vein server';
  AlternateIntentRadio.Checked := False;
  LayoutIntentControl(AlternateIntentRadio, PrimaryIntentRadio.Top + PrimaryIntentRadio.Height + ScaleY(12));
  AlternateIntentRadio.Height := ScaleY(28);
  AlternateIntentRadio.OnClick := @InstallIntentChanged;

  InstallIntentBox := TNewStaticText.Create(InstallIntentPage.Surface);
  InstallIntentBox.Parent := InstallIntentPage.Surface;
  if ExistingAppInstall then
    InstallIntentBox.Caption :=
      'Detected version ' + ExistingAppVersion + ' in:'#13#10 +
      CurrentAppDir() + #13#10#13#10 +
      'Setup will install version {#MyAppVersion}. Update/Repair preserves local configuration, backups, runtime state, server data, and the current server selection. The new-server option keeps the existing server files but changes this management installation to manage the newly installed server.'
  else
    InstallIntentBox.Caption :=
      'A new installation can download SteamCMD and the Vein server automatically. If the server is already installed, Setup can connect the management app to its existing root folder.';
  InstallIntentBox.AutoSize := False;
  LayoutIntentControl(InstallIntentBox, AlternateIntentRadio.Top + AlternateIntentRadio.Height + ScaleY(18));
  InstallIntentBox.Height := ScaleY(112);

  ServerChoicePage := CreateCustomPage(
    wpSelectDir,
    'Existing Server Maintenance',
    'Choose whether the existing Vein server should also be updated or repaired.'
  );

  InstallServerRadio := TNewRadioButton.Create(ServerChoicePage.Surface);
  InstallServerRadio.Parent := ServerChoicePage.Surface;
  InstallServerRadio.Caption := 'Update or repair the existing dedicated server with SteamCMD';
  InstallServerRadio.Checked := False;
  LayoutServerChoiceControl(InstallServerRadio, ScaleY(56));
  InstallServerRadio.Height := ScaleY(26);
  InstallServerRadio.OnClick := @ServerChoiceChanged;

  ExistingServerRadio := TNewRadioButton.Create(ServerChoicePage.Surface);
  ExistingServerRadio.Parent := ServerChoicePage.Surface;
  ExistingServerRadio.Caption := 'Leave the existing dedicated server unchanged (recommended)';
  ExistingServerRadio.Checked := True;
  LayoutServerChoiceControl(ExistingServerRadio, InstallServerRadio.Top + InstallServerRadio.Height + ScaleY(10));
  ExistingServerRadio.Height := ScaleY(26);
  ExistingServerRadio.OnClick := @ServerChoiceChanged;

  InstallServerBox := TNewStaticText.Create(ServerChoicePage.Surface);
  InstallServerBox.Parent := ServerChoicePage.Surface;
  InstallServerBox.Caption :=
    'The management app update does not require a game-server update. Leave the server unchanged for the quickest repair, or select SteamCMD maintenance to validate and refresh app {#SteamAppId} after a controlled shutdown.';
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
  if PreviousServerDir <> '' then
    ServerDirPage.Values[0] := PreviousServerDir;
  LastManagedServerDefault := ServerDirPage.Values[0];

  SteamCmdChoicePage := CreateCustomPage(
    ServerDirPage.ID,
    'SteamCMD Location',
    'Choose whether to use app-managed SteamCMD or an existing SteamCMD install.'
  );

  AppSteamCmdRadio := TNewRadioButton.Create(SteamCmdChoicePage.Surface);
  AppSteamCmdRadio.Parent := SteamCmdChoicePage.Surface;
  AppSteamCmdRadio.Caption := 'Install or use app-managed SteamCMD inside the app folder';
  AppSteamCmdRadio.Checked := True;
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
  NoSteamCmdRadio.Checked := False;
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
  if (PreviousSteamCmdExe <> '') and FileExists(PreviousSteamCmdExe) then
  begin
    ExistingSteamCmdDirPage.Values[0] := ExtractFileDir(PreviousSteamCmdExe);
    ExistingSteamCmdRadio.Checked := True;
    AppSteamCmdRadio.Checked := False;
    NoSteamCmdRadio.Checked := False;
  end
  else if ExistingAppInstall then
  begin
    NoSteamCmdRadio.Checked := True;
    AppSteamCmdRadio.Checked := False;
  end;
  ApplyIntentState;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if Assigned(InstallIntentPage) and (CurPageID = InstallIntentPage.ID) then
    ApplyIntentState;
  if Assigned(ServerDirPage) and (CurPageID = ServerDirPage.ID) then
  begin
    if InstallServer then
    begin
      ServerDirPage.Caption := 'New or Maintained Server Location';
      ServerDirPage.Description := 'Choose the dedicated server root that SteamCMD should install, update, or repair.';
      SyncManagedServerDefault;
    end
    else
    begin
      ServerDirPage.Caption := 'Existing Server Location';
      ServerDirPage.Description := 'Choose the root folder of the existing Vein dedicated server.';
    end;
  end;
  if Assigned(SteamCmdChoicePage) and (CurPageID = SteamCmdChoicePage.ID) then
    UpdateSteamCmdChoiceAvailability;
  if CurPageID = wpReady then
  begin
    if ExistingAppInstall and SetupNewServer then
    begin
      WizardForm.PageNameLabel.Caption := 'Ready to Update the App and Install a New Server';
      WizardForm.PageDescriptionLabel.Caption := 'The existing management app will be refreshed and a separate Vein server will be installed.';
    end
    else if ExistingAppInstall and InstallServer then
    begin
      WizardForm.PageNameLabel.Caption := 'Ready to Update or Repair the App and Server';
      WizardForm.PageDescriptionLabel.Caption := 'The management app and selected Vein server will both receive maintenance.';
    end
    else if ExistingAppInstall then
    begin
      WizardForm.PageNameLabel.Caption := 'Ready to Update or Repair the Management App';
      WizardForm.PageDescriptionLabel.Caption := 'The existing server configuration and server files will be left unchanged.';
    end
    else if InstallServer then
    begin
      WizardForm.PageNameLabel.Caption := 'Ready to Install the App and Vein Server';
      WizardForm.PageDescriptionLabel.Caption := 'Setup will install the management app and download the dedicated server.';
    end
    else
    begin
      WizardForm.PageNameLabel.Caption := 'Ready to Install and Connect';
      WizardForm.PageDescriptionLabel.Caption := 'Setup will install the management app and connect it to the selected server.';
    end;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = wpSelectDir then
    Result := ExistingAppInstall
  else if Assigned(ServerChoicePage) and (PageID = ServerChoicePage.ID) then
    Result := (not ExistingAppInstall) or SetupNewServer
  else if Assigned(ServerDirPage) and (PageID = ServerDirPage.ID) then
    Result := PreserveExistingServerConfig
  else if Assigned(SteamCmdChoicePage) and (PageID = SteamCmdChoicePage.ID) then
    Result := not InstallServer
  else if Assigned(ExistingSteamCmdDirPage) and (PageID = ExistingSteamCmdDirPage.ID) then
    Result := (not InstallServer) or (not UseExistingSteamCmd);
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
  ExeA := AddBackslash(ServerDir) + 'Vein\Binaries\Win64\VeinServer.exe';
  ExeB := AddBackslash(ServerDir) + 'Vein\Binaries\Win64\VeinServer-Win64-Test.exe';
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
  begin
    if ExistingAppInstall and SetupNewServer and
       (NormalizePathForCompare(ServerDir) = NormalizePathForCompare(PreviousServerDir)) then
    begin
      MsgBox(
        'Choose a different folder for the new server. The selected folder is the server already managed by this installation.',
        mbError,
        MB_OK
      );
      Result := False;
      exit;
    end;
    if SetupNewServer and (FileExists(ExeA) or FileExists(ExeB)) then
    begin
      MsgBox(
        'The new-server folder already contains a Vein dedicated server. Choose an empty or new folder so existing server files are not repurposed accidentally.',
        mbError,
        MB_OK
      );
      Result := False;
    end;
    exit;
  end;

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
  if CurPageID = InstallIntentPage.ID then
  begin
    ApplyIntentState;
  end
  else if CurPageID = ServerChoicePage.ID then
  begin
    UpdateServerChoiceState;
  end
  else if Assigned(ServerDirPage) and (CurPageID = ServerDirPage.ID) then
  begin
    Result := ValidateServerDir;
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

procedure UpdateConfigPaths(const ServerDir, SteamCmdExe: string);
var
  RawContent: AnsiString;
  ConfigPath, Content: string;
  ServerRoot, SteamCmdPath: string;
begin
  ConfigPath := ExpandConstant('{app}\Config\config.yaml');
  if LoadStringFromFile(ConfigPath, RawContent) then
  begin
    Content := RawContent;
    ServerRoot := NormalizePathForYaml(ServerDir);
    SteamCmdPath := NormalizePathForYaml(SteamCmdExe);

    ReplaceConfigValue(Content, '  server_root: "Server"', '  server_root: "' + ServerRoot + '"');
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
  ResultCode, RetryResult: Integer;
  InstallSucceeded: Boolean;
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

  UpdateConfigPaths(ServerDir, SteamCmdExe);
  SaveServerInstallPath(ServerDir);
  SetStatus('Stopping monitors and the Vein server before SteamCMD maintenance...');
  if (not Exec(
    ExpandConstant('{app}\VeinTools.exe'),
    'uninstall-cleanup',
    ExpandConstant('{app}'),
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  )) or (ResultCode <> 0) then
  begin
    MsgBox(
      'The Vein server could not be stopped safely. The management app was installed or repaired, but SteamCMD server maintenance was skipped.',
      mbError,
      MB_OK
    );
    exit;
  end;

  SteamCmdLog := ExpandConstant('{app}\Logs\steamcmd-install.log');
  InstallCmd :=
    '/C ""' + SteamCmdExe + '" +@sSteamCmdForcePlatformType windows +force_install_dir "' + ServerDir + '" +login anonymous +app_update {#SteamAppId} -beta public validate +quit > "' + SteamCmdLog + '" 2>&1"';
  RetryResult := IDCANCEL;
  repeat
    SetStatus('Installing Vein dedicated server via SteamCMD. This can take several minutes...');
    DeleteFile(SteamCmdLog);
    InstallSucceeded := Exec(
      ExpandConstant('{cmd}'),
      InstallCmd,
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    ) and ((ResultCode = 0) or FileContainsText(SteamCmdLog, 'Success! App ''{#SteamAppId}'' fully installed.'));

    if not InstallSucceeded then
    begin
      UpdateConfigPaths(ServerDir, SteamCmdExe);
      SaveServerInstallPath(ServerDir);
      RetryResult := MsgBox(
        'SteamCMD could not download the VEIN dedicated server.'#13#10#13#10 +
        'Choose Retry to run the server installation again now, or Cancel to finish installing the management app without server files.'#13#10#13#10 +
        'Installer log:'#13#10 +
        SteamCmdLog + #13#10#13#10 +
        'SteamCMD internal logs:'#13#10 +
        AddBackslash(SteamCmdDir) + 'logs',
        mbError,
        MB_RETRYCANCEL
      );
      if RetryResult = IDRETRY then
        SetStatus('Retrying the Vein dedicated server installation...');
    end;
  until InstallSucceeded or (RetryResult <> IDRETRY);

  if not InstallSucceeded then
  begin
    exit;
  end;

  SetStatus('Updating config paths to match the installed server...');
  UpdateConfigPaths(ServerDir, SteamCmdExe);
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
  UpdateConfigPaths(ServerDir, SteamCmdExe);
  SaveServerInstallPath(ServerDir);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SaveStringToFile(ExpandConstant('{app}\version.txt'), '{#MyAppVersion}', False);
    if InstallServer then
      InstallDedicatedServer
    else if not PreserveExistingServerConfig then
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
