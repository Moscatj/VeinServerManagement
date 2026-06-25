from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import process  # noqa: E402


class ProcessHelperTests(unittest.TestCase):
    def test_exe_matching_supports_globs_and_empty_values(self) -> None:
        self.assertTrue(process._exe_matches_any("VeinServer-Win64-Test.exe", ["VeinServer-*.exe"]))
        self.assertTrue(process._exe_matches_any("VeinServer.exe", ["VeinServer.exe"]))
        self.assertFalse(process._exe_matches_any("", ["VeinServer.exe"]))
        self.assertFalse(process._exe_matches_any(None, ["VeinServer.exe"]))

    def test_cmdline_head_handles_list_and_string(self) -> None:
        self.assertEqual(
            process._cmdline_head({"cmdline": [r"C:\Game\VeinServer.exe", "-log"]}),
            r"C:\Game\VeinServer.exe",
        )
        self.assertEqual(
            process._cmdline_head({"cmdline": r'"C:\Game\VeinServer.exe" -log'}),
            r"C:\Game\VeinServer.exe",
        )
        self.assertEqual(process._cmdline_head({"cmdline": []}), "")

    def test_process_name_candidates_include_name_and_cmdline_basename(self) -> None:
        names = process._process_name_candidates(
            {"name": "python.exe", "cmdline": [r"C:\Game\VeinServer.exe"]}
        )

        self.assertEqual(names, ["python.exe", "VeinServer.exe"])

    def test_matches_known_executables_and_cwd(self) -> None:
        info = {"name": "python.exe", "cmdline": [r"C:\Game\VeinServer.exe"], "cwd": r"C:\Game"}

        self.assertTrue(process._matches_known_executables(info, ["VeinServer.exe"]))
        self.assertFalse(process._matches_known_executables(info, ["Other.exe"]))
        self.assertTrue(process._cwd_matches(info, str(Path(r"C:\Game"))))
        self.assertFalse(process._cwd_matches(info, str(Path(r"C:\Other"))))

    def test_choose_executable_returns_first_existing_candidate(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_dir = Path(tmp)
            second = server_dir / "B.exe"
            second.write_text("", encoding="utf-8")

            chosen = process._choose_executable(server_dir, ["A.exe", "B.exe"])

        self.assertEqual(chosen, second)


if __name__ == "__main__":
    unittest.main()
