"""GameActions.find 的 ``exact``（完全匹配）语义回归测试。

背景（2026-11-15 真机故障）：``exact`` 参数只存在于 vibe-ocr 的**本地源码**，
PyPI 上的同版本号 0.1.6 并不包含它。项目 ``pyproject.toml`` 依赖
``vibe-ocr>=0.1.5``，一旦 ``uv sync`` 装回 PyPI 版本：

* ``find_text(exact=False)`` 直接抛
  ``TypeError: GameActions.find() got an unexpected keyword argument 'exact'``，
  「领取主题奖励」整步中断，上缴/宝箱/奖券兑换全线跳过；
* ``find_text_and_click_safe(exact=True)`` 抛出的同一个 TypeError 被
  ``except Exception`` 吞成 ``False``，表现为日志里一行
  ``首个领取按钮点击结果=False``，静默失效、当天无人发现。

因此本文件锁两条不变量：
1. ``find(exact=True)`` 必须自己实现完全匹配（不依赖上游版本）；
2. 安全封装遇到编程错误必须留痕，不能无声降级。
"""

# ruff: noqa: E402

import logging
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from game_actions import GameActions  # noqa: E402


class _FakeOcrHelper:
    """返回固定 OCR 结果的假 helper。"""

    def __init__(self, items):
        """记录待返回的 OCR 结果。

        Args:
            items: ``capture_and_get_all_texts`` 要返回的元素字典列表。
        """
        self.items = items
        self.calls = []

    def capture_and_get_all_texts(self, use_cache=True, regions=None):
        """模拟 OCR 读取当前画面。

        Args:
            use_cache: 是否复用缓存（仅记录）。
            regions: 限定区域（仅记录）。

        Returns:
            list[dict]: 预设的 OCR 结果。
        """
        self.calls.append({"use_cache": use_cache, "regions": regions})
        return list(self.items)


# 兑换确认框的真实形态：提示语与按钮都在同一区域，且提示语以「确定」开头。
# 子串匹配会先命中提示语 (359, 462)，正确落点是按钮 (359, 830)。
EXCHANGE_SCREEN = [
    {"text": "确定要兑换这件商品吗？", "center": (359, 462), "confidence": 0.98},
    {"text": "确定", "center": (359, 830), "confidence": 0.95},
]


def _make_actions(items):
    """构造一个带假 OCR 的 GameActions。

    Args:
        items: 假 OCR 结果列表。

    Returns:
        tuple[GameActions, _FakeOcrHelper]: 被测对象与其 helper。
    """
    helper = _FakeOcrHelper(items)
    return GameActions(helper), helper


def test_exact_hits_equal_text_not_substring():
    """exact=True 时必须跳过以目标文字开头的提示语，命中完全相等的那一个。

    改前：``find`` 不认识 ``exact``，抛 TypeError。
    """
    actions, _ = _make_actions(EXCHANGE_SCREEN)

    element = actions.find("确定", timeout=0, use_cache=False, exact=True)

    assert element, "exact 查找应当命中完全相等的「确定」"
    assert element.center == (359, 830), "必须点按钮，不能点到提示语 (359, 462)"
    assert element.text == "确定"


def test_without_exact_substring_still_wins():
    """exact=False（默认）保持子串匹配，避免误改既有语义。"""
    actions, _ = _make_actions(EXCHANGE_SCREEN)

    element = actions.find("确定", timeout=0, use_cache=False)

    assert element.center == (359, 462), "子串匹配本就先命中提示语，这是父类既有行为"


def test_exact_tolerates_surrounding_whitespace():
    """OCR 常在文字两侧带空白，exact 应按去掉空白后的内容比较。"""
    actions, _ = _make_actions([{"text": " 领取 ", "center": (579, 799), "confidence": 0.9}])

    element = actions.find("领取", timeout=0, use_cache=False, exact=True)

    assert element.center == (579, 799)


def test_exact_not_found_returns_empty_and_can_raise():
    """exact 未命中时返回空元素；raise_exception=True 时抛 TimeoutError。"""
    actions, _ = _make_actions([{"text": "已领取", "center": (1, 1), "confidence": 0.9}])

    assert not actions.find("领取", timeout=0, use_cache=False, exact=True)

    with pytest.raises(TimeoutError):
        actions.find("领取", timeout=0, use_cache=False, exact=True, raise_exception=True)


def test_find_text_accepts_exact_kwarg():
    """``find_text`` 转发 ``exact`` 不能报错（2026-11-15 崩掉的那条路径）。

    ``_claim_event_chest_reward`` 用 ``find_text("领取", exact=False, ...)``。
    改前父类 ``find`` 不接受 ``exact``，这里必抛 TypeError。
    """
    actions, _ = _make_actions([{"text": "领取(1)", "center": (549, 929), "confidence": 0.92}])

    element = actions.find_text(
        "领取", regions=[6], use_cache=False, timeout=0, exact=False, raise_exception=False
    )

    assert element, "子串匹配应命中「领取(1)」"
    assert element.center == (549, 929)


def test_safe_wrapper_clicks_exact_element():
    """``find_text_and_click_safe(exact=True)`` 必须真的点击，而不是静默返回 False。

    改前：TypeError 被 ``except Exception`` 吞掉 → 返回 False，「领取」从未被点。
    """
    actions, _ = _make_actions(EXCHANGE_SCREEN)
    clicked = []
    actions.touch = lambda pos: clicked.append(pos)  # type: ignore[assignment]

    result = actions.find_text_and_click_safe(
        "确定", regions=[5], timeout=0, use_cache=False, exact=True
    )

    assert result, "命中时应返回元素而不是 False"
    assert clicked == [(359, 830)], "只点一次，且落在真正的按钮上"


def test_safe_wrapper_logs_exception(caplog):
    """安全封装的异常必须留痕 —— 静默降级正是本次故障潜伏一天的原因。"""
    actions, _ = _make_actions([])

    def _boom(*args, **kwargs):
        raise RuntimeError("模拟查找链路故障")

    actions.find = _boom  # type: ignore[assignment]

    with caplog.at_level(logging.WARNING, logger="bottools.game_actions"):
        result = actions.find_text_and_click_safe("领取", default_return="fallback")

    assert result == "fallback"
    assert (
        "find_text_and_click_safe" in caplog.text
    ), "异常被吞掉时必须留下 WARNING，否则线上只能看到「点击结果=False」"
