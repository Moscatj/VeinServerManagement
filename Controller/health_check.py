from __future__ import annotations

import sys
from pathlib import Path


CTRL = Path(__file__).resolve().parent
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools.health_check import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
