#!/usr/bin/env python3
"""Build the VeinManager GUI as a standalone executable and stage release assets."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable


def _repo_root() -> Path:
    cur = Path(__file__).resolve().parent
    for candidate in [cur] + list(cur.parents):
        if (candidate / "Controller").exists() and (candidate / "Config").exists():
            return candidate
    return cur


REPO_ROOT = _repo_root()
ENTRYPOINT = REPO_ROOT / "Controller" / "vein_manager.py"
CLI_ENTRYPOINT = REPO_ROOT / "Controller" / "vein_tools.py"
DEFAULT_DIST = REPO_ROOT / "dist"
DEFAULT_BUILD = REPO_ROOT / "build"
DEFAULT_BUNDLE = DEFAULT_DIST / "VeinServerManager"
SUPPORT_DIRS: tuple[str, ...] = ("Controller", "Config", "Docs", "Scripts")
EMPTY_DIRS: tuple[str, ...] = ("Backups", "Logs", "Runtime")
COMMON_IGNORE_PATTERNS: tuple[str, ...] = ("__pycache__", "*.pyc", "*.pyo")
SUPPORT_IGNORE_PATTERNS: dict[str, tuple[str, ...]] = {
    "Controller": (
        "Backups",
        "*.log",
    ),
    "Config": (
        "Backup",
        "config.yaml",
        "*.local.yaml",
        "*.local.json",
    ),
    "Scripts": (
        "BuildInstaller.bat",
        "InstallGitHooks.bat",
        "RunCoverage.bat",
        "TestSuite.bat",
        "UninstallGitHooks.bat",
    ),
}
EXTRA_FILES: tuple[Path, ...] = tuple(
    Path(p) for p in ("README.md", "AGENTS.md", "Docs/docs_for_codex.md")
)
CONFIG_TEMPLATE = Path("Config/config.example.yaml")
ICON_PATH = REPO_ROOT / "Installer" / "assets" / "VeinServerManager.ico"
VERSION_FILE = "version.txt"
CLI_HIDDEN_IMPORTS: tuple[str, ...] = (
    "start_server",
    "shutdown_server",
    "monitor_log",
    "crash_monitor",
    "nightly_backup",
)


def _ensure_pyinstaller():
    try:
        # Imported lazily so contributors that do not package do not need the dependency.
        import PyInstaller.__main__ as py_main
    except ImportError as exc:  # pragma: no cover - tooling helper
        raise SystemExit(
            "PyInstaller is required for packaging. Install it with 'pip install pyinstaller'."
        ) from exc
    return py_main


def _pyinstaller_args(*, dist: Path, build: Path, onefile: bool) -> list[str]:
    args = [
        str(ENTRYPOINT),
        "--noconfirm",
        "--clean",
        "--name",
        "VeinManager",
        "--distpath",
        str(dist),
        "--workpath",
        str(build),
        "--specpath",
        str(build / "spec"),
        "--paths",
        str(ENTRYPOINT.parent),
        "--collect-submodules",
        "GUI",
        "--collect-submodules",
        "ruamel",
        "--collect-submodules",
        "ruamel.yaml",
        "--collect-data",
        "ruamel",
        "--collect-data",
        "ruamel.yaml",
        "--windowed",
    ]
    args.append("--onefile" if onefile else "--onedir")
    if ICON_PATH.exists():
        args.extend(["--icon", str(ICON_PATH)])
    else:
        print(f"[WARN] Icon not found at {ICON_PATH}; using default PyInstaller icon.")
    return args


def _cli_pyinstaller_args(*, dist: Path, build: Path) -> list[str]:
    args = [
        str(CLI_ENTRYPOINT),
        "--noconfirm",
        "--clean",
        "--name",
        "VeinTools",
        "--distpath",
        str(dist),
        "--workpath",
        str(build),
        "--specpath",
        str(build / "cli" / "spec"),
        "--paths",
        str(ENTRYPOINT.parent),
        "--collect-submodules",
        "Tools",
        "--console",
        "--onefile",
    ]
    for module in CLI_HIDDEN_IMPORTS:
        args.extend(("--hidden-import", module))
    return args


def _copytree(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*COMMON_IGNORE_PATTERNS),
    )


def _copy_support_dir(name: str, src: Path, dst: Path) -> None:
    ignore_patterns = COMMON_IGNORE_PATTERNS + SUPPORT_IGNORE_PATTERNS.get(name, ())
    shutil.copytree(
        src,
        dst,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*ignore_patterns),
    )


def _stage_bundle(pyinstaller_dir: Path, bundle_dir: Path) -> None:
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    if pyinstaller_dir.is_file():
        bundle_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pyinstaller_dir, bundle_dir / pyinstaller_dir.name)
    else:
        shutil.copytree(pyinstaller_dir, bundle_dir)
    for name in SUPPORT_DIRS:
        src = REPO_ROOT / name
        if not src.exists():
            continue
        dst = bundle_dir / name
        if name.lower() == "config":
            _copy_config_dir(src, dst)
        else:
            _copy_support_dir(name, src, dst)
    for name in EMPTY_DIRS:
        (bundle_dir / name).mkdir(parents=True, exist_ok=True)
    for rel in EXTRA_FILES:
        src = REPO_ROOT / rel
        if src.exists():
            shutil.copy2(src, bundle_dir / src.name)
    if ICON_PATH.exists():
        shutil.copy2(ICON_PATH, bundle_dir / ICON_PATH.name)
    _write_version_file(bundle_dir)


def _copy_config_dir(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            *COMMON_IGNORE_PATTERNS,
            *SUPPORT_IGNORE_PATTERNS["Config"],
        ),
    )
    template_src = REPO_ROOT / CONFIG_TEMPLATE
    dst_cfg = dst / "config.yaml"
    if template_src.exists():
        shutil.copy2(template_src, dst_cfg)
    else:
        fallback = src / "config.yaml"
        if fallback.exists():
            shutil.copy2(fallback, dst_cfg)


def _resolve_package_version() -> str:
    for key in ("VEIN_PACKAGE_VERSION", "PACKAGE_VERSION", "VEIN_APP_VERSION"):
        value = os.environ.get(key, "").strip()
        if value:
            return value[1:] if value.lower().startswith("v") else value
    try:
        proc = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "0.0.0-dev"
    value = (proc.stdout or "").strip()
    if not value:
        return "0.0.0-dev"
    return value[1:] if value.lower().startswith("v") else value


def _write_version_file(bundle_dir: Path) -> None:
    (bundle_dir / VERSION_FILE).write_text(
        _resolve_package_version() + "\n",
        encoding="utf-8",
    )


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package VeinManager.exe and stage supporting resources."
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Use --onefile instead of the default directory-based build.",
    )
    parser.add_argument(
        "--dist",
        type=Path,
        default=DEFAULT_DIST,
        help=f"PyInstaller dist directory (default: {DEFAULT_DIST})",
    )
    parser.add_argument(
        "--build",
        type=Path,
        default=DEFAULT_BUILD,
        help=f"PyInstaller work directory (default: {DEFAULT_BUILD})",
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        default=DEFAULT_BUNDLE,
        help=f"Final staged bundle directory (default: {DEFAULT_BUNDLE})",
    )
    parser.add_argument(
        "--skip-stage",
        action="store_true",
        help="Only run PyInstaller; do not create the staged bundle directory.",
    )
    parser.add_argument(
        "--skip-cli",
        action="store_true",
        help="Skip building the VeinTools CLI executable.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = _parse_args(list(argv) if argv is not None else sys.argv[1:])
    py_main = _ensure_pyinstaller()
    pyinstaller_args = _pyinstaller_args(
        dist=args.dist,
        build=args.build,
        onefile=args.onefile,
    )
    py_main.run(pyinstaller_args)

    cli_output: Path | None = None
    if not args.skip_cli:
        cli_dist = args.dist / "cli"
        cli_build = args.build / "cli"
        cli_args = _cli_pyinstaller_args(dist=cli_dist, build=cli_build)
        py_main.run(cli_args)
        cli_output = cli_dist / "VeinTools.exe"
        if not cli_output.exists():
            raise SystemExit(f"CLI executable not found at {cli_output}")

    if args.skip_stage:
        return
    build_output = (
        args.dist / "VeinManager.exe"
        if args.onefile
        else args.dist / "VeinManager"
    )
    if not build_output.exists():
        raise SystemExit(f"PyInstaller output not found at {build_output}")
    _stage_bundle(build_output, args.bundle)
    if cli_output:
        shutil.copy2(cli_output, args.bundle / cli_output.name)
    print(f"Bundle staged at {args.bundle}")


if __name__ == "__main__":
    main()
