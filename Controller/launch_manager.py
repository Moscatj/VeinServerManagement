"""Reliable development bootstrap for the Vein Manager GUI.

The normal GUI redirects output only after its imports complete.  This wrapper
captures failures that happen earlier so a windowless ``pythonw`` launch never
fails without a useful message.
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_LOG_DIR = REPO_ROOT / "Logs" / "gui" / "bootstrap"


def _write_bootstrap_failure(exc: BaseException) -> Path | None:
    try:
        BOOTSTRAP_LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = BOOTSTRAP_LOG_DIR / f"VeinManager-bootstrap.{stamp}.log"
        path.write_text(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            encoding="utf-8",
        )
        return path
    except Exception:
        return None


def _show_bootstrap_failure(exc: BaseException, log_path: Path | None) -> None:
    message = f"Vein Server Manager could not start.\n\n{exc}"
    if log_path is not None:
        message += f"\n\nStartup details:\n{log_path}"
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "Vein Server Manager", 0x10)
    except Exception:
        print(message, file=sys.stderr)


def _run_startup_probe(manager) -> int:
    """Construct the real window and exit normally without displaying it."""
    from PySide6 import QtCore, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    if os.name == "nt":
        app.setStyle("Fusion")
    window = manager.Main()
    window.hide()
    QtCore.QTimer.singleShot(100, app.quit)
    return int(app.exec())


def main() -> int:
    startup_probe = "--startup-probe" in sys.argv
    if startup_probe:
        sys.argv.remove("--startup-probe")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        import vein_manager

        if startup_probe:
            return _run_startup_probe(vein_manager)
        vein_manager.main()
        return 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code == 0:
            return 0
        log_path = _write_bootstrap_failure(exc)
        _show_bootstrap_failure(exc, log_path)
        return code
    except BaseException as exc:
        log_path = _write_bootstrap_failure(exc)
        _show_bootstrap_failure(exc, log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
