"""奖券兑换「先紫后蓝」编排逻辑的模拟测试。

模拟主题兑换一周 70 张奖券的真实节奏（每天 10 张，周五 06:00 换期）：

- 券攒到 **40** → 立刻换第一行「紫色随从碎片」（40 张）
- 换完剩下的券攒到 **30** → 换紧随其后那行「蓝色随从碎片」（30 张）

兑换判据一律以**页面真实券数**为准，不依赖本地累计，
因此漏运行几天、一次攒够 70 张也能补齐，不会漏领。

模拟器 `FakeExchangePage` 会像游戏一样在兑换后真实扣减券余额，
并支持模拟「已兑换的行从列表下架」，用于验证行序变化时的鲁棒性。
"""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import MagicMock

import auto_dungeon_daily
import pytest

# 真机实测的券价布局：行0=40(紫)、行1=30(蓝)、行2=30、行3=20、行4=50
REAL_LAYOUT: tuple[int, ...] = (40, 30, 30, 20, 50)

PURPLE = auto_dungeon_daily.FIRE_TOWER_PURPLE_ITEM_KEY
BLUE = auto_dungeon_daily.FIRE_TOWER_BLUE_ITEM_KEY


class FakeExchangePage:
    """模拟兑换页：持有券余额，兑换后真实扣券。

    Attributes:
        balance: 当前奖券余额（页面上每一行显示的都是这个余额）。
        visible: 页面上还显示的各行券价，顺序即行序。
        redeemed_rows: 本次流程里成功兑换的行，元素为 (行序, 券价)。
        drop_redeemed_row: 兑换成功后是否把该行从列表移除（模拟游戏行为）。
    """

    def __init__(
        self,
        balance: int,
        visible: Optional[tuple[int, ...]] = None,
        drop_redeemed_row: bool = False,
    ) -> None:
        self.balance = balance
        self.visible = list(REAL_LAYOUT if visible is None else visible)
        self.drop_redeemed_row = drop_redeemed_row
        self.redeemed_rows: list[tuple[int, int]] = []

    def snapshot(self) -> list[auto_dungeon_daily.EventExchangeItemState]:
        """按当前页面状态生成行状态列表（行序即列表下标）。"""
        return [
            auto_dungeon_daily.EventExchangeItemState(
                row_index=index,
                item_key=auto_dungeon_daily.DailyCollectManager._resolve_fire_tower_item_key(
                    required
                ),
                required_tickets=required,
                current_tickets=self.balance,
                button_center=(530, 386 + 123 * index),
                is_affordable_by_color=None,
            )
            for index, required in enumerate(self.visible)
        ]

    def redeem_at(self, row_index: int) -> bool:
        """模拟点击某一行的「兑换」按钮。"""
        if row_index < 0 or row_index >= len(self.visible):
            return False
        required = self.visible[row_index]
        if self.balance < required:
            return False
        self.balance -= required
        self.redeemed_rows.append((row_index, required))
        if self.drop_redeemed_row:
            self.visible.pop(row_index)
        return True

    def row_of_point(self, point: tuple[int, int]) -> int:
        """按点击坐标反查行序，用于把 touch 映射回兑换动作。"""
        return round((point[1] - 386) / 123)


def _make_db(completed: set[str]) -> MagicMock:
    """构造按 `completed` 集合记录兑换完成状态的数据库替身。"""
    db = MagicMock()
    db.get_event_cycle_id.return_value = "2026-09-18T06:00:00"

    def _is_completed(event_name: str, item_key: str, cycle_id: Any = None) -> bool:
        return item_key in completed

    def _mark_completed(event_name: str, item_key: str, cycle_id: Any = None) -> None:
        completed.add(item_key)

    db.is_event_item_completed.side_effect = _is_completed
    db.mark_event_item_completed.side_effect = _mark_completed
    return db


def _build_manager(monkeypatch, page: FakeExchangePage, completed: set[str]):
    """构造接入了模拟兑换页的 DailyCollectManager。"""
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=_make_db(completed),
    )
    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        lambda: page.snapshot(),
    )
    # 点击即兑换：按坐标反查行序后真实扣券
    monkeypatch.setattr(
        auto_dungeon_daily,
        "touch",
        lambda point: page.redeem_at(page.row_of_point(point)),
    )
    # 兑换过程没有确认弹窗
    monkeypatch.setattr(
        auto_dungeon_daily,
        "find_text_and_click_safe",
        lambda *args, **kwargs: False,
    )
    # 跳过等待，测试不必真的睡
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *args, **kwargs: None)
    return manager


def _redeemed_item_keys(page: FakeExchangePage) -> list[str]:
    """把模拟器记录的行序还原成物品标识，便于断言。"""
    return [
        auto_dungeon_daily.DailyCollectManager._resolve_fire_tower_item_key(required)
        for _, required in page.redeemed_rows
    ]


# --------------------------------------------------------------------------
# 正常节奏：攒够 40 换紫，再攒够 30 换蓝
# --------------------------------------------------------------------------


def test_redeem_purple_as_soon_as_balance_reaches_40(monkeypatch) -> None:
    """满 40 就立刻换第一行紫色，不等攒到 70。"""
    page = FakeExchangePage(balance=40)
    completed: set[str] = set()
    manager = _build_manager(monkeypatch, page, completed)

    assert manager._redeem_fire_tower_ticket_items() is True

    assert _redeemed_item_keys(page) == [PURPLE]
    assert page.balance == 0
    assert completed == {PURPLE}


def test_redeem_blue_once_remaining_balance_reaches_30(monkeypatch) -> None:
    """紫色已换过、剩下的券攒到 30 时换第二行蓝色。"""
    page = FakeExchangePage(balance=30)
    completed = {PURPLE}
    manager = _build_manager(monkeypatch, page, completed)

    assert manager._redeem_fire_tower_ticket_items() is True

    assert _redeemed_item_keys(page) == [BLUE]
    assert page.balance == 0
    assert completed == {PURPLE, BLUE}


def test_redeem_both_in_one_run_when_balance_reaches_70(monkeypatch) -> None:
    """漏运行几天、一次攒够 70 张时，同一轮连换紫与蓝，不会漏领。"""
    page = FakeExchangePage(balance=70)
    completed: set[str] = set()
    manager = _build_manager(monkeypatch, page, completed)

    assert manager._redeem_fire_tower_ticket_items() is True

    assert _redeemed_item_keys(page) == [PURPLE, BLUE]
    assert page.balance == 0
    assert completed == {PURPLE, BLUE}


def test_redeem_blue_in_same_run_right_after_purple(monkeypatch) -> None:
    """恰好 70 张时第二轮兑换用的是扣掉 40 之后的余额（30 ≥ 30）。"""
    page = FakeExchangePage(balance=70)
    manager = _build_manager(monkeypatch, page, set())

    manager._redeem_fire_tower_ticket_items()

    # 第一次点击对应行0（紫），第二次点击对应行1（蓝）
    assert [row for row, _ in page.redeemed_rows] == [0, 1]


# --------------------------------------------------------------------------
# 券不够：一律不换、不写库，留到下次
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("balance", "completed", "expected_keys"),
    [
        # 只够紫、换完不够蓝 → 只换紫
        (50, set(), [PURPLE]),
        # 只够紫
        (40, set(), [PURPLE]),
        # 差 1 张：什么都不换
        (39, set(), []),
        # 只攒到 30 但紫色还没换过 → 不拿蓝，否则永远攒不到 40
        (30, set(), []),
        # 两个都换过了 → 不再消耗券
        (30, {PURPLE, BLUE}, []),
        # 紫色已换、券不够蓝 → 不换
        (29, {PURPLE}, []),
    ],
)
def test_no_redeem_when_balance_insufficient(
    monkeypatch,
    balance: int,
    completed: set[str],
    expected_keys: list[str],
) -> None:
    """券数不足时必须原样跳过，不能消耗任何奖券。"""
    page = FakeExchangePage(balance=balance)
    manager = _build_manager(monkeypatch, page, completed)

    manager._redeem_fire_tower_ticket_items()

    assert _redeemed_item_keys(page) == expected_keys
    assert page.balance == balance - sum(required for _, required in page.redeemed_rows)


def test_purple_completed_does_not_consume_tickets_again(monkeypatch) -> None:
    """紫色已换过时，即便余额够 40 也不能再换一次。"""
    page = FakeExchangePage(balance=40)
    completed = {PURPLE}
    manager = _build_manager(monkeypatch, page, completed)

    manager._redeem_fire_tower_ticket_items()

    assert _redeemed_item_keys(page) == [BLUE]
    assert page.balance == 10


# --------------------------------------------------------------------------
# 页面行序变化：已兑换的行可能从列表下架
# --------------------------------------------------------------------------


def test_redeem_blue_when_purple_row_disappeared(monkeypatch) -> None:
    """紫色已换过、且它那一行已从列表下架时，仍要能换到蓝色。"""
    page = FakeExchangePage(balance=30, visible=(30, 30, 20, 50))
    completed = {PURPLE}
    manager = _build_manager(monkeypatch, page, completed)

    assert manager._redeem_fire_tower_ticket_items() is True

    # 下架后蓝色成为第一行，仍必须选中它
    assert page.redeemed_rows == [(0, 30)]
    assert page.balance == 0


def test_skip_when_purple_row_missing_but_not_redeemed(monkeypatch) -> None:
    """紫色未换过却读不到它那一行时，保守放弃，乱换会消耗错券。"""
    page = FakeExchangePage(balance=70, visible=(30, 30, 20, 50))
    completed: set[str] = set()
    manager = _build_manager(monkeypatch, page, completed)

    assert manager._redeem_fire_tower_ticket_items() is False

    assert page.redeemed_rows == []
    assert page.balance == 70


def test_redeem_both_when_purple_row_disappears_after_redeem(monkeypatch) -> None:
    """紫色行兑换后立刻下架时，第二个仍要换到蓝色而不是别的 30 张券行。"""
    page = FakeExchangePage(balance=70, drop_redeemed_row=True)
    completed: set[str] = set()
    manager = _build_manager(monkeypatch, page, completed)

    assert manager._redeem_fire_tower_ticket_items() is True

    # 紫色下架后蓝色升到行0，两次点击落在同一位置但换到的是不同物品
    assert page.redeemed_rows == [(0, 40), (0, 30)]
    assert completed == {PURPLE, BLUE}
    assert page.balance == 0


# --------------------------------------------------------------------------
# 兑换校验：券数确实减少才写库
# --------------------------------------------------------------------------


def test_not_marked_completed_when_balance_unchanged(monkeypatch) -> None:
    """点击没生效（券数未变）时不能写库，留待下次重试。"""
    page = FakeExchangePage(balance=40)
    completed: set[str] = set()
    manager = _build_manager(monkeypatch, page, completed)
    # 点击落在按钮之外，模拟点击无效
    monkeypatch.setattr(
        auto_dungeon_daily,
        "touch",
        lambda point: False,
    )

    assert manager._redeem_fire_tower_ticket_items() is False

    assert completed == set()


def test_not_marked_completed_when_page_unreadable(monkeypatch) -> None:
    """复读不到行状态时按未成功处理，不写库。"""
    page = FakeExchangePage(balance=40)
    completed: set[str] = set()
    manager = _build_manager(monkeypatch, page, completed)
    monkeypatch.setattr(
        auto_dungeon_daily,
        "touch",
        lambda point: page.redeem_at(page.row_of_point(point)),
    )
    # 兑换后的复读一律返回空（页面读不到）
    call_state = {"count": 0}
    original_snapshot = page.snapshot

    def _flaky_snapshot():
        call_state["count"] += 1
        if call_state["count"] == 1:
            return original_snapshot()
        return []

    monkeypatch.setattr(
        manager,
        "_load_fire_tower_exchange_states",
        _flaky_snapshot,
    )

    assert manager._redeem_fire_tower_ticket_items() is False

    assert completed == set()


# --------------------------------------------------------------------------
# 告警：券已够却换不成属于异常，必须推送；券不够则静默等待
# --------------------------------------------------------------------------


def test_alert_when_purple_affordable_but_exchange_fails(monkeypatch) -> None:
    """紫色券已够却没换成时必须告警，否则就是静默漏领。"""
    page = FakeExchangePage(balance=40)
    manager = _build_manager(monkeypatch, page, set())
    alerts: list[Any] = []
    monkeypatch.setattr(
        manager,
        "_notify_step_failure",
        lambda step_name, raw_result: alerts.append(step_name),
    )
    # 点击落在按钮之外，模拟点击无效
    monkeypatch.setattr(auto_dungeon_daily, "touch", lambda point: False)

    assert manager._redeem_fire_tower_ticket_items() is False

    assert alerts == ["exchange_purple_first"]


def test_alert_when_blue_affordable_but_exchange_fails(monkeypatch) -> None:
    """蓝色券已够却没换成时同样要告警。"""
    page = FakeExchangePage(balance=30)
    manager = _build_manager(monkeypatch, page, {PURPLE})
    alerts: list[Any] = []
    monkeypatch.setattr(
        manager,
        "_notify_step_failure",
        lambda step_name, raw_result: alerts.append(step_name),
    )
    monkeypatch.setattr(auto_dungeon_daily, "touch", lambda point: False)

    assert manager._redeem_fire_tower_ticket_items() is False

    assert alerts == ["exchange_blue_second"]


def test_no_alert_when_balance_insufficient(monkeypatch) -> None:
    """券还没攒够属于正常等待，不应打扰。"""
    page = FakeExchangePage(balance=39)
    manager = _build_manager(monkeypatch, page, set())
    alerts: list[Any] = []
    monkeypatch.setattr(
        manager,
        "_notify_step_failure",
        lambda *args, **kwargs: alerts.append(args),
    )

    manager._redeem_fire_tower_ticket_items()

    assert alerts == []


# --------------------------------------------------------------------------
# 一周时间线：每天 10 张券，一周期共 70 张
# --------------------------------------------------------------------------


def test_full_week_timeline_redeems_purple_then_blue(monkeypatch) -> None:
    """按每天 10 张的真实节奏跑满一周：满 40 换紫，剩下的满 30 换蓝。"""
    page = FakeExchangePage(balance=0)
    completed: set[str] = set()
    timeline: list[tuple[int, int, list[str]]] = []

    for day in range(7):
        page.balance += 10
        page.redeemed_rows.clear()
        manager = _build_manager(monkeypatch, page, completed)
        manager._redeem_fire_tower_ticket_items()
        timeline.append((day, page.balance, _redeemed_item_keys(page)))

    assert timeline == [
        (0, 10, []),
        (1, 20, []),
        (2, 30, []),
        # 攒到 40 当天就换紫色，不等攒够 70
        (3, 0, [PURPLE]),
        (4, 10, []),
        (5, 20, []),
        # 剩下的券攒到 30 换蓝色，正好用掉本期 70 张
        (6, 0, [BLUE]),
    ]
    assert completed == {PURPLE, BLUE}


def test_whole_week_without_runs_still_redeems_both(monkeypatch) -> None:
    """整周都没运行时券会一直累积，下次运行一次把两个都补齐。"""
    page = FakeExchangePage(balance=10 * 7)
    completed: set[str] = set()
    manager = _build_manager(monkeypatch, page, completed)

    assert manager._redeem_fire_tower_ticket_items() is True

    assert _redeemed_item_keys(page) == [PURPLE, BLUE]
    assert page.balance == 0
    assert completed == {PURPLE, BLUE}
