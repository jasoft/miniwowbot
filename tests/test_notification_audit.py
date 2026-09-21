"""通知审计：**每一条通知都必须留下可回溯的磁盘记录**。

背景（2026-09-21）：大王收到一条

    [unknown | unknown] ⚠️ 每日任务未完成
    每日任务未完成：exchange_purple_first
    结果：券已够（40/40）但兑换未生效
    截图：（截图失败）

却无从判断它**由谁发出、当时上下文是什么** —— 因为通知链路本身不留痕迹：
审计既没记录调用点，也没记录 config/emulator 是「真的不知道」还是「根本没设置」。
这个文件守护的是「通知可回溯」这条约定，防止再退化成黑盒。

约定：
- ``log/notifications/YYYY-MM-DD.jsonl`` —— 机器可读，一条通知一行；
- ``log/notifications.log`` —— 人读摘要。

测试里两处路径由 ``tests/conftest.py::isolate_runtime_dirs`` 重定向到临时目录。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import auto_dungeon_notification as notif

# --------------------------------------------------------------------------
# 辅助
# --------------------------------------------------------------------------


def _audit_file(tmp_path: Path) -> Path:
    """返回当天审计 JSONL 的预期路径。

    Args:
        tmp_path: 当前测试的临时目录。

    Returns:
        Path: JSONL 文件路径。
    """
    day = datetime.now().strftime("%Y-%m-%d")
    return tmp_path / notif.AUDIT_DIR_NAME / f"{day}.jsonl"


def _read_audit(tmp_path: Path) -> list[dict]:
    """读取并解析当天所有审计记录。

    Args:
        tmp_path: 当前测试的临时目录。

    Returns:
        list[dict]: 审计记录列表。
    """
    path = _audit_file(tmp_path)
    assert path.exists(), f"审计文件未生成，通知没有落盘：{path}"
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _last_audit(tmp_path: Path) -> dict:
    """返回最后一条审计记录。

    Args:
        tmp_path: 当前测试的临时目录。

    Returns:
        dict: 最后一条记录。
    """
    records = _read_audit(tmp_path)
    assert records, "审计记录为空"
    return records[-1]


# --------------------------------------------------------------------------
# 各条出口都必须留痕
# --------------------------------------------------------------------------


@pytest.mark.allow_real_notifications
def test_pushover_not_configured_is_audited(monkeypatch, tmp_path) -> None:
    """Pushover 未配置而跳过时，也要记下「跳过了、因为没配置」。

    这里必须清掉 ``PYTEST_CURRENT_TEST``：否则会先命中「pytest 运行期拦截」，
    记成 ``blocked_test`` 而不是 ``skipped``。清掉之后因为没有 app/user key，
    仍然不会发出任何网络请求。
    """
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("PUSHOVER_APP_KEY", raising=False)
    monkeypatch.delenv("PUSHOVER_USER_KEY", raising=False)

    assert notif.send_pushover_notification("标题A", "正文A") is False

    record = _last_audit(tmp_path)
    assert record["event"] == "skipped"
    assert record["provider"] == "pushover"
    assert record["ok"] is False
    assert "未配置" in record["reason"]
    assert record["title"] == "标题A"


@pytest.mark.allow_real_notifications
def test_pytest_runtime_is_audited_as_blocked(monkeypatch, tmp_path) -> None:
    """pytest 运行期被拦截的通知要单独记成 blocked_test，便于和线上区分。"""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_notification_audit")
    monkeypatch.setenv("PUSHOVER_APP_KEY", "dummy")
    monkeypatch.setenv("PUSHOVER_USER_KEY", "dummy")

    assert notif.send_pushover_notification("标题B", "正文B") is False

    record = _last_audit(tmp_path)
    assert record["event"] == "blocked_test"
    assert record["ok"] is False
    assert "pytest" in record["reason"]


@pytest.mark.allow_real_notifications
def test_image_existence_is_recorded(monkeypatch, tmp_path) -> None:
    """审计要记下截图到底存不存在 —— 「截图失败」的根因常在这里。"""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_notification_audit")

    missing = tmp_path / "not-exist.png"
    notif.send_pushover_notification("标题C", "正文C", image=str(missing))

    assert _last_audit(tmp_path)["image_ok"] is False

    real = tmp_path / "real.png"
    real.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)
    notif.send_pushover_notification("标题C2", "正文C2", image=str(real))

    assert _last_audit(tmp_path)["image_ok"] is True


@pytest.mark.allow_real_notifications
def test_unknown_provider_is_audited(monkeypatch, tmp_path) -> None:
    """未知 provider 也要留痕，不能静默返回 False。

    未知 provider 走不到任何网络调用，``allow_real_notifications`` 只是为了让
    conftest 不要提前把 ``send_notification`` 换成桩 —— 否则被测的就是桩了。
    """
    assert notif.send_notification("标题D", "正文D", provider="不存在的服务") is False

    record = _last_audit(tmp_path)
    assert record["event"] == "failed"
    assert "未知的通知服务提供商" in record["reason"]


@pytest.mark.allow_real_notifications
def test_no_available_service_is_audited(monkeypatch, tmp_path) -> None:
    """Pushover 未配置、Bark 未启用时，记「谁都没接」。"""
    monkeypatch.setattr(notif, "_get_pushover_config", lambda: None)
    disabled = MagicMock()
    disabled.is_bark_enabled.return_value = False
    monkeypatch.setattr(notif, "_get_notification_config", lambda: disabled)

    assert notif.send_notification("标题E", "正文E", provider="auto") is False

    record = _last_audit(tmp_path)
    assert record["event"] == "skipped"
    assert record["provider"] == "auto"
    assert "没有任何可用的通知服务" in record["reason"]


# --------------------------------------------------------------------------
# 记录内容本身要能回答「谁发的、什么上下文」
# --------------------------------------------------------------------------


def test_audit_contains_caller_and_timestamp(monkeypatch, tmp_path) -> None:
    """审计必须带上调用点与时间，否则无从回溯。"""
    notif._audit_notification("sent", "pushover", "标题F", "正文F", True)

    record = _last_audit(tmp_path)
    assert record["ts"].startswith(datetime.now().strftime("%Y-%m-%dT"))
    # 调用点应指向本测试函数所在的文件，而不是通知模块自己
    assert "test_notification_audit.py" in record["caller"]
    assert "test_audit_contains_caller_and_timestamp" in record["caller"]
    assert isinstance(record["pid"], int)


def test_context_missing_is_flagged(monkeypatch, tmp_path) -> None:
    """上下文取不到时要标 context_missing，区分「真未知」与「没设置」。"""
    monkeypatch.setattr(notif, "_resolve_log_context", lambda: ("unknown", "unknown", True))

    notif._audit_notification("skipped", "pushover", "标题G", "正文G", False, "测试")

    assert _last_audit(tmp_path)["context_missing"] is True


def test_human_readable_log_is_also_written(monkeypatch, tmp_path) -> None:
    """除 JSONL 外还要有人读的一行摘要，便于直接 grep / 直接看。"""
    notif._audit_notification("skipped", "pushover", "标题H", "正文H", False, "因为没配置")

    text_path = tmp_path / notif.AUDIT_TEXT_NAME
    assert text_path.exists(), "人读审计日志未生成"
    content = text_path.read_text(encoding="utf-8")
    assert "标题H" in content
    assert "因为没配置" in content


def test_audit_never_raises_even_if_disk_write_fails(monkeypatch) -> None:
    """审计写盘失败不能影响通知，更不能阻断主流程。"""

    def boom(*args, **kwargs):
        raise OSError("磁盘满了")

    monkeypatch.setattr(notif, "_project_log_path", boom)

    # 不抛异常即为通过
    notif._audit_notification("sent", "pushover", "标题I", "正文I", True)


# --------------------------------------------------------------------------
# 推送正文要自带上下文说明
# --------------------------------------------------------------------------


def test_enrich_marks_missing_context(monkeypatch) -> None:
    """上下文缺失时正文要显式标注，避免让人以为真有叫 unknown 的配置。"""
    monkeypatch.setattr(notif, "_resolve_log_context", lambda: ("unknown", "unknown", True))

    title, message = notif._enrich_message("每日任务未完成", "结果：xxx")

    assert title == "[unknown | unknown] 每日任务未完成"
    assert "（未设置运行上下文）" in message


def test_enrich_omits_marker_when_context_is_present(monkeypatch) -> None:
    """上下文正常时不要加噪声标注。"""
    monkeypatch.setattr(
        notif,
        "_resolve_log_context",
        lambda: ("warrior", "192.168.1.150:5555", False),
    )

    title, message = notif._enrich_message("每日任务未完成", "结果：xxx")

    assert title == "[warrior | 192.168.1.150:5555] 每日任务未完成"
    assert "未设置运行上下文" not in message
    assert "配置: warrior" in message
