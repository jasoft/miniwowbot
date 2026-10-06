"""根据实时任务页面状态领取任务，并验证大陆切换。"""

from __future__ import annotations

import logging
import time
from typing import Any

from airtest.core.api import sleep, swipe, touch
from state import WorldState
from task_regions import next_region, region_menu_position, task_list_region

logger = logging.getLogger(__name__)


def read_task_screen(state: WorldState) -> list[dict[str, Any]]:
    """获取未使用缓存的当前画面文本。

    Args:
        state: 包含截图和 OCR 服务的运行状态。

    Returns:
        当前画面的 OCR 文本条目。
    """
    return state.ocr.capture_and_get_all_texts(use_cache=False)


def click_text(texts: list[dict[str, Any]], label: str) -> bool:
    """点击当前截图中完全匹配的按钮文字。

    Args:
        texts: 当前截图的 OCR 条目。
        label: 按钮文字。

    Returns:
        找到并点击按钮时返回 True。
    """
    for item in texts:
        if item.get("text", "").strip() == label and item.get("center"):
            touch(tuple(item["center"]))
            sleep(1)
            return True
    return False


def dismiss_task_panel() -> None:
    """点击画面边缘关闭任务弹窗，避免点击放弃任务的红叉。"""
    touch((719, 1))
    sleep(0.5)


def task_detail_title(texts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """识别前景任务详情，排除其背后的清单内容。

    Args:
        texts: 当前截图的 OCR 条目。

    Returns:
        前景详情中的任务标题；没有任务操作按钮时返回 None。
    """
    if not any(
        item.get("text", "").strip() in ("接受任务", "前往", "完成")
        and item.get("center")
        and 820 <= item["center"][1] <= 910
        for item in texts
    ):
        return None
    return next(
        (
            item
            for item in texts
            if item.get("center")
            and 400 <= item["center"][1] <= 460
            and any(name in item.get("text", "") for name in ("支线", "地下城", "主线"))
        ),
        None,
    )


def find_available_task(
    state: WorldState, skipped: set[str] | None = None
) -> dict[str, Any] | None:
    """从列表顶部扫描到末尾，兼顾支线和地下城任务。

    Args:
        state: 当前运行状态。
        skipped: 本轮已确认处于执行中的任务标题。

    Returns:
        可接任务标题的 OCR 条目；完整扫描确认没有任务时返回 None。

    Raises:
        RuntimeError: 清单未打开、OCR 失败或扫描未抵达末尾。
    """
    # 接受任务后清单可能保留上次滚动位置，必须每次从顶部重新检查。
    skipped = skipped or set()
    previous_top: tuple[str, ...] | None = None
    for _ in range(12):
        swipe((360, 420), (360, 860), duration=0.5)
        sleep(0.5)
        texts = read_task_screen(state)
        detail = task_detail_title(texts)
        if detail is not None:
            return detail
        if task_list_region(texts) is None:
            raise RuntimeError("未识别到任务清单标题，不能判定区域任务完成")
        top = tuple(
            item.get("text", "")
            for item in texts
            if item.get("center")
            and 180 <= item["center"][0] <= 600
            and 325 <= item["center"][1] <= 890
        )
        if top == previous_top:
            break
        previous_top = top
    else:
        raise RuntimeError("任务清单未回到顶部，本轮不切区")
    previous: tuple[str, ...] | None = None
    stable_pages = 0
    for _ in range(12):
        texts = read_task_screen(state)
        detail = task_detail_title(texts)
        if detail is not None:
            return detail
        if task_list_region(texts) is None:
            raise RuntimeError("未识别到任务清单标题，不能判定区域任务完成")
        rows = [
            item
            for item in texts
            if item.get("center")
            and 180 <= item["center"][0] <= 600
            and 325 <= item["center"][1] <= 890
        ]
        for category in ("支线", "地下城", "主线"):
            for item in rows:
                text = item.get("text", "")
                if text in skipped:
                    continue
                if f"【{category}】" in text or f"[{category}]" in text:
                    return item
        fingerprint = tuple(item.get("text", "") for item in rows)
        if fingerprint == previous:
            stable_pages += 1
            if stable_pages >= 2:
                return None
        else:
            stable_pages = 0
        previous = fingerprint
        swipe((360, 850), (360, 400), duration=0.5)
        sleep(0.5)
    raise RuntimeError("任务清单扫描未抵达末尾，本轮不切区")


def switch_task_region(state: WorldState, current: str) -> bool:
    """选择下一大陆，并验证任务清单标题确实改变。

    Args:
        state: 当前运行状态。
        current: 已确认清空任务的大陆。

    Returns:
        下一大陆的任务清单已打开时返回 True。
    """
    target = next_region(current)
    if target is None:
        logger.info("区域 %s 没有下一大陆，继续处理已接任务", current)
        return False
    for _ in range(3):
        texts = read_task_screen(state)
        if task_list_region(texts) == target:
            logger.info("区域切换已验证: %s -> %s", current, target)
            return True
        if not click_text(texts, "切换区域"):
            continue
        for _ in range(3):
            position = region_menu_position(read_task_screen(state), target)
            if position is not None:
                touch(position)
                sleep(1)
                break
            sleep(0.5)
        else:
            # 再点同一按钮收起菜单，下一轮从明确的列表状态重试。
            click_text(read_task_screen(state), "切换区域")
            continue
        if task_list_region(read_task_screen(state)) == target:
            logger.info("区域切换已验证: %s -> %s", current, target)
            return True
    logger.warning("切区未验证成功: %s -> %s，将稍后重试", current, target)
    return False


def request_tasks(state: WorldState) -> None:
    """领取本区任务，确认清空后切区并立即领取新区任务。

    Args:
        state: 当前运行状态。
    """
    try:
        skipped: set[str] = set()
        request_el = state.signals.get("request_task_el")
        if not request_el or not request_el.click():
            return
        sleep(1)
        for _ in range(20):
            if state.signals.get("task_complete_pos"):
                return
            texts = read_task_screen(state)
            current = task_list_region(texts)
            if current is None:
                logger.warning("领取入口未打开任务清单，稍后重试")
                return
            candidate = find_available_task(state, skipped)
            if candidate is None:
                if skipped:
                    logger.info("本区仍有已接任务，等待完成后再切区")
                    return
                if switch_task_region(state, current):
                    # 切换成功后留在清单中，直接扫描下一大陆。
                    continue
                return
            touch(tuple(candidate["center"]))
            sleep(1)
            detail = read_task_screen(state)
            if not click_text(detail, "接受任务"):
                # 跳过已接任务，继续查看其他条目；未知弹窗不作为清空证据。
                if not any(item.get("text", "").strip() in ("前往", "完成") for item in detail):
                    logger.warning("未识别到任务操作按钮，保留区域稍后重试")
                    return
                skipped.add(candidate["text"])
                dismiss_task_panel()
            else:
                after_accept = read_task_screen(state)
                if task_detail_title(after_accept) is not None:
                    logger.info("接受任务后详情仍未关闭，等待任务名额或界面恢复")
                    return
                state.last_task_time = time.time()
                logger.info("接受任务已验证: %s", candidate["text"])
            texts = read_task_screen(state)
            if task_list_region(texts) is not None:
                continue
            entry = next(
                (
                    item
                    for item in texts
                    if "领取任务" in item.get("text", "")
                    and item.get("center")
                    and item["center"][0] < 200
                ),
                None,
            )
            if entry is None:
                logger.info("已接受任务，领取入口消失，等待任务完成")
                return
            touch(tuple(entry["center"]))
            sleep(1)
    except Exception:
        logger.exception("领取/切区流程失败，保留区域并稍后重试")
    finally:
        dismiss_task_panel()
        state.signals["request_task_el"] = None
        state.request_retry_after = time.time() + 30
