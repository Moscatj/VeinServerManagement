# Controller/Tools/steam_version.py
"""
Steam version inspector with runtime cache and status helper.

CLI:
  py -3 Controller\\Tools\\steam_version.py --status
  py -3 Controller\\Tools\\steam_version.py --json
  py -3 Controller\\Tools\\steam_version.py --ttl 300
  py -3 Controller\\Tools\\steam_version.py --no-cache

Exit: 0 if data retrieved, 1 on failure
"""

from __future__ import annotations
import sys, re, json, time, subprocess
from pathlib import Path
from typing import Optional, Dict, Any

HERE = Path(__file__).resolve().parent
CTRL = HERE.parent
ROOT = CTRL.parent
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

try:
    from config_helper import config, get_path  # type: ignore
except Exception as e:
    print(f"[steam_version] ERROR: cannot import config_helper: {e}")
    sys.exit(1)


# ───────────────────────────────────────────────────────────────
# Caching utilities
# ───────────────────────────────────────────────────────────────

def _runtime_dir() -> Path:
    rd = config.get("runtime_dir")
    if rd:
        return Path(rd)
    return ROOT / "Runtime"


def _cache_path(app_id: str, branch: str) -> Path:
    safe_branch = branch.lower().replace("/", "_")
    _runtime_dir().mkdir(parents=True, exist_ok=True)
    return _runtime_dir() / f"steam_version_cache_{app_id}_{safe_branch}.json"


def _load_cache(app_id: str, branch: str) -> Optional[Dict[str, Any]]:
    p = _cache_path(app_id, branch)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(app_id: str, branch: str, buildid: Optional[str]) -> None:
    p = _cache_path(app_id, branch)
    payload = {
        "app_id": app_id,
        "branch": branch,
        "buildid": buildid,
        "fetched_at": int(time.time()),
    }
    try:
        p.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        pass


def _cache_fresh(cache: Dict[str, Any], ttl: int) -> bool:
    try:
        return (int(time.time()) - int(cache.get("fetched_at", 0))) <= int(ttl)
    except Exception:
        return False


# ───────────────────────────────────────────────────────────────
# Version fetching
# ───────────────────────────────────────────────────────────────

def _read_installed_buildid(server_dir: Path, app_id: str) -> Optional[str]:
    mf = server_dir / "steamapps" / f"appmanifest_{app_id}.acf"
    if not mf.exists():
        return None
    try:
        txt = mf.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = re.search(r'"\s*buildid\s*"\s*"(?P<id>\d+)"', txt)
    return m.group("id") if m else None


def _query_remote_buildid(steamcmd: Path, app_id: str, branch: Optional[str], timeout_sec: int) -> Optional[str]:
    if not steamcmd.exists():
        return None

    args = [
        str(steamcmd),
        "+login", "anonymous",
        "+app_info_update", "1",
        "+app_info_print", str(app_id),
        "+quit",
    ]
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None

    out = proc.stdout or ""
    target = (branch or "public").strip().lower()

    branches_idx = re.search(r'"\s*branches\s*"\s*\{', out, re.I)
    if branches_idx:
        start = branches_idx.end()
        hdr = re.compile(rf'"\s*{re.escape(target)}\s*"\s*\{{', re.I).search(out, start)
        if not hdr and target != "public":
            return _query_remote_buildid(steamcmd, app_id, "public", timeout_sec)
        if hdr:
            blk_start = hdr.end()
            blk_end = out.find("}", blk_start)
            if blk_end < 0:
                blk_end = len(out)
            seg = out[blk_start:blk_end]
            m = re.search(r'"\s*buildid\s*"\s*"(?P<id>\d+)"', seg)
            if m:
                return m.group("id")

    m_any = re.search(r'"\s*buildid\s*"\s*"(?P<id>\d+)"', out)
    return m_any.group("id") if m_any else None


# ───────────────────────────────────────────────────────────────
# Public API
# ───────────────────────────────────────────────────────────────

def get_versions(branch: Optional[str] = None, timeout_sec: int = 15, ttl_sec: int = 300, use_cache: bool = True) -> dict:
    """
    Returns:
      { ok, installed_buildid, remote_buildid, branch, app_id, server_dir, cached }
    """
    server_dir = Path(get_path("server_dir"))
    steamcmd   = Path(config.get("steamcmd_path") or "")
    app_id     = str(config.get("app_id") or "").strip()
    cfg_branch = str(config.get("steam_update_beta", "") or "").strip() or "public"
    branch     = (branch or cfg_branch).strip()

    result = {
        "ok": False,
        "installed_buildid": None,
        "remote_buildid": None,
        "branch": branch,
        "server_dir": str(server_dir),
        "app_id": app_id,
        "cached": False,
    }

    if not app_id or not server_dir:
        return result

    installed = _read_installed_buildid(server_dir, app_id)

    remote = None
    if use_cache:
        cache = _load_cache(app_id, branch)
        if cache and _cache_fresh(cache, ttl_sec):
            remote = cache.get("buildid")
            result["cached"] = True

    if remote is None:
        remote = _query_remote_buildid(steamcmd, app_id, branch, timeout_sec=timeout_sec)
        _save_cache(app_id, branch, remote)

    result.update(
        installed_buildid=installed,
        remote_buildid=remote,
        ok=bool(installed) or bool(remote),
    )
    return result


# ───────────────────────────────────────────────────────────────
# New helper: friendly status for GUI / CLI
# ───────────────────────────────────────────────────────────────

def get_version_status(branch: Optional[str] = None, ttl_sec: int = 300, timeout_sec: int = 15) -> dict:
    """
    Returns a lightweight dict suitable for GUI:
      {
        "status": "Up-to-date" | "Update available" | "Unknown",
        "installed_buildid": "12345",
        "remote_buildid": "12345",
        "branch": "public",
        "cached": bool,
        "color": "green" | "yellow" | "red"
      }
    """
    info = get_versions(branch=branch, ttl_sec=ttl_sec, timeout_sec=timeout_sec)
    installed, remote = info.get("installed_buildid"), info.get("remote_buildid")
    status = "Unknown"
    color = "red"

    if installed and remote:
        if installed == remote:
            status = "Up-to-date"
            color = "green"
        else:
            status = "Update available"
            color = "yellow"
    elif installed or remote:
        status = "Partial data"
        color = "yellow"

    return {
        **info,
        "status": status,
        "color": color,
    }


# ───────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────

def _parse_args(argv: list[str]) -> dict:
    args = {"json": False, "branch": None, "timeout": 15, "ttl": 300, "no_cache": False, "status": False}
    it = iter(argv)
    for tok in it:
        t = tok.lower()
        if t == "--json": args["json"] = True
        elif t == "--branch":
            try: args["branch"] = next(it)
            except StopIteration: pass
        elif t == "--timeout":
            try: args["timeout"] = int(next(it))
            except Exception: pass
        elif t == "--ttl":
            try: args["ttl"] = max(0, int(next(it)))
            except Exception: pass
        elif t == "--no-cache":
            args["no_cache"] = True
        elif t == "--status":
            args["status"] = True
    return args


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    if args["status"]:
        info = get_version_status(branch=args["branch"], ttl_sec=args["ttl"], timeout_sec=args["timeout"])
        if args["json"]:
            print(json.dumps(info))
        else:
            print(f"[Steam] Status : {info['status']}")
            print(f"[Steam] Color  : {info['color']}")
            print(f"[Steam] Branch : {info['branch']}")
            print(f"[Steam] Local  : {info['installed_buildid'] or 'unknown'}")
            print(f"[Steam] Remote : {info['remote_buildid'] or 'unknown'}{' (cached)' if info['cached'] else ''}")
        return 0

    info = get_versions(branch=args["branch"], timeout_sec=args["timeout"], ttl_sec=args["ttl"], use_cache=not args["no_cache"])
    if args["json"]:
        print(json.dumps(info))
    else:
        print(f"[Steam] Branch     : {info['branch']}")
        print(f"[Steam] Installed  : {info['installed_buildid'] or 'unknown'}")
        print(f"[Steam] Remote     : {info['remote_buildid'] or 'unknown'}{' (cached)' if info['cached'] else ''}")
        if info["installed_buildid"] and info["remote_buildid"]:
            print("[Steam] Up-to-date : " +
                  ("YES" if info["installed_buildid"] == info["remote_buildid"] else "NO"))

    return 0 if info["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
