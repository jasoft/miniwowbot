# -*- encoding=utf8 -*-
__author__ = "soj"

import asyncio
import logging
import os
import sys
import time
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

import requests
from airtest.core.api import Template, auto_setup, exists, sleep, swipe, touch
from airtest.core.settings import Settings as ST

# Add parent directory to sys.path to import modules from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_actions import GameActions
from ocr_helper import OCRHelper

airtest_logger = logging.getLogger("airtest")
airtest_logger.setLevel(logging.INFO)

# Initialize OCR Helper
ocr = OCRHelper()
actions = GameActions(ocr)

auto_setup(__file__)

ST.FIND_TIMEOUT = 1.0
ST.FIND_TIMEOUT_TMP = 1.0
ST.THRESHOLD = 0.8

# Bark通知配置
BARK_URL = "https://api.day.app/LkBmavbbbYqtmjDLVvsbMR"  # 请替换为你的Bark推送地址
TASK_TIMEOUT = 300  # 10分钟 = 600秒

TASK_COMPLETE_TEMPLATE = Template(
    r"task_complete.png",
    record_pos=(-0.281, -0.411),
    resolution=(720, 1280),
)
IN_DUNGEON_TEMPLATE = Template(
    r"in_dungeon.png",
    record_pos=(-0.422, -0.406),
    resolution=(720, 1280),
    threshold=0.9,
)
# 经验条已满
NEXT_DUNGEON_TEMPLATE = Template(
    r"next_dungeon_xp_full.png",
    record_pos=(-0.003, -0.306),
    resolution=(720, 1280),
    threshold=0.9,
)
CONFIRM_DUNGEON_TEMPLATE = Template(
    r"confirm_dungeon.png",
    record_pos=(0.001, 0.318),
    resolution=(720, 1280),
)
ARROW_TEMPLATE = Template(
    r"arrow.png",
    resolution=(720, 1280),
    rgb=True,
    threshold=0.4,
)
ENTER_DUNGEON_TEMPLATE = Template(
    r"enter_dungeon.png",
    threshold=0.92,
    rgb=True,
    resolution=(720, 1280),
)


@dataclass
class DetectionJob:
    """封装一次图片检测与后续动作的任务."""

    name: str
    detector: Callable[[], Coroutine]
    handler: Callable[[object], None]


def send_bark_notification(title, content):
    """发送Bark通知"""
    try:
        url = f"{BARK_URL}/{title}/{content}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"Bark通知发送成功: {title}")
        else:
            print(f"Bark通知发送失败: {response.status_code}")
    except Exception as e:
        print(f"Bark通知发送异常: {e}")


def check_task_timeout(last_task_time):
    """检查是否超过10分钟没有完成任务"""
    current_time = time.time()
    elapsed_time = current_time - last_task_time
    if elapsed_time > TASK_TIMEOUT:
        minutes = int(elapsed_time / 60)
        send_bark_notification(
            "魔兽世界挂机异常", f"已经{minutes}分钟没有完成任务，可能遇到问题，请检查！"
        )
        return True
    return False


def click_back(n=3):
    """点击返回按钮若干次"""
    for _ in range(n):
        touch((719, 1))


def sell_trash():
    """售卖背包垃圾物品"""
    touch((226, 1213))
    sleep(0.5)
    touch((446, 1108))
    sleep(0.5)
    touch((469, 954))
    click_back()


async def detect_first_match(
    jobs: Iterable[DetectionJob],
) -> Optional[DetectionJob]:
    """并发检测多张图片, 任意检测成功立即执行对应后续."""
    task_map = {asyncio.create_task(job.detector()): job for job in jobs}
    if not task_map:
        return None

    try:
        while task_map:
            done, pending = await asyncio.wait(task_map.keys(), return_when=asyncio.FIRST_COMPLETED)
            for finished in done:
                job = task_map.pop(finished)
                result = finished.result()
                if result:
                    for other in pending:
                        other.cancel()
                    job.handler(result)
                    return job
            task_map = {task: task_map[task] for task in pending}
    finally:
        for task in task_map:
            task.cancel()
    return None


def request_task_handler(_):
    """处理请求任务."""

    def accept_task(x):
        touch(x.center)
        sleep(0.5)
        touch((358, 865))  # 接受任务

    button = actions.find("领取任务", regions=[1])
    if button:
        button.click()
        for i in range(4):
            actions.find_all().contains("支线").each(lambda x: accept_task(x))
            swipe((360, 900), (360, 300))

        click_back()


def task_completion_handler(first_match):
    """处理任务完成, 补全所有可完成的任务."""
    global last_task_time
    res = first_match
    while res:
        try:
            touch(res)  # 点击完成任务那个感叹号
            last_task_time = time.time()
            print(
                f"任务完成，更新时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_task_time))}"
            )

            touch((363, 867))
            touch(
                Template(
                    r"accept_task.png",
                    record_pos=(-0.004, 0.319),
                    resolution=(720, 1280),
                )  # 接受任务
            )
        except Exception as e:
            print(e)
            pass
        res = exists(TASK_COMPLETE_TEMPLATE)


def skill_handler(_):
    """自动释放技能."""
    # 前面四个技能是有cd的,第五个没cd
    for i in range(4):
        touch((105 + i * 130, 560))
    for _ in range(10):
        touch((615, 560))
        sleep(0.5)


def dungeon_handler(_):
    """自动选择下一个副本或者区域."""
    touch((160, 112))
    try:
        touch(CONFIRM_DUNGEON_TEMPLATE)
        sleep(0.5)

        for i in range(5):
            arrow_pos = exists(ARROW_TEMPLATE)
            if arrow_pos:
                print(arrow_pos)
                touch((arrow_pos[0], arrow_pos[1] + 100))
                sleep(0.5)  # 点击了大箭头

                if actions.find("声望商店"):
                    touch((355, 780))  # 点击前往
                    sleep(30)
                else:  # 副本
                    touch(ENTER_DUNGEON_TEMPLATE)
                    sleep(3)
                    sell_trash()
                    touch((357, 1209))
                return
        raise Exception("error entering dungeon")
    except Exception:
        click_back()
        print("error entering dungeon, back to main world")


def build_template_job(
    name: str,
    template: Template,
    handler: Callable[[object], None],
    delay: float = 0.2,
) -> DetectionJob:
    async def detector():
        await asyncio.sleep(delay)
        # asyncio.to_thread 在低版本缺失, 用 run_in_executor 兼容
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, exists, template)

    return DetectionJob(name=name, detector=detector, handler=handler)


def build_ocr_job(
    name: str,
    text: str,
    regions: list[int],
    handler: Optional[Callable[[object], None]] = None,
    delay: float = 0.2,
) -> DetectionJob:
    async def detector():
        await asyncio.sleep(delay)
        loop = asyncio.get_event_loop()
        # regions=[1] corresponds to top-left area
        # Pass raise_exception=False to avoid crashing on timeout
        res = await loop.run_in_executor(
            None, actions.find, text, 0.5, 0.8, 1, True, regions, False
        )
        if res and res.get("found"):
            return res
        return None

    def default_handler(result):
        if result and result.get("found"):
            print(f"点击 {text}")
            touch(result["center"])

    return DetectionJob(name=name, detector=detector, handler=handler or default_handler)


async def main_loop():
    global last_task_time
    sell_trash()
    while True:
        if check_task_timeout(last_task_time):
            last_task_time = time.time()

        jobs = [
            build_template_job("task_completion", TASK_COMPLETE_TEMPLATE, task_completion_handler),
            build_template_job("in_dungeon", IN_DUNGEON_TEMPLATE, skill_handler),
            build_template_job("next_dungeon", NEXT_DUNGEON_TEMPLATE, dungeon_handler),
            build_ocr_job("equip_item", "装备", [1]),
            build_ocr_job("level_reached", "等级达到", [1], handler=lambda _: None),
            build_ocr_job("request_task", "领取任务", [1], handler=request_task_handler),
        ]
        matched = await detect_first_match(jobs)
        if not matched:
            dungeon_handler(None)
        await asyncio.sleep(0.2)


# 初始化最后一次完成任务的时间
last_task_time = time.time()


if __name__ == "__main__":
    if hasattr(asyncio, "run"):
        asyncio.run(main_loop())
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main_loop())
