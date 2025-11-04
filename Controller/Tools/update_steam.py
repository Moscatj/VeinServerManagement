# Controller/Tools/update_steam.py
"""
Run Steam update, show versions before/after, and invalidate cache on success.

CLI:
  py -3 Controller\\Tools\\update_steam.py
  py -3 Controller\\Tools\\update_steam.py --show-versions
  py -3 Controller\\Tools\\update_steam.py --json
  py -3 Controller\\Tools\\update_steam.py --ttl 300
  py -3 Controller\\Tools\\update_steam.py --no-cache

Exit: 0 success, 1 failure
"""
from __future__ import annotations
import sys, json
from pathlib import Path

# ── Imports path prep ──────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
CTRL = HERE.parent
ROOT = CTRL.parent
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from config_helper import config, get_path  # type: ignore
from Tools.steam_version import get_versions, invalidate_cache  # type: ignore

# tolerate legacy utils.py OR future Tools/core, prefer legacy for now
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

# ── Arg parsing ────────────────────────────────────────────────────────────────
def _parse_args(argv: list[str]) -> dict:
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
            try: args["ttl"] = max(0, int(argv[i]))
            except Exception: args["ttl"] = 300
        elif tok == "--no-cache":
            args["no_cache"] = True
        i += 1
    return args

# ── Main ──────────────────────────────────────────────────────────────────────
def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    app_id = str(config.get("app_id") or "").strip()
    branch = (str(config.get("steam_update_beta", "") or "") or "public").strip()

    # Before
    before = get_versions(branch=branch,
                          ttl_sec=args["ttl"],
                          use_cache=not args["no_cache"])

    if args["show_versions"] and not args["json"]:
        print(f"[Before] Installed: {before.get('installed_buildid') or 'unknown'}")
        print(f"[Before] Remote   : {before.get('remote_buildid') or 'unknown'}"
              f"{' (cached)' if before.get('cached') else ''}")

    # Update
    ok = bool(check_for_steam_update())
    if not ok:
        if args["json"]:
            print(json.dumps({"ok": False, "error": "update_failed", "before": before}))
        else:
            print("[Update] FAILED")
        return 1

    # Success → nuke cache so GUI/next read is fresh
    if app_id:
        invalidate_cache(app_id, branch)

    # After (force refresh: no cache, ttl=0)
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
