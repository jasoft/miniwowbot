"""按任务目标和前景详情导航，并确认免费副本已经进入。"""

from __future__ import annotations

import logging
import re
from typing import Any

from airtest.core.api import sleep, touch
from state import WorldState
from task_workflow import read_task_screen

logger = logging.getLogger(__name__)
Texts = list[dict[str, Any]]


def find_label(texts: Texts, label: str, min_y: int, max_y: int) -> dict[str, Any] | None:
    """在指定纵向范围内查找精确文字，排除背景内容。

    Args:
        texts: 当前 OCR 条目。
        label: 完全匹配的文字。
        min_y: 最小纵坐标。
        max_y: 最大纵坐标。

    Returns:
        匹配的文字条目，没有匹配时返回 None。
    """
    return next(
        (
            item
            for item in texts
            if item.get("text", "").strip() == label
            and item.get("center")
            and min_y <= item["center"][1] <= max_y
        ),
        None,
    )


def task_target(texts: Texts) -> str | None:
    """从任务详情的前往或通关描述提取地点名称。

    Args:
        texts: 当前 OCR 条目。

    Returns:
        地点名称；描述不明确时返回 None，避免猜测地图坐标。
    """
    for item in texts:
        center = item.get("center")
        if not center or not 480 <= center[1] <= 650:
            continue
        match = re.search(r"(?:前往|通关)\s*[「『“\"]([^」』”\"]+)[」』”\"]", item.get("text", ""))
        if match:
            return match.group(1).strip()
    return None


def free_entry(texts: Texts) -> tuple[dict[str, Any] | None, int | None]:
    """识别详情底部的免费次数和对应入口。

    Args:
        texts: 当前 OCR 条目。

    Returns:
        免费文字条目及剩余次数；没有识别到次数时返回 None。
    """
    for item in texts:
        center = item.get("center")
        if not center or not (180 <= center[0] <= 550 and 820 <= center[1] <= 1040):
            continue
        match = re.fullmatch(
            r"免费\s*[（(]\s*(\d+)\s*/\s*\d+\s*[）)]", item.get("text", "").strip()
        )
        if match:
            return item, int(match.group(1))
    return None, None


def navigate_to_task(state: WorldState) -> str:
    """按目标名称导航，等待加载并验证副本或野外进入结果。

    Args:
        state: 包含实时 OCR 的运行状态。

    Returns:
        成功时返回空字符串；失败时返回具体阶段或免费次数耗尽原因。
    """
    texts = read_task_screen(state)
    target = task_target(texts)
    button = find_label(texts, "前往", 820, 910)
    if not target or not button:
        return "任务详情未识别到目标地点和前往按钮"
    touch(tuple(button["center"]))
    sleep(1)
    selected = False
    entering = False
    stage = "地图未找到任务目标"
    for _ in range(10):
        texts = read_task_screen(state)
        if find_label(texts, f"地下城-{target}", 150, 350):
            logger.info("已确认进入副本：%s", target)
            return ""
        if entering and find_label(texts, target, 25, 80):
            logger.info("已确认进入区域：%s", target)
            return ""
        title = find_label(texts, target, 230, 320)
        dungeon = title and any("地下城等级" in item.get("text", "") for item in texts)
        if dungeon:
            if not entering:
                stage = f"{target}详情尚未识别到免费次数"
            entry, remaining = free_entry(texts)
            paid = any(
                item.get("center")
                and 220 <= item["center"][0] <= 355
                and 890 <= item["center"][1] <= 950
                and re.fullmatch(r"[-−]\s*\d+", item.get("text", "").strip())
                for item in texts
            )
            if paid and not entering:
                return f"{target}免费次数已耗尽（当前需要消耗门票）"
            if remaining == 0 and not entering:
                return f"{target}免费次数已耗尽"
            if entry and remaining and not entering:
                # 实机确认免费次数文字本身就是可点击的免费入口。
                touch(tuple(entry["center"]))
                entering = True
                stage = f"点击{target}免费入口后尚未确认进入"
        elif not selected:
            location = find_label(texts, target, 330, 1010)
            if location:
                touch(tuple(location["center"]))
                selected = True
                stage = f"地图点击{target}后尚未打开详情"
        elif find_label(texts, target, 430, 500) and not entering:
            # 野外详情通过声望商店区分，按实际前往按钮进入。
            if any("声望商店" in item.get("text", "") for item in texts):
                field_button = find_label(texts, "前往", 650, 1040)
                if field_button:
                    touch(tuple(field_button["center"]))
                    entering = True
                    stage = f"点击{target}前往后尚未确认进入"
        sleep(1)
    return stage
