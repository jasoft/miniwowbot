"""Tests for lazy loading Bark configuration."""

from __future__ import annotations

from types import SimpleNamespace

import auto_dungeon_core
import auto_dungeon_notification


class _FakeSystemConfig:
    """System config stub for Bark tests."""

    def __init__(self) -> None:
        """Initialize a fixed Bark config."""
        self._bark_config = {
            "enabled": True,
            "server": "https://example.com",
            "title": "test",
            "group": "test_group",
        }

    def is_bark_enabled(self) -> bool:
        """Return True to indicate Bark is enabled."""
        return True

    def get_bark_config(self) -> dict:
        """Return a copy of the Bark config."""
        return dict(self._bark_config)


def test_send_notification_lazy_load(monkeypatch) -> None:
    """Load system config automatically when sending Bark notification."""
    original_system_config = auto_dungeon_core._container.system_config
    auto_dungeon_core._container.system_config = None
    calls: dict[str, object] = {}

    def fake_load_system_config():
        calls["loaded"] = True
        return _FakeSystemConfig()

    def fake_get(url: str, params: dict | None = None, timeout: int = 0):
        calls["url"] = url
        calls["params"] = params
        calls["timeout"] = timeout
        return SimpleNamespace(status_code=200)

    # Mock requests.get in the notification module
    monkeypatch.setattr(auto_dungeon_notification, "load_system_config", fake_load_system_config)
    monkeypatch.setattr(auto_dungeon_notification.requests, "get", fake_get)

    try:
        result = auto_dungeon_core.send_notification("test-title", "test-message")
        assert calls.get("loaded") is True
        assert auto_dungeon_core._container.system_config is not None
        assert result is True
    finally:
        auto_dungeon_core._container.system_config = original_system_config
