"""上缴满额后领取「物资宝箱」的回归测试。

覆盖 2026-09-21 真机问题：宝箱按钮的文字会带上待领数量（实测「领取(1)」），
而原实现用 ``exact=True`` 精确匹配「领取」—— 于是**偏偏在真有宝箱可领的时候**
匹配失败（没有宝箱可领时按钮才是纯「领取」，那时点了也没意义）。
表现是上缴满 5 次却一直没把宝箱领走，实测因此漏掉 10 张奖券。

顺带覆盖两个同源问题：

- 改用子串匹配后必须排除「已领取」，否则每天会白点一次。
- 领奖成功弹出的「恭喜获得」会压住兑换页，导致后续复读读到 0 行，
  必须顺手关掉。
"""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import MagicMock

import auto_dungeon_daily

CHEST_BUTTON_CENTER = (579, 929)


class FakeElement(dict):
    """模拟 GameElement：下标取字段，同时提供 .text 属性。"""

    @property
    def text(self) -> Optional[str]:
        """返回 OCR 文本。"""
        return self.get("text")


class FakeChestPage:
    """模拟活动主页的「物资宝箱」领取场景。

    Attributes:
        button_texts: 依次返回的宝箱按钮文字；``None`` 表示这一次读不到按钮。
        popup_visible: 是否有「恭喜获得」奖励弹窗。
        clicks: 被点击的坐标。
        confirm_calls: 对「确定」的点击调用，元素为 (文本, kwargs)。
    """

    def __init__(
        self,
        button_texts: list[Optional[str]],
        popup_visible: bool = False,
    ) -> None:
        """初始化假页面。"""
        self.button_texts = list(button_texts)
        self.popup_visible = popup_visible
        self.clicks: list[tuple[int, int]] = []
        self.confirm_calls: list[tuple[str, dict[str, Any]]] = []

    def find_text(self, text: str, **kwargs: Any) -> Optional[FakeElement]:
        """按被查询的文本返回假 OCR 结果。"""
        if text == auto_dungeon_daily.EXCHANGE_REWARD_POPUP_TITLE:
            if self.popup_visible:
                return FakeElement(text=text, center=(360, 498))
            return None
        if text == "领取":
            if not self.button_texts:
                return None
            current = self.button_texts.pop(0)
            if current is None:
                return None
            return FakeElement(text=current, center=CHEST_BUTTON_CENTER)
        return None

    def click_safe(self, text: str, **kwargs: Any) -> bool:
        """模拟 find_text_and_click_safe：点击并关掉奖励弹窗。"""
        self.confirm_calls.append((text, kwargs))
        if self.popup_visible:
            self.popup_visible = False
        return True


def _build_manager(monkeypatch, page: FakeChestPage):
    """构造接入了假页面的 DailyCollectManager。"""
    manager = auto_dungeon_daily.DailyCollectManager(
        config_loader=MagicMock(),
        db=MagicMock(),
    )
    monkeypatch.setattr(auto_dungeon_daily, "find_text", page.find_text)
    monkeypatch.setattr(
        auto_dungeon_daily,
        "touch",
        lambda point: page.clicks.append(point),
    )
    monkeypatch.setattr(auto_dungeon_daily, "sleep", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        auto_dungeon_daily,
        "find_text_and_click_safe",
        page.click_safe,
    )
    return manager


# --------------------------------------------------------------------------
# 按钮文字形态：带计数的「领取(N)」才是真正要点的那个
# --------------------------------------------------------------------------


def test_click_chest_button_with_pending_count(monkeypatch) -> None:
    """按钮文字带待领数量（「领取(1)」）时必须能点到 —— 这是原实现漏领的场景。"""
    page = FakeChestPage(["领取(1)"])
    manager = _build_manager(monkeypatch, page)

    element = manager._claim_event_chest_reward()

    assert element is not None
    assert element.text == "领取(1)"
    assert page.clicks == [CHEST_BUTTON_CENTER]


def test_click_chest_button_without_count(monkeypatch) -> None:
    """没有待领数量时按钮是纯「领取」，同样要能点到。"""
    page = FakeChestPage(["领取"])
    manager = _build_manager(monkeypatch, page)

    element = manager._claim_event_chest_reward()

    assert element is not None
    assert element.text == "领取"
    assert page.clicks == [CHEST_BUTTON_CENTER]


def test_never_click_already_claimed(monkeypatch) -> None:
    """按钮显示「已领取」时一下都不能点（子串匹配会命中它）。"""
    page = FakeChestPage(["已领取"])
    manager = _build_manager(monkeypatch, page)

    element = manager._claim_event_chest_reward()

    assert element is not None  # 说明确实识别到了这个按钮
    assert element.text == "已领取"
    assert page.clicks == []


# --------------------------------------------------------------------------
# 渲染时序：按钮慢一拍出现时不能只查一次就放弃
# --------------------------------------------------------------------------


def test_retry_until_button_appears(monkeypatch) -> None:
    """前两次读不到按钮、第三次才出现时，仍然要把它领掉。"""
    page = FakeChestPage([None, None, "领取(1)"])
    manager = _build_manager(monkeypatch, page)

    element = manager._claim_event_chest_reward()

    assert element is not None
    assert page.clicks == [CHEST_BUTTON_CENTER]


def test_give_up_after_max_attempts(monkeypatch) -> None:
    """始终读不到按钮时放弃，并保证一次都没乱点。"""
    page = FakeChestPage([None, None, None, None])
    manager = _build_manager(monkeypatch, page)

    assert manager._claim_event_chest_reward() is False

    assert page.clicks == []


# --------------------------------------------------------------------------
# 奖励弹窗：不关掉会挡住后面的兑换页
# --------------------------------------------------------------------------


def test_reward_popup_dismissed_after_claim(monkeypatch) -> None:
    """领取成功后弹出的「恭喜获得」要被关掉。"""
    page = FakeChestPage(["领取(1)"], popup_visible=True)
    manager = _build_manager(monkeypatch, page)

    manager._claim_event_chest_reward()

    assert page.popup_visible is False
    assert [text for text, _ in page.confirm_calls] == ["确定"]


def test_confirm_uses_exact_match(monkeypatch) -> None:
    """关弹窗用的「确定」必须精确匹配，否则会点中「确定要兑换…」这类长句。"""
    page = FakeChestPage(["领取(1)"], popup_visible=True)
    manager = _build_manager(monkeypatch, page)

    manager._claim_event_chest_reward()

    assert page.confirm_calls
    assert page.confirm_calls[0][1].get("exact") is True


def test_no_popup_means_no_extra_click(monkeypatch) -> None:
    """没有弹窗时不要碰「确定」。"""
    page = FakeChestPage(["领取(1)"], popup_visible=False)
    manager = _build_manager(monkeypatch, page)

    manager._claim_event_chest_reward()

    assert page.confirm_calls == []
