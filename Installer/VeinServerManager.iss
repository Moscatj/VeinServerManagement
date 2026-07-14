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
AppId={{2D6A61E2-0A8B-4F6B-9F8B-9912879D7499}{code:InstallAppIdSuffix}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={commonpf}\VeinServerManagement
DefaultGroupName={#MyAppName}{code:InstanceDisplaySuffix}
OutputDir=..\dist\installer
OutputBaseFilename=VeinServerManagement-Setup-v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64compatible
DisableProgramGroupPage=yes
DisableDirPage=no
UninstallDisplayName={#MyAppName}{code:InstanceDisplaySuffix}
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallFilesDir={app}\Uninstall
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
CloseApplicationsFilter=VeinManager.exe,VeinTools.exe
UsePreviousLanguage=no
#ifexist "{#MyAppIcon}"
SetupIconFile={#MyAppIcon}
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#MyStageDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "Backups\*,Logs\*,Runtime\*,Config\config.yaml"
Source: "{#MyStageDir}\Config\config.yaml"; DestDir: "{app}\Config"; Flags: onlyifdoesntexist uninsneveruninstall

[Dirs]
Name: "{app}"; Flags: uninsalwaysuninstall
Name: "{app}\Controller"; Flags: uninsalwaysuninstall
Name: "{app}\Uninstall"; Flags: uninsalwaysuninstall
Name: "{app}\Backups"; Permissions: users-modify
Name: "{app}\Config"; Permissions: users-modify
Name: "{app}\Logs"; Permissions: users-modify
Name: "{app}\Runtime"; Permissions: users-modify
Name: "{app}\SteamCMD"; Permissions: users-modify
Name: "{app}\Server"; Permissions: users-modify

[Icons]
Name: "{group}\Vein Server Manager{code:InstanceDisplaySuffix}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppShortcutIcon}"
Name: "{group}\Open Config Folder"; Filename: "{app}\Config"; WorkingDir: "{app}\Config"
Name: "{group}\Docs"; Filename: "{app}\Docs"; WorkingDir: "{app}\Docs"
Name: "{group}\Uninstall Vein Server Management"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Vein Server Manager{code:InstanceDisplaySuffix}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppShortcutIcon}"; Tasks: desktopicon

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
Type: dirifempty; Name: "{app}\Controller"
Type: dirifempty; Name: "{app}\Uninstall"
Type: dirifempty; Name: "{app}"

[Code]
var
  InstallIntentPage: TWizardPage;
  PrimaryIntentRadio: TRadioButton;
  AlternateIntentRadio: TRadioButton;
  UninstallIntentRadio: TRadioButton;
  InstallIntentBox: TNewStaticText;
  ServerChoicePage: TWizardPage;
  InstallServerRadio: TRadioButton;
  ExistingServerRadio: TRadioButton;
  SkipServerRadio: TRadioButton;
  ServerDirPage: TInputDirWizardPage;
  SteamCmdChoicePage: TWizardPage;
  AppSteamCmdRadio: TRadioButton;
  ExistingSteamCmdRadio: TRadioButton;
  NoSteamCmdRadio: TRadioButton;
  ExistingSteamCmdDirPage: TInputDirWizardPage;
  SteamCmdProgressPage: TOutputMarqueeProgressWizardPage;
  SteamCmdMessagePumpPage: TOutputProgressWizardPage;
  SteamCmdProgressNote: TNewStaticText;
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
  ExistingUninstallerPath: string;
  SetupNewServer: Boolean;
  InstallNewServer: Boolean;
  RepairMissingServer: Boolean;
  FreshAppInstall: Boolean;
  FreshServerMaintenance: Boolean;
  SkipServerSetup: Boolean;
  UninstallExistingApp: Boolean;
  UninstallerLaunched: Boolean;
  PathScopedExistingInstall: Boolean;
  ExistingAppDir: string;
  PreserveExistingServerConfig: Boolean;
  SteamCmdProgressLog: string;
  SteamCmdProgressAction: string;
  SteamCmdCancelFile: string;
  SteamCmdMessagePumpStep: Integer;
  SteamCmdRunnerPhase: string;

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
  if (not ExistingAppInstall) or FreshAppInstall then
  begin
    InstallServer := InstallServerRadio.Checked;
    InstallNewServer := InstallServer and (not FreshServerMaintenance);
    SetupNewServer := InstallNewServer;
    SkipServerSetup := SkipServerRadio.Checked;
    PreserveExistingServerConfig := False;
  end
  else
  begin
    InstallServer := InstallServerRadio.Checked;
    InstallNewServer := False;
    SetupNewServer := False;
    SkipServerSetup := False;
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
  NoSteamCmdRadio.Visible := not InstallServer;
  NoSteamCmdRadio.Enabled := not InstallServer;
  if InstallServer then
  begin
    if NoSteamCmdRadio.Checked then
    begin
      AppSteamCmdRadio.Checked := True;
      ExistingSteamCmdRadio.Checked := False;
      NoSteamCmdRadio.Checked := False;
    end;
    SteamCmdChoiceBox.Top := ExistingSteamCmdRadio.Top + ExistingSteamCmdRadio.Height + ScaleY(20);
  end
  else if AppSteamCmdRadio.Checked then
  begin
    NoSteamCmdRadio.Checked := True;
  end;
  if not InstallServer then
    SteamCmdChoiceBox.Top := NoSteamCmdRadio.Top + NoSteamCmdRadio.Height + ScaleY(20);
  UpdateSteamCmdChoiceState;
end;

function CurrentAppDir(): string; forward;
function DefaultManagedServerDir(): string; forward;
function NormalizePathForCompare(const Value: string): string; forward;

function DefaultSeparateAppDir(): string;
var
  BaseDir: string;
  Suffix: Integer;
begin
  BaseDir := ExpandConstant('{commonpf}\VeinServerManagement');
  Result := BaseDir + '-2';
  Suffix := 3;
  while DirExists(Result) do
  begin
    Result := BaseDir + '-' + IntToStr(Suffix);
    Suffix := Suffix + 1;
  end;
end;

procedure ApplyIntentState;
begin
  FreshAppInstall := ExistingAppInstall and AlternateIntentRadio.Checked;
  UninstallExistingApp := ExistingAppInstall and UninstallIntentRadio.Checked;
  if (not ExistingAppInstall) or FreshAppInstall then
  begin
    InstallServer := Assigned(InstallServerRadio) and InstallServerRadio.Checked;
    InstallNewServer := InstallServer and (not FreshServerMaintenance);
    SetupNewServer := InstallNewServer;
    SkipServerSetup := Assigned(SkipServerRadio) and SkipServerRadio.Checked;
    PreserveExistingServerConfig := False;
  end
  else
  begin
    InstallServer := Assigned(InstallServerRadio) and InstallServerRadio.Checked;
    InstallNewServer := False;
    SetupNewServer := False;
    SkipServerSetup := False;
    PreserveExistingServerConfig := Assigned(ExistingServerRadio) and ExistingServerRadio.Checked;
  end;

  if Assigned(ServerDirPage) then
  begin
    if InstallNewServer then
      ServerDirPage.Values[0] := DefaultManagedServerDir()
    else if SkipServerSetup then
      ServerDirPage.Values[0] := ''
    else if FreshAppInstall or (not ExistingAppInstall) then
      ServerDirPage.Values[0] := ''
    else if (PreviousServerDir <> '') then
      ServerDirPage.Values[0] := PreviousServerDir
    else
      ServerDirPage.Values[0] := DefaultManagedServerDir();
    LastManagedServerDefault := ServerDirPage.Values[0];
  end;

  if Assigned(AppSteamCmdRadio) then
  begin
    if InstallServer and (not FreshAppInstall) and
       (PreviousSteamCmdExe <> '') and FileExists(PreviousSteamCmdExe) then
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
  if ExistingAppInstall and AlternateIntentRadio.Checked then
  begin
    if NormalizePathForCompare(CurrentAppDir()) = NormalizePathForCompare(ExistingAppDir) then
      WizardForm.DirEdit.Text := DefaultSeparateAppDir();
    InstallServerRadio.Checked := True;
    ExistingServerRadio.Checked := False;
    SkipServerRadio.Checked := False;
  end
  else if ExistingAppInstall and PrimaryIntentRadio.Checked then
  begin
    WizardForm.DirEdit.Text := ExistingAppDir;
    InstallServerRadio.Checked := False;
    ExistingServerRadio.Checked := True;
    SkipServerRadio.Checked := False;
  end;
  ApplyIntentState;
  WizardForm.NextButton.Enabled := True;
end;

procedure ServerChoiceChanged(Sender: TObject);
begin
  UpdateServerChoiceState;
  if Assigned(ServerDirPage) and ((not ExistingAppInstall) or FreshAppInstall) then
  begin
    if InstallServer then
      ServerDirPage.Values[0] := DefaultManagedServerDir()
    else
      ServerDirPage.Values[0] := '';
    LastManagedServerDefault := ServerDirPage.Values[0];
  end;
  if InstallServer and Assigned(AppSteamCmdRadio) then
  begin
    if (not FreshAppInstall) and
       (PreviousSteamCmdExe <> '') and FileExists(PreviousSteamCmdExe) and
       Assigned(ExistingSteamCmdRadio) and Assigned(ExistingSteamCmdDirPage) then
    begin
      ExistingSteamCmdRadio.Checked := True;
      ExistingSteamCmdDirPage.Values[0] := ExtractFileDir(PreviousSteamCmdExe);
    end
    else
    begin
      AppSteamCmdRadio.Checked := True;
      ExistingSteamCmdRadio.Checked := False;
      NoSteamCmdRadio.Checked := False;
    end;
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

function ManagementAppOnlyRequested(): Boolean;
var
  Value: string;
begin
  Value := Lowercase(Trim(ExpandConstant('{param:MANAGEMENTAPPONLY|0}')));
  Result := WizardSilent and
    ((Value = '1') or (Value = 'true') or (Value = 'yes'));
end;

function CurrentAppDir(): string;
begin
  Result := WizardDirValue();
  if Result = '' then
    Result := ExpandConstant('{commonpf}\VeinServerManagement');
end;

function AppDirectoryLabel(): string;
var
  Value: string;
begin
  Value := CurrentAppDir();
  while (Length(Value) > 3) and (Copy(Value, Length(Value), 1) = '\') do
    Delete(Value, Length(Value), 1);
  Result := ExtractFileName(Value);
  if Result = '' then
    Result := 'Separate';
end;

function InstallAppIdSuffix(Param: string): string;
begin
  if FreshAppInstall or PathScopedExistingInstall then
    Result := '-' + GetMD5OfString(NormalizePathForCompare(CurrentAppDir()))
  else
    Result := '';
end;

function InstanceDisplaySuffix(Param: string): string;
begin
  if FreshAppInstall or PathScopedExistingInstall then
    Result := ' (' + AppDirectoryLabel() + ')'
  else
    Result := '';
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

function IsManagementInstallAt(const AppDir: string): Boolean;
begin
  Result :=
    FileExists(AddBackslash(AppDir) + '{#MyAppExeName}') or
    FileExists(AddBackslash(AppDir) + 'VeinTools.exe') or
    FileExists(AddBackslash(AppDir) + 'version.txt') or
    FileExists(AddBackslash(AppDir) + 'Config\config.yaml');
end;

procedure LoadExistingInstallAt(const AppDir: string);
var
  ConfigPath, Candidate: string;
begin
  ExistingAppInstall := IsManagementInstallAt(AppDir);
  ExistingAppVersion := '';
  ExistingAppDir := '';
  PreviousServerDir := '';
  PreviousSteamCmdExe := '';
  ExistingUninstallerPath := '';

  if not ExistingAppInstall then
    exit;

  ExistingAppDir := AppDir;

  LoadTrimmedFile(AddBackslash(AppDir) + 'version.txt', ExistingAppVersion);
  if ExistingAppVersion = '' then
    ExistingAppVersion := 'unknown';
  LoadTrimmedFile(AddBackslash(AppDir) + 'Runtime\server_install_path.txt', PreviousServerDir);
  LoadTrimmedFile(AddBackslash(AppDir) + 'Runtime\uninstaller_path.txt', ExistingUninstallerPath);
  ConfigPath := AddBackslash(AppDir) + 'Config\config.yaml';
  if (PreviousServerDir = '') and ReadYamlScalar(ConfigPath, 'server_root', Candidate) then
  begin
    StringChangeEx(Candidate, '/', '\', True);
    if ((Length(Candidate) >= 2) and (Candidate[2] = ':')) or
       (Copy(Candidate, 1, 2) = '\\') then
      PreviousServerDir := Candidate
    else
      PreviousServerDir := AddBackslash(AppDir) + Candidate;
  end;
  if ReadYamlScalar(ConfigPath, 'steamcmd_path', Candidate) then
  begin
    StringChangeEx(Candidate, '/', '\', True);
    if FileExists(Candidate) then
      PreviousSteamCmdExe := Candidate
    else if FileExists(AddBackslash(AppDir) + Candidate) then
      PreviousSteamCmdExe := AddBackslash(AppDir) + Candidate;
  end;
  if (PreviousSteamCmdExe = '') and
     FileExists(AddBackslash(AppDir) + 'SteamCMD\steamcmd.exe') then
    PreviousSteamCmdExe := AddBackslash(AppDir) + 'SteamCMD\steamcmd.exe';
end;

procedure DetectExistingInstall;
begin
  PathScopedExistingInstall := False;
  LoadExistingInstallAt(CurrentAppDir());
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  ToolPath: string;
begin
  Result := '';
  if (not ExistingAppInstall) or FreshAppInstall then
    exit;

  ToolPath := AddBackslash(ExistingAppDir) + 'VeinTools.exe';
  if FileExists(ToolPath) then
    Exec(
      ToolPath,
      'stop-all-monitors',
      ExistingAppDir,
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
  if InstallNewServer then
    NextDefault := DefaultManagedServerDir()
  else if PreviousServerDir <> '' then
    NextDefault := PreviousServerDir
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

function HasVeinServerAt(const ServerDir: string): Boolean;
begin
  Result :=
    FileExists(AddBackslash(ServerDir) + 'Vein\Binaries\Win64\VeinServer.exe') or
    FileExists(AddBackslash(ServerDir) + 'Vein\Binaries\Win64\VeinServer-Win64-Test.exe');
end;

procedure RefreshInstallIntentPresentation;
begin
  if ExistingAppInstall then
  begin
    InstallIntentPage.Caption := 'Choose What Setup Should Do';
    InstallIntentPage.Description := 'Select the installation goal for this computer.';
    PrimaryIntentRadio.Visible := True;
    AlternateIntentRadio.Visible := True;
    PrimaryIntentRadio.Caption := 'Update or repair the detected installation (recommended)';
    AlternateIntentRadio.Caption := 'Install a separate, fresh management app in another folder';
    UninstallIntentRadio.Caption := 'Uninstall the detected management app';
    UninstallIntentRadio.Visible := True;
    InstallIntentBox.Caption :=
      'Detected version ' + ExistingAppVersion + ' in:'#13#10 +
      ExistingAppDir + #13#10#13#10 +
      'Update/Repair preserves configuration and data. Fresh install uses an independent app folder. Uninstall launches this installation''s own uninstaller.';
    InstallIntentBox.Top := UninstallIntentRadio.Top + UninstallIntentRadio.Height + ScaleY(18);
  end
  else
  begin
    InstallIntentPage.Caption := 'Install Vein Server Management Suite';
    InstallIntentPage.Description := 'A guided installer for the management app and optional Vein dedicated server.';
    PrimaryIntentRadio.Visible := False;
    AlternateIntentRadio.Visible := False;
    UninstallIntentRadio.Visible := False;
    InstallIntentBox.Caption :=
      'This installer first installs Vein Server Management Suite, the desktop app for configuring, starting, stopping, monitoring, backing up, and maintaining a Vein dedicated server.'#13#10#13#10 +
      'Next, choose where to install the management app. You can then install a new Vein server with SteamCMD, connect an existing server, or finish with the management app only.';
    InstallIntentBox.Top := ScaleY(48);
  end;
  InstallIntentBox.Height := InstallIntentPage.SurfaceHeight - InstallIntentBox.Top - ScaleY(8);
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
  PrimaryIntentRadio.Checked := True;
  LayoutIntentControl(PrimaryIntentRadio, ScaleY(48));
  PrimaryIntentRadio.Height := ScaleY(28);
  PrimaryIntentRadio.OnClick := @InstallIntentChanged;

  AlternateIntentRadio := TNewRadioButton.Create(InstallIntentPage.Surface);
  AlternateIntentRadio.Parent := InstallIntentPage.Surface;
  AlternateIntentRadio.Checked := False;
  LayoutIntentControl(AlternateIntentRadio, PrimaryIntentRadio.Top + PrimaryIntentRadio.Height + ScaleY(12));
  AlternateIntentRadio.Height := ScaleY(28);
  AlternateIntentRadio.OnClick := @InstallIntentChanged;

  UninstallIntentRadio := TNewRadioButton.Create(InstallIntentPage.Surface);
  UninstallIntentRadio.Parent := InstallIntentPage.Surface;
  UninstallIntentRadio.Checked := False;
  LayoutIntentControl(UninstallIntentRadio, AlternateIntentRadio.Top + AlternateIntentRadio.Height + ScaleY(12));
  UninstallIntentRadio.Height := ScaleY(28);
  UninstallIntentRadio.OnClick := @InstallIntentChanged;

  InstallIntentBox := TNewStaticText.Create(InstallIntentPage.Surface);
  InstallIntentBox.Parent := InstallIntentPage.Surface;
  InstallIntentBox.AutoSize := False;
  InstallIntentBox.WordWrap := True;
  LayoutIntentControl(InstallIntentBox, UninstallIntentRadio.Top + UninstallIntentRadio.Height + ScaleY(18));
  InstallIntentBox.Height := InstallIntentPage.SurfaceHeight - InstallIntentBox.Top - ScaleY(8);
  RefreshInstallIntentPresentation;

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

  SkipServerRadio := TNewRadioButton.Create(ServerChoicePage.Surface);
  SkipServerRadio.Parent := ServerChoicePage.Surface;
  SkipServerRadio.Caption := 'Skip server setup for now';
  SkipServerRadio.Checked := False;
  LayoutServerChoiceControl(SkipServerRadio, ExistingServerRadio.Top + ExistingServerRadio.Height + ScaleY(10));
  SkipServerRadio.Height := ScaleY(26);
  SkipServerRadio.OnClick := @ServerChoiceChanged;

  InstallServerBox := TNewStaticText.Create(ServerChoicePage.Surface);
  InstallServerBox.Parent := ServerChoicePage.Surface;
  InstallServerBox.Caption :=
    'The management app update does not require a game-server update. Leave the server unchanged for the quickest repair, or select SteamCMD maintenance to validate and refresh app {#SteamAppId} after a controlled shutdown.';
  InstallServerBox.AutoSize := False;
  InstallServerBox.WordWrap := True;
  LayoutServerChoiceControl(InstallServerBox, SkipServerRadio.Top + SkipServerRadio.Height + ScaleY(16));
  InstallServerBox.Height := ServerChoicePage.SurfaceHeight - InstallServerBox.Top - ScaleY(8);

  ServerDirPage := CreateInputDirPage(
    ServerChoicePage.ID,
    'Vein Server Location',
    'Confirm which dedicated server this management app should use.',
    'The recommended location is selected automatically. Click Next to accept it, or use Browse when a different location is needed.',
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
  SteamCmdChoiceBox.WordWrap := True;
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
  if not ExistingAppInstall then
  begin
    InstallServerRadio.Checked := True;
    ExistingServerRadio.Checked := False;
    SkipServerRadio.Checked := False;
  end;
  SteamCmdProgressPage := CreateOutputMarqueeProgressPage(
    'Installing Vein Dedicated Server',
    'SteamCMD is downloading, validating, and preparing the dedicated server.'
  );
  SteamCmdProgressNote := TNewStaticText.Create(SteamCmdProgressPage.Surface);
  SteamCmdProgressNote.Parent := SteamCmdProgressPage.Surface;
  SteamCmdProgressNote.Caption :=
    'SteamCMD cannot be cancelled safely from this installer step. If Setup or the computer is interrupted, run Update/Repair later to resume and validate the partial files.';
  SteamCmdProgressNote.Left := ScaleX(0);
  SteamCmdProgressNote.Top := SteamCmdProgressPage.ProgressBar.Top + SteamCmdProgressPage.ProgressBar.Height + ScaleY(24);
  SteamCmdProgressNote.Width := SteamCmdProgressPage.SurfaceWidth;
  SteamCmdProgressNote.Height := ScaleY(52);
  SteamCmdProgressNote.AutoSize := False;
  SteamCmdProgressNote.WordWrap := True;
  SteamCmdMessagePumpPage := CreateOutputProgressPage('', '');
  SteamCmdMessagePumpPage.SetProgress(0, 1);
  ApplyIntentState;
  if ManagementAppOnlyRequested() then
  begin
    InstallServerRadio.Checked := False;
    ExistingServerRadio.Checked := False;
    SkipServerRadio.Checked := True;
    ApplyIntentState;
    Log('Silent management-app-only installation requested; SteamCMD and server setup are skipped.');
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
var
  SteamCmdNote: string;
begin
  if CurPageID = wpFinished then
  begin
    WizardForm.Enabled := True;
    WizardForm.NextButton.Enabled := True;
  end;
  if Assigned(InstallIntentPage) and (CurPageID = InstallIntentPage.ID) then
    ApplyIntentState;
  if Assigned(ServerDirPage) and (CurPageID = ServerDirPage.ID) then
  begin
    if InstallServer and ExistingAppInstall and (not FreshAppInstall) then
    begin
      RepairMissingServer := not HasVeinServerAt(ServerDirPage.Values[0]);
      if RepairMissingServer then
      begin
        ServerDirPage.Caption := 'Server Repair or Reinstall Location';
        ServerDirPage.Description := 'Confirm where SteamCMD should restore the missing Vein dedicated server files.';
        ServerDirPage.SubCaptionLabel.Caption :=
          'The configured location does not currently contain a supported Vein server executable. Click Next to reinstall and validate the server in this folder, or use Browse to correct the location.';
      end
      else
      begin
        ServerDirPage.Caption := 'Existing Server to Update or Repair';
        ServerDirPage.Description := 'Confirm the detected dedicated server root that SteamCMD should maintain.';
        ServerDirPage.SubCaptionLabel.Caption :=
          'Setup prefilled the configured existing server. Click Next to confirm it, or use Browse only to correct the location.';
      end;
      SyncManagedServerDefault;
    end
    else if InstallServer and (not FreshServerMaintenance) then
    begin
      ServerDirPage.Caption := 'New Server Installation Location';
      ServerDirPage.Description := 'Choose where SteamCMD should install the new Vein dedicated server.';
      ServerDirPage.SubCaptionLabel.Caption :=
        'The app-managed Server folder is selected by default. Click Next to keep the server with this management app, or use Browse for an advanced custom location.';
      SyncManagedServerDefault;
    end
    else if InstallServer then
    begin
      ServerDirPage.Caption := 'Existing Server to Update or Repair';
      ServerDirPage.Description := 'Confirm the detected dedicated server root that SteamCMD should maintain.';
      ServerDirPage.SubCaptionLabel.Caption :=
        'Setup prefilled the configured existing server. Click Next to confirm it, or use Browse only to correct the location.';
      SyncManagedServerDefault;
    end
    else
    begin
      ServerDirPage.Caption := 'Existing Server Location';
      ServerDirPage.Description := 'Choose the root folder of the existing Vein dedicated server.';
      ServerDirPage.SubCaptionLabel.Caption :=
        'Select the existing server root that contains Vein\Binaries\Win64, then click Next.';
    end;
  end;
  if Assigned(ServerChoicePage) and (CurPageID = ServerChoicePage.ID) then
  begin
    if (not ExistingAppInstall) or FreshAppInstall then
    begin
      FreshServerMaintenance := HasVeinServerAt(DefaultManagedServerDir());
      UpdateServerChoiceState;
      ServerChoicePage.Caption := 'Choose Server Setup';
      ServerChoicePage.Description := 'Choose what the new management app should do with the Vein dedicated server.';
      if FreshServerMaintenance then
        InstallServerRadio.Caption := 'Update or repair the detected dedicated server with SteamCMD (recommended)'
      else
        InstallServerRadio.Caption := 'Install a new dedicated server with SteamCMD (recommended)';
      ExistingServerRadio.Caption := 'Connect to an existing dedicated server';
      SkipServerRadio.Caption := 'Skip server setup for now';
      SkipServerRadio.Visible := True;
      InstallServerBox.Top := SkipServerRadio.Top + SkipServerRadio.Height + ScaleY(16);
      if FreshServerMaintenance then
        InstallServerBox.Caption :=
          'A Vein server was detected inside the selected app''s managed Server folder. The recommended option updates or repairs it; connect and skip choices do not change server files.'
      else
        InstallServerBox.Caption :=
          'The recommended option installs a new server inside the app-managed Server folder. Existing-server and skip choices do not download or change server files.';
    end
    else
    begin
      ServerChoicePage.Caption := 'Existing Server Maintenance';
      RepairMissingServer := not HasVeinServerAt(ServerDirPage.Values[0]);
      if RepairMissingServer then
      begin
        ServerChoicePage.Description := 'The configured Vein server is missing. Choose whether to reinstall it during app repair.';
        InstallServerRadio.Caption := 'Repair or reinstall the missing dedicated server with SteamCMD (recommended)';
        ExistingServerRadio.Caption := 'Repair the management app only and leave the server missing';
        InstallServerRadio.Checked := True;
        ExistingServerRadio.Checked := False;
        UpdateServerChoiceState;
      end
      else
      begin
        ServerChoicePage.Description := 'Choose whether the existing Vein server should also be updated or repaired.';
        InstallServerRadio.Caption := 'Update or repair the existing dedicated server with SteamCMD';
        ExistingServerRadio.Caption := 'Leave the existing dedicated server unchanged (recommended)';
      end;
      SkipServerRadio.Visible := False;
      InstallServerBox.Top := ExistingServerRadio.Top + ExistingServerRadio.Height + ScaleY(16);
      if (PreviousSteamCmdExe <> '') and FileExists(PreviousSteamCmdExe) then
        SteamCmdNote := 'SteamCMD will be reused automatically:'#13#10 + PreviousSteamCmdExe
      else
        SteamCmdNote := 'The app-managed SteamCMD copy will be used or installed automatically.';
      if RepairMissingServer then
        InstallServerBox.Caption :=
          'Configured server location:'#13#10 + ServerDirPage.Values[0] + #13#10#13#10 +
          'Status: dedicated server executable is missing.'#13#10#13#10 +
          SteamCmdNote + #13#10#13#10 +
          'The recommended option recreates the server files at this configured location and validates them through SteamCMD.'
      else if PreviousServerDir <> '' then
        InstallServerBox.Caption :=
          'Detected server:'#13#10 + PreviousServerDir + #13#10#13#10 +
          SteamCmdNote + #13#10#13#10 +
          'The app repair does not require a server update. Leave it unchanged for the quickest repair, or select SteamCMD maintenance and confirm the server location on the next screen.'
      else
        InstallServerBox.Caption :=
          'No existing server root was detected.'#13#10#13#10 + SteamCmdNote + #13#10#13#10 +
          'The app repair can leave server settings unchanged. If you select SteamCMD maintenance, Setup will ask for the existing server location.';
    end;
  end;
  if Assigned(SteamCmdChoicePage) and (CurPageID = SteamCmdChoicePage.ID) then
  begin
    UpdateSteamCmdChoiceAvailability;
    if InstallServer then
    begin
      if FreshServerMaintenance then
        SteamCmdChoicePage.Caption := 'SteamCMD for Server Update or Repair'
      else
        SteamCmdChoicePage.Caption := 'SteamCMD for the New Server';
      SteamCmdChoicePage.Description := 'Use the recommended app-managed SteamCMD or select an existing copy.';
      SteamCmdChoiceBox.Caption :=
        'App-managed SteamCMD is selected by default and requires no extra setup. Advanced users may reuse an existing SteamCMD folder.';
    end;
  end;
  if CurPageID = wpReady then
  begin
    if (not ExistingAppInstall) or FreshAppInstall then
    begin
      WizardForm.PageNameLabel.Caption := 'Ready to Install Vein Server Management';
      if InstallServer and (not FreshServerMaintenance) then
        WizardForm.PageDescriptionLabel.Caption := 'The management app and a new Vein server will be installed in their selected locations.'
      else if InstallServer then
        WizardForm.PageDescriptionLabel.Caption := 'The management app will be installed and the detected Vein server will be updated or repaired.'
      else if SkipServerSetup then
        WizardForm.PageDescriptionLabel.Caption := 'The management app will be installed without configuring a Vein server.'
      else
        WizardForm.PageDescriptionLabel.Caption := 'The management app will be installed and connected to the selected Vein server.';
    end
    else if ExistingAppInstall and InstallServer then
    begin
      if RepairMissingServer then
      begin
        WizardForm.PageNameLabel.Caption := 'Ready to Repair the App and Reinstall the Server';
        WizardForm.PageDescriptionLabel.Caption := 'SteamCMD will restore and validate the missing Vein server files at the configured location.';
      end
      else
      begin
        WizardForm.PageNameLabel.Caption := 'Ready to Update or Repair the App and Server';
        WizardForm.PageDescriptionLabel.Caption := 'The management app and selected Vein server will both receive maintenance.';
      end;
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
    Result := ExistingAppInstall and (not FreshAppInstall)
  else if Assigned(ServerChoicePage) and (PageID = ServerChoicePage.ID) then
    Result := UninstallExistingApp
  else if Assigned(ServerDirPage) and (PageID = ServerDirPage.ID) then
    Result := PreserveExistingServerConfig or SkipServerSetup
  else if Assigned(SteamCmdChoicePage) and (PageID = SteamCmdChoicePage.ID) then
    Result := (not InstallServer) or (ExistingAppInstall and (not FreshAppInstall))
  else if Assigned(ExistingSteamCmdDirPage) and (PageID = ExistingSteamCmdDirPage.ID) then
    Result := (not InstallServer) or (not UseExistingSteamCmd) or
      (ExistingAppInstall and (not FreshAppInstall));
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
    RepairMissingServer := ExistingAppInstall and (not FreshAppInstall) and
      (not SetupNewServer) and (not FileExists(ExeA)) and (not FileExists(ExeB));
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
      Result := MsgBox(
        'A Vein dedicated server already exists in the selected folder.'#13#10#13#10 +
        'Choose Yes to update or repair that server with SteamCMD, or No to return and choose a different folder.',
        mbConfirmation,
        MB_YESNO
      ) = IDYES;
      if Result then
      begin
        FreshServerMaintenance := True;
        InstallNewServer := False;
        SetupNewServer := False;
      end;
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

function ValidateFreshAppDir: Boolean;
var
  Candidate, ExistingRoot: string;
begin
  Result := True;
  Candidate := NormalizePathForCompare(CurrentAppDir());
  ExistingRoot := NormalizePathForCompare(ExistingAppDir);
  if Candidate = '' then
  begin
    MsgBox('Choose a folder for the separate management app installation.', mbError, MB_OK);
    Result := False;
    exit;
  end;

  if ExistingAppInstall and FreshAppInstall and
     ((Candidate = ExistingRoot) or
      (Pos(ExistingRoot + '\', Candidate) = 1) or
      (Pos(Candidate + '\', ExistingRoot) = 1)) then
  begin
    MsgBox(
      'Choose a separate app folder that is not the existing installation or one of its parent/child folders.',
      mbError,
      MB_OK
    );
    Result := False;
    exit;
  end;

  if IsManagementInstallAt(CurrentAppDir()) then
  begin
    LoadExistingInstallAt(CurrentAppDir());
    PathScopedExistingInstall := True;
    WizardForm.DirEdit.Text := ExistingAppDir;
    PrimaryIntentRadio.Checked := True;
    AlternateIntentRadio.Checked := False;
    UninstallIntentRadio.Checked := False;
    RefreshInstallIntentPresentation;
    ApplyIntentState;
    MsgBox(
      'An existing Vein Server Management installation was found in the selected folder.'#13#10#13#10 +
      'Setup will return to the first page so you can update/repair it, uninstall it, or choose a different folder for a fresh installation.',
      mbInformation,
      MB_OK
    );
    WizardForm.BackButton.OnClick(WizardForm.BackButton);
    Result := False;
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

function FindUninstallerInFolder(const Folder: string; var UninstallerPath: string): Boolean;
var
  FindRec: TFindRec;
  Candidate: string;
begin
  Result := False;
  if not DirExists(Folder) then
    exit;
  if FindFirst(AddBackslash(Folder) + 'unins*.exe', FindRec) then
  begin
    try
      repeat
        Candidate := AddBackslash(Folder) + FindRec.Name;
        if FileExists(Candidate) then
        begin
          UninstallerPath := Candidate;
          Result := True;
          exit;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

function ResolveExistingUninstaller(var UninstallerPath: string): Boolean;
begin
  UninstallerPath := ExistingUninstallerPath;
  if (UninstallerPath <> '') and FileExists(UninstallerPath) then
  begin
    Result := True;
    exit;
  end;

  UninstallerPath := AddBackslash(ExistingAppDir) + 'Uninstall\unins000.exe';
  if FileExists(UninstallerPath) then
  begin
    Result := True;
    exit;
  end;
  UninstallerPath := AddBackslash(ExistingAppDir) + 'unins000.exe';
  if FileExists(UninstallerPath) then
  begin
    Result := True;
    exit;
  end;

  Result := FindUninstallerInFolder(AddBackslash(ExistingAppDir) + 'Uninstall', UninstallerPath);
  if not Result then
    Result := FindUninstallerInFolder(ExistingAppDir, UninstallerPath);
end;

function LaunchExistingUninstaller: Boolean;
var
  UninstallerPath: string;
  ResultCode: Integer;
begin
  Result := False;
  if not ResolveExistingUninstaller(UninstallerPath) then
  begin
    MsgBox(
      'The uninstaller could not be found for:'#13#10#13#10 + ExistingAppDir + #13#10#13#10 +
      'Use Windows Installed Apps to remove this installation, or choose Update/Repair.',
      mbError,
      MB_OK
    );
    exit;
  end;

  Result := Exec(
    UninstallerPath,
    '',
    ExistingAppDir,
    SW_SHOWNORMAL,
    ewNoWait,
    ResultCode
  );
  if Result then
    UninstallerLaunched := True
  else
    MsgBox('The detected uninstaller could not be started.', mbError, MB_OK);
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if UninstallerLaunched then
  begin
    Cancel := True;
    Confirm := False;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = InstallIntentPage.ID then
  begin
    ApplyIntentState;
    if UninstallExistingApp then
    begin
      Result := False;
      if LaunchExistingUninstaller then
        WizardForm.Close;
    end;
  end
  else if CurPageID = wpSelectDir then
  begin
    Result := ValidateFreshAppDir;
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

function ExtractSteamCmdProgress(const Line: string): string;
var
  LowerLine: string;
  StartPos, EndPos: Integer;
begin
  Result := '';
  LowerLine := Lowercase(Line);
  StartPos := Pos('progress: ', LowerLine);
  if StartPos = 0 then
    exit;

  StartPos := StartPos + Length('progress: ');
  EndPos := StartPos;
  while (EndPos <= Length(Line)) and
        (Pos(Copy(Line, EndPos, 1), '0123456789.') > 0) do
    EndPos := EndPos + 1;
  if EndPos > StartPos then
    Result := Copy(Line, StartPos, EndPos - StartPos) + '%';
end;

procedure SteamCmdOutput(const S: string; const Error, FirstLine: Boolean);
var
  CleanLine, LowerLine, Phase, ProgressValue: string;
begin
  SteamCmdMessagePumpStep := 1 - SteamCmdMessagePumpStep;
  SteamCmdMessagePumpPage.SetProgress(SteamCmdMessagePumpStep, 1);

  CleanLine := Trim(S);
  if CleanLine = '__VEIN_STEAMCMD_HEARTBEAT__' then
    exit;
  if Pos('__VEIN_STEAMCMD_PHASE__:', CleanLine) = 1 then
  begin
    SteamCmdRunnerPhase := Copy(CleanLine, Length('__VEIN_STEAMCMD_PHASE__:') + 1, MaxInt);
    if SteamCmdRunnerPhase = 'bootstrap' then
      SteamCmdProgressPage.SetText(
        'Initializing SteamCMD...',
        'Checking for SteamCMD first-run updates before installing the Vein server.'
      )
    else if SteamCmdRunnerPhase = 'server' then
      SteamCmdProgressPage.SetText(
        SteamCmdProgressAction,
        'SteamCMD is initialized. Starting the Vein server download and validation.'
      );
    exit;
  end;

  if SteamCmdProgressLog <> '' then
    SaveStringToFile(SteamCmdProgressLog, S + #13#10, True);

  if Error then
  begin
    Log('SteamCMD output capture warning: ' + S);
    SteamCmdProgressPage.SetText(
      SteamCmdProgressAction,
      'SteamCMD is still running, but live output is unavailable. Details will remain in steamcmd-install.log.'
    );
    exit;
  end;

  if CleanLine = '' then
    exit;
  Log('[SteamCMD] ' + CleanLine);

  LowerLine := Lowercase(CleanLine);
  if Pos('type ''quit'' to exit', LowerLine) > 0 then
    exit;
  Phase := SteamCmdProgressAction;
  if Pos('downloading', LowerLine) > 0 then
  begin
    if SteamCmdRunnerPhase = 'bootstrap' then
      Phase := 'Updating SteamCMD...'
    else
      Phase := 'Downloading Vein server files...';
  end
  else if Pos('verifying', LowerLine) > 0 then
    Phase := 'Verifying Vein server files...'
  else if Pos('success!', LowerLine) > 0 then
    Phase := 'SteamCMD completed successfully.';

  ProgressValue := ExtractSteamCmdProgress(CleanLine);
  if ProgressValue <> '' then
    Phase := Phase + ' ' + ProgressValue;
  SteamCmdProgressPage.SetText(Phase, Copy(CleanLine, 1, 180));
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
  ServerDir, SteamCmdDir, SteamCmdExe, TempZip, ExtractDir, ExtractedSteamCmdExe, SteamCmdLog, DownloadCmd, ExtractCmd, InstallParams: string;
  ResultCode, RetryResult, AttemptNumber: Integer;
  InstallSucceeded: Boolean;
begin
  ServerDir := ServerDirPage.Values[0];
  if ServerDir = '' then
    exit;
  ForceDirectories(ServerDir);
  SteamCmdCancelFile := ExpandConstant('{tmp}\steamcmd-cancel.request');
  DeleteFile(SteamCmdCancelFile);

  if SetupNewServer then
    SteamCmdProgressAction := 'Installing the new Vein dedicated server...'
  else if RepairMissingServer then
    SteamCmdProgressAction := 'Reinstalling the missing Vein dedicated server...'
  else
    SteamCmdProgressAction := 'Updating or repairing the Vein dedicated server...';
  SteamCmdProgressPage.SetText(SteamCmdProgressAction, 'Preparing SteamCMD...');
  SteamCmdProgressPage.Show;
  SteamCmdProgressPage.Animate;
  try

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
      SteamCmdProgressPage.SetText('Downloading SteamCMD from Valve...', 'Preparing the app-managed SteamCMD copy.');
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
      SteamCmdProgressPage.SetText('Extracting SteamCMD...', 'Preparing steamcmd.exe inside the management app folder.');
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
  SteamCmdProgressLog := SteamCmdLog;
  InstallParams :=
    'steamcmd-run --steamcmd-exe "' + SteamCmdExe + '" --server-dir "' + ServerDir + '" --app-id {#SteamAppId} --cancel-file "' + SteamCmdCancelFile + '"';
  RetryResult := IDCANCEL;
  AttemptNumber := 0;
  DeleteFile(SteamCmdLog);
  repeat
    AttemptNumber := AttemptNumber + 1;
    if SetupNewServer then
      SetStatus('Installing the new Vein dedicated server via SteamCMD...')
    else if RepairMissingServer then
      SetStatus('Repairing or reinstalling the missing Vein dedicated server via SteamCMD...')
    else
      SetStatus('Updating or repairing the existing Vein dedicated server via SteamCMD...');
    DeleteFile(SteamCmdCancelFile);
    SteamCmdRunnerPhase := '';
    SteamCmdProgressPage.SetText(SteamCmdProgressAction, 'Waiting for live SteamCMD status...');
    SaveStringToFile(
      SteamCmdLog,
      '' + #13#10 + '===== SteamCMD attempt ' + IntToStr(AttemptNumber) + ' =====' + #13#10,
      True
    );
    ResultCode := -1;
    try
      InstallSucceeded := ExecAndLogOutput(
        ExpandConstant('{app}\VeinTools.exe'),
        InstallParams,
        ExpandConstant('{app}'),
        SW_SHOWNORMAL,
        ewWaitUntilTerminated,
        ResultCode,
        @SteamCmdOutput
      ) and ((ResultCode = 0) or FileContainsText(SteamCmdLog, 'Success! App ''{#SteamAppId}'' fully installed.'));
    except
      Log('SteamCMD execution failed: ' + GetExceptionMessage);
      InstallSucceeded := False;
    end;

    if not InstallSucceeded then
    begin
      UpdateConfigPaths(ServerDir, SteamCmdExe);
      SaveServerInstallPath(ServerDir);
      if AttemptNumber = 1 then
      begin
        RetryResult := IDRETRY;
        SetStatus('The first SteamCMD attempt did not complete; retrying automatically...');
        SteamCmdProgressPage.SetText(
          'Retrying SteamCMD automatically...',
          'SteamCMD can require a second invocation after first-run initialization. Both attempts are retained in the installer log.'
        );
      end
      else
      begin
        RetryResult := MsgBox(
          'SteamCMD could not install, update, or repair the VEIN dedicated server after two attempts.'#13#10#13#10 +
          'Choose Retry to run SteamCMD again now, or Cancel to finish the management app setup without changing server files.'#13#10#13#10 +
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
    end;
  until InstallSucceeded or (RetryResult <> IDRETRY);

  if not InstallSucceeded then
  begin
    exit;
  end;

  SetStatus('Updating config paths to match the installed server...');
  UpdateConfigPaths(ServerDir, SteamCmdExe);
  SaveServerInstallPath(ServerDir);
  finally
    DeleteFile(SteamCmdCancelFile);
    SteamCmdProgressLog := '';
    SteamCmdProgressPage.Hide;
  end;
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
    SaveStringToFile(
      ExpandConstant('{app}\Runtime\uninstaller_path.txt'),
      ExpandConstant('{uninstallexe}'),
      False
    );
    if InstallServer then
      InstallDedicatedServer
    else if (not PreserveExistingServerConfig) and (not SkipServerSetup) then
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
      SuppressibleMsgBox(
        'Remove local Vein Server Management backups too?'#13#10#13#10 +
        ExpandConstant('{app}\Backups') + #13#10#13#10 +
        'Choose No to preserve backup files.',
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON2,
        IDNO
      ) = IDYES;
  end;

  if DirExists(ExpandConstant('{app}\Config')) then
  begin
    RemoveLocalConfig :=
      SuppressibleMsgBox(
        'Remove local Vein Server Management config files too?'#13#10#13#10 +
        ExpandConstant('{app}\Config') + #13#10#13#10 +
        'Choose No to preserve local settings for a future reinstall.',
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON2,
        IDNO
      ) = IDYES;
  end;

  if LoadInstalledServerPath(ServerDir) then
  begin
    if IsPathInsideApp(ServerDir) then
    begin
      AppManagedServerDir := ServerDir;
      RemoveAppManagedServer :=
        SuppressibleMsgBox(
          'The Vein dedicated server appears to be installed inside the app folder:'#13#10#13#10 +
          ServerDir + #13#10#13#10 +
          'Deleting it can permanently remove world saves, logs, SteamCMD data, and server files.'#13#10#13#10 +
          'Choose No to preserve all server data.'#13#10#13#10 +
          'Delete the app-managed Vein dedicated server folder too?',
          mbCriticalError,
          MB_YESNO or MB_DEFBUTTON2,
          IDNO
        ) = IDYES;
    end
    else
    begin
      SuppressibleMsgBox(
        'The Vein dedicated server folder is outside the app install folder and will not be removed:'#13#10#13#10 +
        ServerDir + #13#10#13#10 +
        'The uninstaller will remove the management app only after stopping monitors/server processes.',
        mbInformation,
        MB_OK,
        IDOK
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
