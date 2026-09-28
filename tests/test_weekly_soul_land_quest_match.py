"""weekly_soul_land 秘境任务识别的回归测试。

背景（2026-09-28 真机）：游戏里「秘境」周挑战的**副本名会换** ——
2026-09-22 是「聚魂之地」，2026-09-28 变成「凋零废墟」。旧代码把副本名
硬编码成 ``QUEST_KEYWORD = "聚魂之地"``，换副本后 ``has_quest_in_track()``
与 ``accept_from_list()`` 全部失效，脚本判「任务清单里没有可接的任务」
直接退出（本周 10:00 那轮之后无法再自动跑）。

修复后：清单条目认「【秘境】」前缀（稳定），追踪栏 / 副本标题认「史诗」
（稳定），两者都与具体副本名解耦。本测试锁住这个不变量。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import weekly_soul_land as w

# 任务清单里的 OCR 条目（含本周真实条目「【秘境】凋零废墟-史诗4」）
LIST_ITEMS: List[Dict] = [
    {
        "text": "【秘境】凋零废墟-史诗4",
        "center": (309, 351),
        "box": (200, 335, 430, 372),
        "score": 0.99,
    },
    {
        "text": "【悬赏】亡灵异界",
        "center": (279, 480),
        "box": (200, 465, 360, 500),
        "score": 0.99,
    },
]

# 追踪栏会被 OCR 拆行（实测「通关史诗7-聚魂之地」→「通关史诗7-聚」+「魂之地」）
TRACK_ITEMS: List[Dict] = [
    {"text": "通关史诗4-凋", "center": (59, 98), "box": (20, 90, 100, 108), "score": 0.99},
    {"text": "零废墟", "center": (32, 119), "box": (18, 112, 46, 128), "score": 0.99},
]


def _frame(items: List[Dict]) -> w.Frame:
    """构造一个只带 OCR items 的轻量 Frame（不触发截图 / OCR）。

    Args:
        items: 伪造的 OCR 条目。

    Returns:
        w.Frame: 可直接调用 find / has 的帧对象。
    """
    frame = w.Frame(Path("."))
    frame.items = items
    return frame


def test_list_keyword_matches_renamed_dungeon() -> None:
    """副本改名后（聚魂之地 → 凋零废墟），清单里的秘境条目仍要能被命中。

    改前 ``accept_from_list()`` 用的是硬编码副本名 ``QUEST_KEYWORD``，
    对「【秘境】凋零废墟-史诗4」返回 ``None`` → 本断言失败（AttributeError
    或断言不成立）。
    """
    frame = _frame(LIST_ITEMS)
    hit = frame.find(w.QUEST_LIST_KEYWORD, w.LIST_BOX)
    assert hit is not None, "换了副本名的秘境条目必须能被清单识别词命中"
    assert "凋零废墟" in hit["text"]


def test_track_keyword_matches_renamed_dungeon() -> None:
    """副本改名后，追踪栏（OCR 拆行）仍要能被识别为秘境任务。"""
    frame = _frame(TRACK_ITEMS)
    assert frame.has(w.QUEST_KEYWORD, w.TRACK_BOX), "追踪栏换副本名也要能识别"


def test_keywords_are_dungeon_agnostic() -> None:
    """识别词里不能出现任何具体副本名（否则每周换副本必挂）。"""
    for keyword in (w.QUEST_KEYWORD, w.QUEST_LIST_KEYWORD, *w.TRACK_MARKERS):
        assert "聚魂" not in keyword
        assert "凋零" not in keyword
