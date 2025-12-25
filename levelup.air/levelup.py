# -*- encoding=utf8 -*-
"""
LevelUp 重构版：生产者-消费者架构
1. Producer: 并发检测屏幕（OCR/Template/Status）。
2. PriorityQueue: 事件分发中心，按优先级排序。
3. Consumer: 顺序动作执行，互不干扰。
"""

import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from queue import PriorityQueue
from typing import Any, Callable

import requests
from airtest.core.api import Template, auto_setup, exists, sleep, swipe, touch

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_actions import GameActions
from ocr_helper import OCRHelper

# 配置日志
logger = logging.getLogger("levelup")
logger.setLevel(logging.INFO)

# Bark通知配置
BARK_URL = "https://api.day.app/LkBmavbbbYqtmjDLVvsbMR"
TASK_TIMEOUT = 120


@dataclass(order=True)
class GameEvent:
    """游戏事件，支持优先级排序 (priority 越小优先级越高)"""

    priority: int
    name: str = field(compare=False)
    handler: Callable[[Any], Any] = field(compare=False)
    data: Any = field(default=None, compare=False)
    timestamp: float = field(default_factory=time.time, compare=False)


class LevelUpEngine:
    def __init__(self):
        self.ocr = OCRHelper()
        self.actions = GameActions(self.ocr)
        self.queue = PriorityQueue()
        self.running = True
        self.last_task_time = time.time()
        self.failed_in_dungeon = False

        # 模板定义
        self.templates = {
            "task_complete": Template(r"task_complete.png", resolution=(720, 1280)),
            "in_dungeon": Template(r"in_dungeon.png", resolution=(720, 1280), threshold=0.9),
            "xp_full": Template(r"next_dungeon_xp_full.png", resolution=(720, 1280), threshold=0.9),
            "enter_dungeon": Template(
                r"enter_dungeon.png", resolution=(720, 1280), threshold=0.92, rgb=True
            ),
            "arrow": Template(r"arrow.png", resolution=(720, 1280), rgb=True, threshold=0.4),
            "accept_task": Template(r"accept_task.png", resolution=(720, 1280)),
        }

    def push_event(self, priority: int, name: str, handler: Callable, data: Any = None):
        """推送事件到队列"""
        # 简单去重：如果队列里已经有同名事件，不再重复推送（除非是紧急事件）
        if priority > 10:
            if any(e.name == name for e in list(self.queue.queue)):
                return

        event = GameEvent(priority, name, handler, data)
        logger.debug(f"📤 推送事件: {name} (P{priority})")
        self.queue.put(event)

    def send_notification(self, title, content):
        """发送通知"""
        try:
            requests.get(f"{BARK_URL}/{title}/{content}", timeout=5)
        except Exception as e:
            logger.error(f"Bark通知失败: {e}")

    # --- 生产者 (检测器) ---

    async def producer_loop(self):
        logger.info("🚀 生产者主循环启动")
        while self.running:
            try:
                # 触发一次 OCR 识别，后续并行任务会命中 OCR 缓存
                # 这里不直接存图片，让 GameActions 自己管截图和缓存哈希
                await asyncio.gather(
                    self.detect_workflow(),
                    self.detect_combat(),
                    self.check_status(),
                )
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"生产者循环异常: {e}")
                await asyncio.sleep(1)

    async def detect_workflow(self):
        """流程类检测 (P20-P50)"""
        loop = asyncio.get_event_loop()

        # 1. 任务完成感叹号
        res_complete = await loop.run_in_executor(None, exists, self.templates["task_complete"])
        if res_complete:
            self.push_event(20, "task_completion", self.handle_task_completion, res_complete)

        # 2. OCR 检测：领取任务
        res_task = await loop.run_in_executor(
            None, self.actions.find, "领取任务", 0.5, 0.8, 1, True, [1]
        )
        if res_task:
            self.push_event(40, "request_task", self.handle_request_task, res_task)

        # 3. 经验满切换副本
        res_xp = await loop.run_in_executor(None, exists, self.templates["xp_full"])
        if res_xp:
            self.push_event(45, "next_dungeon", self.handle_dungeon_transition)

        # 4. 穿装备
        res_equip = await loop.run_in_executor(
            None, self.actions.find, "装备", 0.5, 0.8, 1, True, [1]
        )
        if res_equip:
            self.push_event(60, "equip_item", lambda el: el.click(), res_equip)

    async def detect_combat(self):
        """战斗检测 (P80)"""
        loop = asyncio.get_event_loop()
        if await loop.run_in_executor(None, exists, self.templates["in_dungeon"]):
            self.push_event(80, "in_combat", self.handle_combat)

    async def check_status(self):
        """状态检查与补救 (P15, P100)"""
        # 超时补救
        if time.time() - self.last_task_time > TASK_TIMEOUT:
            self.push_event(15, "task_timeout", self.handle_timeout_recovery)

        # 如果队列为空，且没在战斗，也没报错，执行推进逻辑 (P100)
        if self.queue.empty() and not self.failed_in_dungeon:
            self.push_event(100, "idle_push", lambda _: self.handle_dungeon_transition(None))

    # --- 消费者 (动作执行) ---

    async def consumer_loop(self):
        logger.info("🛠️ 消费者动作线程启动")
        while self.running:
            try:
                if not self.queue.empty():
                    event = self.queue.get()
                    if time.time() - event.timestamp > 15:  # 丢弃太久的事件
                        self.queue.task_done()
                        continue

                    logger.info(f"⚡ 执行: {event.name} (P{event.priority})")
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, event.handler, event.data)
                    self.queue.task_done()
            except Exception as e:
                logger.error(f"消费者执行异常: {e}")

            await asyncio.sleep(0.1)

    # --- 处理函数 (Actions) ---

    def handle_task_completion(self, pos):
        touch(pos)
        self.last_task_time = time.time()
        sleep(0.5)
        touch((363, 867))  # 完成任务
        sleep(0.5)
        touch(self.templates["accept_task"])  # 尝试接下一个

    def handle_request_task(self, el):
        if el.center[1] > 290:
            return  # 3个任务不满
        el.click()
        for _ in range(3):
            self.actions.find_all(use_cache=False).contains("支线").each(
                lambda x: touch(x.center) or sleep(0.5) or touch((358, 865))
            )
            swipe((360, 900), (360, 300))
        self.click_back()

    def handle_combat(self, _):
        for i in range(4):
            touch((105 + i * 130, 560))
        for _ in range(5):
            touch((615, 560))
            sleep(0.3)

    def handle_dungeon_transition(self, _):
        logger.info("推进副本/区域流程")
        touch((160, 112))  # 地图
        sleep(1)
        self.goto_next_place()

    def handle_timeout_recovery(self, _):
        logger.warning("任务超时，执行补救强制导航")
        touch((65, 265))  # 第一个任务位
        self.goto_next_place()
        self.last_task_time = time.time()

    def goto_next_place(self):
        try:
            next_btn = self.actions.find_all(use_cache=False).equals("前往").first()
            if next_btn:
                next_btn.click()
            else:
                return

            sleep(0.5)
            for _ in range(5):
                arrow = exists(self.templates["arrow"])
                if arrow:
                    touch((arrow[0], arrow[1] + 100))
                    sleep(0.5)
                    if self.actions.find("声望商店"):
                        touch((355, 780))
                        sleep(30)
                    else:
                        try:
                            touch(self.templates["enter_dungeon"])
                            sleep(3)
                            self.sell_trash()
                            touch((357, 1209))
                        except:
                            self.failed_in_dungeon = True
                            self.send_notification("异常", "副本推进失败")
                    return
        except Exception as e:
            logger.error(f"导航异常: {e}")
            self.click_back()

    def sell_trash(self):
        touch((226, 1213))
        sleep(0.5)
        touch((446, 1108))
        sleep(0.5)
        touch((469, 954))
        self.click_back()

    def click_back(self, n=2):
        for _ in range(n):
            touch((719, 1))


async def main():
    auto_setup(__file__)
    engine = LevelUpEngine()
    await asyncio.gather(engine.producer_loop(), engine.consumer_loop())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
