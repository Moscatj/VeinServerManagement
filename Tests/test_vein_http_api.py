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

    def test_http_api_settings_handles_invalid_values_and_disabled_config(self) -> None:
        with mock.patch.dict(
            vein_http_api.config,
            {
                "http_api": {
                    "enabled": False,
                    "host": "",
                    "port": "bad",
                    "scheme": "",
                    "timeout_seconds": "bad",
                    "base_path": "///",
                }
            },
            clear=True,
        ):
            settings = vein_http_api.http_api_settings()

        self.assertFalse(settings.enabled)
        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 8080)
        self.assertEqual(settings.scheme, "http")
        self.assertEqual(settings.timeout_seconds, vein_http_api.DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(settings.base_path, "")

        with mock.patch.dict(vein_http_api.config, {"http_api": "not-a-dict"}, clear=True):
            self.assertFalse(vein_http_api.http_api_settings().enabled)

    def test_configured_client_helpers_return_client_or_raise_disabled(self) -> None:
        with mock.patch.object(
            vein_http_api,
            "http_api_settings",
            return_value=vein_http_api.HTTPAPISettings(enabled=False),
        ):
            self.assertIsNone(vein_http_api.get_configured_client())
            with self.assertRaises(vein_http_api.VeinHTTPAPIDisabledError):
                vein_http_api.require_configured_client()

        with mock.patch.object(
            vein_http_api,
            "http_api_settings",
            return_value=vein_http_api.HTTPAPISettings(enabled=True),
        ):
            self.assertIsInstance(vein_http_api.get_configured_client(), vein_http_api.VeinHTTPClient)

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

    def test_client_build_url_normalizes_empty_and_relative_endpoints(self) -> None:
        client = vein_http_api.VeinHTTPClient(
            settings=vein_http_api.HTTPAPISettings(enabled=True, host="host", port=1, base_path="/api/")
        )

        self.assertEqual(client._build_url("status"), "http://host:1/api/status")
        self.assertEqual(client._build_url(""), "http://host:1/api/")

    def test_client_uses_requests_get_when_no_session(self) -> None:
        client = vein_http_api.VeinHTTPClient(
            settings=vein_http_api.HTTPAPISettings(enabled=True, host="host", port=1, timeout_seconds=2.5)
        )

        with mock.patch.object(
            vein_http_api.requests,
            "get",
            return_value=FakeResponse(200, payload={"ok": True}),
        ) as get:
            self.assertEqual(client.status(), {"ok": True})

        get.assert_called_once_with("http://host:1/status", timeout=2.5)

    def test_client_errors_when_requests_dependency_is_missing_or_request_fails(self) -> None:
        client = vein_http_api.VeinHTTPClient(settings=vein_http_api.HTTPAPISettings(enabled=True))

        with mock.patch.object(vein_http_api, "requests", None):
            with self.assertRaises(vein_http_api.VeinHTTPAPIMissingDependencyError):
                client.status()

        failing = vein_http_api.VeinHTTPClient(
            settings=vein_http_api.HTTPAPISettings(enabled=True),
            session=FakeSession(OSError("connection failed")),
        )
        with self.assertRaisesRegex(vein_http_api.VeinHTTPAPIRequestError, "Failed to reach"):
            failing.status()

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

    def test_route_methods_and_fetch_helpers_delegate_to_client(self) -> None:
        client = mock.Mock(spec=vein_http_api.VeinHTTPClient)
        client.status.return_value = {"status": "ok"}
        client.players.return_value = {"players": []}
        client.player.return_value = {"id": "p1"}
        client.character.return_value = {"id": "c1"}
        client.time.return_value = {"time": 1}
        client.weather.return_value = {"weather": "clear"}

        self.assertEqual(vein_http_api.fetch_status(client), {"status": "ok"})
        self.assertEqual(vein_http_api.fetch_players(client), {"players": []})
        self.assertEqual(vein_http_api.fetch_player("p1", client), {"id": "p1"})
        self.assertEqual(vein_http_api.fetch_character("c1", client), {"id": "c1"})
        self.assertEqual(vein_http_api.fetch_time(client), {"time": 1})
        self.assertEqual(vein_http_api.fetch_weather(client), {"weather": "clear"})
        client.player.assert_called_once_with("p1")
        client.character.assert_called_once_with("c1")

    def test_route_methods_validate_ids_and_call_expected_endpoints(self) -> None:
        session = FakeSession(FakeResponse(200, payload={"ok": True}))
        client = vein_http_api.VeinHTTPClient(
            settings=vein_http_api.HTTPAPISettings(enabled=True, host="host", port=1),
            session=session,
        )

        self.assertEqual(client.player("player-1"), {"ok": True})
        self.assertEqual(client.character("char-1"), {"ok": True})
        self.assertEqual(client.time(), {"ok": True})
        self.assertEqual(client.weather(), {"ok": True})

        urls = [call[0] for call in session.calls]
        self.assertIn("http://host:1/players/player-1", urls)
        self.assertIn("http://host:1/characters/char-1", urls)
        self.assertIn("http://host:1/time", urls)
        self.assertIn("http://host:1/weather", urls)

        with self.assertRaises(ValueError):
            client.player("")
        with self.assertRaises(ValueError):
            client.character("")

    def test_fetch_helpers_require_configured_client_when_client_missing(self) -> None:
        configured = mock.Mock(spec=vein_http_api.VeinHTTPClient)
        configured.status.return_value = {"status": "ok"}

        with mock.patch.object(vein_http_api, "require_configured_client", return_value=configured):
            self.assertEqual(vein_http_api.fetch_status(), {"status": "ok"})

        configured.status.assert_called_once()


if __name__ == "__main__":
    unittest.main()
