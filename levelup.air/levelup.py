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
from enum import Enum
from queue import PriorityQueue
from typing import Any, Callable

import requests
from airtest.core.api import Template, auto_setup, exists, sleep, snapshot, swipe, touch
from airtest.core.settings import Settings as ST

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_actions import GameActions
from ocr_helper import OCRHelper
from color_helper import ColorHelper

# 配置 Airtest 图像识别策略：优先使用模板匹配，避免 SIFT/SURF 特征点不足导致的 OpenCV 报错
# "tpl": 模板匹配 (Template Matching)
# "mstpl": 多尺度模板匹配 (Multi-Scale Template Matching)
ST.CVSTRATEGY = ["mstpl", "tpl"]
ST.FIND_TIMEOUT = 10  # type: ignore[assignment]
ST.FIND_TIMEOUT_TMP = 0.1  # type: ignore[assignment]

# 配置日志
logger = logging.getLogger("levelup")
logger.setLevel(logging.INFO)
logging.getLogger("airtest").setLevel(logging.CRITICAL)

# Bark通知配置
BARK_URL = "https://api.day.app/LkBmavbbbYqtmjDLVvsbMR"
TASK_TIMEOUT = 120


class LevelUpState(Enum):
    ROAMING = 0
    COMBAT = 1


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
        self.last_track_time = 0
        self.failed_in_dungeon = False
        self.state = LevelUpState.ROAMING

        # 模板定义
        self.templates = {
            "task_complete": Template(
                r"task_complete.png", resolution=(720, 1280), rgb=True, threshold=0.8
            ),
            "in_dungeon": Template(r"in_dungeon.png", resolution=(720, 1280), threshold=0.9),
            "xp_full": Template(r"next_dungeon_xp_full.png", resolution=(720, 1280), threshold=0.9),
            "arrow": Template(r"arrow.png", resolution=(720, 1280), rgb=True, threshold=0.4),
        }

    def push_event(self, priority: int, name: str, handler: Callable, data: Any = None):
        """推送事件到队列"""
        # 简单去重：如果队列里已经有同名事件，不再重复推送（除非是紧急事件）
        if priority > 10:
            if any(e.name == name for e in list(self.queue.queue)):
                return

        event = GameEvent(priority, name, handler, data)
        logger.info(f"📤 推送事件: {name} (P{priority})")
        self.queue.put(event)
        logger.debug(self.queue)

    def send_notification(self, title, content):
        """发送通知"""
        try:
            requests.get(f"{BARK_URL}/{title}/{content}", timeout=5)
        except Exception as e:
            logger.error(f"Bark通知失败: {e}")

    # --- 生产者 (检测器) ---

    async def workflow_producer_loop(self):
        """慢速循环：处理工作流、状态检查 (OCR, 重逻辑)"""
        logger.info("🐢 慢速生产者循环启动 (Workflow)")
        while self.running:
            try:
                start_time = time.time()
                await asyncio.gather(
                    self.detect_workflow(),
                    self.check_status(),
                )
                cost = time.time() - start_time
                logger.info(f"workflow_producer_loop cycle cost: {cost:.4f}s")
            except Exception as e:
                logger.error(f"Workflow循环异常: {e}")
                await asyncio.sleep(1)

    async def combat_producer_loop(self):
        """快速循环：处理战斗 (Template, 轻逻辑)"""
        logger.info("🐇 快速生产者循环启动 (Combat)")
        while self.running:
            try:
                await self.detect_combat()
                await asyncio.sleep(0.2)  # 战斗检测需要高频
            except Exception as e:
                logger.error(f"Combat循环异常: {e}")
                await asyncio.sleep(1)

    async def detect_workflow(self):
        """流程类检测 (P20-P50) - 全并行检测 + 优先级裁决"""
        loop = asyncio.get_event_loop()
        is_combat = self.state == LevelUpState.COMBAT

        # --- 1. 准备所有检测任务 ---

        # T1: 任务完成 (所有状态)
        future_complete = loop.run_in_executor(None, exists, self.templates["task_complete"])

        # T2: 经验满 (所有状态)
        future_xp = loop.run_in_executor(None, exists, self.templates["xp_full"])

        # T3 & T4: OCR 检测 (仅 ROAMING)
        future_request = None
        future_equip = None

        if not is_combat:
            future_request = loop.run_in_executor(
                None, self.actions.find, "领取任务", 0.5, 0.8, 1, True, [1]
            )
            future_equip = loop.run_in_executor(
                None, self.actions.find, "装备", 0.5, 0.8, 1, True, [1]
            )

        # --- 2. 并行执行所有任务 ---

        # 构造任务列表
        tasks = [future_complete, future_xp]
        if future_request:
            tasks.append(future_request)
        if future_equip:
            tasks.append(future_equip)

        # 等待所有结果
        results = await asyncio.gather(*tasks)

        # --- 3. 解包结果 ---

        res_complete = results[0]
        res_xp = results[1]

        # 根据 task 是否存在来获取结果，注意索引偏移
        idx = 2
        res_request = None
        if future_request:
            res_request = results[idx]
            idx += 1

        res_equip = None
        if future_equip:
            res_equip = results[idx]

        # --- 4. 优先级裁决 (互斥逻辑) ---

        # 优先级 1: 任务完成 (最高)
        if res_complete:
            self.push_event(20, "task_completion", self.handle_task_completion, res_complete)
            return  # ⛔ 互斥：优先交任务

        # 战斗中不处理其他逻辑，专心打怪直到任务完成
        if is_combat:
            return

        # 优先级 2: 领取任务 (仅 ROAMING)
        if res_request and res_request.center[1] <= 290:
            self.push_event(40, "request_task", self.handle_request_task, res_request)
            return  # ⛔ 互斥：优先接任务

        # 优先级 3: 其他非互斥事件 (可以同时发生)

        # 经验满 (切换副本)
        if res_xp:
            self.push_event(45, "next_dungeon", self.handle_dungeon_transition)

        # 穿装备
        if res_equip:
            self.push_event(60, "equip_item", lambda el: el.click(), res_equip)

    async def detect_combat(self):
        """战斗检测 (P80) - 负责更新战斗状态"""
        loop = asyncio.get_event_loop()
        res_combat = await loop.run_in_executor(None, exists, self.templates["in_dungeon"])

        if res_combat:
            self.state = LevelUpState.COMBAT
            self.push_event(80, "in_combat", self.handle_combat)

        else:
            self.state = LevelUpState.ROAMING

    async def check_status(self):
        """状态检查与补救 (P15, P100)"""
        # 战斗中不计算超时，重置计时器
        if self.state == LevelUpState.COMBAT:
            self.last_task_time = time.time()
            return

        # 超时补救 (仅在 ROAMING 状态下生效)
        if time.time() - self.last_task_time > TASK_TIMEOUT:
            self.push_event(15, "task_timeout", self.handle_timeout_recovery)

        # 如果队列为空，且没在战斗，也没报错，执行推进逻辑 (P100)
        # if self.queue.empty() and not self.failed_in_dungeon:
        #     self.push_event(100, "idle_push", lambda _: self.handle_dungeon_transition(None))

    # --- 消费者 (动作执行) ---

    async def consumer_loop(self):
        logger.info("🛠️ 消费者动作线程启动")
        while self.running:
            try:
                if not self.queue.empty():
                    logger.debug(self.queue)
                    event = self.queue.get()

                    logger.info(f"⚡ 处理事件: {event.name} (P{event.priority})")
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, event.handler, event.data)
                    self.queue.task_done()
            except Exception as e:
                logger.error(f"消费者执行异常: {e}")

            await asyncio.sleep(0.1)

    # --- 处理函数 (Actions) ---

    def handle_task_completion(self, pos):
        """处理任务完成事件"""
        touch(pos)
        self.last_task_time = time.time()
        sleep(0.5)
        touch((363, 867))  # 完成任务
        sleep(0.5)
        touch((363, 867))  # 接下一个

    def handle_request_task(self, el):
        el.click()
        sleep(1.5)

        # 1. 检查是否有区域选择弹窗 (绿色文字指示当前等级)
        temp_path = os.path.join(self.ocr.temp_dir, "task_request.png")
        snapshot(filename=temp_path)
        
        ocr_results = self.ocr.get_all_texts_from_image(temp_path)
        green_pos = ColorHelper.find_green_text(temp_path, ocr_results)
        
        if green_pos:
            logger.info(f"🟢 找到当前区域(绿色文字): {green_pos}")
            # 点击下一个区域 (y + 50 像素偏移，约一个条目高度)
            next_area_pos = (green_pos[0], green_pos[1] + 50)
            logger.info(f"👆 点击下一个区域: {next_area_pos}")
            touch(next_area_pos)
            sleep(1)
            
            # 尝试点击确认按钮
            confirm_btn = self.actions.find("切换区域", use_cache=False)
            if confirm_btn:
                confirm_btn.click()
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return

        if os.path.exists(temp_path):
            os.remove(temp_path)

        # 2. 原有逻辑 (寻找支线任务)
        for _ in range(5):
            if self.actions.find_all(use_cache=False).contains("支线").first().click():
                sleep(1)
                touch((358, 865))
            else:
                swipe((360, 900), (360, 300))
        self.click_back()

    def handle_track_task(self, _):
        """点击任务栏，驱动自动寻路或交任务"""
        touch((65, 265))

    def handle_combat(self, _):
        for i in range(5):
            touch((105 + i * 130, 560))

    def handle_dungeon_transition(self, _):
        logger.info("推进副本/区域流程")
        touch((160, 112))  # 主任务的叹号图标
        sleep(1)
        self.goto_next_place()

    def handle_timeout_recovery(self, _):
        logger.warning("任务超时，执行补救强制导航")
        touch((65, 265))  # 第一个任务位
        self.goto_next_place()
        self.last_task_time = time.time()

    def goto_next_place(self):
        try:
            if not self.actions.find_all(use_cache=False).equals("前往").first().click():
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
                    elif self.actions.find("免费", use_cache=False).click():
                        logger.info("检测到免费副本, 正在进入...")
                        sleep(3)
                        self.sell_trash()
                        touch((357, 1209))
                    else:
                        self.failed_in_dungeon = True
                        fail_msg = "❌ 未找到免费按钮，副本难度太大, 无法自动通过"
                        logger.warning(fail_msg)
                        self.send_notification("副本助手 - 错误", fail_msg)
                        self.click_back()
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

    def click_back(self, n=5):
        for _ in range(n):
            touch((719, 1))


async def main():
    auto_setup(__file__)
    engine = LevelUpEngine()
    await asyncio.gather(
        engine.workflow_producer_loop(),
        engine.combat_producer_loop(),
        engine.consumer_loop(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
