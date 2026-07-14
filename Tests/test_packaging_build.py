from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "Controller" / "Tools" / "packing" / "build_gui_exe.py"
INSTALLER_SCRIPT = ROOT / "Installer" / "VeinServerManager.iss"
BUILD_INSTALLER_SCRIPT = ROOT / "Scripts" / "BuildInstaller.bat"
SMOKE_INSTALLER_SCRIPT = ROOT / "Scripts" / "SmokeTestInstaller.ps1"
CONFIG_TEMPLATE = ROOT / "Config" / "config.example.yaml"


def _load_build_module():
    spec = importlib.util.spec_from_file_location("build_gui_exe_for_test", BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load packaging build script")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PackagingBuildTests(unittest.TestCase):
    def test_installer_build_rejects_unavailable_python_and_nonzero_tools(self) -> None:
        text = BUILD_INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Python packaging runtime is unavailable", text)
        self.assertGreaterEqual(text.count('if not "%errorlevel%"=="0"'), 4)

    def test_installer_grants_modify_permissions_to_writable_app_dirs(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        for folder in ("Backups", "Config", "Logs", "Runtime", "SteamCMD", "Server"):
            self.assertIn(f'Name: "{{app}}\\{folder}"; Permissions: users-modify', text)

    def test_installer_excludes_runtime_folder_contents(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('Excludes: "Backups\\*,Logs\\*,Runtime\\*,Config\\config.yaml"', text)

    def test_silent_management_app_only_install_skips_server_setup(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function ManagementAppOnlyRequested(): Boolean;", text)
        self.assertIn("{param:MANAGEMENTAPPONLY|0}", text)
        self.assertIn("Result := WizardSilent", text)
        self.assertIn("SkipServerRadio.Checked := True;", text)
        self.assertIn("Silent management-app-only installation requested", text)

    def test_installer_smoke_script_verifies_package_and_cleanup_contract(self) -> None:
        text = SMOKE_INSTALLER_SCRIPT.read_text(encoding="utf-8")

        for value in (
            "/MANAGEMENTAPPONLY=1",
            "VeinManager.exe",
            "VeinTools.exe",
            "Config\\config.yaml",
            "Runtime\\uninstaller_path.txt",
            '"--config", $config, "health-check"',
            "Uninstaller did not preserve local configuration",
        ):
            self.assertIn(value, text)
        self.assertIn("Installer smoke-test directory must be new or empty", text)
        self.assertIn("Recorded uninstaller escapes", text)

    def test_installer_preserves_local_config_during_upgrade_and_repair(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Config\\config.yaml", text)
        self.assertIn("Flags: onlyifdoesntexist uninsneveruninstall", text)
        self.assertIn("Update or repair the detected installation (recommended)", text)
        self.assertIn("Update/Repair preserves configuration and data", text)
        self.assertIn("FileExists(AddBackslash(AppDir) + 'Config\\config.yaml')", text)

    def test_installer_detects_previous_server_and_steamcmd_paths(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("procedure DetectExistingInstall;", text)
        self.assertIn("Runtime\\server_install_path.txt", text)
        self.assertIn("ReadYamlScalar(ConfigPath, 'server_root', Candidate)", text)
        self.assertIn("PreviousServerDir := AddBackslash(AppDir) + Candidate;", text)
        self.assertIn("ReadYamlScalar(ConfigPath, 'steamcmd_path', Candidate)", text)
        self.assertIn("FileExists(AddBackslash(AppDir) + 'SteamCMD\\steamcmd.exe')", text)
        self.assertIn("ServerDirPage.Values[0] := PreviousServerDir;", text)
        self.assertIn("ExistingSteamCmdDirPage.Values[0] := ExtractFileDir(PreviousSteamCmdExe);", text)

    def test_existing_server_maintenance_is_prefilled_and_clearly_labeled(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Existing Server to Update or Repair", text)
        self.assertIn("Confirm the detected dedicated server root that SteamCMD should maintain.", text)
        self.assertIn("'Detected server:'#13#10 + PreviousServerDir", text)
        self.assertIn("use Browse only to correct the location", text)
        self.assertNotIn("New or Maintained Server Location", text)
        self.assertNotIn("does not contain the existing Vein dedicated server executable", text)
        self.assertIn("Updating or repairing the existing Vein dedicated server via SteamCMD", text)

    def test_existing_maintenance_can_reinstall_a_missing_server(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("RepairMissingServer := not HasVeinServerAt(ServerDirPage.Values[0]);", text)
        self.assertIn("Server Repair or Reinstall Location", text)
        self.assertIn("Repair or reinstall the missing dedicated server with SteamCMD (recommended)", text)
        self.assertIn("Repair the management app only and leave the server missing", text)
        self.assertIn("recreates the server files at this configured location", text)
        self.assertIn("Reinstalling the missing Vein dedicated server...", text)
        self.assertIn("Repairing or reinstalling the missing Vein dedicated server via SteamCMD", text)

    def test_in_place_server_maintenance_reuses_steamcmd_without_choice_pages(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("SteamCMD will be reused automatically", text)
        self.assertIn("The app-managed SteamCMD copy will be used or installed automatically.", text)
        self.assertIn(
            "Result := (not InstallServer) or (ExistingAppInstall and (not FreshAppInstall))",
            text,
        )
        self.assertIn(
            "(ExistingAppInstall and (not FreshAppInstall));",
            text,
        )

    def test_installer_offers_optional_server_update_and_repair(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Update or repair the existing dedicated server with SteamCMD", text)
        self.assertIn("Leave the existing dedicated server unchanged (recommended)", text)
        self.assertIn("steamcmd-run --steamcmd-exe", text)
        self.assertIn("--app-id {#SteamAppId}", text)
        self.assertIn("InstallServerRadio.Checked := False;", text)
        self.assertIn("ExistingServerRadio.Checked := True;", text)
        self.assertIn("Stopping monitors and the Vein server before SteamCMD maintenance", text)
        self.assertIn("'uninstall-cleanup'", text)
        self.assertIn("SteamCMD server maintenance was skipped", text)

    def test_installer_prepares_running_app_for_in_place_upgrade(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("CloseApplications=yes", text)
        self.assertIn("RestartApplications=no", text)
        self.assertIn("CloseApplicationsFilter=VeinManager.exe,VeinTools.exe", text)
        self.assertIn("function PrepareToInstall(var NeedsRestart: Boolean): String;", text)
        self.assertIn("'stop-all-monitors'", text)

    def test_installer_starts_with_an_explicit_installation_intent(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("CreateCustomPage(\n    wpWelcome,", text)
        self.assertIn("Choose What Setup Should Do", text)
        self.assertIn("Update or repair the detected installation (recommended)", text)
        self.assertIn("Install a separate, fresh management app in another folder", text)
        self.assertIn("Uninstall the detected management app", text)

    def test_upgrade_only_skips_irrelevant_new_install_pages(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Result := ExistingAppInstall and (not FreshAppInstall)", text)
        self.assertIn("Result := PreserveExistingServerConfig or SkipServerSetup", text)
        self.assertIn(
            "Result := (not InstallServer) or (ExistingAppInstall and (not FreshAppInstall))",
            text,
        )
        self.assertIn("else if (not PreserveExistingServerConfig) and (not SkipServerSetup) then", text)
        self.assertIn("The existing server configuration and server files will be left unchanged.", text)

    def test_existing_install_can_create_an_independent_app_instance(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("AppId={{2D6A61E2-0A8B-4F6B-9F8B-9912879D7499}{code:InstallAppIdSuffix}", text)
        self.assertIn("function DefaultSeparateAppDir(): string;", text)
        self.assertIn("BaseDir := ExpandConstant('{commonpf}\\VeinServerManagement');", text)
        self.assertIn("while DirExists(Result) do", text)
        self.assertIn("GetMD5OfString(NormalizePathForCompare(CurrentAppDir()))", text)
        self.assertIn("UninstallDisplayName={#MyAppName}{code:InstanceDisplaySuffix}", text)
        self.assertIn("function ValidateFreshAppDir: Boolean;", text)
        self.assertIn("An existing Vein Server Management installation was found", text)
        self.assertIn("LoadExistingInstallAt(CurrentAppDir());", text)
        self.assertIn("WizardForm.BackButton.OnClick(WizardForm.BackButton);", text)
        self.assertIn("Result := ExistingAppInstall and (not FreshAppInstall)", text)
        self.assertIn("UsePreviousLanguage=no", text)

    def test_intent_helper_text_uses_remaining_page_height(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("InstallIntentBox.WordWrap := True;", text)
        self.assertIn(
            "InstallIntentBox.Height := InstallIntentPage.SurfaceHeight - InstallIntentBox.Top - ScaleY(8);",
            text,
        )

    def test_fresh_app_has_an_explicit_server_choice(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Choose Server Setup", text)
        self.assertIn("Install a new dedicated server with SteamCMD (recommended)", text)
        self.assertIn("Connect to an existing dedicated server", text)
        self.assertIn("Skip server setup for now", text)
        self.assertIn("InstallNewServer := InstallServer and (not FreshServerMaintenance);", text)

    def test_clean_install_starts_with_app_location_then_three_server_outcomes(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("DisableDirPage=no", text)
        self.assertIn("DefaultDirName={commonpf}\\VeinServerManagement", text)
        self.assertIn("Result := UninstallExistingApp", text)
        self.assertIn("SkipServerSetup := SkipServerRadio.Checked;", text)
        self.assertIn("Result := PreserveExistingServerConfig or SkipServerSetup", text)
        self.assertIn("if InstallServer then\n      ServerDirPage.Values[0] := DefaultManagedServerDir()", text)
        self.assertIn("else\n      ServerDirPage.Values[0] := '';", text)

    def test_clean_install_introduces_the_management_suite_before_server_choices(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Install Vein Server Management Suite", text)
        self.assertIn("A guided installer for the management app and optional Vein dedicated server.", text)
        self.assertIn("This installer first installs Vein Server Management Suite", text)
        self.assertIn("PrimaryIntentRadio.Visible := False;", text)
        self.assertIn("Next, choose where to install the management app.", text)

    def test_fresh_location_detects_existing_managed_or_custom_server(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function HasVeinServerAt(const ServerDir: string): Boolean;", text)
        self.assertIn("FreshServerMaintenance := HasVeinServerAt(DefaultManagedServerDir());", text)
        self.assertIn("Update or repair the detected dedicated server with SteamCMD", text)
        self.assertIn("A Vein dedicated server already exists in the selected folder.", text)
        self.assertIn("FreshServerMaintenance := True;", text)

    def test_detected_install_can_launch_its_uninstaller(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function LaunchExistingUninstaller: Boolean;", text)
        self.assertIn("Uninstall\\unins000.exe", text)
        self.assertIn("function ResolveExistingUninstaller", text)
        self.assertIn("Runtime\\uninstaller_path.txt", text)
        self.assertIn("ExpandConstant('{uninstallexe}')", text)
        self.assertIn("FindFirst(AddBackslash(Folder) + 'unins*.exe'", text)
        self.assertIn("FindUninstallerInFolder(ExistingAppDir", text)
        self.assertIn("if LaunchExistingUninstaller then", text)
        self.assertIn("procedure CancelButtonClick", text)

    def test_new_server_pages_use_app_managed_defaults_without_repair_language(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("The app-managed Server folder is selected by default.", text)
        self.assertIn("SteamCMD for the New Server", text)
        self.assertIn("App-managed SteamCMD is selected by default", text)
        self.assertIn("SteamCmdChoiceBox.WordWrap := True;", text)
        self.assertIn("ServerDirPage.SubCaptionLabel.Caption :=", text)
        self.assertNotIn("Setup prefills a detected existing server.", text)

    def test_required_steamcmd_hides_and_clears_the_no_configure_option(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("NoSteamCmdRadio.Visible := not InstallServer;", text)
        self.assertIn("NoSteamCmdRadio.Enabled := not InstallServer;", text)
        self.assertIn("if NoSteamCmdRadio.Checked then", text)
        self.assertIn("NoSteamCmdRadio.Checked := False;", text)
        self.assertIn(
            "SteamCmdChoiceBox.Top := ExistingSteamCmdRadio.Top + ExistingSteamCmdRadio.Height + ScaleY(20);",
            text,
        )
        self.assertIn("UpdateSteamCmdChoiceState;", text)

    def test_installer_filename_includes_version(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("OutputBaseFilename=VeinServerManagement-Setup-v{#MyAppVersion}", text)
        self.assertIn("SaveStringToFile(ExpandConstant('{app}\\version.txt'), '{#MyAppVersion}', False);", text)

    def test_installer_moves_default_uninstaller_files_out_of_app_root(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("UninstallFilesDir={app}\\Uninstall", text)
        self.assertIn("UninstallDisplayIcon={app}\\{#MyAppExeName}", text)
        self.assertIn('Name: "{group}\\Uninstall Vein Server Management"; Filename: "{uninstallexe}"', text)

    def test_installer_runs_cleanup_before_uninstalling_files(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("[UninstallRun]", text)
        self.assertIn('Filename: "{app}\\VeinTools.exe"; Parameters: "uninstall-cleanup"', text)
        self.assertIn('StatusMsg: "Stopping Vein server and monitors..."', text)
        self.assertIn('RunOnceId: "VeinServerManagement.UninstallCleanup"', text)

    def test_uninstaller_removes_transient_app_owned_dirs(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("[UninstallDelete]", text)
        for folder in ("Logs", "Runtime", "SteamCMD"):
            self.assertIn(f'Type: filesandordirs; Name: "{{app}}\\{folder}"', text)
        for folder in ("Controller", "Uninstall"):
            self.assertIn(f'Name: "{{app}}\\{folder}"; Flags: uninsalwaysuninstall', text)
            self.assertIn(f'Type: dirifempty; Name: "{{app}}\\{folder}"', text)
        self.assertIn('Name: "{app}"; Flags: uninsalwaysuninstall', text)
        self.assertIn('Type: dirifempty; Name: "{app}"', text)

    def test_uninstaller_prompts_before_removing_backups_and_config(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("RemoveBackups: Boolean;", text)
        self.assertIn("RemoveLocalConfig: Boolean;", text)
        self.assertIn("Remove local Vein Server Management backups too?", text)
        self.assertIn("Remove local Vein Server Management config files too?", text)
        self.assertIn("MB_YESNO or MB_DEFBUTTON2", text)
        self.assertIn("DelTree(ExpandConstant('{app}\\Backups'), True, True, True);", text)
        self.assertIn("DelTree(ExpandConstant('{app}\\Config'), True, True, True);", text)
        self.assertIn("RemoveDir(ExpandConstant('{app}'));", text)

    def test_installer_server_choice_controls_have_explicit_heights(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("InstallServerRadio.Height := ScaleY(26);", text)
        self.assertIn("ExistingServerRadio.Height := ScaleY(26);", text)
        self.assertIn("InstallServerBox.WordWrap := True;", text)
        self.assertIn(
            "InstallServerBox.Height := ServerChoicePage.SurfaceHeight - InstallServerBox.Top - ScaleY(8);",
            text,
        )

    def test_uninstaller_preserves_external_server_roots(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function IsPathInsideApp(const Value: string): Boolean;", text)
        self.assertIn("Candidate <> AppRoot", text)
        self.assertIn("The Vein dedicated server folder is outside the app install folder and will not be removed", text)

    def test_uninstaller_requires_explicit_opt_in_for_app_managed_server_delete(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Deleting it can permanently remove world saves, logs, SteamCMD data, and server files.", text)
        self.assertIn("Choose No to preserve all server data.", text)
        self.assertIn("MB_YESNO or MB_DEFBUTTON2", text)
        self.assertIn("DelTree(AppManagedServerDir, True, True, True);", text)

    def test_installer_configures_existing_server_paths(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("ExistingServerRadio.Caption := 'Leave the existing dedicated server unchanged (recommended)';", text)
        self.assertIn("procedure ConfigureExistingServer;", text)
        self.assertIn("SteamCmdExe := SelectedSteamCmdExe();", text)
        self.assertIn("UpdateConfigPaths(ServerDir, SteamCmdExe);", text)
        self.assertIn("if CurStep = ssPostInstall then", text)

    def test_installer_defaults_steamcmd_server_to_app_managed_folder(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function CurrentAppDir(): string;", text)
        self.assertIn("Result := WizardDirValue();", text)
        self.assertIn("function DefaultManagedServerDir(): string;", text)
        self.assertIn("Result := AddBackslash(CurrentAppDir()) + 'Server';", text)
        self.assertIn("procedure SyncManagedServerDefault;", text)
        self.assertIn("CurPageID = ServerDirPage.ID", text)
        self.assertIn("Choose where SteamCMD should install the new Vein dedicated server.", text)
        self.assertNotIn("ServerDirPage.Values[0] := ExpandConstant('{sd}\\VeinServer');", text)

    def test_installer_defaults_to_guided_server_and_steamcmd_install(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("PrimaryIntentRadio.Checked := True;", text)
        self.assertIn("SetupNewServer := InstallNewServer;", text)
        self.assertIn("if not ExistingAppInstall then", text)
        self.assertIn("InstallServerRadio.Checked := True;", text)
        self.assertIn("InstallServerRadio.Checked := False;", text)
        self.assertIn("ExistingServerRadio.Checked := True;", text)
        self.assertIn("AppSteamCmdRadio.Checked := True;", text)
        self.assertIn("NoSteamCmdRadio.Checked := False;", text)

    def test_config_template_defaults_to_app_managed_install_layout(self) -> None:
        text = CONFIG_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('  server_root: "Server"', text)
        self.assertIn("save_games:", text)
        self.assertIn("game_log:", text)
        self.assertIn('  override: ""', text)
        self.assertNotIn("  logs_dir:", text)
        self.assertNotIn("  absolute_log_file:", text)
        self.assertIn('  steamcmd_path: "SteamCMD/steamcmd.exe"', text)

    def test_installer_rewrites_app_managed_template_paths(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('ReplaceConfigValue(Content, \'  server_root: "Server"\'', text)
        self.assertNotIn("  saves_dir:", text)
        self.assertNotIn("  logs_dir:", text)
        self.assertNotIn("  absolute_log_file:", text)
        self.assertIn('ReplaceConfigValue(Content, \'  steamcmd_path: "SteamCMD/steamcmd.exe"\'', text)
        self.assertIn('\'  steamcmd_path: ""\'', text)

    def test_installer_supports_existing_steamcmd_for_server_install(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("ExistingSteamCmdRadio.Caption := 'Use an existing SteamCMD folder';", text)
        self.assertIn("NoSteamCmdRadio.Caption := 'Do not configure SteamCMD now';", text)
        self.assertIn("SteamCmdChoiceBox.Width := SteamCmdChoicePage.SurfaceWidth - ScaleX(12);", text)
        self.assertIn("SteamCmdChoiceBox.Height := ScaleY(96);", text)
        self.assertIn("procedure UpdateSteamCmdChoiceAvailability;", text)
        self.assertIn("AppSteamCmdRadio.Enabled := InstallServer;", text)
        self.assertIn("function ValidateExistingSteamCmdDir: Boolean;", text)
        self.assertIn("SteamCmdExe := AddBackslash(ExistingSteamCmdDirPage.Values[0]) + 'steamcmd.exe';", text)
        self.assertIn("if UseExistingSteamCmd then", text)
        self.assertIn(
            "Result := (not InstallServer) or (not UseExistingSteamCmd) or",
            text,
        )
        self.assertIn("function ValidateSteamCmdChoice: Boolean;", text)

    def test_installer_derives_server_data_paths_from_server_root(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn("DataDirPage", text)
        self.assertNotIn("SaveGames folder:", text)
        self.assertNotIn("Logs folder:", text)
        self.assertNotIn("procedure SyncDataPathDefaults;", text)
        self.assertNotIn("function ValidateDataDirs: Boolean;", text)
        self.assertIn("UpdateConfigPaths(ServerDir, SteamCmdExe);", text)

    def test_installer_validates_existing_server_executable_candidates(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("'Vein\\Binaries\\Win64\\VeinServer.exe'", text)
        self.assertIn("'Vein\\Binaries\\Win64\\VeinServer-Win64-Test.exe'", text)
        self.assertIn("'Use this folder anyway?'", text)

    def test_installer_keeps_steamcmd_out_of_server_root(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Result := AddBackslash(CurrentAppDir()) + 'SteamCMD';", text)
        self.assertIn("SteamCmdDir := DefaultAppSteamCmdDir();", text)
        self.assertNotIn("SteamCmdDir := AddBackslash(ServerDir) + 'SteamCMD';", text)

    def test_installer_extracts_steamcmd_to_temp_before_copying(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function PowerShellQuote(const Value: string): string;", text)
        self.assertIn("ExtractDir := ExpandConstant('{tmp}\\steamcmd_extract');", text)
        self.assertIn("[System.IO.Compression.ZipFile]::ExtractToDirectory", text)
        self.assertIn("PowerShellQuote(TempZip) + ', ' + PowerShellQuote(ExtractDir)", text)
        self.assertIn("ExtractedSteamCmdExe := AddBackslash(ExtractDir) + 'steamcmd.exe';", text)
        self.assertIn("CopyFile(ExtractedSteamCmdExe, SteamCmdExe, False);", text)
        self.assertNotIn("ForceDirectories(ExtractDir);", text)
        self.assertNotIn("Expand-Archive -Path", text)
        self.assertNotIn('ExtractToDirectory("' + "' + TempZip", text)

    def test_installer_captures_steamcmd_install_output_to_log(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("SteamCmdLog := ExpandConstant('{app}\\Logs\\steamcmd-install.log');", text)
        self.assertIn("SteamCmdProgressLog := SteamCmdLog;", text)
        self.assertIn("SaveStringToFile(SteamCmdProgressLog, S + #13#10, True);", text)
        self.assertIn("SteamCMD internal logs:", text)
        self.assertIn("AddBackslash(SteamCmdDir) + 'logs'", text)

    def test_installer_streams_steamcmd_status_to_animated_progress_page(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("CreateOutputMarqueeProgressPage", text)
        self.assertIn("SteamCmdProgressPage.Animate;", text)
        self.assertIn("ExecAndLogOutput(", text)
        self.assertIn("@SteamCmdOutput", text)
        self.assertIn("Waiting for live SteamCMD status...", text)
        self.assertIn("ExtractSteamCmdProgress", text)
        self.assertIn("Downloading Vein server files...", text)
        self.assertIn("Verifying Vein server files...", text)
        self.assertIn("Updating or repairing the existing Vein dedicated server via SteamCMD", text)
        self.assertNotIn("This can take several minutes...", text)

    def test_installer_uses_owned_steamcmd_runner_and_preserves_config_on_failure(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("steamcmd-run --steamcmd-exe", text)
        self.assertIn("--app-id {#SteamAppId} --cancel-file", text)
        self.assertIn("FileContainsText(SteamCmdLog, 'Success! App ''{#SteamAppId}'' fully installed.')", text)
        self.assertIn(
            "SteamCMD could not install, update, or repair the VEIN dedicated server after two attempts.",
            text,
        )
        self.assertIn("MB_RETRYCANCEL", text)
        self.assertIn("RetryResult = IDRETRY", text)
        self.assertIn("until InstallSucceeded or (RetryResult <> IDRETRY);", text)
        self.assertIn("UpdateConfigPaths(ServerDir, SteamCmdExe);", text)
        self.assertIn("SaveServerInstallPath(ServerDir);", text)
        self.assertIn("mbInformation", text)

    def test_installer_does_not_offer_a_nonfunctional_steamcmd_cancel_control(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn("SteamCmdCancelButton", text)
        self.assertNotIn("procedure SteamCmdCancelClick", text)
        self.assertIn("SteamCMD cannot be cancelled safely from this installer step.", text)
        self.assertIn("run Update/Repair later to resume and validate the partial files", text)
        self.assertIn("type ''quit'' to exit", text)

    def test_installer_pumps_button_events_while_waiting_for_steamcmd(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("SteamCmdMessagePumpPage := CreateOutputProgressPage('', '');", text)
        self.assertIn("SteamCmdMessagePumpPage.SetProgress(SteamCmdMessagePumpStep, 1);", text)
        self.assertIn("if CleanLine = '__VEIN_STEAMCMD_HEARTBEAT__' then", text)

        callback_start = text.index("procedure SteamCmdOutput")
        callback_end = text.index("function RunPowerShell", callback_start)
        callback = text[callback_start:callback_end]
        self.assertLess(callback.index("__VEIN_STEAMCMD_HEARTBEAT__"), callback.index("SaveStringToFile"))

    def test_installer_restores_finish_page_interaction(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn("SteamCmdOperationActive", text)
        self.assertNotIn("WizardForm.Enabled := False;", text)
        self.assertIn("if CurPageID = wpFinished then", text)
        self.assertIn("WizardForm.NextButton.Enabled := True;", text)

    def test_installer_automatically_retries_first_steamcmd_failure_and_keeps_both_logs(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("AttemptNumber := AttemptNumber + 1;", text)
        self.assertIn("if AttemptNumber = 1 then", text)
        self.assertIn("RetryResult := IDRETRY;", text)
        self.assertIn("retrying automatically", text.lower())
        self.assertIn("after two attempts", text)
        self.assertIn("===== SteamCMD attempt ", text)
        self.assertEqual(text.count("DeleteFile(SteamCmdLog);"), 1)

    def test_installer_distinguishes_steamcmd_initialization_from_server_download(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("__VEIN_STEAMCMD_PHASE__:", text)
        self.assertIn("Initializing SteamCMD...", text)
        self.assertIn("Updating SteamCMD...", text)
        self.assertIn("SteamCMD is initialized. Starting the Vein server download", text)

    def test_cli_packaging_collects_dynamic_tools_subcommands(self) -> None:
        module = _load_build_module()
        args = module._cli_pyinstaller_args(dist=ROOT / "dist", build=ROOT / "build")

        self.assertIn("--collect-submodules", args)
        self.assertIn("Tools", args)
        for module_name in module.CLI_HIDDEN_IMPORTS:
            self.assertIn(module_name, args)

    def test_installer_rejects_inner_vein_folder_selection(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("'Binaries\\Win64\\VeinServer.exe'", text)
        self.assertIn("'The selected folder appears to be the inner Vein game folder.'", text)
        self.assertIn("'Choose its parent folder instead. For example, choose:'", text)

    def test_copy_config_dir_stages_example_as_runtime_config(self) -> None:
        module = _load_build_module()
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            src = root / "Config"
            dst = root / "Bundle" / "Config"
            src.mkdir()
            (src / "config.yaml").write_text("secret: true\n", encoding="utf-8")
            (src / "config.example.yaml").write_text("secret: false\n", encoding="utf-8")

            original_root = module.REPO_ROOT
            original_template = module.CONFIG_TEMPLATE
            try:
                module.REPO_ROOT = root
                module.CONFIG_TEMPLATE = Path("Config/config.example.yaml")
                module._copy_config_dir(src, dst)
            finally:
                module.REPO_ROOT = original_root
                module.CONFIG_TEMPLATE = original_template

            self.assertEqual((dst / "config.yaml").read_text(encoding="utf-8"), "secret: false\n")
            self.assertEqual((dst / "config.example.yaml").read_text(encoding="utf-8"), "secret: false\n")

    def test_stage_bundle_excludes_local_sensitive_and_dev_files(self) -> None:
        module = _load_build_module()
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            pyinstaller_dir = root / "PyInstallerOutput"
            pyinstaller_dir.mkdir()
            (pyinstaller_dir / "VeinManager.exe").write_text("exe", encoding="utf-8")

            controller = root / "Controller"
            (controller / "Backups" / "Configs").mkdir(parents=True)
            (controller / "Backups" / "Configs" / "config-secret.yaml").write_text("secret", encoding="utf-8")
            (controller / "Legacy" / "WebAdmin").mkdir(parents=True)
            (controller / "Legacy" / "WebAdmin" / "user_accounts.json").write_text("secret", encoding="utf-8")
            (controller / "Legacy" / "WebAdmin" / "web_admin.py").write_text("ok", encoding="utf-8")

            config = root / "Config"
            (config / "Backup").mkdir(parents=True)
            (config / "Backup" / "config.json").write_text("secret", encoding="utf-8")
            (config / "config.yaml").write_text("secret: true\n", encoding="utf-8")
            (config / "config.example.yaml").write_text("secret: false\n", encoding="utf-8")

            scripts = root / "Scripts"
            scripts.mkdir()
            (scripts / "StartServer.bat").write_text("ok", encoding="utf-8")
            (scripts / "TestSuite.bat").write_text("dev", encoding="utf-8")

            (root / "Docs").mkdir()
            (root / "Docs" / "readme.md").write_text("docs", encoding="utf-8")

            bundle = root / "Bundle"
            original_root = module.REPO_ROOT
            original_template = module.CONFIG_TEMPLATE
            try:
                module.REPO_ROOT = root
                module.CONFIG_TEMPLATE = Path("Config/config.example.yaml")
                module._stage_bundle(pyinstaller_dir, bundle)
            finally:
                module.REPO_ROOT = original_root
                module.CONFIG_TEMPLATE = original_template

            self.assertFalse((bundle / "Controller" / "Backups").exists())
            self.assertFalse((bundle / "Controller" / "Legacy" / "WebAdmin" / "user_accounts.json").exists())
            self.assertTrue((bundle / "Controller" / "Legacy" / "WebAdmin" / "web_admin.py").exists())
            self.assertFalse((bundle / "Config" / "Backup").exists())
            self.assertEqual((bundle / "Config" / "config.yaml").read_text(encoding="utf-8"), "secret: false\n")
            self.assertTrue((bundle / "Scripts" / "StartServer.bat").exists())
            self.assertFalse((bundle / "Scripts" / "TestSuite.bat").exists())

    def test_stage_bundle_writes_package_version_file(self) -> None:
        module = _load_build_module()
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            pyinstaller_dir = root / "PyInstallerOutput"
            pyinstaller_dir.mkdir()
            (pyinstaller_dir / "VeinManager.exe").write_text("exe", encoding="utf-8")
            for name in ("Controller", "Config", "Docs", "Scripts"):
                (root / name).mkdir()
            (root / "Config" / "config.example.yaml").write_text("version: 2\n", encoding="utf-8")

            bundle = root / "Bundle"
            original_root = module.REPO_ROOT
            original_template = module.CONFIG_TEMPLATE
            try:
                module.REPO_ROOT = root
                module.CONFIG_TEMPLATE = Path("Config/config.example.yaml")
                with mock.patch.dict(module.os.environ, {"VEIN_PACKAGE_VERSION": "v9.8.7"}):
                    module._stage_bundle(pyinstaller_dir, bundle)
            finally:
                module.REPO_ROOT = original_root
                module.CONFIG_TEMPLATE = original_template

            self.assertEqual((bundle / "version.txt").read_text(encoding="utf-8"), "9.8.7\n")


if __name__ == "__main__":
    unittest.main()
