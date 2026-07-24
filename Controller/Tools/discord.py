# Controller/Tools/discord.py
from __future__ import annotations

from typing import Optional
import os

from config_helper import config, is_discord_channel_enabled as _cfg_is_enabled

# Optional: requests for Discord webhooks; no-op if unavailable.
try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore


_TRUE_VALUES = {"1", "true", "yes", "on"}


def _discord_notifications_disabled() -> bool:
    """Return whether this process is forbidden from sending Discord posts."""
    return os.environ.get("VEIN_DISABLE_DISCORD", "").strip().lower() in _TRUE_VALUES


def _discord_webhook_url() -> Optional[str]:
    """
    Resolve webhook URL from config with ENV: support.
    - Accepts direct URL string.
    - If the value starts with 'ENV:', read that environment variable.
    - Returns None if unset or empty.
    """
    raw = config.get("discord_webhook") or config.get("discord_webhook_url")
    if not raw:
        return None

    s = str(raw).strip()
    if s.upper().startswith("ENV:"):
        env_key = s.split(":", 1)[1].strip()
        val = os.environ.get(env_key, "").strip()
        return val or None

    return s or None


def is_discord_channel_enabled(channel: str) -> bool:
    """
    Small wrapper over config_helper.is_discord_channel_enabled so tools
    can import from Tools.discord without caring about config internals.
    """
    return _cfg_is_enabled(channel)


def send_discord_message(message: str, channel: str = "startup") -> None:
    """
    Post message to Discord via webhook.
    Respects global & per-channel flags; truncates near Discord limit.
    """
    if _discord_notifications_disabled() or not is_discord_channel_enabled(channel):
        return

    url = _discord_webhook_url()
    if not url or requests is None:
        return

    max_len = 1800
    content = (message[:max_len] + "...") if len(message) > max_len else message

    try:
        requests.post(
            url,
            json={
                "content": content,
                "allowed_mentions": {"parse": []},
            },
            timeout=10,
        )
    except Exception as e:
        print(f"[Discord] Failed to post message: {e}")
