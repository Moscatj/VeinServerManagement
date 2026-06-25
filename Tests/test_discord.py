from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import discord  # noqa: E402


class DiscordTests(unittest.TestCase):
    def test_discord_webhook_url_supports_env_reference(self) -> None:
        with mock.patch.dict(discord.config, {"discord_webhook": "ENV:TEST_WEBHOOK"}, clear=True), mock.patch.dict(
            os.environ, {"TEST_WEBHOOK": "https://example.test/webhook"}
        ):
            self.assertEqual(discord._discord_webhook_url(), "https://example.test/webhook")

    def test_send_discord_message_respects_channel_and_truncates(self) -> None:
        requests = mock.Mock()
        with mock.patch.object(discord, "requests", requests), mock.patch.object(
            discord,
            "is_discord_channel_enabled",
            return_value=True,
        ), mock.patch.object(
            discord,
            "_discord_webhook_url",
            return_value="https://example.test/webhook",
        ):
            discord.send_discord_message("x" * 1900, channel="startup")

        payload = requests.post.call_args.kwargs["json"]
        self.assertEqual(requests.post.call_args.args[0], "https://example.test/webhook")
        self.assertEqual(requests.post.call_args.kwargs["timeout"], 10)
        self.assertEqual(len(payload["content"]), 1803)
        self.assertTrue(payload["content"].endswith("..."))

    def test_send_discord_message_noops_when_channel_disabled(self) -> None:
        requests = mock.Mock()
        with mock.patch.object(discord, "requests", requests), mock.patch.object(
            discord,
            "is_discord_channel_enabled",
            return_value=False,
        ):
            discord.send_discord_message("hello")

        requests.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
