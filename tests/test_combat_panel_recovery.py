"""回归测试：战斗超时后的「角色面板块自愈」，以及「绝不盲点底部导航『战斗』页签」。

背景（2026-11-07 体检，回溯 2026-10-26 / 10-27 / 10-28 / 11-06 共 5 次真机故障）：

    战斗循环一路空转到 180 秒超时、抛出 ``TimeoutError`` → ``main_wrapper`` 走
    「超时重启」→ 停/重启模拟器 + 重跑整轮（约 4 分钟），并误发一条「超时重启」。

    而这 5 次的错误截图（``log/error_auto_combat_timeout_*.png``）画面完全同构：
    战斗画面被**角色面板**整块遮住，底部导航「战斗」页签处于**高亮选中**态，
    BOSS 血量却一直在掉 —— 战斗其实在正常进行，只是 ``is_main_world()``（靠主世界
    「礼包」模板判定）被面板挡住，永远命中不了。

    遮挡从哪来：``_start_battle_sequence`` 与 ``auto_combat`` **各**盲点了一次
    ``find_text_and_click_safe("战斗", regions=[8])``，而该区域里唯一稳定存在的
    「战斗」文案就是底部导航页签（真机 ``(361, 1243)``）。这个页签是**角色面板的
    开关（toggle）** —— 点一次开、再点一次关（``weekly_soul_land.NAV_BATTLE`` 的
    注释就是「也用于关面板」）。于是流程实际是靠"开一次 + 关一次"的**奇偶性**维持
    面板关闭的：只要其中一次被进场动画吞掉（两次点击都发生在点「免费」后的
    0.4 秒 / 2.0 秒，正压在进场动画上），面板就会留在屏幕上。

本文件锁死的不变量：

1. **不再盲点导航页签**：命中的 y 落在底部导航栏内时，只记日志、绝不点击
   （源码级守卫 + 运行时行为各一条）。
2. **超时先自愈再判失败**：到达 ``COMBAT_TIMEOUT_SECONDS`` 时先点一次导航页签
   收起面板，并给有限轮数继续观察；面板收起后能正常返回（不再白跑一轮重启）。
3. **自愈必须是有界的**：收起面板后仍回不到主界面时，照样抛 ``TimeoutError``，
   且只尝试一次（不许变成死循环重试）。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auto_dungeon_combat  # noqa: E402
import auto_dungeon_ui  # noqa: E402
from auto_dungeon_combat import auto_combat  # noqa: E402

#: 旧代码没有 ``BATTLE_NAV_TEXT`` / ``tap_battle_entry_if_not_nav``，用 ``getattr`` 兜底，
#: 否则"改前反证"会以 ``ImportError`` 收场 —— 那是**机械失败**（打桩目标不存在），
#: 证明不了"行为确实缺失"。兜底之后，旧代码能正常跑起来，失败会落在真正的行为断言上。
BATTLE_NAV_TEXT = getattr(auto_dungeon_ui, "BATTLE_NAV_TEXT", "战斗")
_NAV_HELPER = getattr(auto_dungeon_ui, "tap_battle_entry_if_not_nav", None)


def tap_battle_entry_if_not_nav(*args, **kwargs):
    """转发到被测函数；旧代码上以断言失败暴露"函数根本没实现"。

    Returns:
        bool: 被测函数的返回值。

    Raises:
        AssertionError: 模块里没有这个函数（旧实现仍在盲点导航页签）。
    """
    if _NAV_HELPER is None:
        raise AssertionError(
            "auto_dungeon_ui 里没有 tap_battle_entry_if_not_nav：仍在盲点底部导航「战斗」页签"
        )
    return _NAV_HELPER(*args, **kwargs)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: 真机实测的底部导航「战斗」页签落点（见 ``weekly_soul_land.NAV_BATTLE``）。
NAV_CENTER = (361, 1243)

#: 超时自愈时应当被点到的坐标。旧版本没有这个常量，用 ``getattr`` 兜底以避免
#: "打桩目标不存在"造成的机械失败。
TOGGLE_POSITION = getattr(auto_dungeon_combat, "BATTLE_NAV_TOGGLE_POSITION", (362, 1245))

#: 伪造的「实等秒数」，必须大于 ``COMBAT_TIMEOUT_SECONDS`` 才会进超时分支。
FAKE_ELAPSED = 200.0


class _FakeElement:
    """替身元素：只提供 ``center`` / ``click()`` / 布尔真值。"""

    def __init__(self, center):
        self.center = center
        self.clicked = False

    def __bool__(self):
        return True

    def click(self):
        self.clicked = True
        return self


class _FakeGameActions:
    """替身 GameActions：``find`` 返回预先摆好的元素。"""

    def __init__(self, element):
        self._element = element

    def find(self, text, **kwargs):
        assert text == BATTLE_NAV_TEXT, f"应查找「{BATTLE_NAV_TEXT}」，实际 {text!r}"
        return self._element


class _FakeContainer:
    def __init__(self, game_actions):
        self.game_actions = game_actions


def _patch_container(monkeypatch, element):
    """把 ``auto_dungeon_ui.get_container()`` 换成返回替身 GameActions 的桩。"""
    fake = _FakeGameActions(element)
    monkeypatch.setattr(auto_dungeon_ui, "get_container", lambda: _FakeContainer(fake))
    return fake


def _fake_monotonic_factory():
    """第一次返回 0（``combat_start``），之后固定返回 ``FAKE_ELAPSED``。

    Returns:
        Callable[[], float]: 供 ``monkeypatch`` 挂到 ``auto_dungeon_combat.time.monotonic``。
    """
    calls = {"count": 0}

    def _fake_monotonic() -> float:
        calls["count"] += 1
        return 0.0 if calls["count"] == 1 else FAKE_ELAPSED

    return _fake_monotonic


def _patch_recovery_environment(monkeypatch, *, main_world_after_toggle: bool):
    """打桩 ``auto_combat`` 的外部依赖，并让「主界面是否可达」由是否点过导航页签决定。

    Args:
        monkeypatch: pytest 的 monkeypatch fixture。
        main_world_after_toggle: True 时，一旦点了导航页签 ``is_main_world()`` 就变真
            （模拟"面板收起后画面恢复、战斗照常结束"）。
    """
    state = {"toggled": False}

    def _touch(pos):
        if tuple(pos) == tuple(TOGGLE_POSITION):
            state["toggled"] = True

    monkeypatch.setattr(
        auto_dungeon_combat, "tap_battle_entry_if_not_nav", lambda *a, **k: None, raising=False
    )
    monkeypatch.setattr(auto_dungeon_combat, "wait", lambda *a, **k: True)
    monkeypatch.setattr(auto_dungeon_combat, "check_stop_signal", lambda: False)
    monkeypatch.setattr(
        auto_dungeon_combat,
        "is_main_world",
        lambda: bool(main_world_after_toggle and state["toggled"]),
    )
    monkeypatch.setattr(auto_dungeon_combat, "touch", _touch)
    monkeypatch.setattr(auto_dungeon_combat, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(auto_dungeon_combat, "SKILL_POSITIONS", [(0, 0)] * 5)
    monkeypatch.setattr(auto_dungeon_combat.time, "monotonic", _fake_monotonic_factory())
    monkeypatch.setattr(auto_dungeon_combat.time, "time", lambda: 1_700_000_000.0)
    return state


def test_no_blind_battle_nav_click_left_in_source():
    """源码级守卫：战斗入口不得再出现「盲点『战斗』」的调用。

    这是**改前必 FAIL** 的那条 —— 旧代码在 ``auto_dungeon_combat.py`` 与
    ``auto_dungeon_state_machine.py`` 里各有一处
    ``find_text_and_click_safe("战斗", regions=[8])``。盲点的后果见模块 docstring：
    该区域唯一稳定的「战斗」就是底部导航页签（角色面板开关），点它就等于把面板打开。
    注释行（以 ``#`` 开头）允许出现该写法 —— 本次修复特意在注释里保留了"不要退回"的说明。
    """
    forbidden = 'find_text_and_click_safe("战斗"'
    offenders = []
    for name in ("auto_dungeon_combat.py", "auto_dungeon_state_machine.py"):
        for lineno, line in enumerate((PROJECT_ROOT / name).read_text("utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if forbidden in line:
                offenders.append(f"{name}:{lineno}")

    assert not offenders, f"仍在盲点底部导航「战斗」页签（= 角色面板开关）: {offenders}"


def test_helper_skips_click_when_only_match_is_bottom_nav(monkeypatch):
    """命中的 y 落在底部导航栏内时，只记日志、不做点击。"""
    element = _FakeElement(NAV_CENTER)
    _patch_container(monkeypatch, element)

    assert tap_battle_entry_if_not_nav() is False
    assert element.clicked is False, "底部导航「战斗」页签是角色面板开关，绝不能点"


def test_helper_clicks_when_match_is_above_bottom_nav(monkeypatch):
    """命中在导航栏以上（真正的「战斗」按钮）时照常点击。"""
    element = _FakeElement((360, 900))
    _patch_container(monkeypatch, element)

    assert tap_battle_entry_if_not_nav() is True
    assert element.clicked is True


def test_helper_tolerates_missing_element(monkeypatch):
    """没找到「战斗」时安静返回 False，不抛异常。"""
    _patch_container(monkeypatch, None)

    assert tap_battle_entry_if_not_nav() is False


def test_timeout_recovers_after_closing_panel(monkeypatch, caplog):
    """超时后面板被收起、画面恢复 ⇒ 正常返回，**不再**抛 ``TimeoutError``。

    改前行为：到点直接 ``raise TimeoutError`` → 上层「超时重启」→ 停/重启模拟器并
    重跑整轮（约 4 分钟），而这 5 次故障里战斗本来就在打。
    """
    state = _patch_recovery_environment(monkeypatch, main_world_after_toggle=True)

    with patch.object(auto_dungeon_combat, "save_error_screenshot", return_value="/tmp/x.png"):
        with patch.object(auto_dungeon_combat, "describe_foreground", return_value="unknown"):
            with caplog.at_level(logging.WARNING, logger="auto_dungeon_combat"):
                auto_combat(completed_dungeons=2, total_dungeons=11)

    assert state["toggled"] is True, "超时后应点一次底部导航「战斗」尝试收起遮挡面板"
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("遮挡" in line for line in warnings), f"应留下遮挡自愈的 WARNING，实际: {warnings!r}"


def test_timeout_still_fails_when_panel_recovery_does_not_help(monkeypatch, caplog):
    """收起面板也回不到主界面时，仍抛 ``TimeoutError``，且**只尝试一次**。"""
    state = _patch_recovery_environment(monkeypatch, main_world_after_toggle=False)
    toggles = {"count": 0}

    def _touch(pos):
        if tuple(pos) == tuple(TOGGLE_POSITION):
            state["toggled"] = True
            toggles["count"] += 1

    monkeypatch.setattr(auto_dungeon_combat, "touch", _touch)

    with patch.object(auto_dungeon_combat, "save_error_screenshot", return_value="/tmp/x.png"):
        with patch.object(
            auto_dungeon_combat, "describe_foreground", return_value="com.ms.ysjyzr/AppActivity"
        ):
            with caplog.at_level(logging.ERROR, logger="auto_dungeon_combat"):
                with pytest.raises(TimeoutError, match="180"):
                    auto_combat()

    assert toggles["count"] == 1, f"自愈只应尝试一次，实际点击了 {toggles['count']} 次"
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("com.ms.ysjyzr" in line for line in errors), "最终 ERROR 仍须带前台应用信息"
