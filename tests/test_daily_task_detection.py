"""每日任务成败判定与失败告警的回归测试。

覆盖三类关键行为：

1. ``_run_step`` 只认显式 ``True``：返回 False / None 一律判失败。
   历史实现用 ``raw_result is not False``，导致所有不返回值的方法（None）
   都被误判为成功，数据库记成「已完成」而游戏里并未领取。
2. ``_locate_mail_claim_button`` 的三级兜底：
   正常查找 → 等待 ``MAIL_PANEL_WAIT_SECONDS`` 秒重试 → 固定坐标点击。
3. 失败告警去重：同一天同一步骤只推送一次，避免整轮重试造成重复轰炸。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auto_dungeon_daily as daily
from auto_dungeon_daily import MAIL_PANEL_WAIT_SECONDS, DailyCollectManager
from coordinates import MAIL_CLAIM_ALL_BUTTON


@pytest.fixture()
def manager(monkeypatch):
    """构造隔离的 DailyCollectManager，并屏蔽失败告警的副作用。"""
    mgr = DailyCollectManager(config_loader=None, db=None)
    notified = []
    monkeypatch.setattr(mgr, "_notify_step_failure", lambda *args: notified.append(args))
    mgr.notified = notified  # type: ignore[attr-defined]
    return mgr


# ---------------------------------------------------------------- _run_step


def test_run_step_accepts_explicit_true(manager):
    """显式返回 True 的步骤应判成功。"""
    assert manager._run_step("__t_true__", lambda: True) is True
    assert manager.notified == []


def test_run_step_rejects_explicit_false(manager):
    """显式返回 False 的步骤应判失败并触发告警。"""
    assert manager._run_step("__t_false__", lambda: False) is False
    assert manager.notified == [("__t_false__", False)]


def test_run_step_rejects_missing_return_value(manager):
    """不返回值（None）的步骤应判失败 —— 这是修复「假完成」的核心用例。"""

    def step_without_return():
        """模拟历史上大量不写 return 的任务方法。"""

    assert manager._run_step("__t_none__", lambda: None) is False
    assert manager._run_step("__t_none2__", step_without_return) is False
    assert manager.notified == [("__t_none__", None), ("__t_none2__", None)]


def test_run_step_rejects_truthy_non_true(manager):
    """返回真值但非 True（如 GameElement）同样不算成功，必须显式声明 True。"""
    assert manager._run_step("__t_truthy__", lambda: "ok") is False


# ------------------------------------------------- _locate_mail_claim_button


def test_locate_mail_claim_uses_found_center(manager, monkeypatch):
    """正常找到时应返回 OCR 给出的按钮中心。"""
    monkeypatch.setattr(daily, "find_text", lambda *a, **k: {"center": (475, 901)})
    assert manager._locate_mail_claim_button() == (475, 901)


def test_locate_mail_claim_retries_then_uses_fixed_position(manager, monkeypatch):
    """两次都找不到时，应等待一次后回退到固定坐标。"""
    calls = {"find": 0, "slept": []}

    def fake_find_text(*args, **kwargs):
        """始终报告未找到。"""
        calls["find"] += 1
        return None

    monkeypatch.setattr(daily, "find_text", fake_find_text)
    monkeypatch.setattr(daily, "sleep", lambda *a, **k: calls["slept"].append(a))

    assert manager._locate_mail_claim_button() == MAIL_CLAIM_ALL_BUTTON
    assert calls["find"] == 2, "应尝试查找两次：首次 + 等待后重试"
    assert calls["slept"] == [(MAIL_PANEL_WAIT_SECONDS, "等待邮箱面板渲染完成")]


def test_locate_mail_claim_succeeds_on_second_attempt(manager, monkeypatch):
    """首次失败、等待后成功时，应使用第二次的坐标且不回退固定坐标。"""
    results = [None, {"center": (480, 905)}]

    def fake_find_text(*args, **kwargs):
        """第一次返回 None，第二次返回坐标。"""
        return results.pop(0)

    monkeypatch.setattr(daily, "find_text", fake_find_text)
    monkeypatch.setattr(daily, "sleep", lambda *a, **k: None)

    assert manager._locate_mail_claim_button() == (480, 905)


def test_locate_mail_claim_passes_use_cache_false(manager, monkeypatch):
    """查找必须显式关闭感知哈希缓存，否则会读到历史误识别结果。"""
    seen = {}

    def fake_find_text(*args, **kwargs):
        """记录查找参数。"""
        seen.update(kwargs)
        return {"center": (475, 901)}

    monkeypatch.setattr(daily, "find_text", fake_find_text)
    manager._locate_mail_claim_button()

    assert seen.get("use_cache") is False
    assert seen.get("regions") == [8, 9]


# --------------------------------------------------- 失败告警的去重与内容


def test_failure_notification_sent_once_per_day(monkeypatch, tmp_path):
    """同一逻辑日内同一步骤只推送一次告警。"""
    marker = tmp_path / "step.flag"
    monkeypatch.setattr(
        DailyCollectManager,
        "_failure_notice_marker",
        staticmethod(lambda step_name, today: str(marker)),
    )
    sent = []
    monkeypatch.setattr(daily, "send_notification", lambda **kw: sent.append(kw) or True)
    monkeypatch.setattr(
        daily, "save_error_screenshot", lambda name: str(tmp_path / "shot.png")
    )

    mgr = DailyCollectManager(config_loader=None, db=None)
    mgr._notify_step_failure("receive_mails", False)
    mgr._notify_step_failure("receive_mails", False)

    assert len(sent) == 1, "第二次调用应被去重"
    assert marker.exists(), "首次告警后应写入标记文件"


def test_failure_notification_attaches_screenshot(monkeypatch, tmp_path):
    """告警必须带上现场截图，并说明失败形态。"""
    monkeypatch.setattr(
        DailyCollectManager,
        "_failure_notice_marker",
        staticmethod(lambda step_name, today: str(tmp_path / "step.flag")),
    )
    sent = []
    monkeypatch.setattr(daily, "send_notification", lambda **kw: sent.append(kw) or True)
    monkeypatch.setattr(
        daily, "save_error_screenshot", lambda name: str(tmp_path / "shot.png")
    )

    mgr = DailyCollectManager(config_loader=None, db=None)
    mgr._notify_step_failure("idle_rewards", None)

    assert len(sent) == 1
    payload = sent[0]
    assert payload["provider"] == "pushover"
    assert payload["image"] == str(tmp_path / "shot.png")
    assert "idle_rewards" in payload["message"]
    assert "未声明成功" in payload["message"]


def test_failure_notification_without_screenshot(monkeypatch, tmp_path):
    """截图失败时不应传 image 参数，但仍要发出告警。"""
    monkeypatch.setattr(
        DailyCollectManager,
        "_failure_notice_marker",
        staticmethod(lambda step_name, today: str(tmp_path / "step.flag")),
    )
    sent = []
    monkeypatch.setattr(daily, "send_notification", lambda **kw: sent.append(kw) or True)
    monkeypatch.setattr(daily, "save_error_screenshot", lambda name: "")

    mgr = DailyCollectManager(config_loader=None, db=None)
    mgr._notify_step_failure("collect_gifts", False)

    assert len(sent) == 1
    assert "image" not in sent[0]


def test_failure_notification_swallows_send_errors(monkeypatch, tmp_path):
    """通知发送异常不应向上抛出，避免阻断后续任务。"""
    monkeypatch.setattr(
        DailyCollectManager,
        "_failure_notice_marker",
        staticmethod(lambda step_name, today: str(tmp_path / "step.flag")),
    )
    monkeypatch.setattr(daily, "save_error_screenshot", lambda name: "")

    def boom(**kwargs):
        """模拟通知服务异常。"""
        raise RuntimeError("pushover down")

    monkeypatch.setattr(daily, "send_notification", boom)

    mgr = DailyCollectManager(config_loader=None, db=None)
    mgr._notify_step_failure("small_cookie", False)  # 不应抛出
