"""兑换页「行锚点数」完整性判据的回归测试。

背景（2026-10-16 真机）：
    战士会话的兑换页第 5 行是**一次性、已拥有**的物品，按钮区只显示「已拥有」、
    压根没有券价文字。于是「带券价的行」只有 4 行，而页面上「兑换」按钮有 5 个。
    旧判据 `len(states) < FIRE_TOWER_EXCHANGE_EXPECTED_ROWS` 把这种页面算成
    「OCR 漏检了一行」→ 整轮跳过兑换 + 误发「每日任务未完成」告警，
    并且 `_read_exchange_states_until_complete` 还会为一个**稳定**的页面形态
    白打两次 OCR（重读永远补不齐，与 2026-10-03 的教训同源）。

判据：行序的唯一依据是**行锚点（「兑换」按钮）**，券价只是它的校验位。
    锚点齐备即可信；有没有券价文字不影响行序。

本文件的用例都断言**行为**（是否重读 / 是否告警 / 是否兑换），
因此在未修复的代码上会以 AssertionError 失败，而不是 AttributeError。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import auto_dungeon_daily

# 2026-10-16 真机兑换页（冰霜骑士团 · 骑士奖券兑换）全量 OCR 摘录。
# 关键点：5 个「兑换」按钮，但第 5 行的按钮区是「已拥有」、没有券价文字。
REAL_OCR_PRICE_LESS_LAST_ROW: list[dict[str, Any]] = [
    {"text": "0/1", "center": (36, 12), "confidence": 0.97},
    {"text": "冰霜骑士团", "center": (357, 181), "confidence": 0.95},
    {"text": "骑士奖券兑换", "center": (359, 285), "confidence": 0.99},
    {"text": "兑换", "center": (522, 372), "confidence": 0.99},
    {"text": "剩余次数：13/13", "center": (316, 383), "confidence": 0.99},
    {"text": "10/40", "center": (539, 400), "confidence": 1.00},
    {"text": "10", "center": (196, 420), "confidence": 1.00},
    {"text": "兑换", "center": (522, 495), "confidence": 0.99},
    {"text": "剩余次数：13/13", "center": (315, 507), "confidence": 0.99},
    {"text": "10/30", "center": (538, 523), "confidence": 1.00},
    {"text": "8", "center": (198, 541), "confidence": 0.06},
    {"text": "兑换", "center": (522, 618), "confidence": 0.99},
    {"text": "剩余次数：13/13", "center": (316, 628), "confidence": 0.99},
    {"text": "10/30", "center": (539, 646), "confidence": 1.00},
    {"text": "10", "center": (194, 666), "confidence": 1.00},
    {"text": "兑换", "center": (522, 740), "confidence": 0.99},
    {"text": "剩余次数：13/13", "center": (315, 751), "confidence": 0.99},
    {"text": "10/20", "center": (538, 770), "confidence": 1.00},
    {"text": "10", "center": (194, 790), "confidence": 1.00},
    # ↓ 第 5 行：一次性、已拥有的物品 —— 有按钮锚点，但没有券价文字
    {"text": "兑换", "center": (521, 864), "confidence": 0.99},
    {"text": "剩余次数：1/1", "center": (303, 875), "confidence": 0.99},
    {"text": "已拥有", "center": (522, 892), "confidence": 1.00},
    {"text": "用骑士奖券兑换物品", "center": (277, 1072), "confidence": 1.00},
]

EXPECTED_UNPRICED_ROW_COUNT = 4
EXPECTED_PRICE_LESS_ANCHOR_COUNT = 5


def _build_manager(monkeypatch, ocr_results: list[dict[str, Any]], db=None):
    """构造注入了固定 OCR 结果的 DailyCollectManager。"""
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=db if db is not None else MagicMock(),
    )
    monkeypatch.setattr(
        manager,
        "_capture_exchange_screen",
        lambda: (ocr_results, None),
    )
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *args, **kwargs: None)
    return manager


def _affordable_variant(ocr_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把第 1 行的券数改成够换（40/40），其余保持真机原样。"""
    return [
        {**item, "text": "40/40"} if item.get("text") == "10/40" else dict(item)
        for item in ocr_results
    ]


def test_price_less_row_only_yields_four_priced_rows(monkeypatch) -> None:
    """前置事实：真机这种页面确实只解析出 4 个带券价的行（行序 0..3）。"""
    manager = _build_manager(monkeypatch, REAL_OCR_PRICE_LESS_LAST_ROW)

    states = manager._load_fire_tower_exchange_states()

    assert len(states) == EXPECTED_UNPRICED_ROW_COUNT
    assert [state.row_index for state in states] == [0, 1, 2, 3]
    assert [state.required_tickets for state in states] == [40, 30, 30, 20]


def test_read_until_complete_does_not_reread_price_less_row_page(monkeypatch) -> None:
    """页面其实已读全时不能再重读：否则为一个稳定形态白打两次 OCR。

    反证：未修复时 `len(best)=4 < 5` → 会重读 2 次（reads 有 2 条记录）。
    """
    manager = _build_manager(monkeypatch, REAL_OCR_PRICE_LESS_LAST_ROW)
    reads: list[int] = []

    def counting_capture():
        reads.append(1)
        return REAL_OCR_PRICE_LESS_LAST_ROW, None

    monkeypatch.setattr(manager, "_capture_exchange_screen", counting_capture)
    existing = manager._load_fire_tower_exchange_states()
    reads.clear()

    result = manager._read_exchange_states_until_complete(existing)

    assert result == existing
    assert reads == [], f"页面已读全却重读了 {len(reads)} 次"


def test_redeem_does_not_alert_when_only_a_price_less_row_exists(monkeypatch) -> None:
    """券不够时只记 info，不该发「每日任务未完成」告警。

    反证：未修复时会把 4 行误判成漏检 → alerts == ['exchange_incomplete_rows']。
    """
    fake_db = MagicMock()
    fake_db.is_event_item_completed.return_value = False
    fake_db.get_event_cycle_id.return_value = "cycle-1"
    manager = _build_manager(monkeypatch, REAL_OCR_PRICE_LESS_LAST_ROW, db=fake_db)
    alerts: list[str] = []
    monkeypatch.setattr(
        manager,
        "_notify_step_failure",
        lambda step_name, raw_result: alerts.append(step_name),
    )
    states = manager._load_fire_tower_exchange_states()

    assert manager._redeem_fire_tower_ticket_items(states) is False
    assert alerts == []
    fake_db.mark_event_item_completed.assert_not_called()


def test_redeem_still_exchanges_purple_when_later_row_has_no_price(monkeypatch) -> None:
    """券够 40 时，第 5 行没有券价不能阻止第 1 行（紫色）的兑换。

    反证：未修复时行序闸门先拦下，attempted == []（白白错过一次兑换机会）。
    """
    fake_db = MagicMock()
    fake_db.is_event_item_completed.return_value = False
    fake_db.get_event_cycle_id.return_value = "cycle-1"
    manager = _build_manager(
        monkeypatch,
        _affordable_variant(REAL_OCR_PRICE_LESS_LAST_ROW),
        db=fake_db,
    )
    attempted: list[int] = []
    monkeypatch.setattr(
        manager,
        "_attempt_fire_tower_item_exchange",
        lambda state: attempted.append(state.row_index) or True,
    )
    alerts: list[str] = []
    monkeypatch.setattr(
        manager,
        "_notify_step_failure",
        lambda step_name, raw_result: alerts.append(step_name),
    )
    states = manager._load_fire_tower_exchange_states()

    assert manager._redeem_fire_tower_ticket_items(states) is True
    assert attempted == [auto_dungeon_daily.FIRE_TOWER_PURPLE_ROW_INDEX]
    assert alerts == []
    fake_db.mark_event_item_completed.assert_called_once()


def test_redeem_still_alerts_when_row_anchors_are_truly_missing(monkeypatch) -> None:
    """真正的漏检（连「兑换」按钮都少读了）仍要走原来的跳过 + 告警路径。"""
    # 只读到 2 行锚点、券价也整体前移 —— 2026-09-21 的形态
    truncated_ocr: list[dict[str, Any]] = [
        {"text": "兑换", "center": (522, 618), "confidence": 0.99},
        {"text": "剩余次数：13/13", "center": (316, 628), "confidence": 0.99},
        {"text": "10/30", "center": (539, 646), "confidence": 1.00},
        {"text": "兑换", "center": (522, 740), "confidence": 0.99},
        {"text": "剩余次数：13/13", "center": (315, 751), "confidence": 0.99},
        {"text": "10/20", "center": (538, 770), "confidence": 1.00},
    ]
    fake_db = MagicMock()
    fake_db.is_event_item_completed.return_value = False
    fake_db.get_event_cycle_id.return_value = "cycle-1"
    manager = _build_manager(monkeypatch, truncated_ocr, db=fake_db)
    alerts: list[str] = []
    monkeypatch.setattr(
        manager,
        "_notify_step_failure",
        lambda step_name, raw_result: alerts.append(step_name),
    )
    states = manager._load_fire_tower_exchange_states()

    assert manager._redeem_fire_tower_ticket_items(states) is False
    assert alerts == ["exchange_incomplete_rows"]
    fake_db.mark_event_item_completed.assert_not_called()
