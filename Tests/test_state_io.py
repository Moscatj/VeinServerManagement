from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import state_io  # noqa: E402


class StateIoTests(unittest.TestCase):
    def test_default_state_has_expected_schema_and_status(self) -> None:
        state = state_io.default_state(status="running", pid=1234, headless=False)

        self.assertEqual(state["schema"], state_io.STATE_SCHEMA_VERSION)
        self.assertEqual(state["status"], "running")
        self.assertEqual(state["pid"], 1234)
        self.assertFalse(state["headless"])
        self.assertEqual(state["version"], "unknown")
        self.assertTrue(state["last_updated"].endswith("Z"))

    def test_write_state_creates_parent_and_updates_timestamp(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "Runtime" / "server_state.json"
            state = state_io.default_state(status="running", pid=99)
            state["last_updated"] = "stale"

            state_io.write_state(path, state)
            written = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(written["status"], "running")
        self.assertEqual(written["pid"], 99)
        self.assertIn("last_updated", written)
        self.assertNotEqual(written["last_updated"], "stale")

    def test_bump_heartbeat_initializes_missing_state(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "Runtime" / "server_state.json"

            state = state_io.bump_heartbeat(path, incr_seconds=5)
            written = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(state["uptime_seconds"], 5)
        self.assertEqual(written["uptime_seconds"], 5)


if __name__ == "__main__":
    unittest.main()
