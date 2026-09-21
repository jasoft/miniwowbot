"""Tests for lazy loading Bark configuration."""

from __future__ import annotations

from types import SimpleNamespace

import auto_dungeon_core
import auto_dungeon_notification
import pytest


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


@pytest.mark.allow_real_notifications
def test_send_notification_lazy_load(monkeypatch) -> None:
    """Load system config automatically when sending Bark notification.

    这个测试要验证的是「派发时惰性加载系统配置」，必须走真实派发链路，
    所以显式豁免 conftest 的通知拦网。但网络出口本身仍是打桩的：
    强制走 Bark 分支（`requests.get` 已 mock），确保不会真的推到大王手机上
    —— 本机 .env 配了 Pushover，`provider="auto"` 会优先走 Pushover 走真网络。
    """
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
    # 关掉 Pushover 分支，避免走到真实网络（Bark 分支的 requests.get 已打桩）
    monkeypatch.setattr(auto_dungeon_notification, "_get_pushover_config", lambda: None)

    try:
        result = auto_dungeon_core.send_notification("test-title", "test-message")
        assert calls.get("loaded") is True
        assert auto_dungeon_core._container.system_config is not None
        assert result is True
        # 证明走的是被打桩的 Bark 出口，而非真实 Pushover
        assert str(calls.get("url", "")).startswith("https://example.com")
    finally:
        auto_dungeon_core._container.system_config = original_system_config
