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


def _load_build_module():
    spec = importlib.util.spec_from_file_location("build_gui_exe_for_test", BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load packaging build script")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PackagingBuildTests(unittest.TestCase):
    def test_installer_grants_modify_permissions_to_writable_app_dirs(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        for folder in ("Backups", "Config", "Logs", "Runtime", "SteamCMD", "Server"):
            self.assertIn(f'Name: "{{app}}\\{folder}"; Permissions: users-modify', text)

    def test_installer_excludes_runtime_folder_contents(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('Excludes: "Backups\\*,Logs\\*,Runtime\\*"', text)

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
        self.assertIn('Type: dirifempty; Name: "{app}"', text)

    def test_installer_server_choice_controls_have_explicit_heights(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("InstallServerRadio.Height := ScaleY(26);", text)
        self.assertIn("ExistingServerRadio.Height := ScaleY(26);", text)
        self.assertIn("InstallServerBox.Height := ScaleY(56);", text)

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

        self.assertIn("ExistingServerRadio.Caption := 'Use an existing dedicated server folder';", text)
        self.assertIn("procedure ConfigureExistingServer;", text)
        self.assertIn("SteamCmdExe := SelectedSteamCmdExe();", text)
        self.assertIn("UpdateConfigPaths(ServerDir, DataDirPage.Values[0], DataDirPage.Values[1], SteamCmdExe);", text)
        self.assertIn("if CurStep = ssPostInstall then", text)

    def test_installer_defaults_steamcmd_server_to_app_managed_folder(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function DefaultManagedServerDir(): string;", text)
        self.assertIn("Result := ExpandConstant('{app}\\Server');", text)
        self.assertIn("procedure SyncManagedServerDefault;", text)
        self.assertIn("CurPageID = ServerDirPage.ID", text)
        self.assertIn("SteamCMD installs use the app-managed Server folder by default", text)
        self.assertNotIn("ServerDirPage.Values[0] := ExpandConstant('{sd}\\VeinServer');", text)

    def test_installer_supports_existing_steamcmd_for_server_install(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("ExistingSteamCmdRadio.Caption := 'Use an existing SteamCMD folder';", text)
        self.assertIn("NoSteamCmdRadio.Caption := 'Do not configure SteamCMD now';", text)
        self.assertIn("procedure UpdateSteamCmdChoiceAvailability;", text)
        self.assertIn("AppSteamCmdRadio.Enabled := InstallServer;", text)
        self.assertIn("function ValidateExistingSteamCmdDir: Boolean;", text)
        self.assertIn("SteamCmdExe := AddBackslash(ExistingSteamCmdDirPage.Values[0]) + 'steamcmd.exe';", text)
        self.assertIn("if UseExistingSteamCmd then", text)
        self.assertIn("Result := not UseExistingSteamCmd;", text)
        self.assertIn("function ValidateSteamCmdChoice: Boolean;", text)

    def test_installer_supports_save_and_log_path_overrides(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("DataDirPage := CreateInputDirPage", text)
        self.assertIn("DataDirPage.Add('SaveGames folder:');", text)
        self.assertIn("DataDirPage.Add('Logs folder:');", text)
        self.assertIn("procedure SyncDataPathDefaults;", text)
        self.assertIn("function ValidateDataDirs: Boolean;", text)
        self.assertIn("UpdateConfigPaths(ServerDir, DataDirPage.Values[0], DataDirPage.Values[1], SteamCmdExe);", text)

    def test_installer_validates_existing_server_executable_candidates(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("'Vein\\Binaries\\Win64\\VeinServer.exe'", text)
        self.assertIn("'Vein\\Binaries\\Win64\\VeinServer-Win64-Test.exe'", text)
        self.assertIn("'Use this folder anyway?'", text)

    def test_installer_keeps_steamcmd_out_of_server_root(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

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
        self.assertIn('> "\' + SteamCmdLog + \'" 2>&1"', text)
        self.assertIn("SteamCMD internal logs:", text)
        self.assertIn("AddBackslash(SteamCmdDir) + 'logs'", text)

    def test_installer_hides_blank_steamcmd_console_and_sets_wait_status(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "Installing Vein dedicated server via SteamCMD. This can take several minutes...",
            text,
        )
        self.assertIn("SW_HIDE", text)

    def test_installer_uses_explicit_steamcmd_platform_and_preserves_config_on_failure(self) -> None:
        text = INSTALLER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("+@sSteamCmdForcePlatformType windows", text)
        self.assertIn("+app_update {#SteamAppId} -beta public validate +quit", text)
        self.assertIn("FileContainsText(SteamCmdLog, 'Success! App ''{#SteamAppId}'' fully installed.')", text)
        self.assertIn("The management app was installed, but SteamCMD could not download", text)
        self.assertIn("UpdateConfigPaths(ServerDir, DataDirPage.Values[0], DataDirPage.Values[1], SteamCmdExe);", text)
        self.assertIn("SaveServerInstallPath(ServerDir);", text)
        self.assertIn("mbInformation", text)

    def test_cli_packaging_collects_dynamic_tools_subcommands(self) -> None:
        module = _load_build_module()
        args = module._cli_pyinstaller_args(dist=ROOT / "dist", build=ROOT / "build")

        self.assertIn("--collect-submodules", args)
        self.assertIn("Tools", args)

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
