from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import vein_http_api  # noqa: E402


class FakeResponse:
    def __init__(self, status_code: int, payload=None, json_error: Exception | None = None):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse | Exception):
        self.response = response
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, timeout: float):
        self.calls.append((url, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class VeinHttpApiTests(unittest.TestCase):
    def test_settings_base_url_handles_base_path(self) -> None:
        settings = vein_http_api.HTTPAPISettings(
            enabled=True,
            host="localhost",
            port=9000,
            scheme="https",
            base_path="/api/",
        )

        self.assertEqual(settings.base_url(), "https://localhost:9000/api")

    def test_http_api_settings_reads_config_defaults_and_bounds_timeout(self) -> None:
        with mock.patch.dict(
            vein_http_api.config,
            {
                "http_api": {
                    "enabled": True,
                    "hostname": "0.0.0.0",
                    "http_port": "7778",
                    "scheme": "HTTP",
                    "timeout": "-5",
                    "base_path": "/v1/",
                }
            },
            clear=True,
        ):
            settings = vein_http_api.http_api_settings()

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.host, "0.0.0.0")
        self.assertEqual(settings.port, 7778)
        self.assertEqual(settings.scheme, "http")
        self.assertEqual(settings.timeout_seconds, 0.1)
        self.assertEqual(settings.base_path, "v1")

    def test_client_get_wraps_array_payload_and_uses_session(self) -> None:
        session = FakeSession(FakeResponse(200, payload=[{"id": 1}]))
        client = vein_http_api.VeinHTTPClient(
            settings=vein_http_api.HTTPAPISettings(
                enabled=True, host="127.0.0.1", port=8080, base_path="api"
            ),
            session=session,
        )

        payload = client.players()

        self.assertEqual(payload, {"data": [{"id": 1}]})
        self.assertEqual(session.calls[0], ("http://127.0.0.1:8080/api/players", 5.0))

    def test_client_errors_for_disabled_http_status_and_invalid_json(self) -> None:
        disabled = vein_http_api.VeinHTTPClient(
            settings=vein_http_api.HTTPAPISettings(enabled=False),
            session=FakeSession(FakeResponse(200, payload={})),
        )
        with self.assertRaises(vein_http_api.VeinHTTPAPIDisabledError):
            disabled.status()

        failing = vein_http_api.VeinHTTPClient(
            settings=vein_http_api.HTTPAPISettings(enabled=True),
            session=FakeSession(FakeResponse(500, payload={})),
        )
        with self.assertRaises(vein_http_api.VeinHTTPAPIRequestError) as ctx:
            failing.status()
        self.assertEqual(ctx.exception.status_code, 500)

        invalid = vein_http_api.VeinHTTPClient(
            settings=vein_http_api.HTTPAPISettings(enabled=True),
            session=FakeSession(FakeResponse(200, json_error=ValueError("bad json"))),
        )
        with self.assertRaisesRegex(vein_http_api.VeinHTTPAPIRequestError, "invalid JSON"):
            invalid.status()

    def test_fetch_helpers_validate_required_ids(self) -> None:
        with self.assertRaises(ValueError):
            vein_http_api.fetch_player("")
        with self.assertRaises(ValueError):
            vein_http_api.fetch_character("")


if __name__ == "__main__":
    unittest.main()
