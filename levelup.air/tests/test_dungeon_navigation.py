"""验证目标定位、延迟加载、免费次数及进入确认。"""

# ruff: noqa: E402

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path(__file__).resolve().parents[2]))

import actions
import dungeon_navigation as navigation
import manual_intervention
from behavior_rule import BehaviorRule
from engine import LevelUpEngine
from state import WorldState


def item(text: str, x: int, y: int) -> dict:
    """创建带位置的 OCR 条目。

    Args:
        text: 文字。
        x: 横坐标。
        y: 纵坐标。

    Returns:
        OCR 条目。
    """
    return {"text": text, "center": (x, y)}


@pytest.fixture
def state(monkeypatch: pytest.MonkeyPatch) -> WorldState:
    """替换设备操作并构建状态。

    Args:
        monkeypatch: 测试替换工具。

    Returns:
        使用模拟 OCR 的运行状态。
    """
    monkeypatch.setattr(navigation, "touch", Mock())
    monkeypatch.setattr(navigation, "sleep", Mock())
    return WorldState(ocr=Mock(), actions=Mock(), templates={})


def frames(state: WorldState, remaining: int = 1) -> tuple[list, list, list]:
    """构造任务、地图和副本详情页面。

    Args:
        state: 要设置任务截图的状态。
        remaining: 剩余免费次数。

    Returns:
        三个依次出现的页面。
    """
    quest = [item("通关「深渊囚牢」。", 354, 557), item("前往", 360, 865)]
    map_screen = [item("堕落教堂", 374, 662), item("深渊囚牢", 604, 749)]
    panel = [
        item("深渊囚牢", 359, 259),
        item("地下城等级：430~435", 359, 295),
        item(f"免费({remaining}/1)", 306, 922),
        item("前往", 413, 921),
    ]
    state.ocr.capture_and_get_all_texts.return_value = quest
    return quest, map_screen, panel


def test_delayed_free_entry_uses_exact_target(state: WorldState) -> None:
    """详情延迟出现时等待，不点箭头推测位置，也不误报。

    Args:
        state: 模拟运行状态。
    """
    quest, map_screen, panel = frames(state)
    state.ocr.capture_and_get_all_texts.side_effect = [
        quest,
        [],
        map_screen,
        map_screen,
        panel[:2],
        panel,
        [item("地下城-深渊囚牢", 359, 210)],
    ]
    assert navigation.navigate_to_task(state) == ""
    assert navigation.touch.call_args_list == [  # type: ignore[attr-defined]
        call((360, 865)),
        call((604, 749)),
        call((306, 922)),
    ]
    for capture_call in state.ocr.capture_and_get_all_texts.call_args_list:
        assert capture_call.kwargs == {"use_cache": False}


def test_exhausted_free_entry_never_clicked(state: WorldState) -> None:
    """免费次数耗尽不点击入口，也不视为识别不到按钮。

    Args:
        state: 模拟运行状态。
    """
    quest, map_screen, panel = frames(state, remaining=0)
    state.ocr.capture_and_get_all_texts.side_effect = [quest, map_screen, panel, panel]
    assert "今日免费次数已用完" in navigation.navigate_to_task(state)
    assert navigation.touch.call_count == 2  # type: ignore[attr-defined]


def test_click_requires_entered_confirmation(state: WorldState) -> None:
    """点击后仍停留详情时不能宣布成功或再次消耗次数。

    Args:
        state: 模拟运行状态。
    """
    quest, map_screen, panel = frames(state)
    state.ocr.capture_and_get_all_texts.side_effect = [quest, map_screen] + [panel] * 9
    assert "尚未确认进入" in navigation.navigate_to_task(state)
    assert navigation.touch.call_count == 3  # type: ignore[attr-defined]


def test_wrong_map_never_becomes_missing_free_error(state: WorldState) -> None:
    """地图没有目标时报告地图阶段，不点击错误的地点。

    Args:
        state: 模拟运行状态。
    """
    quest, _, _ = frames(state)
    state.ocr.capture_and_get_all_texts.side_effect = [quest] + [[item("堕落教堂", 374, 662)]] * 10
    assert navigation.navigate_to_task(state) == "地图未找到任务目标"
    assert navigation.touch.call_count == 1  # type: ignore[attr-defined]


def test_only_foreground_free_count_is_accepted() -> None:
    """背景或未识别次数的免费文字不能成为免费进入依据。"""
    assert navigation.free_entry([item("免费(1/1)", 50, 200)]) == (None, None)
    assert navigation.free_entry([item("免费", 306, 922)]) == (None, None)
    assert navigation.free_entry([item("免费（1/1）", 306, 922)])[1] == 1
    assert navigation.task_target([item("等级达到434/435级", 360, 527)]) is None


def test_paid_entry_is_exhausted_not_missing(state: WorldState) -> None:
    """重复确认目标副本需要门票，不把付费入口误判为免费。

    Args:
        state: 模拟运行状态。
    """
    quest, map_screen, panel = frames(state)
    panel[2] = item("-21", 322, 921)
    state.ocr.capture_and_get_all_texts.side_effect = [quest, map_screen, panel, panel]
    assert "今日免费次数已用完" in navigation.navigate_to_task(state)
    assert navigation.touch.call_count == 2  # type: ignore[attr-defined]


def test_field_panel_has_different_title_position(state: WorldState) -> None:
    """野外详情标题位置不同，使用实机前往按钮并验证区域。

    Args:
        state: 模拟运行状态。
    """
    state.ocr.capture_and_get_all_texts.side_effect = [
        [item("前往「亡者战场」消灭「软泥巨人」。", 355, 557), item("前往", 359, 865)],
        [item("亡者战场", 396, 530)],
        [item("亡者战场", 360, 477), item("声望商店", 258, 668), item("前往", 359, 775)],
        [item("亡者战场", 359, 34)],
    ]
    assert navigation.navigate_to_task(state) == ""
    assert navigation.touch.call_args_list == [  # type: ignore[attr-defined]
        call((359, 865)),
        call((396, 530)),
        call((359, 775)),
    ]


def test_navigation_notice_has_cooldown(state: WorldState, monkeypatch: pytest.MonkeyPatch) -> None:
    """相同导航失败的多次恢复不会反复发送通知。

    Args:
        state: 模拟运行状态。
        monkeypatch: 测试替换工具。
    """
    notice = Mock()
    monkeypatch.setattr(actions, "navigate_to_task", Mock(return_value="地图未找到任务目标"))
    monkeypatch.setattr(actions, "back_to_main", Mock())
    monkeypatch.setattr(actions, "send_notification", notice)
    actions.goto_next_place(state)
    actions.goto_next_place(state)
    notice.assert_called_once()


def test_level_task_uses_field_instead_of_old_dungeon(
    state: WorldState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """升级主线没有地图目标时优先做野外支线，避免旧副本。

    Args:
        state: 模拟运行状态。
        monkeypatch: 测试替换工具。
    """
    click = Mock()
    goto = Mock()
    monkeypatch.setattr(actions, "touch", click)
    monkeypatch.setattr(actions, "sleep", Mock())
    monkeypatch.setattr(actions, "back_to_main", Mock())
    monkeypatch.setattr(actions, "goto_next_place", goto)
    state.ocr.capture_and_get_all_texts.side_effect = [
        [
            item("等级达到434/435级", 55, 98),
            item("消灭0/2个软", 55, 178),
            item("通关0/1次凋", 55, 255),
        ],
        [item("等级达到434/435级", 360, 527)],
        [item("前往「亡者战场」消灭「软泥巨人」。", 354, 557)],
    ]
    actions.navigate_active_tasks(state)
    assert click.call_args_list == [call((55, 98)), call((55, 178))]
    goto.assert_called_once_with(state)


def test_navigation_failure_keeps_main_target(
    state: WorldState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """主线导航失败时不自动改去其他旧副本或支线。

    Args:
        state: 模拟运行状态。
        monkeypatch: 测试替换工具。
    """
    goto = Mock(return_value=False)
    click = Mock()
    monkeypatch.setattr(actions, "goto_next_place", goto)
    monkeypatch.setattr(actions, "touch", click)
    monkeypatch.setattr(actions, "sleep", Mock())
    monkeypatch.setattr(actions, "back_to_main", Mock())
    state.ocr.capture_and_get_all_texts.side_effect = [
        [item("通关0/1次猩", 55, 98), item("通关0/1次凋", 55, 255)],
        [item("通关「猩红古堡」。", 354, 557)],
    ]
    actions.navigate_active_tasks(state)
    goto.assert_called_once_with(state)
    assert click.call_args_list == [call((55, 98))]


@pytest.mark.parametrize("entry_text", ["免费(1/1)", "-21"])
def test_wrong_dungeon_never_clicks_or_reports_exhaustion(
    state: WorldState, entry_text: str
) -> None:
    """即使错误副本有入口，也不点击或通知免费次数耗尽。

    Args:
        state: 模拟运行状态。
        entry_text: 错误副本中的入口文字。
    """
    quest, map_screen, panel = frames(state)
    panel[0] = item("凋零废墟", 359, 259)
    panel[2] = item(entry_text, 306, 922)
    state.ocr.capture_and_get_all_texts.side_effect = [quest, map_screen, panel]
    reason = navigation.navigate_to_task(state)
    assert "任务目标是深渊囚牢，当前打开的是凋零废墟" in reason
    assert "今日免费次数已用完" not in reason
    assert navigation.touch.call_count == 2  # type: ignore[attr-defined]


def test_no_free_notifies_once_and_preserves_panel(
    state: WorldState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """确证免费次数已用完后保留详情并等待玩家，不重复通知。

    Args:
        state: 模拟运行状态。
        monkeypatch: 测试替换工具。
    """
    notice, close = Mock(), Mock()
    quest, map_screen, panel = frames(state, remaining=0)
    state.ocr.capture_and_get_all_texts.side_effect = [quest, map_screen, panel, panel]
    monkeypatch.setattr(actions, "send_notification", notice)
    monkeypatch.setattr(actions, "back_to_main", close)
    assert not actions.goto_next_place(state)
    assert state.manual_dungeon == "深渊囚牢"
    assert state.manual_wait_day == date.today().isoformat()
    assert not actions.goto_next_place(state)
    actions.navigate_active_tasks(state)
    notice.assert_called_once()
    assert "深渊囚牢今日免费次数已用完" in notice.call_args.args[1]
    close.assert_not_called()


def test_manual_wait_only_resumes_after_correct_entry(state: WorldState) -> None:
    """玩家进入错误副本不会解除等待，进入指定副本后恢复。

    Args:
        state: 模拟运行状态。
    """
    state.manual_dungeon = "深渊囚牢"
    state.manual_wait_day = date.today().isoformat()
    state.ocr.capture_and_get_all_texts.side_effect = [
        [item("地下城-凋零废墟", 359, 210)],
        [item("地下城-深渊囚牢", 359, 210)],
    ]
    manual_intervention.refresh_manual_wait(state)
    assert state.manual_dungeon == "深渊囚牢"
    manual_intervention.refresh_manual_wait(state)
    assert state.manual_dungeon is None
    navigation.touch.assert_not_called()  # type: ignore[attr-defined]


def test_new_day_rechecks_instead_of_permanent_skip(state: WorldState) -> None:
    """每天的免费资格重新检查，不永久跳过昨天无次数的副本。

    Args:
        state: 模拟运行状态。
    """
    state.manual_dungeon = "深渊囚牢"
    state.manual_wait_day = (date.today() - timedelta(days=1)).isoformat()
    manual_intervention.refresh_manual_wait(state)
    assert state.manual_dungeon is None
    assert state.last_task_time == 0.0
    state.ocr.capture_and_get_all_texts.assert_not_called()


@pytest.mark.asyncio
async def test_manual_wait_blocks_selected_rule(state: WorldState) -> None:
    """等待手工处理时，已经选中的超时或交任务规则也不能点击。

    Args:
        state: 模拟运行状态。
    """
    state.manual_dungeon = "深渊囚牢"
    runtime = object.__new__(LevelUpEngine)
    runtime._state = state
    runtime._action_lock = asyncio.Lock()
    action = Mock()
    await runtime._execute_rule(BehaviorRule("超时恢复", Mock(return_value=True), action))
    action.assert_not_called()


def test_close_panel_avoids_android_debug_overlay(
    state: WorldState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """关闭弹窗时避开顶部调试栏，使用实机验证的外侧空白。

    Args:
        state: 模拟运行状态。
        monkeypatch: 测试替换工具。
    """
    click = Mock()
    monkeypatch.setattr(actions, "touch", click)
    monkeypatch.setattr(actions, "sleep", Mock())
    actions.back_to_main(state, taps=2)
    assert click.call_args_list == [call((710, 1150)), call((710, 1150))]
