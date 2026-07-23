"""vein_tools.py - Consolidated CLI launcher for packaged deployments.

This script allows packaged builds (VeinTools.exe) to run controller helpers
without requiring a standalone Python installation. Subcommands call the
existing modules directly (start_server, shutdown_server, monitors, etc.).
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


def _mgmt_root() -> Path:
    env = os.environ.get("VEIN_MGMT_ROOT")
    if env:
        return Path(env).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


ROOT = _mgmt_root()
CONFIG_DIR = ROOT / "Config"
CTRL_DIR = ROOT / "Controller"

if str(CTRL_DIR) not in sys.path:
    sys.path.insert(0, str(CTRL_DIR))


def _list_config_files(folder: Path) -> list[Path]:
    files = list(folder.glob("*.yaml")) + list(folder.glob("*.yml"))
    files += list(folder.glob("*.json"))
    return sorted(files)


def _default_config() -> Path:
    explicit = os.environ.get("VEIN_CONFIG")
    if explicit:
        p = Path(explicit).expanduser()
        if p.exists():
            return p
    for cand in _list_config_files(CONFIG_DIR):
        if cand.exists():
            return cand
    return CONFIG_DIR / "config.yaml"


DEFAULT_CONFIG = _default_config()


@contextmanager
def _clean_child_argv():
    original = sys.argv[:]
    sys.argv = [original[0] if original else "VeinTools.exe"]
    try:
        yield
    finally:
        sys.argv = original


@dataclass(frozen=True)
class CommandSpec:
    module: str
    attr: str
    description: str

    def run(self) -> int:
        module = importlib.import_module(self.module)
        func: Callable[..., int] | Callable[..., None] = getattr(module, self.attr)
        with _clean_child_argv():
            result = func()
        return int(result) if isinstance(result, int) else 0


COMMANDS: dict[str, CommandSpec] = {
    "start-server": CommandSpec("start_server", "main", "Start the Vein server"),
    "stop-server": CommandSpec("shutdown_server", "main", "Stop the Vein server"),
    "monitor-log": CommandSpec(
        "monitor_log", "monitor", "Run the log monitor (blocking)"
    ),
    "stop-log-monitor": CommandSpec(
        "Tools.monitors", "stop_log_monitor", "Stop the log monitor"
    ),
    "crash-monitor": CommandSpec(
        "crash_monitor", "main", "Run the crash monitor (blocking)"
    ),
    "stop-crash-monitor": CommandSpec(
        "Tools.monitors", "stop_crash_monitor", "Stop the crash monitor"
    ),
    "stop-all-monitors": CommandSpec(
        "Tools.monitors", "stop_all_monitors", "Stop log + crash monitors"
    ),
    "uninstall-cleanup": CommandSpec(
        "Tools.uninstall_cleanup",
        "main",
        "Stop monitors and any running server before uninstall",
    ),
    "health-check": CommandSpec(
        "Tools.health_check", "main", "Run project health diagnostics"
    ),
    "server-config-check": CommandSpec(
        "Tools.server_config_validator",
        "main",
        "Run read-only Vein server install and config diagnostics",
    ),
    "nightly-backup": CommandSpec(
        "nightly_backup", "main", "Run the nightly backup routine once"
    ),
    "manual-backup": CommandSpec(
        "Tools.backups", "manual_backup_main", "Create one manual save backup"
    ),
}

SPECIAL_COMMANDS = {"restart-server", "steamcmd-run"}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="vein_tools",
        description="Launcher for Vein Server Management helpers.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=sorted(list(COMMANDS.keys()) + list(SPECIAL_COMMANDS)),
        help="Which helper to run",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to config.yaml (relative paths resolved from VEIN_MGMT_ROOT)",
    )
    parser.add_argument(
        "--restart-delay",
        type=int,
        default=2,
        help="Seconds to wait between stop/start when using restart-server",
    )
    parser.add_argument("--steamcmd-exe", default="", help=argparse.SUPPRESS)
    parser.add_argument("--server-dir", default="", help=argparse.SUPPRESS)
    parser.add_argument("--app-id", default="", help=argparse.SUPPRESS)
    parser.add_argument("--cancel-file", default="", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def _ensure_env(config_path: Path) -> None:
    # Explicit CLI arguments are authoritative.  A packaged GUI may switch
    # configs during its lifetime, so inherited values must not win here.
    os.environ["VEIN_MGMT_ROOT"] = str(ROOT)
    os.environ["VEIN_CONFIG"] = str(config_path)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    config_path = Path(args.config).expanduser()
    if not config_path.is_absolute():
        config_path = (ROOT / config_path).resolve()

    _ensure_env(config_path)

    cmd = args.command
    if cmd in SPECIAL_COMMANDS and cmd == "restart-server":
        stop = COMMANDS["stop-server"].run()
        if stop != 0:
            return stop
        delay = max(0, int(args.restart_delay))
        if delay:
            import time

            time.sleep(delay)
        return COMMANDS["start-server"].run()

    if cmd in SPECIAL_COMMANDS and cmd == "steamcmd-run":
        required = {
            "--steamcmd-exe": args.steamcmd_exe,
            "--server-dir": args.server_dir,
            "--app-id": args.app_id,
            "--cancel-file": args.cancel_file,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise SystemExit(f"steamcmd-run requires: {', '.join(missing)}")
        from Tools.steamcmd_runner import run_steamcmd

        return run_steamcmd(
            Path(args.steamcmd_exe),
            Path(args.server_dir),
            args.app_id,
            Path(args.cancel_file),
        )

    spec = COMMANDS.get(cmd)
    if not spec:
        raise SystemExit(f"Unknown command: {cmd}")
    return spec.run()


if __name__ == "__main__":
    raise SystemExit(main())
