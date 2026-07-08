from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


WINDOWS_SERVER_CONFIG_DIR = Path("Vein") / "Saved" / "Config" / "WindowsServer"
GAME_INI_SECTION = "/Script/Vein.VeinGameSession"
ENGINE_GAME_SESSION_SECTION = "/Script/Engine.GameSession"
ONLINE_STEAM_SECTION = "OnlineSubsystemSteam"
URL_SECTION = "URL"
CORE_LOG_SECTION = "Core.Log"


@dataclass(frozen=True)
class ServerConfigCheck:
    name: str
    status: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _path_from_value(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return Path(str(value)).expanduser()


def _int_from_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bool_from_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _nested_get(data: Mapping[str, Any], dotted: str, default: Any = None) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def _strip_unreal_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def read_unreal_ini(path: Path) -> dict[str, dict[str, list[str]]]:
    """Read an Unreal INI without losing duplicate or +prefixed keys."""
    sections: dict[str, dict[str, list[str]]] = {}
    current = ""

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            sections.setdefault(current, {})
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        normalized_key = key.strip().lstrip("+").strip()
        if not normalized_key:
            continue
        section = sections.setdefault(current, {})
        section.setdefault(normalized_key, []).append(_strip_unreal_value(value))

    return sections


def _first_value(
    sections: Mapping[str, Mapping[str, list[str]]],
    section: str,
    key: str,
) -> str | None:
    values = sections.get(section, {}).get(key)
    if not values:
        return None
    return values[0]


def _all_values(
    sections: Mapping[str, Mapping[str, list[str]]],
    section: str,
    key: str,
) -> list[str]:
    return list(sections.get(section, {}).get(key, []))


def server_config_paths(server_root: Path) -> dict[str, Path]:
    config_dir = server_root / WINDOWS_SERVER_CONFIG_DIR
    return {
        "config_dir": config_dir,
        "game_ini": config_dir / "Game.ini",
        "engine_ini": config_dir / "Engine.ini",
        "win64_dir": server_root / "Vein" / "Binaries" / "Win64",
        "steam_api64": server_root / "Vein" / "Binaries" / "Win64" / "steam_api64.dll",
    }


def _configured_executable_paths(cfg: Mapping[str, Any], server_root: Path) -> list[Path]:
    candidates = cfg.get("server_executables")
    if not isinstance(candidates, list) or not candidates:
        candidates = [
            "Vein/Binaries/Win64/VeinServer.exe",
            "Vein/Binaries/Win64/VeinServer-Win64-Test.exe",
            "Vein/Binaries/Win64/VeinServer-Win64-Shipping.exe",
        ]
    return [server_root / str(candidate) for candidate in candidates]


def _check_expected_int(
    checks: list[ServerConfigCheck],
    *,
    name: str,
    label: str,
    sections: Mapping[str, Mapping[str, list[str]]],
    section: str,
    key: str,
    expected: int,
) -> None:
    actual = _first_value(sections, section, key)
    if actual is None:
        checks.append(
            ServerConfigCheck(
                name,
                "WARN",
                f"{label} is not configured in Game.ini section [{section}] as {key}.",
            )
        )
        return

    try:
        actual_int = int(actual)
    except ValueError:
        checks.append(ServerConfigCheck(name, "WARN", f"{label} is not numeric: {actual}"))
        return

    if actual_int == expected:
        checks.append(ServerConfigCheck(name, "PASS", f"{label} matches configured value {expected}."))
    else:
        checks.append(
            ServerConfigCheck(
                name,
                "WARN",
                f"{label} is {actual_int}, but management config expects {expected}.",
            )
        )


def validate_server_config(cfg: Mapping[str, Any]) -> list[ServerConfigCheck]:
    checks: list[ServerConfigCheck] = []
    server_root = _path_from_value(cfg.get("server_dir"))
    if server_root is None:
        return [ServerConfigCheck("server.config.root", "WARN", "Server root is not configured.")]

    paths = server_config_paths(server_root)
    if not server_root.exists():
        return [ServerConfigCheck("server.config.root", "WARN", f"Server root does not exist: {server_root}")]

    executable_paths = _configured_executable_paths(cfg, server_root)
    existing_exe = [path for path in executable_paths if path.is_file()]
    if existing_exe:
        checks.append(ServerConfigCheck("server.install.executable", "PASS", f"Found server executable: {existing_exe[0]}"))
    else:
        checks.append(
            ServerConfigCheck(
                "server.install.executable",
                "WARN",
                "No configured server executable was found under the server root.",
            )
        )

    if paths["steam_api64"].is_file():
        checks.append(ServerConfigCheck("server.install.steam_api64", "PASS", f"Found Steam API DLL: {paths['steam_api64']}"))
    else:
        checks.append(
            ServerConfigCheck(
                "server.install.steam_api64",
                "WARN",
                f"Missing steam_api64.dll at {paths['steam_api64']}; Steam server discovery may fail.",
            )
        )

    game_ini = paths["game_ini"]
    if not game_ini.is_file():
        checks.append(ServerConfigCheck("server.config.game_ini", "WARN", f"Game.ini was not found: {game_ini}"))
        return checks

    checks.append(ServerConfigCheck("server.config.game_ini", "PASS", f"Game.ini is readable: {game_ini}"))
    game_sections = read_unreal_ini(game_ini)

    http_enabled = _bool_from_value(_nested_get(cfg, "http_api.enabled"), False)
    if http_enabled:
        _check_expected_int(
            checks,
            name="server.config.http_port",
            label="HTTP API port",
            sections=game_sections,
            section=GAME_INI_SECTION,
            key="HTTPPort",
            expected=_int_from_value(_nested_get(cfg, "http_api.port"), 8080),
        )

    _check_expected_int(
        checks,
        name="server.config.game_port",
        label="Gameplay port",
        sections=game_sections,
        section=URL_SECTION,
        key="Port",
        expected=_int_from_value(cfg.get("game_port"), 7777),
    )
    _check_expected_int(
        checks,
        name="server.config.query_port",
        label="Steam query port",
        sections=game_sections,
        section=ONLINE_STEAM_SECTION,
        key="GameServerQueryPort",
        expected=_int_from_value(cfg.get("query_port"), 27015),
    )
    _check_expected_int(
        checks,
        name="server.config.max_players",
        label="Max players",
        sections=game_sections,
        section=ENGINE_GAME_SESSION_SECTION,
        key="MaxPlayers",
        expected=_int_from_value(cfg.get("max_players"), 8),
    )

    server_name = _first_value(game_sections, GAME_INI_SECTION, "ServerName")
    if server_name:
        checks.append(ServerConfigCheck("server.config.server_name", "PASS", f"ServerName is configured: {server_name}"))
    else:
        checks.append(ServerConfigCheck("server.config.server_name", "WARN", "ServerName is not configured in Game.ini."))

    admins = _all_values(game_sections, GAME_INI_SECTION, "AdminSteamIDs")
    super_admins = _all_values(game_sections, GAME_INI_SECTION, "SuperAdminSteamIDs")
    if admins or super_admins:
        checks.append(ServerConfigCheck("server.config.admins", "PASS", "Admin Steam ID entries are present."))
    else:
        checks.append(ServerConfigCheck("server.config.admins", "WARN", "No AdminSteamIDs or SuperAdminSteamIDs are configured."))

    engine_ini = paths["engine_ini"]
    if not engine_ini.is_file():
        checks.append(ServerConfigCheck("server.config.engine_ini", "WARN", f"Engine.ini was not found: {engine_ini}"))
        return checks

    checks.append(ServerConfigCheck("server.config.engine_ini", "PASS", f"Engine.ini is readable: {engine_ini}"))
    engine_sections = read_unreal_ini(engine_ini)
    core_log = engine_sections.get(CORE_LOG_SECTION, {})
    if core_log.get("LogOnline") or core_log.get("LogOnlineSession"):
        checks.append(ServerConfigCheck("server.config.core_log", "PASS", "Optional Core.Log noise controls are configured."))
    else:
        checks.append(
            ServerConfigCheck(
                "server.config.core_log",
                "WARN",
                "Optional Core.Log noise controls are not configured; EOS log spam may be noisy.",
            )
        )

    return checks


def summarize(results: Iterable[ServerConfigCheck]) -> dict[str, int]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return counts


def format_text_report(results: list[ServerConfigCheck]) -> str:
    counts = summarize(results)
    lines = ["Vein Server Config Check", ""]
    for result in results:
        lines.append(f"[{result.status}] {result.name}: {result.message}")
    lines.extend(
        [
            "",
            f"Summary: {counts['PASS']} passed, {counts['WARN']} warning(s), {counts['FAIL']} failure(s).",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run read-only Vein server install and config checks.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    import config as config_module

    results = validate_server_config(config_module.load_config())
    counts = summarize(results)
    if args.json:
        print(json.dumps({"summary": counts, "results": [result.as_dict() for result in results]}, indent=2))
    else:
        print(format_text_report(results))
    return 1 if counts.get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
