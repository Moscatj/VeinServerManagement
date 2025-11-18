# Controller/nightly_backup.py
from __future__ import annotations
import os, sys, traceback
from pathlib import Path

# Optional: validate config once to ensure Runtime path exists and warnings print nicely
try:
    from Tools.config_io import load_and_validate_config
except Exception:
    load_and_validate_config = None


def main() -> int:
    # If the GUI launched this, VEIN_CONFIG is already set. If not, backups.py will auto-pick YAML > JSON.
    cfg_path = os.environ.get("VEIN_CONFIG", "")

    if load_and_validate_config and cfg_path:
        try:
            load_and_validate_config(cfg_path, fatal=False)
        except Exception as e:
            print(f"[Nightly] Config load warning: {e}")

    try:
        from Tools.backups import make_backup, BackupSkip, BackupError, prune_backups

        # Create Nightly backup
        zip_path = make_backup("Nightly")
        print(f"[Nightly] OK: {zip_path}")
        # Optional: prune again right after (backups.py already prunes on create; this is harmless)
        prune_backups("Nightly")
        return 0
    except BackupSkip as e:
        print(f"[Nightly] SKIP: {e}")
        return 0
    except Exception as e:
        print(f"[Nightly] FAIL: {e}")
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
