"""奖券兑换页解析与兑换校验测试。

覆盖 2026-09-18 修复的根因：兑换页的券进度文字印在「兑换」按钮内部，
按钮中心反而比进度文字更靠左，旧的「按钮 x 必须大于进度 x」判据
会让每一行都匹配不到按钮，导致兑换从未成功过。

目标行的选取按**固定行序**（第 1 行紫色、第 2 行蓝色）：每期可换的碎片
会更换，但两行在列表里的位置不变，兑换后也不会下架，因此位置才是稳定身份。

其中的 OCR 数据取自真机截图（1920x1080 缩放回 720x1280 坐标系）。
"""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import MagicMock

import auto_dungeon_daily
import pytest

# 真机兑换页（海盗船 · 海盗奖券兑换）的全量 OCR 结果摘录
REAL_EXCHANGE_OCR: list[dict[str, Any]] = [
    {"text": "海盗奖券兑换", "center": (360, 286), "confidence": 0.97},
    {"text": "兑换", "center": (522, 372), "confidence": 0.98},
    {"text": "剩余次数：13/13", "center": (316, 383), "confidence": 1.00},
    {"text": "10/40", "center": (538, 401), "confidence": 1.00},
    {"text": "10", "center": (199, 420), "confidence": 0.78},
    {"text": "兑换", "center": (521, 494), "confidence": 0.98},
    {"text": "剩余次数：13/13", "center": (315, 507), "confidence": 1.00},
    {"text": "10/30", "center": (538, 523), "confidence": 1.00},
    {"text": "10", "center": (196, 543), "confidence": 1.00},
    {"text": "兑换", "center": (522, 618), "confidence": 0.98},
    {"text": "剩余次数：13/13", "center": (316, 629), "confidence": 1.00},
    {"text": "10/30", "center": (538, 646), "confidence": 1.00},
    {"text": "10", "center": (193, 666), "confidence": 1.00},
    {"text": "兑换", "center": (521, 740), "confidence": 0.98},
    {"text": "剩余次数：13/13", "center": (316, 753), "confidence": 1.00},
    {"text": "10/20", "center": (538, 770), "confidence": 1.00},
    {"text": "兑换", "center": (521, 864), "confidence": 0.98},
    {"text": "剩余次数：1/1", "center": (303, 876), "confidence": 1.00},
    {"text": "10/50", "center": (538, 893), "confidence": 1.00},
]


def _build_manager(monkeypatch, ocr_results: list[dict[str, Any]]):
    """构造注入了固定 OCR 结果的 DailyCollectManager。

    Args:
        monkeypatch: pytest 的 monkeypatch 夹具。
        ocr_results: 要注入的 OCR 结果列表。

    Returns:
        注入了 OCR 结果的 manager 实例。
    """
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=MagicMock(),
    )
    monkeypatch.setattr(
        manager,
        "_capture_exchange_screen",
        lambda: (ocr_results, None),
    )
    return manager


def _make_state(
    *,
    row_index: int,
    required_tickets: int,
    current_tickets: Optional[int],
    button_center: Optional[tuple[int, int]] = (300, 400),
    item_key: Optional[str] = None,
) -> auto_dungeon_daily.EventExchangeItemState:
    """构造兑换状态测试数据（物品标识默认按行序推导）。"""
    return auto_dungeon_daily.EventExchangeItemState(
        row_index=row_index,
        item_key=item_key
        or auto_dungeon_daily.DailyCollectManager._resolve_fire_tower_item_key(row_index),
        required_tickets=required_tickets,
        current_tickets=current_tickets,
        button_center=button_center,
        is_affordable_by_color=None,
    )


def test_load_states_parses_every_row_with_button(monkeypatch) -> None:
    """真机布局下每一行都要解析出券价与按钮坐标。"""
    manager = _build_manager(monkeypatch, REAL_EXCHANGE_OCR)

    states = manager._load_fire_tower_exchange_states()

    assert [state.required_tickets for state in states] == [40, 30, 30, 20, 50]
    assert [state.current_tickets for state in states] == [10, 10, 10, 10, 10]
    assert all(state.button_center is not None for state in states)
    # 点击点 = 「兑换」文字与券进度文字的中点
    assert states[0].button_center == (530, 386)
    assert states[1].button_center == (529, 508)


def test_load_states_matches_progress_printed_inside_button(monkeypatch) -> None:
    """回归：券进度印在按钮内部、按钮中心比进度更靠左时也要能匹配到按钮。"""
    ocr_results = [
        {"text": "兑换", "center": (522, 372), "confidence": 0.98},
        {"text": "40/40", "center": (538, 401), "confidence": 1.00},
    ]
    manager = _build_manager(monkeypatch, ocr_results)

    states = manager._load_fire_tower_exchange_states()

    assert len(states) == 1
    assert states[0].button_center is not None
    assert states[0].current_tickets == 40
    assert states[0].required_tickets == 40


def test_load_states_ignores_remaining_attempts_text(monkeypatch) -> None:
    """「剩余次数：13/13」不能当成券进度文本。"""
    ocr_results = [
        {"text": "兑换", "center": (522, 372), "confidence": 0.98},
        {"text": "剩余次数：13/13", "center": (316, 383), "confidence": 1.00},
        {"text": "10/40", "center": (538, 401), "confidence": 1.00},
    ]
    manager = _build_manager(monkeypatch, ocr_results)

    states = manager._load_fire_tower_exchange_states()

    assert len(states) == 1
    assert states[0].required_tickets == 40
    assert states[0].current_tickets == 10


def test_load_states_ignores_icon_badge_number(monkeypatch) -> None:
    """物品图标上的角标数字不能当成券进度。"""
    ocr_results = [
        {"text": "兑换", "center": (522, 372), "confidence": 0.98},
        {"text": "10", "center": (199, 420), "confidence": 0.78},
        {"text": "10/40", "center": (538, 401), "confidence": 1.00},
    ]
    manager = _build_manager(monkeypatch, ocr_results)

    states = manager._load_fire_tower_exchange_states()

    assert len(states) == 1
    assert states[0].current_tickets == 10


def test_load_states_does_not_cross_rows(monkeypatch) -> None:
    """相邻行的券进度不会跨行错配。"""
    ocr_results = [
        {"text": "兑换", "center": (522, 372), "confidence": 0.98},
        {"text": "10/40", "center": (538, 401), "confidence": 1.00},
        {"text": "兑换", "center": (521, 494), "confidence": 0.98},
        {"text": "20/30", "center": (538, 523), "confidence": 1.00},
    ]
    manager = _build_manager(monkeypatch, ocr_results)

    states = manager._load_fire_tower_exchange_states()

    assert [(state.current_tickets, state.required_tickets) for state in states] == [
        (10, 40),
        (20, 30),
    ]


def test_select_row_by_fixed_index_ignores_duplicate_prices() -> None:
    """目标行按固定行序选取：券价相同的两行（实测两行都是 30 张）不会取错。"""
    states = [
        _make_state(row_index=0, required_tickets=40, current_tickets=40),
        _make_state(row_index=1, required_tickets=30, current_tickets=30),
        _make_state(row_index=2, required_tickets=30, current_tickets=30),
    ]

    purple = auto_dungeon_daily.DailyCollectManager._row_state(
        states,
        auto_dungeon_daily.FIRE_TOWER_PURPLE_ROW_INDEX,
    )
    blue = auto_dungeon_daily.DailyCollectManager._row_state(
        states,
        auto_dungeon_daily.FIRE_TOWER_BLUE_ROW_INDEX,
    )

    assert purple is not None and purple.row_index == 0
    assert blue is not None and blue.row_index == 1


def test_select_row_returns_none_when_row_absent() -> None:
    """目标行序在列表里不存在时返回 None，而不是随便挑一行。"""
    states = [_make_state(row_index=0, required_tickets=40, current_tickets=40)]

    assert (
        auto_dungeon_daily.DailyCollectManager._row_state(
            states,
            auto_dungeon_daily.FIRE_TOWER_BLUE_ROW_INDEX,
        )
        is None
    )


def test_item_key_is_derived_from_row_index() -> None:
    """物品标识按行序命名：每期碎片会更换，位置才是稳定身份。"""
    resolve = auto_dungeon_daily.DailyCollectManager._resolve_fire_tower_item_key

    assert resolve(0) == auto_dungeon_daily.FIRE_TOWER_PURPLE_ITEM_KEY
    assert resolve(1) == auto_dungeon_daily.FIRE_TOWER_BLUE_ITEM_KEY
    assert resolve(2) == "row_2"


def test_warn_when_row_price_differs_from_observation() -> None:
    """券价与历史观测不符时只告警、不改变行为（可能本期换了碎片）。"""
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=MagicMock(),
    )
    alerts: list[str] = []
    manager.logger.warning = lambda message, *args: alerts.append(message % args)
    states = [
        _make_state(row_index=0, required_tickets=50, current_tickets=50),
        _make_state(row_index=1, required_tickets=30, current_tickets=30),
    ]

    manager._warn_on_unexpected_layout(states)

    assert len(alerts) == 1
    assert "第 1 行" in alerts[0] and "50" in alerts[0]


def test_no_warn_when_layout_matches_observation() -> None:
    """券价与观测一致时不产生告警噪音。"""
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=MagicMock(),
    )
    alerts: list[str] = []
    manager.logger.warning = lambda message, *args: alerts.append(message % args)
    states = [
        _make_state(row_index=0, required_tickets=40, current_tickets=10),
        _make_state(row_index=1, required_tickets=30, current_tickets=10),
    ]

    manager._warn_on_unexpected_layout(states)

    assert alerts == []


def test_redeem_alerts_when_exchange_page_unreadable(monkeypatch) -> None:
    """一行都读不到时无法判断券数，必须告警而不是静默跳过。"""
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=MagicMock(),
    )
    monkeypatch.setattr(manager, "_load_fire_tower_exchange_states", lambda: [])
    alerts: list[str] = []
    monkeypatch.setattr(
        manager,
        "_notify_step_failure",
        lambda step_name, raw_result: alerts.append(step_name),
    )

    assert manager._redeem_fire_tower_ticket_items() is False

    assert alerts == ["exchange_page"]


# --------------------------------------------------------------------------
# 「兑换」标签：图形按钮，OCR 读不出文字 → 用固定坐标点击并以行数据校验
# --------------------------------------------------------------------------


def _build_tab_manager(monkeypatch, reads: list[Any]):
    """构造用于测试「兑换」标签点击的 manager，`reads` 决定每次复读的行状态。"""
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=MagicMock(),
    )
    responses = iter(reads)
    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: next(responses),
    )
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *a, **k: None)
    return manager


def test_open_exchange_tab_skips_click_when_already_on_page(monkeypatch) -> None:
    """已经停在兑换页时不点击：那个按钮是开关，再点会退回活动主页。"""
    states = [_make_state(row_index=0, required_tickets=40, current_tickets=40)]
    manager = _build_tab_manager(monkeypatch, [states])
    touched: list[Any] = []
    monkeypatch.setattr(auto_dungeon_daily, "touch", lambda point: touched.append(point))
    monkeypatch.setattr(
        auto_dungeon_daily,
        "find_text_and_click_safe",
        lambda *a, **k: pytest.fail("不应再按文字查找「兑换」：会误点行内按钮"),
    )

    assert manager._open_exchange_tab() == states

    assert touched == []


def test_open_exchange_tab_clicks_fixed_coordinate(monkeypatch) -> None:
    """不在兑换页时按固定坐标点击标签（OCR 读不出标签文字）。"""
    states = [_make_state(row_index=0, required_tickets=40, current_tickets=40)]
    manager = _build_tab_manager(monkeypatch, [[], states])
    touched: list[Any] = []
    monkeypatch.setattr(auto_dungeon_daily, "touch", lambda point: touched.append(point))
    monkeypatch.setattr(
        auto_dungeon_daily,
        "find_text_and_click_safe",
        lambda *a, **k: pytest.fail("不应再按文字查找「兑换」：会误点行内按钮"),
    )

    assert manager._open_exchange_tab() == states

    assert touched == [auto_dungeon_daily.EVENT_EXCHANGE_TAB_BUTTON]


def test_open_exchange_tab_retries_once_when_page_not_readable(monkeypatch) -> None:
    """点击一次后没读到兑换页时再点一次，避免一次失败浪费当天机会。"""
    states = [_make_state(row_index=0, required_tickets=40, current_tickets=40)]
    manager = _build_tab_manager(monkeypatch, [[], [], states])
    touched: list[Any] = []
    monkeypatch.setattr(auto_dungeon_daily, "touch", lambda point: touched.append(point))

    assert manager._open_exchange_tab() == states

    assert touched == [auto_dungeon_daily.EVENT_EXCHANGE_TAB_BUTTON] * 2


def test_open_exchange_tab_returns_empty_after_two_failures(monkeypatch) -> None:
    """两次点击都读不到时返回空列表，交由兑换流程告警。"""
    manager = _build_tab_manager(monkeypatch, [[], [], []])
    touched: list[Any] = []
    monkeypatch.setattr(auto_dungeon_daily, "touch", lambda point: touched.append(point))

    assert manager._open_exchange_tab() == []

    assert touched == [auto_dungeon_daily.EVENT_EXCHANGE_TAB_BUTTON] * 2


def test_redeem_uses_passed_states_without_reloading(monkeypatch) -> None:
    """调用方刚读过行状态时直接复用，入口不再多打一次 OCR。"""
    fake_db = MagicMock()
    fake_db.is_event_item_completed.side_effect = (
        lambda event_name, item_key, cycle_id=None: item_key
        == auto_dungeon_daily.FIRE_TOWER_PURPLE_ITEM_KEY
    )
    fake_db.get_event_cycle_id.return_value = "cycle-1"
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=fake_db,
    )
    loads: list[int] = []
    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: loads.append(1) or [],
    )
    attempted: list[int] = []
    monkeypatch.setattr(
        manager,
        "_attempt_fire_tower_item_exchange",
        lambda state: attempted.append(state.row_index) or True,
    )
    states = [
        _make_state(row_index=0, required_tickets=40, current_tickets=0),
        _make_state(row_index=1, required_tickets=30, current_tickets=30),
    ]

    assert manager._redeem_fire_tower_ticket_items(states) is True

    assert loads == []
    assert attempted == [1]


def test_verify_returns_true_when_tickets_decrease(monkeypatch) -> None:
    """兑换后券数减少即判定成功。"""
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=MagicMock(),
    )
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: [_make_state(row_index=0, required_tickets=40, current_tickets=0)],
    )
    before = _make_state(row_index=0, required_tickets=40, current_tickets=40)

    assert manager._verify_fire_tower_exchange(before) is True


def test_verify_returns_false_when_tickets_unchanged(monkeypatch) -> None:
    """点击后券数没变说明未生效。"""
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=MagicMock(),
    )
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: [_make_state(row_index=0, required_tickets=40, current_tickets=40)],
    )
    before = _make_state(row_index=0, required_tickets=40, current_tickets=40)

    assert manager._verify_fire_tower_exchange(before) is False


def test_verify_returns_none_when_row_unreadable(monkeypatch) -> None:
    """兑换后读不到该行时返回 None，交由调用方保守处理。"""
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=MagicMock(),
    )
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *args, **kwargs: None)
    monkeypatch.setattr(manager, "_load_fire_tower_exchange_states", lambda: [])
    before = _make_state(row_index=0, required_tickets=40, current_tickets=40)

    assert manager._verify_fire_tower_exchange(before) is None


def test_attempt_exchange_returns_false_when_not_verified(monkeypatch) -> None:
    """券数未变化时不能报成功，否则会写库并从此不再重试。"""
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=MagicMock(),
    )
    monkeypatch.setattr(auto_dungeon_daily, "touch", lambda *args, **kwargs: None)
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        auto_dungeon_daily,
        "find_text_and_click_safe",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(manager, "_verify_fire_tower_exchange", lambda state: False)
    state = _make_state(row_index=0, required_tickets=40, current_tickets=40)

    assert manager._attempt_fire_tower_item_exchange(state) is False


def test_attempt_exchange_returns_true_when_verified(monkeypatch) -> None:
    """券数确认减少后才算兑换成功。"""
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=MagicMock(),
    )
    monkeypatch.setattr(auto_dungeon_daily, "touch", lambda *args, **kwargs: None)
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        auto_dungeon_daily,
        "find_text_and_click_safe",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(manager, "_verify_fire_tower_exchange", lambda state: True)
    state = _make_state(row_index=0, required_tickets=40, current_tickets=40)

    assert manager._attempt_fire_tower_item_exchange(state) is True


def test_redeem_returns_false_when_purple_row_unreadable(monkeypatch) -> None:
    """第 1 行读不到时无法确认行序映射完整，保守跳过、不写库。"""
    fake_db = MagicMock()
    fake_db.is_event_item_completed.return_value = False
    fake_db.get_event_cycle_id.return_value = "cycle-1"
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=fake_db,
    )
    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: [_make_state(row_index=1, required_tickets=30, current_tickets=30)],
    )

    assert manager._redeem_fire_tower_ticket_items() is False
    fake_db.mark_event_item_completed.assert_not_called()


def test_redeem_skips_blue_when_second_row_unreadable(monkeypatch) -> None:
    """紫色已换、第 2 行读不到时只跳过蓝色，不影响已完成的紫色。"""
    fake_db = MagicMock()
    fake_db.is_event_item_completed.side_effect = (
        lambda event_name, item_key, cycle_id=None: item_key
        == auto_dungeon_daily.FIRE_TOWER_PURPLE_ITEM_KEY
    )
    fake_db.get_event_cycle_id.return_value = "cycle-1"
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=fake_db,
    )
    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: [_make_state(row_index=0, required_tickets=40, current_tickets=0)],
    )
    attempted: list[int] = []
    monkeypatch.setattr(
        manager,
        "_attempt_fire_tower_item_exchange",
        lambda state: attempted.append(state.row_index) or True,
    )

    assert manager._redeem_fire_tower_ticket_items() is False
    assert attempted == []


def test_redeem_stops_when_purple_unaffordable(monkeypatch) -> None:
    """紫色券不够时不能越过它去兑蓝色物品。"""
    fake_db = MagicMock()
    fake_db.is_event_item_completed.return_value = False
    fake_db.get_event_cycle_id.return_value = "cycle-1"
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=fake_db,
    )
    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: [
            _make_state(row_index=0, required_tickets=40, current_tickets=10),
            _make_state(row_index=1, required_tickets=30, current_tickets=10),
        ],
    )
    attempted: list[int] = []
    monkeypatch.setattr(
        manager,
        "_attempt_fire_tower_item_exchange",
        lambda state: attempted.append(state.row_index) or True,
    )

    assert manager._redeem_fire_tower_ticket_items() is False
    assert attempted == []
    fake_db.mark_event_item_completed.assert_not_called()


def test_redeem_buys_purple_then_blue_in_row_order(monkeypatch) -> None:
    """紫色可兑时先兑紫色，随后复读页面再兑紧随其后的蓝色行。"""
    fake_db = MagicMock()
    fake_db.is_event_item_completed.return_value = False
    fake_db.get_event_cycle_id.return_value = "cycle-1"
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=fake_db,
    )

    before = [
        _make_state(row_index=0, required_tickets=40, current_tickets=40),
        _make_state(row_index=1, required_tickets=30, current_tickets=30),
        _make_state(row_index=2, required_tickets=30, current_tickets=30),
    ]
    after = [
        _make_state(row_index=0, required_tickets=40, current_tickets=0),
        _make_state(row_index=1, required_tickets=30, current_tickets=30),
        _make_state(row_index=2, required_tickets=30, current_tickets=30),
    ]
    responses = iter([before, after])
    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: next(responses),
    )
    attempted: list[int] = []
    monkeypatch.setattr(
        manager,
        "_attempt_fire_tower_item_exchange",
        lambda state: attempted.append(state.row_index) or True,
    )

    assert manager._redeem_fire_tower_ticket_items() is True
    assert attempted == [0, 1]
    marked = [call.args[1] for call in fake_db.mark_event_item_completed.call_args_list]
    assert marked == [
        auto_dungeon_daily.FIRE_TOWER_PURPLE_ITEM_KEY,
        auto_dungeon_daily.FIRE_TOWER_BLUE_ITEM_KEY,
    ]


def test_redeem_skips_already_bought_purple(monkeypatch) -> None:
    """本期紫色已购时只处理蓝色，避免重复消耗奖券。"""
    fake_db = MagicMock()
    fake_db.is_event_item_completed.side_effect = (
        lambda event_name, item_key, cycle_id=None: item_key
        == auto_dungeon_daily.FIRE_TOWER_PURPLE_ITEM_KEY
    )
    fake_db.get_event_cycle_id.return_value = "cycle-1"
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=fake_db,
    )
    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: [
            _make_state(row_index=0, required_tickets=40, current_tickets=0),
            _make_state(
                row_index=1, required_tickets=30, current_tickets=30, item_key="blue_second"
            ),
        ],
    )
    attempted: list[int] = []
    monkeypatch.setattr(
        manager,
        "_attempt_fire_tower_item_exchange",
        lambda state: attempted.append(state.row_index) or True,
    )

    assert manager._redeem_fire_tower_ticket_items() is True
    assert attempted == [1]
