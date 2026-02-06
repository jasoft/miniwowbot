"""Action handlers for the levelup behavior tree."""

from __future__ import annotations

import logging
import os
import time

import requests
from airtest.core.api import exists, sleep, snapshot, swipe, touch

from color_helper import ColorHelper
from config import BARK_URL
from state import WorldState

logger = logging.getLogger(__name__)


def send_notification(title: str, content: str) -> None:
    """Send a Bark notification.

    Args:
        title: Notification title.
        content: Notification content.
    """
    try:
        requests.get(f"{BARK_URL}/{title}/{content}", timeout=5)
    except Exception as exc:
        logger.error("Bark notification failed: %s", exc)


def should_preempt(state: WorldState) -> bool:
    """Check whether current action should be preempted.

    Args:
        state: Shared world state.

    Returns:
        True if a high-priority task completion is detected.
    """
    return state.signals.get("task_complete_pos") is not None


def clear_signal(state: WorldState, key: str) -> None:
    """Clear a signal value.

    Args:
        state: Shared world state.
        key: Signal key to clear.
    """
    state.signals[key] = None


def action_task_completion(state: WorldState) -> None:
    """Handle task completion flow.

    Args:
        state: Shared world state.
    """
    pos = state.signals.get("task_complete_pos")
    if not pos:
        return

    touch(pos)
    logger.info("Task completion icon tapped: %s", pos)

    state.last_task_time = time.time()
    sleep(0.5)
    touch((363, 867))
    logger.info("Task completed")

    sleep(0.5)
    touch((363, 867))
    logger.info("Next task accepted")
    sleep(2)

    clear_signal(state, "task_complete_pos")


def action_request_task(state: WorldState) -> None:
    """Handle task request flow.

    Args:
        state: Shared world state.
    """
    request_el = state.signals.get("request_task_el")
    if not request_el:
        return

    request_el.click()
    sleep(1.5)

    tasks_available = False
    for _ in range(5):
        if should_preempt(state):
            return
        if state.actions.find_all(use_cache=False).contains("支线").first().click():
            sleep(1)
            touch((358, 865))
            tasks_available = True
        else:
            swipe((360, 900), (360, 300))

    if not tasks_available:
        logger.warning("No side tasks found, switching area")
        switch_el = state.actions.find("切换区域")
        if switch_el:
            switch_el.click()
        else:
            logger.warning("Area switch element not found")
            return

        temp_path = os.path.join(state.ocr.temp_dir, "task_request.png")
        snapshot(filename=temp_path)

        ocr_results = state.ocr.get_all_texts_from_image(temp_path)
        green_pos = ColorHelper.find_green_text(temp_path, ocr_results)

        if green_pos:
            logger.info("Current area (green text) detected: %s", green_pos)
            next_area_pos = (green_pos[0], green_pos[1] + 50)
            logger.info("Tap next area: %s", next_area_pos)
            touch(next_area_pos)
            sleep(1)
        else:
            logger.warning("Green text not found, manual selection needed")
            send_notification("Dungeon Helper - Error", "Green text not found")

        if os.path.exists(temp_path):
            os.remove(temp_path)

    back_to_main(state)
    clear_signal(state, "request_task_el")


def action_combat(state: WorldState) -> None:
    """Execute combat actions.

    Args:
        state: Shared world state.
    """
    if not state.signals.get("in_combat"):
        return
    for i in range(5):
        touch((105 + i * 130, 560))


def action_dungeon_transition(state: WorldState) -> None:
    """Advance to the next dungeon or area.

    Args:
        state: Shared world state.
    """
    logger.info("Advancing dungeon/area")
    touch((160, 112))
    sleep(1)
    goto_next_place(state)
    clear_signal(state, "xp_full")


def action_timeout_recovery(state: WorldState) -> None:
    """Recover from task timeout.

    Args:
        state: Shared world state.
    """
    logger.warning("Task timeout, forcing navigation recovery")

    back_to_main(state)
    touch((65, 265))
    goto_next_place(state)
    state.last_task_time = time.time()


def action_equip_item(state: WorldState) -> None:
    """Equip items when available.

    Args:
        state: Shared world state.
    """
    equip_el = state.signals.get("equip_el")
    if not equip_el:
        return
    equip_el.click()
    clear_signal(state, "equip_el")


def goto_next_place(state: WorldState) -> None:
    """Navigate to the next place.

    Args:
        state: Shared world state.
    """
    try:
        if not state.actions.find_all(use_cache=False).equals("前往").first().click():
            return

        sleep(0.5)
        for _ in range(5):
            if should_preempt(state):
                return
            arrow = exists(state.templates["arrow"])
            if not arrow:
                continue
            touch((arrow[0], arrow[1] + 100))
            sleep(0.5)
            if state.actions.find("声望商店"):
                touch((355, 780))
                sleep(30)
            elif state.actions.find("免费", use_cache=False).click():
                logger.info("Free dungeon detected, entering")
                sleep(3)
                sell_trash(state)
                touch((357, 1209))
            else:
                state.failed_in_dungeon = True
                fail_msg = "Free dungeon button not found"
                logger.warning(fail_msg)
                send_notification("Dungeon Helper - Error", fail_msg)
                back_to_main(state)
            return
    except Exception as exc:
        logger.error("Navigation failed: %s", exc)
        back_to_main(state)


def sell_trash(state: WorldState) -> None:
    """Sell trash items in the dungeon UI.

    Args:
        state: Shared world state.
    """
    touch((226, 1213))
    sleep(0.5)
    touch((446, 1108))
    sleep(0.5)
    touch((469, 954))
    back_to_main(state)


def back_to_main(state: WorldState, taps: int = 5) -> None:
    """Return to the main screen by tapping back.

    Args:
        state: Shared world state.
        taps: Number of back taps.
    """
    for _ in range(taps):
        touch((719, 1))
