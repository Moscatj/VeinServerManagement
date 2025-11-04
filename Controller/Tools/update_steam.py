# Controller/Tools/update_steam.py
"""
Run Steam update, print versions before/after, and invalidate cache on success.

CLI:
  py -3 Controller\\Tools\\update_steam.py
  py -3 Controller\\Tools\\update_steam.py --show-versions
  py -3 Controller\\Tools\\update_steam.py --json    # JSON with before/after

Exit: 0 success, 1 failure
"""
from __future__ import annotations
import sys, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CTRL = HERE.parent
ROOT = CTRL.parent
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

# existing helpers
from config_helper import config, get_path  # type: ignore

# tolerate legacy utils.py OR future Tools/core, but prefer legacy for now
check_for_steam_update = None
try:
    import utils as _legacy  # type: ignore
    check_for_steam_update = getattr(_legacy, "check_for_steam_update", None)
except Exception:
    pass
if check_for_steam_update is None:
    try:
        from Tools import core as _core  # type: ignore
        check_for_steam_update = getattr(_core, "check_for_steam_update", None)
    except Exception:
        pass
if check_for_steam_update is None:
    print("[Update] ERROR: could not locate check_for_steam_update in utils.")
    sys.exit(1)

# import our version helper
from Tools.steam_version import get_versions, _cache_path  # type: ignore


def _parse_args(argv: list[str]) -> dict:
    return {
        "show_versions": ("--show-versions" in argv),
        "json": ("--json" in argv),
        # allow overriding cache TTL when showing versions (default 300s)
        "ttl": next((int(argv[i+1]) for i,a in enumerate(argv) if a == "--ttl"), 300),
    }


def _invalidate_cache(app_id: str, branch: str) -> None:
    try:
        p = _cache_path(app_id, branch)
        if p.exists():
            p.unlink(missing_ok=True)
    except Exception:
        pass


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    server_dir = Path(get_path("server_dir"))
    app_id = str(config.get("app_id") or "").strip()
    branch = (str(config.get("steam_update_beta", "") or "") or "public").strip()

    before = get_versions(branch=branch, ttl_sec=args["ttl"], use_cache=True)

    if args["show_versions"] and not args["json"]:
        print(f"[Before] Installed: {before.get('installed_buildid') or 'unknown'}")
        print(f"[Before] Remote   : {before.get('remote_buildid') or 'unknown'}{' (cached)' if before.get('cached') else ''}")

    ok = bool(check_for_steam_update())
    if not ok:
        if args["json"]:
            print(json.dumps({"ok": False, "error": "update_failed", "before": before}))
        else:
            print("[Update] FAILED")
        return 1

    # update succeeded → invalidate cache for this branch so next read is fresh
    if app_id:
        _invalidate_cache(app_id, branch)

    after = get_versions(branch=branch, ttl_sec=0, use_cache=False)  # force refetch

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
