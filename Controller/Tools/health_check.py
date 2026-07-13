from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from Tools.server_config_validator import validate_server_config


HERE = Path(__file__).resolve().parent
CTRL = HERE.parent
ROOT = CTRL.parent
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

DISCORD_WEBHOOK_MARKER = "discord.com/api/webhooks/"


@dataclass(frozen=True)
class HealthCheckResult:
    name: str
    status: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def repo_root() -> Path:
    return ROOT


def _status_rank(status: str) -> int:
    return {"PASS": 0, "INFO": 1, "WARN": 2, "FAIL": 3}.get(status, 3)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _path_from_value(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return Path(str(value)).expanduser()


def _readable(path: Path) -> bool:
    try:
        if path.is_dir():
            next(path.iterdir(), None)
        else:
            with path.open("rb") as handle:
                handle.read(1)
        return True
    except StopIteration:
        return True
    except OSError:
        return False


def _writable_existing_dir(path: Path) -> bool:
    probe = path / ".health_check_write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _check_directory(
    name: str,
    value: Any,
    *,
    writable_inside_repo: bool = False,
    required: bool = False,
) -> HealthCheckResult:
    path = _path_from_value(value)
    if path is None:
        status = "FAIL" if required else "WARN"
        return HealthCheckResult(name, status, "Path is not configured.")

    if not path.exists():
        status = "FAIL" if required else "WARN"
        return HealthCheckResult(name, status, f"Directory does not exist: {path}")

    if not path.is_dir():
        return HealthCheckResult(name, "FAIL", f"Path is not a directory: {path}")

    if not _readable(path):
        return HealthCheckResult(name, "FAIL", f"Directory is not readable: {path}")

    if writable_inside_repo:
        if _is_within(path, repo_root()):
            if not _writable_existing_dir(path):
                return HealthCheckResult(name, "FAIL", f"Directory is not writable: {path}")
        else:
            return HealthCheckResult(
                name,
                "PASS",
                f"External directory is readable; write probe skipped: {path}",
            )

    return HealthCheckResult(name, "PASS", f"Directory is available: {path}")


def _check_file(name: str, value: Any, *, required: bool = False) -> HealthCheckResult:
    path = _path_from_value(value)
    if path is None:
        status = "FAIL" if required else "WARN"
        return HealthCheckResult(name, status, "File path is not configured.")

    if not path.exists():
        status = "FAIL" if required else "WARN"
        return HealthCheckResult(name, status, f"File does not exist: {path}")

    if not path.is_file():
        return HealthCheckResult(name, "FAIL", f"Path is not a file: {path}")

    if not _readable(path):
        return HealthCheckResult(name, "FAIL", f"File is not readable: {path}")

    return HealthCheckResult(name, "PASS", f"File is readable: {path}")


def _active_config_path(root: Path) -> Path | None:
    env_path = os.environ.get("VEIN_CONFIG", "").strip()
    if env_path:
        path = Path(env_path).expanduser()
        if not path.is_absolute():
            path = root / path
        return path

    for candidate in (
        root / "Config" / "config.yaml",
        root / "Config" / "config.yml",
        root / "Config" / "config.json",
        root / "Controller" / "config.json",
    ):
        if candidate.exists():
            return candidate
    return None


def _load_raw_config(path: Path | None) -> Mapping[str, Any]:
    if path is None or not path.exists():
        return {}

    try:
        if path.suffix.lower() in {".yaml", ".yml"}:
            import yaml

            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        else:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
    except Exception:
        return {}

    return data if isinstance(data, Mapping) else {}


def _walk_strings(data: Any, prefix: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(data, Mapping):
        for key, value in data.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from _walk_strings(value, child)
    elif isinstance(data, list):
        for index, value in enumerate(data):
            yield from _walk_strings(value, f"{prefix}[{index}]")
    elif isinstance(data, str):
        yield prefix, data


def check_config_load() -> tuple[dict[str, Any], HealthCheckResult]:
    try:
        import config as config_module

        if hasattr(config_module, "_CONFIG_CACHE"):
            config_module._CONFIG_CACHE = None
        cfg = config_module.load_config()
    except Exception as exc:
        return {}, HealthCheckResult("config.load", "FAIL", f"Config failed to load: {exc}")

    return dict(cfg), HealthCheckResult("config.load", "PASS", "Config loaded successfully.")


def check_dependencies() -> list[HealthCheckResult]:
    required = ("yaml", "psutil")
    optional = ("requests", "PySide6")
    results: list[HealthCheckResult] = []

    for module in required:
        status = "PASS" if importlib.util.find_spec(module) else "FAIL"
        message = "Dependency is importable." if status == "PASS" else "Required dependency is missing."
        results.append(HealthCheckResult(f"dependency.{module}", status, message))

    for module in optional:
        available = bool(importlib.util.find_spec(module))
        if module == "PySide6" and getattr(sys, "frozen", False) and not available:
            status = "INFO"
            message = "GUI runtime is bundled separately in VeinManager.exe."
        else:
            status = "PASS" if available else "WARN"
            message = (
                "Dependency is importable."
                if status == "PASS"
                else "Optional dependency is missing."
            )
        results.append(HealthCheckResult(f"dependency.{module}", status, message))

    return results


def check_discord_config(raw_cfg: Mapping[str, Any], resolved_cfg: Mapping[str, Any]) -> list[HealthCheckResult]:
    strings = list(_walk_strings(raw_cfg.get("discord", {})))
    strings.extend(_walk_strings({"discord_webhook": raw_cfg.get("discord_webhook", "")}))
    webhook_values = [
        (path, value.strip())
        for path, value in strings
        if value.strip() and ("webhook" in path.lower() or DISCORD_WEBHOOK_MARKER in value)
    ]

    raw_urls = [(path, value) for path, value in webhook_values if DISCORD_WEBHOOK_MARKER in value.lower()]
    if raw_urls:
        names = ", ".join(path for path, _ in raw_urls)
        return [
            HealthCheckResult(
                "discord.webhooks",
                "FAIL",
                f"Raw Discord webhook URL found in config at: {names}. Use ENV: variables.",
            )
        ]

    env_refs = [(path, value[4:]) for path, value in webhook_values if value.upper().startswith("ENV:")]
    missing = [env_name for _, env_name in env_refs if not os.environ.get(env_name)]
    if missing:
        return [
            HealthCheckResult(
                "discord.webhooks",
                "WARN",
                "Webhook config uses environment variables, but these are not set locally: "
                + ", ".join(sorted(set(missing))),
            )
        ]

    if env_refs:
        return [HealthCheckResult("discord.webhooks", "PASS", "Webhook config uses environment variables.")]

    if resolved_cfg.get("discord_webhook"):
        return [
            HealthCheckResult(
                "discord.webhooks",
                "WARN",
                "Discord webhook is available only after config resolution; verify it is not committed raw.",
            )
        ]

    return [HealthCheckResult("discord.webhooks", "PASS", "No raw Discord webhook URL found.")]


def check_server_executable(cfg: Mapping[str, Any]) -> HealthCheckResult:
    server_root = _path_from_value(cfg.get("server_dir"))
    candidates = cfg.get("server_executables") or []
    if server_root is None:
        return HealthCheckResult("server.executable", "WARN", "Server root is not configured.")
    if not server_root.exists():
        return HealthCheckResult("server.executable", "WARN", f"Server root does not exist: {server_root}")
    if not isinstance(candidates, list) or not candidates:
        return HealthCheckResult("server.executable", "WARN", "No server executable candidates are configured.")

    found = [server_root / str(candidate) for candidate in candidates if (server_root / str(candidate)).is_file()]
    if found:
        return HealthCheckResult("server.executable", "PASS", f"Found server executable: {found[0]}")

    return HealthCheckResult(
        "server.executable",
        "WARN",
        "No configured server executable was found under server root.",
    )


def check_steamcmd(cfg: Mapping[str, Any]) -> HealthCheckResult:
    features = cfg.get("features")
    steam_updates_enabled = True
    if isinstance(features, Mapping):
        steam_updates_enabled = bool(features.get("enable_steam_update", True))

    auto_update_on_start = bool(cfg.get("auto_update_on_start", True))
    steamcmd = str(cfg.get("steamcmd_path") or "").strip()
    if not steamcmd:
        if not steam_updates_enabled:
            return HealthCheckResult("steam.steamcmd", "PASS", "SteamCMD path is not set; Steam updates are disabled.")
        if not auto_update_on_start:
            return HealthCheckResult(
                "steam.steamcmd",
                "PASS",
                "SteamCMD path is not set; startup Steam updates are disabled.",
            )
        return HealthCheckResult("steam.steamcmd", "WARN", "SteamCMD path is not set.")

    path = Path(steamcmd).expanduser()
    if path.exists():
        return HealthCheckResult("steam.steamcmd", "PASS", f"SteamCMD path exists: {path}")

    return HealthCheckResult("steam.steamcmd", "WARN", f"SteamCMD path does not exist: {path}")


def run_health_checks(
    cfg: Mapping[str, Any] | None = None,
    raw_cfg: Mapping[str, Any] | None = None,
) -> list[HealthCheckResult]:
    results: list[HealthCheckResult] = []

    if cfg is None:
        loaded_cfg, config_result = check_config_load()
        cfg = loaded_cfg
        results.append(config_result)
    else:
        cfg = dict(cfg)
        results.append(HealthCheckResult("config.load", "PASS", "Config provided by caller."))

    if raw_cfg is None:
        raw_cfg = _load_raw_config(_active_config_path(repo_root()))

    results.extend(check_dependencies())

    if not cfg:
        return sorted(results, key=lambda item: (_status_rank(item.status), item.name))

    results.append(_check_directory("paths.server_root", cfg.get("server_dir"), required=True))
    results.append(_check_directory("paths.runtime_dir", cfg.get("runtime_dir"), writable_inside_repo=True))
    results.append(_check_directory("paths.mgmt_log_dir", cfg.get("mgmt_log_dir"), writable_inside_repo=True))
    results.append(_check_directory("backups.root", cfg.get("backup_root"), writable_inside_repo=True))
    results.append(_check_directory("paths.saves_dir", cfg.get("save_dir")))
    results.append(_check_directory("game_log.directory", cfg.get("logs_dir")))
    results.append(_check_file("game_log.active_file", cfg.get("game_log_file") or cfg.get("absolute_log_file")))
    results.append(check_server_executable(cfg))
    results.append(check_steamcmd(cfg))
    for check in validate_server_config(cfg):
        results.append(HealthCheckResult(check.name, check.status, check.message))
    results.extend(check_discord_config(raw_cfg, cfg))

    return sorted(results, key=lambda item: (_status_rank(item.status), item.name))


def summarize(results: Iterable[HealthCheckResult]) -> dict[str, int]:
    counts = {"PASS": 0, "INFO": 0, "WARN": 0, "FAIL": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return counts


def format_text_report(results: list[HealthCheckResult]) -> str:
    counts = summarize(results)
    lines = ["Vein Management Health Check", ""]
    for result in results:
        lines.append(f"[{result.status}] {result.name}: {result.message}")
    lines.extend(
        [
            "",
            f"Summary: {counts['PASS']} passed, {counts.get('INFO', 0)} info, {counts['WARN']} warning(s), {counts['FAIL']} failure(s).",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run read-only project health checks.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    results = run_health_checks()
    counts = summarize(results)
    if args.json:
        print(json.dumps({"summary": counts, "results": [result.as_dict() for result in results]}, indent=2))
    else:
        print(format_text_report(results))

    return 1 if counts.get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
