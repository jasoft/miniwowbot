"""活动主页上缴流程的容错测试。

覆盖 2026-09-20 报告的问题：原实现是无反馈的「盲点 5 次」，
某次点击被卡掉（网络抖动、界面还在动画）就会出现「点 5 次只缴上 3 次」的漏缴，
剩下两次只能手工补。

新实现每次点击后复读活动主页上的「每上缴(N/5)次领取一次宝箱」进度来确认
这一下是否真的生效，没生效就补点。该进度文本取自真机截图 OCR
（置信度 0.998，括号与 `/5` 都能稳定读出）。
"""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import MagicMock

import auto_dungeon_daily
import pytest


class FakeDonatePage:
    """模拟活动主页的上缴场景。

    Attributes:
        done: 已上缴次数。
        required: 需要上缴的总次数。
        click_effects: 每次点击是否生效的序列；用完后默认按生效处理。
        progress_visible: 进度文本是否可见（模拟弹窗遮挡等）。
        hide_after_clicks: 点击达到该次数后进度文本消失；`None` 表示不消失。
        click_count: 累计被点击次数。
    """

    def __init__(
        self,
        done: int = 0,
        required: int = 5,
        click_effects: Optional[list[bool]] = None,
        progress_visible: bool = True,
        hide_after_clicks: Optional[int] = None,
        dirty_texts: Optional[list[str]] = None,
    ):
        """初始化假页面。"""
        self.done = done
        self.required = required
        self.click_effects = list(click_effects or [])
        self.progress_visible = progress_visible
        self.hide_after_clicks = hide_after_clicks
        # 排在真实进度框之前的「脏」文本框，用于模拟 OCR 多认/认错一位数字
        self.dirty_texts = list(dirty_texts or [])
        self.click_count = 0

    def click(self) -> None:
        """模拟一次点击：按 click_effects 决定这一次是否推进进度。"""
        self.click_count += 1
        effective = self.click_effects.pop(0) if self.click_effects else True
        if effective:
            self.done += 1
        if self.hide_after_clicks is not None and self.click_count >= self.hide_after_clicks:
            self.progress_visible = False

    def ocr_results(self) -> list[dict[str, Any]]:
        """返回当前页面上的 OCR 结果。"""
        items: list[dict[str, Any]] = [{"text": "上缴", "center": (362, 639)}]
        items.extend({"text": text, "center": (308, 946)} for text in self.dirty_texts)
        if self.progress_visible:
            items.append(
                {
                    "text": f"每上缴({self.done}/{self.required})次领取一次宝箱",
                    "center": (308, 946),
                }
            )
        return items


def _build_manager(monkeypatch, page: FakeDonatePage):
    """构造注入了假页面的 DailyCollectManager。

    Args:
        monkeypatch: pytest 的 monkeypatch 夹具。
        page: 假的上缴页面。

    Returns:
        注入完成的 manager 实例。
    """
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=MagicMock(),
    )
    # 测试期不往真实日志里写，同时便于断言「有没有把原始文本留痕」
    manager.logger = MagicMock()
    monkeypatch.setattr(
        manager,
        "_capture_full_ocr",
        lambda prefix: (page.ocr_results(), None),
    )
    monkeypatch.setattr(auto_dungeon_daily, "touch", lambda center: page.click())
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *args, **kwargs: None)
    return manager


def test_all_clicks_effective_does_not_waste_clicks(monkeypatch) -> None:
    """5 次点击全部生效时，正好点 5 次。"""
    page = FakeDonatePage(done=0, required=5)
    manager = _build_manager(monkeypatch, page)

    assert manager._donate_event_materials((362, 639)) is True
    assert page.done == 5
    assert page.click_count == 5


def test_retries_dropped_clicks_until_complete(monkeypatch) -> None:
    """回归本次报告的问题：中间有两次点击没生效，必须补点凑满 5 次。"""
    page = FakeDonatePage(
        done=0,
        required=5,
        click_effects=[True, False, True, False, True, True, True],
    )
    manager = _build_manager(monkeypatch, page)

    assert manager._donate_event_materials((362, 639)) is True
    assert page.done == 5
    # 5 次有效点击 + 2 次补点
    assert page.click_count == 7


def test_already_completed_skips_clicking(monkeypatch) -> None:
    """读到 5/5 时不再点击（手工补过或重复运行时不得再消耗物资）。"""
    page = FakeDonatePage(done=5, required=5)
    manager = _build_manager(monkeypatch, page)

    assert manager._donate_event_materials((362, 639)) is True
    assert page.click_count == 0


def test_required_count_comes_from_page(monkeypatch) -> None:
    """目标次数取页面读到的 `/N`，游戏调整每日次数时自动适配。"""
    page = FakeDonatePage(done=0, required=3)
    manager = _build_manager(monkeypatch, page)

    assert manager._donate_event_materials((362, 639)) is True
    assert page.click_count == 3


def test_gives_up_after_consecutive_stalls(monkeypatch) -> None:
    """连续补点仍无进展时放弃，不会无限点击。"""
    page = FakeDonatePage(done=0, required=5, click_effects=[False] * 20)
    manager = _build_manager(monkeypatch, page)

    assert manager._donate_event_materials((362, 639)) is False
    assert page.click_count == auto_dungeon_daily.DONATE_MAX_STALLS


def test_stall_counter_resets_after_each_success(monkeypatch) -> None:
    """偶发丢点不会累积：每次成功后失败计数清零，仍能缴满。"""
    page = FakeDonatePage(
        done=0,
        required=5,
        click_effects=[False, True, False, True, False, True, False, True, True],
    )
    manager = _build_manager(monkeypatch, page)

    assert manager._donate_event_materials((362, 639)) is True
    assert page.done == 5


def test_stops_when_progress_disappears(monkeypatch) -> None:
    """上缴后进度文本消失（弹窗遮挡、页面切换）时停止补救，不乱点。"""
    page = FakeDonatePage(done=0, required=5, hide_after_clicks=1)
    manager = _build_manager(monkeypatch, page)

    assert manager._donate_event_materials((362, 639)) is False
    assert page.click_count == 1


def test_unreadable_progress_falls_back_to_blind_clicks(monkeypatch) -> None:
    """读不到进度时退化为盲点 5 次，且不谎报成功。"""
    page = FakeDonatePage(progress_visible=False)
    manager = _build_manager(monkeypatch, page)

    assert manager._donate_event_materials((362, 639)) is False
    assert page.click_count == auto_dungeon_daily.DONATE_TARGET_TIMES


def test_rejects_out_of_range_required_count(monkeypatch) -> None:
    """OCR 把 `/5` 读成 `/50` 时不采信该行，退化为盲点并返回失败。"""
    page = FakeDonatePage(done=0, required=50)
    manager = _build_manager(monkeypatch, page)

    assert manager._donate_event_materials((362, 639)) is False
    assert page.click_count == auto_dungeon_daily.DONATE_TARGET_TIMES


def test_rejects_done_greater_than_required(monkeypatch) -> None:
    """已完成数超过上限（如 `7/5`）说明读错，不采信。"""
    page = FakeDonatePage(done=7, required=5)
    manager = _build_manager(monkeypatch, page)

    assert manager._donate_event_materials((362, 639)) is False
    assert page.click_count == auto_dungeon_daily.DONATE_TARGET_TIMES


def test_skips_misread_candidate_and_uses_later_valid_one(monkeypatch) -> None:
    """回归 2026-09-23：首条候选被 OCR 多认一位（15/5）时不能整页放弃。

    2026-09-21 ~ 09-23 小号连续三天把上缴进度读成 `10/5` / `15/5`，旧实现
    遇到第一条越界候选就 `return None`，整页退化为盲点 5 次。正确行为是继续
    扫描后面的候选，用合法的那条把次数补满。
    """
    page = FakeDonatePage(
        done=2,
        required=5,
        dirty_texts=["每上缴(15/5)次领取一次宝箱"],
    )
    manager = _build_manager(monkeypatch, page)

    assert manager._donate_event_materials((362, 639)) is True
    assert page.done == 5
    assert page.click_count == 3


def test_logs_raw_text_when_every_candidate_is_invalid(monkeypatch) -> None:
    """全部候选都不合法时，必须把原始文本写进日志。

    否则事后只看到「读到 15/5」，无法判断到底哪几个字被认错，
    第二天照样只能盲点。
    """
    page = FakeDonatePage(
        progress_visible=False,
        dirty_texts=["每上缴(15/5)次领取一次宝箱"],
    )
    manager = _build_manager(monkeypatch, page)

    assert manager._donate_event_materials((362, 639)) is False
    assert page.click_count == auto_dungeon_daily.DONATE_TARGET_TIMES
    logged = " ".join(str(call) for call in manager.logger.warning.call_args_list)
    assert "每上缴(15/5)次领取一次宝箱" in logged


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("每上缴(3/5)次领取一次宝箱", ("3", "5")),
        ("每上缴（2/5）次领取一次宝箱", ("2", "5")),
        ("每上缴 (4/5) 次领取一次宝箱", ("4", "5")),
    ],
)
def test_donate_progress_pattern_accepts_real_variants(text, expected) -> None:
    """真机文案（含全角括号与空格差异）都要能解析出进度。"""
    match = auto_dungeon_daily.DONATE_PROGRESS_PATTERN.search(text)
    assert match is not None
    assert match.groups() == expected


@pytest.mark.parametrize(
    "text",
    [
        "上缴",
        "10/40",
        "剩余次数：13/13",
        "每日可获得物资x5",
        "已领取",
    ],
)
def test_donate_progress_pattern_ignores_other_text(text) -> None:
    """其它含数字或含「上缴」二字的文案都不能被当成上缴进度。"""
    assert auto_dungeon_daily.DONATE_PROGRESS_PATTERN.search(text) is None
