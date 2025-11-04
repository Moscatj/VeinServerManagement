# Controller/crash_monitor.py
#!/usr/bin/env python3
from __future__ import annotations

import json, os, time
from datetime import datetime, timedelta
from pathlib import Path

from config_helper import config, is_feature_enabled
from utils import (
    RUNTIME_DIR,
    STATE_FLAG,
    find_running_server,
    is_shutdown_in_progress,
    startup_grace_active,
    autorestart_quiet_active,
    initiate_controlled_restart,
    send_discord_message,
)

# Cadence
MONITOR_INTERVAL_SEC   = max(5, int(config.get("crash_monitor_interval_seconds", 60)))
IDLE_NOTIFY_MINUTES    = int(config.get("crash_monitor_idle_notify_minutes", 15))

# New, optional knobs (with safe defaults)
CRASH_NOTIFY_DEBOUNCE  = int(config.get("crash_notify_debounce_seconds", 300))
BACKOFF_BASE           = int(config.get("crash_backoff_base", 2))
BACKOFF_MAX_SECONDS    = int(config.get("crash_backoff_max_seconds", 900))
BREAKER_MAX_ATTEMPTS   = int(config.get("crash_loop_max_attempts", 5))
BREAKER_WINDOW_MIN     = int(config.get("crash_loop_window_minutes", 10))
BREAKER_COOLDOWN_SEC   = int(config.get("crash_loop_cooldown_seconds", 600))

# Runtime files
PID_FILE    = Path(RUNTIME_DIR) / "crash_monitor.pid"
STATE_FILE  = Path(RUNTIME_DIR) / "crash_monitor_state.json"
STOP_FLAG   = Path(RUNTIME_DIR) / "stop_crash_monitor.flag"
RESTART_LOG = Path(RUNTIME_DIR) / "restart_state.json"
BREAKER     = Path(RUNTIME_DIR) / "breaker.tripped"
LAST_CRASH_NOTIFY = Path(RUNTIME_DIR) / "crash_notify.last"

def _now() -> datetime:
    return datetime.utcnow()

def _atomic_write_json(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass

def _write_state(mode: str) -> None:
    _atomic_write_json(STATE_FILE, {"ts": _now().isoformat() + "Z", "mode": mode, "pid": os.getpid()})

def _write_pid() -> None:
    try: PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception: pass

def _clear_pid_and_stopflag() -> None:
    for p in (PID_FILE, STOP_FLAG):
        try: p.unlink(missing_ok=True)
        except Exception: pass

def _debounced_crash_notify(msg: str) -> None:
    try:
        last = int(LAST_CRASH_NOTIFY.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        last = 0
    now = int(time.time())
    if now - last >= CRASH_NOTIFY_DEBOUNCE:
        send_discord_message(msg, channel="crash_monitor")
        try: LAST_CRASH_NOTIFY.write_text(str(now), encoding="utf-8")
        except Exception: pass

def _send(msg: str) -> None:
    send_discord_message(msg, channel="crash_monitor")

def _append_attempt(backoff_sec: int) -> None:
    data = {}
    try:
        data = json.loads(RESTART_LOG.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    at = data.get("attempts", [])
    at.append(_now().isoformat()+"Z")
    data["attempts"] = at[-100:]
    data["last_backoff_sec"] = backoff_sec
    _atomic_write_json(RESTART_LOG, data)

def _count_attempts_in_window(minutes: int) -> int:
    try:
        data = json.loads(RESTART_LOG.read_text(encoding="utf-8"))
        at = data.get("attempts", [])
    except Exception:
        return 0
    cutoff = _now() - timedelta(minutes=minutes)
    c = 0
    for iso in at:
        try:
            if datetime.fromisoformat(iso.replace("Z","")) >= cutoff:
                c += 1
        except Exception:
            pass
    return c

def _breaker_active() -> bool:
    if not BREAKER.exists(): return False
    try:
        until = int(BREAKER.read_text(encoding="utf-8").strip() or "0")
        if int(time.time()) < until:
            return True
    except Exception:
        pass
    try: BREAKER.unlink(missing_ok=True)
    except Exception: pass
    return False

def _trip_breaker() -> None:
    until = int(time.time()) + BREAKER_COOLDOWN_SEC
    try: BREAKER.write_text(str(until), encoding="utf-8")
    except Exception: pass
    _send(f"⚠️ Crash loop detected — breaker tripped for {BREAKER_COOLDOWN_SEC}s.")

def _next_backoff(prev: int) -> int:
    if prev <= 0: back = 1
    else: back = min(BACKOFF_MAX_SECONDS, prev * BACKOFF_BASE)
    return back

def main() -> None:
    if not is_feature_enabled("enable_crash_monitor"):
        print("[CrashMon] Disabled via config; exiting.")
        return

    print("[CrashMon] Starting crash monitor…")
    _send("🟢 Crash monitor started.")
    _write_pid()
    _write_state("startup")

    last_idle_notice_at = None
    announced_watching = False
    backoff = 0

    while True:
        # Stop flag
        if STOP_FLAG.exists():
            _send("🛑 Crash monitor stop requested; exiting.")
            _write_state("stopped")
            _clear_pid_and_stopflag()
            return

        # Live disable
        if not is_feature_enabled("enable_crash_monitor"):
            _write_state("disabled")
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # Intentional shutdown
        if is_shutdown_in_progress():
            _write_state("intentional_shutdown")
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # Breaker cooldown
        if _breaker_active():
            _write_state("breaker_cooldown")
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # Determine server state
        flag_present = STATE_FLAG.exists()
        process_running = find_running_server() is not None

        # Idle (no flag yet)
        if not flag_present:
            _write_state("idle")
            now_local = datetime.now()
            if last_idle_notice_at is None:
                _send("🟡 Crash monitor idle: server flag not present (offline).")
                last_idle_notice_at = now_local
                announced_watching = False
            elif now_local - last_idle_notice_at >= timedelta(minutes=IDLE_NOTIFY_MINUTES):
                _send("🟡 Crash monitor idle (still waiting for server flag)…")
                last_idle_notice_at = now_local
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # Watching
        if process_running:
            _write_state("watching")
            if not announced_watching:
                _send("🧭 Crash monitor active: watching for unexpected exit.")
                announced_watching = True
            # Healthy: reset attempt history if we’ve been up a while
            try:
                data = {"attempts": []}
                _atomic_write_json(RESTART_LOG, data)
            except Exception:
                pass
            backoff = 0
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # Crash condition: flag present, process missing
        _write_state("restart_pending")

        # Respect quiet windows
        if startup_grace_active(180) or autorestart_quiet_active():
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # Crash-loop protection
        if _count_attempts_in_window(BREAKER_WINDOW_MIN) >= BREAKER_MAX_ATTEMPTS:
            _trip_breaker()
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # Exponential backoff before attempting restart
        backoff = _next_backoff(backoff)
        sleep_for = min(backoff, BACKOFF_MAX_SECONDS)
        time.sleep(sleep_for)

        # Debounced notification + controlled restart
        _debounced_crash_notify("❌ Crash detected. Attempting controlled restart…")
        ok = initiate_controlled_restart(reason="proc_missing")
        if ok:
            _send("🔄 Auto-restart initiated by crash monitor.")
        else:
            # Throttled or already restarting — don’t spam
            pass

        _append_attempt(sleep_for)
        # Small buffer before next loop
        time.sleep(2)

if __name__ == "__main__":
    try:
        main()
    finally:
        _clear_pid_and_stopflag()
