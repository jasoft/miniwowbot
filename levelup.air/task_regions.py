"""解析任务清单的大陆名称和切区菜单，避免依赖固定行间距。"""

from __future__ import annotations

import re
from typing import Any

# 按游戏切区菜单的顺序排列，区域名称来自实际 OCR 画面。
REGIONS = (
    "东部大陆",
    "虚空领域",
    "冰封大陆",
    "元素之地",
    "迷雾大陆",
    "暗影大陆",
    "军团领域",
    "风暴群岛",
    "亡灵之地",
)


def task_list_region(texts: list[dict[str, Any]]) -> str | None:
    """从任务清单标题读取当前大陆。

    Args:
        texts: 当前截图的 OCR 文本条目。

    Returns:
        已识别的大陆名称；不是任务清单页面时返回 None。
    """
    for item in texts:
        text = item.get("text", "")
        if "任务清单" in text:
            return next((name for name in REGIONS if name in text), None)
    return None


def next_region(current: str) -> str | None:
    """按菜单顺序选择下一大陆，并处理末区边界。

    Args:
        current: 当前大陆名称。

    Returns:
        下一大陆名称；当前未知或已处于末区时返回 None。
    """
    if current not in REGIONS:
        return None
    index = REGIONS.index(current) + 1
    return REGIONS[index] if index < len(REGIONS) else None


def region_menu_position(texts: list[dict[str, Any]], target: str) -> tuple[int, int] | None:
    """定位切区菜单中的目标行，排除背景任务描述。

    Args:
        texts: 切区菜单截图的 OCR 条目。
        target: 目标大陆名称。

    Returns:
        目标菜单文字的中心坐标；未可靠识别时返回 None。
    """
    for item in texts:
        text = item.get("text", "")
        center = item.get("center")
        if (
            target in text
            and re.search(r"LV\s*\.?\s*\d+", text, re.IGNORECASE)
            and center
            and 250 <= center[0] <= 475
            and 450 <= center[1] <= 930
        ):
            return int(center[0]), int(center[1])
    return None
