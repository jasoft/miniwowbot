"""错误截图的可诊断性：失败必须能说清**为什么**失败。

背景（2026-09-21）：大王收到的告警里写着「截图：（截图失败）」，
但磁盘上查不到任何原因 —— ``save_error_screenshot`` 把异常记在
``logger.debug`` 级，默认日志级别下看不见，等于静默吞掉。
于是「截图失败」成了一条无法排查的死信息。

约定：
- 失败要在 WARNING 级留下原因；
- 原因要能通过 :func:`get_last_screenshot_error` 被通知正文引用；
- 保存路径基于**项目根**，不依赖当前工作目录（cron 的 cwd 未必是项目根）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

import auto_dungeon_daily
import auto_dungeon_navigation as nav


@pytest.fixture(autouse=True)
def _reset_last_error() -> None:
    """每个用例前把「上次失败原因」清干净，避免用例间串味。"""
    nav._last_screenshot_error = None
    yield
    nav._last_screenshot_error = None


def test_no_connected_device_gives_actionable_reason(monkeypatch) -> None:
    """没有设备时要说清是「设备没连上」，而不是笼统的失败。"""
    monkeypatch.setattr(nav, "_has_connected_device", lambda: False)

    assert nav.save_error_screenshot("demo") == ""

    reason = nav.get_last_screenshot_error()
    assert reason is not None
    assert "设备" in reason


def test_success_clears_reason_and_returns_path(monkeypatch, tmp_path) -> None:
    """保存成功时返回路径，并把失败原因清空。"""
    monkeypatch.setattr(nav, "_has_connected_device", lambda: True)

    def fake_snapshot(filename: str) -> None:
        Path(filename).write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)

    monkeypatch.setattr(nav, "snapshot", fake_snapshot)

    path = nav.save_error_screenshot("demo")

    assert path
    assert Path(path).exists()
    assert nav.get_last_screenshot_error() is None


def test_snapshot_exception_is_reported_not_swallowed(monkeypatch, tmp_path) -> None:
    """airtest 抛异常时必须把异常类型记下来，不能静默返回空串。"""
    monkeypatch.setattr(nav, "_has_connected_device", lambda: True)

    def boom(filename: str) -> None:
        raise RuntimeError("device offline")

    monkeypatch.setattr(nav, "snapshot", boom)

    assert nav.save_error_screenshot("demo") == ""

    reason = nav.get_last_screenshot_error()
    assert reason is not None
    assert "RuntimeError" in reason
    assert "device offline" in reason


def test_empty_snapshot_file_is_treated_as_failure(monkeypatch, tmp_path) -> None:
    """snapshot 不报错但没写出内容时，也算失败（设备掉线的典型表现）。"""
    monkeypatch.setattr(nav, "_has_connected_device", lambda: True)
    monkeypatch.setattr(nav, "snapshot", lambda filename: None)

    assert nav.save_error_screenshot("demo") == ""

    reason = nav.get_last_screenshot_error()
    assert reason is not None
    assert "空" in reason or "未生成" in reason


def test_path_is_project_root_based_not_cwd(monkeypatch, tmp_path) -> None:
    """路径必须由项目根推导，换工作目录也要落到同一个 log 目录。"""
    monkeypatch.setattr(nav, "_has_connected_device", lambda: True)

    written: list[str] = []

    def fake_snapshot(filename: str) -> None:
        written.append(filename)
        Path(filename).write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)

    monkeypatch.setattr(nav, "snapshot", fake_snapshot)
    monkeypatch.chdir(tmp_path)  # 故意把 cwd 换成完全无关的地方

    path = nav.save_error_screenshot("demo")

    assert path
    assert str(tmp_path) in path
    assert written and str(tmp_path) in written[0]


def test_notification_body_carries_screenshot_reason(monkeypatch, tmp_path) -> None:
    """告警正文里的「截图失败」必须带上原因，否则收件人无从排查。"""
    marker_dir = tmp_path / "notify_state"
    monkeypatch.setattr(
        auto_dungeon_daily.DailyCollectManager,
        "_failure_notice_marker",
        staticmethod(lambda step_name, today: str(marker_dir / f"{today}_{step_name}.flag")),
    )
    monkeypatch.setattr(auto_dungeon_daily, "save_error_screenshot", lambda name: "")
    monkeypatch.setattr(auto_dungeon_daily, "get_last_screenshot_error", lambda: "没有已连接的设备")

    sent: list[dict] = []
    monkeypatch.setattr(
        auto_dungeon_daily, "send_notification", lambda **kw: sent.append(kw) or True
    )

    manager = auto_dungeon_daily.DailyCollectManager(config_loader=None, db=None)
    manager._notify_step_failure("receive_mails", False)

    assert len(sent) == 1
    assert "截图失败：没有已连接的设备" in sent[0]["message"]
