"""通知策略相关测试。"""

from __future__ import annotations

import auto_dungeon_notification


def test_send_notification_suppressed_when_exit_only_enabled(monkeypatch) -> None:
    """启用退出时汇总模式后，运行期通知应被抑制。"""
    calls: list[tuple[str, str]] = []

    monkeypatch.setenv("MINIWOW_NOTIFY_ON_EXIT_ONLY", "1")
    monkeypatch.setattr(
        auto_dungeon_notification,
        "send_pushover_notification",
        lambda title, message, priority=0, html=False, **kwargs: (
            calls.append((title, message)) or True
        ),
    )

    sent = auto_dungeon_notification.send_notification(
        "副本运行错误",
        "模拟器启动失败",
        provider="pushover",
    )

    assert sent is False
    assert calls == []


def test_send_notification_force_bypasses_exit_only(monkeypatch) -> None:
    """强制发送应绕过退出时汇总模式。"""
    calls: list[tuple[str, str]] = []

    monkeypatch.setenv("MINIWOW_NOTIFY_ON_EXIT_ONLY", "1")
    monkeypatch.setattr(
        auto_dungeon_notification,
        "send_pushover_notification",
        lambda title, message, priority=0, html=False, **kwargs: (
            calls.append((title, message)) or True
        ),
    )

    sent = auto_dungeon_notification.send_notification(
        "poe cron 完成",
        "全部任务执行完毕",
        provider="pushover",
        force=True,
    )

    assert sent is True
    assert calls == [("poe cron 完成", "全部任务执行完毕")]
