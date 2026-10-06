"""验证区域任务清单的识别、切区边界和领取后续流程。"""

# ruff: noqa: E402

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path(__file__).resolve().parents[2]))

import task_workflow as workflow
from state import WorldState
from task_regions import next_region, region_menu_position, task_list_region


def screen(region: str, *rows: str) -> list[dict]:
    """构造任务清单 OCR 画面。

    Args:
        region: 当前大陆名称。
        rows: 列表行文本。

    Returns:
        包含标题和任务行的模拟 OCR 结果。
    """
    return [
        {"text": f"任务清单({region})", "center": (360, 271)},
        *({"text": row, "center": (280, 350 + i * 130)} for i, row in enumerate(rows)),
    ]


@pytest.fixture
def state(monkeypatch: pytest.MonkeyPatch) -> WorldState:
    """构造禁止真实点击和等待的运行状态。

    Args:
        monkeypatch: pytest 替换工具。

    Returns:
        使用模拟 OCR 与点击入口的世界状态。
    """
    monkeypatch.setattr(workflow, "touch", Mock())
    monkeypatch.setattr(workflow, "swipe", Mock())
    monkeypatch.setattr(workflow, "sleep", Mock())
    return WorldState(ocr=Mock(), actions=Mock(), templates={}, signals={"request_task_el": Mock()})


def test_region_selection_ignores_green_background_and_offsets() -> None:
    """只有带等级的目标菜单行可以作为下一大陆坐标。"""
    texts = [
        {"text": "前往「元素之地」", "center": (360, 530)},
        {"text": "消灭12/12个怪物", "center": (55, 180)},
        {"text": "Lv.200 元素之地", "center": (355, 660)},
    ]
    assert region_menu_position(texts, "元素之地") == (355, 660)
    assert next_region("冰封大陆") == "元素之地"
    assert next_region("亡灵之地") is None
    assert next_region("未知区域") is None
    assert task_list_region(screen("风暴群岛")) == "风暴群岛"


def test_dungeon_tasks_prevent_premature_region_switch(state: WorldState) -> None:
    """没有支线时，剩余地下城任务仍必须领取。"""
    state.ocr.capture_and_get_all_texts.return_value = screen("亡灵之地", "【地下城】废墟探宝")
    assert workflow.find_available_task(state)["center"] == (280, 350)
    state.ocr.capture_and_get_all_texts.assert_called_with(use_cache=False)


def test_scroll_checks_lower_tasks_and_restarts_at_top(state: WorldState) -> None:
    """首屏没有任务时继续滚动，不能误判本区已完成。"""
    state.ocr.capture_and_get_all_texts.side_effect = [
        screen("军团领域"),
        screen("军团领域"),
        screen("军团领域"),
        screen("军团领域", "【支线】后续任务"),
    ]
    assert workflow.find_available_task(state)["center"] == (280, 350)
    workflow.swipe.assert_any_call((360, 420), (360, 860), duration=0.5)


def test_empty_ocr_is_not_an_exhausted_region(state: WorldState) -> None:
    """OCR 失败时拒绝切区。"""
    state.ocr.capture_and_get_all_texts.return_value = []
    with pytest.raises(RuntimeError, match="任务清单标题"):
        workflow.find_available_task(state)


def test_empty_list_requires_stable_end(state: WorldState) -> None:
    """确认到达列表末尾之后才返回没有可接任务。"""
    state.ocr.capture_and_get_all_texts.return_value = screen("风暴群岛")
    assert workflow.find_available_task(state) is None
    assert state.ocr.capture_and_get_all_texts.call_count == 5


def test_switch_waits_for_menu_and_verifies_heading(state: WorldState) -> None:
    """菜单延迟出现时重读画面，并确认切换后的标题。"""
    state.ocr.capture_and_get_all_texts.side_effect = [
        [*screen("风暴群岛"), {"text": "切换区域", "center": (359, 963)}],
        screen("风暴群岛"),
        [{"text": "Lv.445亡灵之地", "center": (356, 889)}],
        screen("亡灵之地"),
    ]
    assert workflow.switch_task_region(state, "风暴群岛")
    workflow.touch.assert_any_call((356, 889))


def test_last_region_never_clicks_below_menu(state: WorldState) -> None:
    """末区没有下一大陆，不点击菜单外的位置。"""
    assert not workflow.switch_task_region(state, "亡灵之地")
    workflow.touch.assert_not_called()


def test_active_task_does_not_hide_other_available_tasks(state: WorldState) -> None:
    """已接支线仍出现在清单时，继续选择其他地下城任务。"""
    state.ocr.capture_and_get_all_texts.return_value = screen(
        "亡灵之地", "【支线】进行中的任务", "【地下城】废墟探宝"
    )
    candidate = workflow.find_available_task(state, {"【支线】进行中的任务"})
    assert candidate["text"] == "【地下城】废墟探宝"


def test_menu_failure_does_not_report_success(state: WorldState) -> None:
    """只点击按钮而未见目标区域标题时不得报告切区成功。"""
    state.ocr.capture_and_get_all_texts.return_value = screen("风暴群岛")
    assert not workflow.switch_task_region(state, "风暴群岛")


def test_foreground_detail_stops_list_scrolling(state: WorldState) -> None:
    """滑动误触详情时识别前景弹窗，不能反复滚动背景清单。"""
    title = {"text": "【支线】斩草除根", "center": (360, 431)}
    state.ocr.capture_and_get_all_texts.return_value = [
        *screen("亡灵之地"),
        title,
        {"text": "接受任务", "center": (359, 866)},
    ]
    assert workflow.find_available_task(state) == title
    assert workflow.swipe.call_count == 1


def test_no_accept_button_keeps_region(state: WorldState, monkeypatch) -> None:
    """任务已接或达到上限时不能切区。"""
    monkeypatch.setattr(
        workflow,
        "find_available_task",
        Mock(side_effect=[{"text": "【支线】已有任务", "center": (280, 350)}, None]),
    )
    switch = Mock()
    monkeypatch.setattr(workflow, "switch_task_region", switch)
    state.ocr.capture_and_get_all_texts.side_effect = [
        screen("风暴群岛"),
        [{"text": "前往", "center": (359, 865)}],
        screen("风暴群岛"),
        screen("风暴群岛"),
    ]
    workflow.request_tasks(state)
    switch.assert_not_called()
    assert state.signals["request_task_el"] is None
    assert state.request_retry_after > 0


def test_switch_continues_accepting_new_region(state: WorldState, monkeypatch) -> None:
    """切区后立即接新区任务，不能直接返回主界面。"""
    monkeypatch.setattr(
        workflow,
        "find_available_task",
        Mock(side_effect=[None, {"text": "【支线】新区任务", "center": (280, 350)}]),
    )
    switch = Mock(return_value=True)
    monkeypatch.setattr(workflow, "switch_task_region", switch)
    state.ocr.capture_and_get_all_texts.side_effect = [
        screen("风暴群岛"),
        screen("亡灵之地"),
        [{"text": "接受任务", "center": (359, 866)}],
        [{"text": "消灭0/12个怪物", "center": (55, 177)}],
        [{"text": "消灭0/12个怪物", "center": (55, 177)}],
    ]
    workflow.request_tasks(state)
    switch.assert_called_once_with(state, "风暴群岛")
    workflow.touch.assert_any_call((359, 866))


@pytest.mark.asyncio
async def test_cli_device_is_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Airtest 已连接设备时，不得覆盖命令行指定的序列号。"""
    import levelup

    monkeypatch.setattr(levelup.G, "DEVICE_LIST", [Mock()])
    setup = Mock()
    monkeypatch.setattr(levelup, "auto_setup", setup)
    monkeypatch.setattr(levelup, "device", Mock(return_value=Mock(uuid="127.0.0.1:5565")))
    engine = Mock()
    from unittest.mock import AsyncMock

    engine.run = AsyncMock()
    monkeypatch.setattr(levelup, "LevelUpEngine", Mock(return_value=engine))
    monkeypatch.setattr(levelup, "configure_airtest", Mock())
    monkeypatch.setattr(levelup, "setup_logging", Mock(return_value=logging.getLogger("test")))
    monkeypatch.setenv("ANDROID_SERIAL", "old-device")
    await levelup.main()
    setup.assert_called_once_with(levelup.__file__)


@pytest.mark.asyncio
async def test_empty_ocr_element_does_not_trigger_actions(state: WorldState, monkeypatch) -> None:
    """真实空元素不应触发装备动作，避免没有任务时一直空转。"""
    import detectors
    from behavior_setup import build_behavior_tree
    from vibe_ocr.game_actions import GameElement

    monkeypatch.setattr(detectors, "exists", Mock(return_value=False))
    state.templates = {"xp_full": Mock()}
    state.actions.find.return_value = GameElement.empty(state.actions)
    await detectors.scan_workflow(state, 0)
    tree = build_behavior_tree(logging.getLogger("test"))
    assert tree.select(state) is None
