from __future__ import annotations

"""
SteamCMD update helper + CLI entrypoint.

Usage (CLI):
  py -3 Controller\\Tools\\update_steam.py
  py -3 Controller\\Tools\\update_steam.py --show-versions
  py -3 Controller\\Tools\\update_steam.py --json
  py -3 Controller\\Tools\\update_steam.py --ttl 300
  py -3 Controller\\Tools\\update_steam.py --no-cache
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent
CTRL = HERE.parent
ROOT = CTRL.parent
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from config_helper import config, get_path  # type: ignore
from Tools.features import is_feature_enabled  # type: ignore
from Tools.discord import send_discord_message  # type: ignore
from Tools.steam_version import get_versions, invalidate_cache  # type: ignore

SERVER_DIR = Path(get_path("server_dir"))
STEAMCMD_PATH: str = str(config.get("steamcmd_path", "") or "")
APP_ID: str = str(config.get("app_id", "") or "")


def check_for_steam_update() -> bool:
    """
    Run SteamCMD update for the configured app_id (retries + timeout).
    Fully gated by features.enable_steam_update.
    """
    if not is_feature_enabled("enable_steam_update", True):
        return True

    if not STEAMCMD_PATH or not APP_ID:
        print("[Update] SteamCMD path or App ID missing; skipping update.")
        return False

    validate = bool(config.get("steam_update_validate", True))
    beta = str(config.get("steam_update_beta", "") or "")
    beta_pwd = str(config.get("steam_update_beta_password", "") or "")
    retries = int(config.get("steam_update_retries", 2))
    timeout = int(config.get("steam_update_timeout_seconds", 900))

    app_arg = f"{APP_ID}"
    if beta:
        app_arg += f" -beta {beta}"
        if beta_pwd:
            app_arg += f" -betapassword {beta_pwd}"
    if validate:
        app_arg += " validate"

    cmd = [
        STEAMCMD_PATH,
        "+force_install_dir",
        str(SERVER_DIR),
        "+login",
        "anonymous",
        "+app_update",
        app_arg,
        "+quit",
    ]

    print("[Update] Running SteamCMD update…")
    for attempt in range(1, retries + 2):
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(SERVER_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                check=False,
            )
            out = proc.stdout or ""
            ok = (
                ("Success! App" in out)
                or ("fully installed" in out)
                or (proc.returncode == 0)
            )
            if ok:
                print("[Update] SteamCMD update completed successfully.")
                send_discord_message("✅ SteamCMD update completed.", channel="startup")
                return True
            else:
                print(f"[Update] Attempt {attempt} failed — retrying…")
                print(out[-400:])
        except subprocess.TimeoutExpired:
            print("[Update] SteamCMD timed out; retrying…")
        except Exception as e:
            print(f"[Update] SteamCMD error: {e}; retrying…")
        time.sleep(5)

    send_discord_message("⚠️ SteamCMD update failed after retries.", channel="startup")
    print("[Update] SteamCMD update failed after retries.")
    return False


def _parse_args(argv: List[str]) -> Dict[str, object]:
    args = {
        "show_versions": False,
        "json": False,
        "ttl": 300,
        "no_cache": False,
    }
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--show-versions":
            args["show_versions"] = True
        elif tok == "--json":
            args["json"] = True
        elif tok == "--ttl" and i + 1 < len(argv):
            i += 1
            try:
                args["ttl"] = max(0, int(argv[i]))
            except Exception:
                args["ttl"] = 300
        elif tok == "--no-cache":
            args["no_cache"] = True
        i += 1
    return args


def main(argv: List[str]) -> int:
    args = _parse_args(argv)
    app_id = str(config.get("app_id") or "").strip()
    branch = (str(config.get("steam_update_beta", "") or "") or "public").strip()

    before = get_versions(
        branch=branch, ttl_sec=args["ttl"], use_cache=not args["no_cache"]
    )

    if args["show_versions"] and not args["json"]:
        print(f"[Before] Installed: {before.get('installed_buildid') or 'unknown'}")
        print(
            f"[Before] Remote   : {before.get('remote_buildid') or 'unknown'}"
            f"{' (cached)' if before.get('cached') else ''}"
        )

    ok = bool(check_for_steam_update())
    if not ok:
        if args["json"]:
            print(json.dumps({"ok": False, "error": "update_failed", "before": before}))
        else:
            print("[Update] FAILED")
        return 1

    if app_id:
        invalidate_cache(app_id, branch)

    after = get_versions(branch=branch, ttl_sec=0, use_cache=False)

    if args["json"]:
        print(json.dumps({"ok": True, "before": before, "after": after}))
    else:
        print("[Update] SUCCESS")
        if args["show_versions"]:
            print(f"[After ] Installed: {after.get('installed_buildid') or 'unknown'}")
            print(f"[After ] Remote   : {after.get('remote_buildid') or 'unknown'}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
