from __future__ import annotations

import os
import subprocess
import sys
import time

from config_helper import config
from Tools.discord import send_discord_message
from Tools.process import win_creationflags_for_headless
from Tools.runtime import (
    PROJECT_ROOT,
    CONTROLLER_DIR,
    RESTARTING_LOCK,
    RESTART_STAMP,
)


START_SCRIPT = (CONTROLLER_DIR / "start_server.py").resolve()


def initiate_controlled_restart(reason: str = "unknown") -> bool:
    """
    Fire-and-forget restart respecting a simple throttle window.
    Writes a small lock to avoid duplicate spawns.
    """
    try:
        throttle_seconds = int(config.get("restart_throttle_seconds", 120))
    except (TypeError, ValueError):
        throttle_seconds = 120
    now = time.time()
    lock_acquired = False
    try:
        if RESTART_STAMP.exists():
            try:
                last = float(RESTART_STAMP.read_text().strip() or "0")
                if (now - last) < throttle_seconds:
                    print(f"[Restart] Throttled ({int(now - last)}s since last).")
                    return False
            except Exception:
                pass

        try:
            RESTARTING_LOCK.parent.mkdir(parents=True, exist_ok=True)
            with RESTARTING_LOCK.open("x", encoding="utf-8") as lock_file:
                lock_file.write(reason)
            lock_acquired = True
        except FileExistsError:
            return False
        except OSError as exc:
            print(f"[Restart] Could not acquire restart lock: {exc}")
            return False

        env = os.environ.copy()
        if os.environ.get("VEIN_CONFIG"):
            env["VEIN_CONFIG"] = os.environ["VEIN_CONFIG"]
        env.setdefault("PYEXE", sys.executable)

        creationflags = win_creationflags_for_headless()

        try:
            send_discord_message(
                f"Crash monitor initiated controlled restart (reason={reason}).",
                channel="startup",
            )
        except Exception as exc:
            print(f"[Restart] Discord notification failed: {exc}")

        command = (
            [sys.executable, "start-server", "--config", env.get("VEIN_CONFIG", "")]
            if getattr(sys, "frozen", False)
            else [sys.executable, str(START_SCRIPT)]
        )
        try:
            subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                env=env,
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except OSError as exc:
            print(f"[Restart] Failed to launch controlled restart: {exc}")
            return False

        try:
            RESTART_STAMP.write_text(str(now), encoding="utf-8")
        except OSError as exc:
            print(f"[Restart] Restart launched but throttle stamp could not be written: {exc}")

        time.sleep(int(config.get("restart_settle_seconds", 5)))
        return True
    finally:
        if lock_acquired:
            try:
                RESTARTING_LOCK.unlink(missing_ok=True)
            except Exception:
                pass
