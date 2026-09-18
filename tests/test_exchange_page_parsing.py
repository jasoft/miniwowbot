"""奖券兑换页解析与兑换校验测试。

覆盖 2026-09-18 修复的根因：兑换页的券进度文字印在「兑换」按钮内部，
按钮中心反而比进度文字更靠左，旧的「按钮 x 必须大于进度 x」判据
会让每一行都匹配不到按钮，导致兑换从未成功过。

其中的 OCR 数据取自真机截图（1920x1080 缩放回 720x1280 坐标系）。
"""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import MagicMock

import auto_dungeon_daily

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
    item_key: str = "purple_first",
) -> auto_dungeon_daily.EventExchangeItemState:
    """构造兑换状态测试数据。"""
    return auto_dungeon_daily.EventExchangeItemState(
        row_index=row_index,
        item_key=item_key,
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


def test_select_target_skips_duplicate_price_rows(monkeypatch) -> None:
    """券价相同的两行（实测两行都是 30 张）必须按行序区分，不能取错行。"""
    states = [
        _make_state(row_index=0, required_tickets=40, current_tickets=40),
        _make_state(row_index=1, required_tickets=30, current_tickets=30, item_key="blue_second"),
        _make_state(row_index=2, required_tickets=30, current_tickets=30, item_key="blue_second"),
    ]

    purple = auto_dungeon_daily.DailyCollectManager._select_fire_tower_target(states, 40)
    blue = auto_dungeon_daily.DailyCollectManager._select_fire_tower_target(
        states,
        30,
        after_row=purple.row_index,
    )

    assert purple is not None and purple.row_index == 0
    assert blue is not None and blue.row_index == 1


def test_select_target_returns_none_when_price_absent() -> None:
    """页面上没有目标券价时应返回 None，而不是随便挑一行。"""
    states = [_make_state(row_index=0, required_tickets=20, current_tickets=20)]

    assert auto_dungeon_daily.DailyCollectManager._select_fire_tower_target(states, 40) is None


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


def test_redeem_returns_false_when_purple_row_missing(monkeypatch) -> None:
    """页面上找不到 40 张券的目标行时不写库、不误报成功。"""
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
        lambda: [_make_state(row_index=0, required_tickets=20, current_tickets=20)],
    )

    assert manager._redeem_fire_tower_ticket_items() is False
    fake_db.mark_event_item_completed.assert_not_called()


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
        _make_state(row_index=1, required_tickets=30, current_tickets=30, item_key="blue_second"),
        _make_state(row_index=2, required_tickets=30, current_tickets=30, item_key="blue_second"),
    ]
    after = [
        _make_state(row_index=0, required_tickets=40, current_tickets=0),
        _make_state(row_index=1, required_tickets=30, current_tickets=30, item_key="blue_second"),
        _make_state(row_index=2, required_tickets=30, current_tickets=30, item_key="blue_second"),
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
