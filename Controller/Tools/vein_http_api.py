"""
Helpers around the optional Vein HTTP API.

This file only defines shared client utilities. Callers are responsible for
invoking them off the UI thread so that GUI responsiveness is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from config_helper import config

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - requests may be unavailable
    requests = None  # type: ignore

DEFAULT_TIMEOUT_SECONDS = 5.0


class VeinHTTPAPIError(RuntimeError):
    """Base exception for HTTP API helpers."""


class VeinHTTPAPIDisabledError(VeinHTTPAPIError):
    """Raised when the HTTP API is disabled or not configured."""


class VeinHTTPAPIMissingDependencyError(VeinHTTPAPIError):
    """Raised when the optional 'requests' dependency is missing."""


class VeinHTTPAPIRequestError(VeinHTTPAPIError):
    """Raised when a HTTP request fails or returns invalid JSON."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class HTTPAPISettings:
    """
    Configuration for the Vein HTTP API.

    Attributes mirror the sample config block but default to safe local values
    so callers can still instantiate a client manually without editing YAML.
    """

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8080
    scheme: str = "http"
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    base_path: str = ""

    def base_url(self) -> str:
        path = self.base_path.strip("/")
        suffix = f"/{path}" if path else ""
        return f"{self.scheme}://{self.host}:{self.port}{suffix}"


def http_api_settings() -> HTTPAPISettings:
    """
    Read `http_api` values from config.yaml (if present) and map them to a
    strongly-typed view. All keys are optional and fall back to sensible
    defaults so that the module can be exercised in isolation/tests.
    """

    raw = config.get("http_api")
    data: Dict[str, Any] = raw if isinstance(raw, dict) else {}

    enabled = bool(data.get("enabled", False))
    host = str(data.get("host") or data.get("hostname") or "127.0.0.1")

    try:
        port = int(data.get("port") or data.get("http_port") or 8080)
    except Exception:
        port = 8080

    scheme = str(data.get("scheme") or "http").strip().lower() or "http"

    try:
        timeout_seconds = float(
            data.get("timeout_seconds") or data.get("timeout") or DEFAULT_TIMEOUT_SECONDS
        )
    except Exception:
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS

    base_path = str(data.get("base_path") or "").strip().strip("/")

    return HTTPAPISettings(
        enabled=enabled,
        host=host,
        port=port,
        scheme=scheme,
        timeout_seconds=max(timeout_seconds, 0.1),
        base_path=base_path,
    )


def get_configured_client() -> Optional["VeinHTTPClient"]:
    """
    Instantiate a client from config. Returns None when disabled.
    """

    settings = http_api_settings()
    if not settings.enabled:
        return None
    return VeinHTTPClient(settings=settings)


def require_configured_client() -> "VeinHTTPClient":
    """
    Same as `get_configured_client()` but raises if the HTTP API is disabled.
    """

    client = get_configured_client()
    if client is None:
        raise VeinHTTPAPIDisabledError(
            "The Vein HTTP API is disabled or missing required config."
        )
    return client


class VeinHTTPClient:
    """
    Thin wrapper over the Vein HTTP API endpoints.

    Callers can either construct the client manually or via
    `get_configured_client()`. All network operations should run outside the
    UI thread.
    """

    def __init__(
        self,
        settings: HTTPAPISettings,
        *,
        session: Optional["requests.Session"] = None,
    ) -> None:
        self.settings = settings
        self._session = session

    # ------------------------------------------------------------------ utils
    def _ensure_ready(self) -> None:
        if requests is None:
            raise VeinHTTPAPIMissingDependencyError(
                "The 'requests' dependency is required for HTTP API calls."
            )
        if not self.settings.enabled:
            raise VeinHTTPAPIDisabledError(
                "The Vein HTTP API is disabled in config. "
                "Enable `http_api.enabled` to use it."
            )

    def _build_url(self, endpoint: str) -> str:
        endpoint = endpoint or "/"
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        base = self.settings.base_url().rstrip("/")
        return f"{base}{endpoint}"

    def _get(self, endpoint: str) -> Dict[str, Any]:
        self._ensure_ready()

        assert requests is not None  # for type-checkers
        url = self._build_url(endpoint)

        try:
            if self._session is not None:
                response = self._session.get(url, timeout=self.settings.timeout_seconds)
            else:
                response = requests.get(url, timeout=self.settings.timeout_seconds)
        except Exception as exc:
            raise VeinHTTPAPIRequestError(
                f"Failed to reach Vein HTTP API at {url}: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise VeinHTTPAPIRequestError(
                f"Vein HTTP API returned {response.status_code} for {url}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise VeinHTTPAPIRequestError(
                f"Vein HTTP API returned invalid JSON for {url}"
            ) from exc

        if not isinstance(payload, dict):
            # Unreal sometimes returns arrays; surface as-is for completeness.
            return {"data": payload}

        return payload

    # ----------------------------------------------------------------- routes
    def status(self) -> Dict[str, Any]:
        """GET /status"""
        return self._get("/status")

    def players(self) -> Dict[str, Any]:
        """GET /players"""
        return self._get("/players")

    def player(self, player_id: str) -> Dict[str, Any]:
        """GET /players/:id"""
        if not player_id:
            raise ValueError("player_id is required")
        return self._get(f"/players/{player_id}")

    def character(self, character_id: str) -> Dict[str, Any]:
        """GET /characters/:id"""
        if not character_id:
            raise ValueError("character_id is required")
        return self._get(f"/characters/{character_id}")

    def time(self) -> Dict[str, Any]:
        """GET /time"""
        return self._get("/time")

    def weather(self) -> Dict[str, Any]:
        """GET /weather"""
        return self._get("/weather")


# ---------------------------------------------------------------- convenience
def fetch_status(client: Optional[VeinHTTPClient] = None) -> Dict[str, Any]:
    return (client or require_configured_client()).status()


def fetch_players(client: Optional[VeinHTTPClient] = None) -> Dict[str, Any]:
    return (client or require_configured_client()).players()


def fetch_player(
    player_id: str, client: Optional[VeinHTTPClient] = None
) -> Dict[str, Any]:
    if not player_id:
        raise ValueError("player_id is required")
    return (client or require_configured_client()).player(player_id)


def fetch_character(
    character_id: str, client: Optional[VeinHTTPClient] = None
) -> Dict[str, Any]:
    if not character_id:
        raise ValueError("character_id is required")
    return (client or require_configured_client()).character(character_id)


def fetch_time(client: Optional[VeinHTTPClient] = None) -> Dict[str, Any]:
    return (client or require_configured_client()).time()


def fetch_weather(client: Optional[VeinHTTPClient] = None) -> Dict[str, Any]:
    return (client or require_configured_client()).weather()
