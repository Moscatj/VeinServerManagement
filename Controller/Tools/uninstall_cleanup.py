from __future__ import annotations

from Tools.monitors import stop_all_monitors


def _list_running_servers():
    from Tools.process import list_all_servers

    return list_all_servers(verbose=True)


def cleanup_for_uninstall() -> int:
    """Best-effort cleanup before the installed app is removed."""
    print("[Uninstall] Stopping log and crash monitors...")
    stop_all_monitors()

    try:
        server_procs = _list_running_servers()
    except Exception as exc:
        print(f"[Uninstall] Could not inspect server processes: {exc}")
        server_procs = []

    if not server_procs:
        print("[Uninstall] No running Vein server process found.")
        return 0

    print("[Uninstall] Running controlled server shutdown...")
    import shutdown_server

    shutdown_server.main()
    return 0


def main() -> int:
    return cleanup_for_uninstall()
