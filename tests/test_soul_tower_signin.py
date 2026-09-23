"""灵魂之塔签到任务的单测。

覆盖 ``DailyCollectManager._soul_tower_signin`` 的主要分支：
已签到、正常一键签到、补点失败告警、活动入口消失、
状态文字未渲染时点第一个格子刷新。
"""

from __future__ import annotations

import auto_dungeon_daily
from auto_dungeon_daily import DailyCollectManager


class FakeElement:
    """模拟 GameElement：带中心坐标、可点击。"""

    def __init__(self, center: tuple[int, int] = (100, 100)) -> None:
        self.center = center
        self.clicked: list[tuple[int, int]] = []

    def click(self) -> None:
        """记录一次点击。"""
        self.clicked.append(self.center)


class World:
    """脚本化的界面世界：维护可见文字集合与状态迁移。

    Attributes:
        visible: 当前「屏幕上可见」的文字集合。
        clicks: 通过 find_text_and_click_safe 成功点击的文字记录。
        touches: 固定坐标点击记录。
        on_click: 点击钩子 ``(text) -> bool``，返回 False 表示没点到。
        on_find: 查找钩子 ``(text) -> element or None``，
            返回 (True, element) 时短路默认判定。
    """

    def __init__(self, visible: set[str]) -> None:
        self.visible = set(visible)
        self.clicks: list[str] = []
        self.touches: list[tuple[int, int]] = []
        self.on_click = None
        self.on_find = None

    def find_text(self, text: str, *args, **kwargs):
        """按钩子与可见集合应答查找。"""
        if self.on_find:
            handled, element = self.on_find(text)
            if handled:
                return element
        return FakeElement() if text in self.visible else None

    def find_text_and_click_safe(self, text: str, *args, **kwargs) -> bool:
        """可见即点击成功并记录。"""
        if self.on_click:
            if not self.on_click(text):
                return False
        if text in self.visible:
            self.clicks.append(text)
            return True
        return False

    def touch(self, pos) -> None:
        """记录固定坐标点击。"""
        self.touches.append(tuple(pos))


def _make_manager(monkeypatch, world: World) -> tuple[DailyCollectManager, list[str]]:
    """构造被测管理器并把界面桩接入模块。

    Args:
        monkeypatch: pytest monkeypatch。
        world: 界面桩。

    Returns:
        (管理器, 告警记录列表)。
    """
    manager = DailyCollectManager(config_loader=None, db=None)
    failures: list[str] = []
    monkeypatch.setattr(manager, "_notify_step_failure", lambda step, raw: failures.append(step))
    monkeypatch.setattr(auto_dungeon_daily, "back_to_main", lambda: None)
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(auto_dungeon_daily, "find_text", world.find_text)
    monkeypatch.setattr(
        auto_dungeon_daily, "find_text_and_click_safe", world.find_text_and_click_safe
    )
    monkeypatch.setattr(auto_dungeon_daily, "touch", world.touch)
    return manager, failures


def test_soul_tower_already_signed_returns_true(monkeypatch) -> None:
    """无可签到格子但有解锁标记：判当天已签到，不应触发一键或兜底坐标。"""
    world = World({"灵魂之塔", "兑换", "累计签到", "签到", "解锁"})
    manager, failures = _make_manager(monkeypatch, world)

    assert manager.execute_task("灵魂之塔签到") is True
    assert failures == []
    assert "签到" in world.clicks
    assert not any("键签到" in t for t in world.clicks)
    assert world.touches == []


def test_soul_tower_full_claim_success(monkeypatch) -> None:
    """有可签到格子：一键签到 → 关奖励弹窗 → 复读无可签到 → 成功。"""
    world = World({"灵魂之塔", "兑换", "累计签到", "签到"})
    claimable = FakeElement()
    state = {"claimed": False, "popup": False}

    def on_find(text: str):
        if text == "可签到":
            return True, (claimable if not state["claimed"] else None)
        if text == "确定":
            return True, (FakeElement() if state["popup"] else None)
        if text == "恭喜获得":
            return True, (FakeElement() if state["popup"] else None)
        return False, None

    def on_click(text: str) -> bool:
        if text == "键签到" and not state["claimed"]:
            state["claimed"] = True
            state["popup"] = True
        return True

    world.on_find = on_find
    world.on_click = on_click
    world.visible.add("键签到")
    world.visible.add("确定")

    manager, failures = _make_manager(monkeypatch, world)

    assert manager.execute_task("灵魂之塔签到") is True
    assert failures == []
    assert "键签到" in world.clicks
    assert "确定" in world.clicks
    assert world.touches == []


def test_soul_tower_claim_still_claimable_after_retry_fails(monkeypatch) -> None:
    """一键后仍可签到、补点一次仍可签到：判失败并告警，绝不无限补点。"""
    world = World({"灵魂之塔", "兑换", "累计签到", "可签到", "键签到"})
    manager, failures = _make_manager(monkeypatch, world)

    # 可签到永远可见，模拟签到一直没生效
    assert manager.execute_task("灵魂之塔签到") is False
    assert failures == ["soul_tower_signin"]
    assert world.clicks.count("键签到") == 1


def test_soul_tower_entry_missing_fails_with_notice(monkeypatch) -> None:
    """活动入口消失：判失败并告警（活动结束口径）。"""
    world = World(set())
    manager, failures = _make_manager(monkeypatch, world)

    assert manager.execute_task("灵魂之塔签到") is False
    assert failures == ["soul_tower_signin"]
    # OCR 与固定坐标兜底都尝试过
    assert auto_dungeon_daily.SOUL_TOWER_ENTRY_FALLBACK in world.touches


def test_soul_tower_state_not_rendered_clicks_first_slot(monkeypatch) -> None:
    """状态文字未渲染：点第一个格子图标刷新后再走一键签到。"""
    world = World({"灵魂之塔", "兑换", "累计签到"})
    state = {"refreshed": False, "claimed": False, "popup": False}

    def on_find(text: str):
        if text == "可签到":
            ok = state["refreshed"] and not state["claimed"]
            return True, (FakeElement() if ok else None)
        if text == "确定":
            return True, (FakeElement() if state["popup"] else None)
        if text == "恭喜获得":
            return True, (FakeElement() if state["popup"] else None)
        return False, None

    def on_touch(pos) -> None:
        if tuple(pos) == auto_dungeon_daily.SOUL_TOWER_FIRST_SLOT_FALLBACK:
            state["refreshed"] = True

    def on_click(text: str) -> bool:
        if text == "键签到" and state["refreshed"] and not state["claimed"]:
            state["claimed"] = True
            state["popup"] = True
        return True

    world.on_find = on_find
    world.on_click = on_click
    world.touch = on_touch  # type: ignore[method-assign]
    world.visible.add("键签到")
    world.visible.add("确定")

    manager, failures = _make_manager(monkeypatch, world)

    assert manager.execute_task("灵魂之塔签到") is True
    assert failures == []
    assert state["refreshed"] is True
    assert "键签到" in world.clicks
