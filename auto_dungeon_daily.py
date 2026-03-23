"""auto_dungeon 每日收集模块。

本模块提供每日收集相关的操作管理。
"""

from dataclasses import dataclass
import logging
import os
import re
import uuid
from typing import Any, Optional

import cv2
import numpy as np
from airtest.core.api import snapshot, touch

from auto_dungeon_config import CLICK_INTERVAL
from auto_dungeon_container import get_container
from auto_dungeon_navigation import back_to_main, open_map, save_error_screenshot
from auto_dungeon_notification import send_notification
from auto_dungeon_ui import (
    click_back,
    find_text,
    find_text_and_click,
    find_text_and_click_safe,
    switch_to,
    text_exists,
)
from auto_dungeon_utils import sleep

# 坐标常量
from coordinates import (
    DAILY_REWARD_BOX_OFFSET_Y,
    DAILY_REWARD_CONFIRM,
    DEPLOY_CONFIRM_BUTTON,
    ONE_KEY_DEPLOY,
    ONE_KEY_REWARD,
    QUICK_AFK_COLLECT_BUTTON,
)


FIRE_TOWER_EVENT_NAME = "fire_tower_ticket_exchange"
FIRE_TOWER_PURPLE_ITEM_KEY = "purple_first"
FIRE_TOWER_BLUE_ITEM_KEY = "blue_second"
EXCHANGE_PROGRESS_PATTERN = re.compile(r"(\d+)\s*/\s*(\d+)")


@dataclass(frozen=True)
class EventExchangeItemState:
    """主题兑换项状态。

    Attributes:
        row_index: 列表中的行序号，从 0 开始。
        item_key: 兑换物品标识。
        required_tickets: 兑换所需奖券数量。
        current_tickets: 当前识别到的奖券数量。
        button_center: 对应“兑换”按钮的中心坐标。
        is_affordable_by_color: 价格颜色是否表现为可买状态。
    """

    row_index: int
    item_key: str
    required_tickets: int
    current_tickets: Optional[int]
    button_center: Optional[tuple[int, int]]
    is_affordable_by_color: Optional[bool]


class DailyCollectManager:
    """
    每日收集管理器
    负责处理所有每日收集相关的操作，包括：
    - 每日挂机奖励领取
    - 快速挂机领取
    - 随从派遣
    - 每日免费地下城领取
    """

    def __init__(self, config_loader=None, db=None):
        """初始化每日收集管理器。

        Args:
            config_loader: 配置加载器实例。
            db: DungeonProgressDB 实例。
        """
        self.config_loader = config_loader
        self.db = db
        self.logger = logging.getLogger(__name__)

        # 任务映射：任务名称 -> (方法, 步骤key)
        self.TASK_MAPPING = {
            "领取挂机奖励": (self._collect_idle_rewards, "idle_rewards"),
            "购买商店每日": (self._buy_market_items, "buy_market_items"),
            "随从派遣": (self._handle_retinue_deployment, "retinue_deployment"),
            "每日免费地下城": (self._collect_free_dungeons, "free_dungeons"),
            "开启宝箱": (self._open_chests_wrapper, "open_chests"),
            "世界BOSS": (self._kill_world_boss_wrapper, "world_boss"),
            "领取邮件": (self._receive_mails, "receive_mails"),
            "领取主题奖励": (self._claim_event_rewards, "small_cookie"),
            "领取礼包": (self._collect_gifts, "collect_gifts"),
            # "领取广告奖励": (self._buy_ads_items, "buy_ads_items"),
            "猎魔试炼": (self._demonhunter_exam, "demonhunter_exam"),
        }

    def execute_task(self, task_name: str) -> bool:
        """根据任务名称执行每日任务。

        Args:
            task_name: 任务名称。

        Returns:
            bool: 执行是否成功。
        """
        if task_name not in self.TASK_MAPPING:
            self.logger.warning(f"⚠️ 未知的每日任务: {task_name}")
            return False

        method, step_key = self.TASK_MAPPING[task_name]
        try:
            self.logger.info(f"🚀 执行每日任务: {task_name}")
            return self._run_step(step_key, method)
        except Exception as e:
            self.logger.error(f"❌ 执行每日任务 {task_name} 失败: {e}")
            save_error_screenshot(f"daily_{task_name}")
            return False

    def _open_chests_wrapper(self):
        """宝箱包装器"""
        if self.config_loader and self.config_loader.get_chest_name():
            self._open_chests(self.config_loader.get_chest_name())
        else:
            self.logger.info("ℹ️ 未配置宝箱名称，跳过开启宝箱")

    def _kill_world_boss_wrapper(self):
        """世界BOSS包装器"""
        for _ in range(3):
            self._kill_world_boss()

    @staticmethod
    def _summarize_match_result(result: Optional[dict[str, Any]]) -> str:
        """格式化 OCR/控件查找结果，便于日志输出。

        Args:
            result: 查找结果字典。

        Returns:
            适合日志打印的摘要文本。
        """
        if not result:
            return "None"

        center = result.get("center")
        text = result.get("text")
        confidence = result.get("confidence")
        return (
            f"text={text!r}, center={center}, confidence={confidence}"
            if text is not None or confidence is not None
            else f"center={center}"
        )

    def _run_step(self, step_name: str, func, *args, **kwargs) -> bool:
        """执行单个步骤，并按显式结果记录进度。

        Args:
            step_name: 步骤标识。
            func: 需要执行的步骤函数。
            *args: 传递给步骤函数的位置参数。
            **kwargs: 传递给步骤函数的关键字参数。

        Returns:
            bool: 步骤是否成功完成。
        """
        if self.db and self.db.is_daily_step_completed(step_name):
            self.logger.info(f"⏭️ 步骤 {step_name} 已完成，跳过")
            return True

        self.logger.info(f"🧩 开始执行步骤: {step_name}")
        raw_result = func(*args, **kwargs)
        step_succeeded = raw_result is not False
        self.logger.info(
            "🧾 步骤 %s 执行结束，返回值=%r，判定成功=%s",
            step_name,
            raw_result,
            step_succeeded,
        )

        if not step_succeeded:
            self.logger.warning(f"⚠️ 步骤 {step_name} 未完成，本次不写入完成记录")
            return False

        if self.db:
            self.db.mark_daily_step_completed(step_name)
            self.logger.info(f"💾 已记录每日步骤完成: {step_name}")

        return True

    def _parse_exchange_progress(self, text: str) -> tuple[Optional[int], Optional[int]]:
        """解析奖券进度文本。

        Args:
            text: OCR 识别出的文本，例如 `40/40`。

        Returns:
            tuple[Optional[int], Optional[int]]: 当前奖券和所需奖券；
            无法解析时返回 `(None, None)`。
        """
        normalized_text = (
            text.replace("O", "0").replace("o", "0").replace(" ", "").strip()
        )
        match = EXCHANGE_PROGRESS_PATTERN.search(normalized_text)
        if match is None:
            return None, None
        return int(match.group(1)), int(match.group(2))

    @staticmethod
    def _extract_bbox(item: dict[str, Any]) -> Optional[list[list[int]]]:
        """提取 OCR 项的边界框。

        Args:
            item: OCR 结果项。

        Returns:
            Optional[list[list[int]]]: 标准化后的四点边界框。
        """
        bbox = item.get("bbox") or item.get("poly")
        if not bbox:
            return None
        return [[int(point[0]), int(point[1])] for point in bbox]

    def _capture_exchange_screen(self) -> tuple[list[dict[str, Any]], Optional[str]]:
        """截取当前兑换页并返回 OCR 结果。

        Returns:
            tuple[list[dict[str, Any]], Optional[str]]: OCR 结果及截图路径。
        """
        container = get_container()
        ocr_helper = container.ocr_helper
        if ocr_helper is None:
            self.logger.warning("⚠️ OCRHelper 未初始化，无法读取兑换页状态")
            return [], None

        screenshot_path = os.path.join(
            ocr_helper.temp_dir,
            f"exchange_{uuid.uuid4().hex[:8]}.png",
        )
        snapshot_func = ocr_helper.snapshot_func or snapshot
        snapshot_func(filename=screenshot_path)
        return ocr_helper.find_all_matching_texts(screenshot_path, "", confidence_threshold=0.0), screenshot_path

    def _cleanup_temp_screenshot(self, screenshot_path: Optional[str]) -> None:
        """清理临时截图文件。

        Args:
            screenshot_path: 临时截图路径。

        Returns:
            None.
        """
        if screenshot_path and os.path.exists(screenshot_path):
            os.remove(screenshot_path)

    def _match_exchange_button(
        self,
        progress_item: dict[str, Any],
        button_items: list[dict[str, Any]],
    ) -> Optional[tuple[int, int]]:
        """按行匹配兑换按钮。

        Args:
            progress_item: 进度文本 OCR 项。
            button_items: 全部“兑换”按钮 OCR 项。

        Returns:
            Optional[tuple[int, int]]: 匹配到的按钮中心坐标。
        """
        progress_center = progress_item.get("center")
        if not progress_center:
            return None

        matched_buttons = [
            button
            for button in button_items
            if button.get("center")
            and button["center"][0] > progress_center[0]
            and abs(button["center"][1] - progress_center[1]) <= 90
        ]
        if not matched_buttons:
            return None

        matched_buttons.sort(
            key=lambda button: (
                abs(button["center"][1] - progress_center[1]),
                button["center"][0] - progress_center[0],
            )
        )
        return tuple(matched_buttons[0]["center"])

    def _detect_exchange_affordable_by_color(
        self,
        screenshot_path: Optional[str],
        progress_item: dict[str, Any],
    ) -> Optional[bool]:
        """根据价格颜色辅助判断是否可兑换。

        Args:
            screenshot_path: 当前截图路径。
            progress_item: 奖券进度 OCR 项。

        Returns:
            Optional[bool]: `True` 表示更像白色可买态，`False` 表示更像红色不可买态，
            `None` 表示无法判断。
        """
        if screenshot_path is None:
            return None

        bbox = self._extract_bbox(progress_item)
        if bbox is None:
            return None

        image = cv2.imread(screenshot_path)
        if image is None:
            return None

        xs = [point[0] for point in bbox]
        ys = [point[1] for point in bbox]
        x_min, x_max = max(0, min(xs)), min(image.shape[1], max(xs))
        y_min, y_max = max(0, min(ys)), min(image.shape[0], max(ys))
        if x_max <= x_min or y_max <= y_min:
            return None

        region = image[y_min:y_max, x_min:x_max]
        if region.size == 0:
            return None

        hsv_region = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        white_mask = cv2.inRange(
            hsv_region,
            np.array([0, 0, 180]),
            np.array([180, 70, 255]),
        )
        red_mask_1 = cv2.inRange(
            hsv_region,
            np.array([0, 70, 80]),
            np.array([10, 255, 255]),
        )
        red_mask_2 = cv2.inRange(
            hsv_region,
            np.array([160, 70, 80]),
            np.array([180, 255, 255]),
        )
        red_mask = cv2.bitwise_or(red_mask_1, red_mask_2)

        total_pixels = region.shape[0] * region.shape[1]
        if total_pixels == 0:
            return None

        white_ratio = float(cv2.countNonZero(white_mask)) / float(total_pixels)
        red_ratio = float(cv2.countNonZero(red_mask)) / float(total_pixels)

        if white_ratio >= 0.08 and white_ratio > red_ratio:
            return True
        if red_ratio >= 0.08 and red_ratio > white_ratio:
            return False
        return None

    def _load_fire_tower_exchange_states(self) -> list[EventExchangeItemState]:
        """读取火焰塔兑换页前两个目标物品状态。

        Returns:
            list[EventExchangeItemState]: 目标物品状态列表。
        """
        ocr_results, screenshot_path = self._capture_exchange_screen()
        try:
            button_items = [
                item
                for item in ocr_results
                if item.get("text") == "兑换" and item.get("center")
            ]
            progress_items = []
            for item in ocr_results:
                current_tickets, required_tickets = self._parse_exchange_progress(
                    item.get("text", "")
                )
                if required_tickets not in {40, 30}:
                    continue
                if item.get("center") is None:
                    continue
                progress_items.append(
                    {
                        "ocr": item,
                        "current_tickets": current_tickets,
                        "required_tickets": required_tickets,
                    }
                )

            progress_items.sort(
                key=lambda item: (
                    item["ocr"]["center"][1],
                    item["ocr"]["center"][0],
                )
            )

            target_configs = [
                (FIRE_TOWER_PURPLE_ITEM_KEY, 40),
                (FIRE_TOWER_BLUE_ITEM_KEY, 30),
            ]
            states = []
            used_indexes: set[int] = set()
            for row_index, (item_key, required_tickets) in enumerate(target_configs):
                matched_index = next(
                    (
                        index
                        for index, item in enumerate(progress_items)
                        if index not in used_indexes
                        and item["required_tickets"] == required_tickets
                    ),
                    None,
                )
                if matched_index is None:
                    continue

                used_indexes.add(matched_index)
                matched_item = progress_items[matched_index]
                states.append(
                    EventExchangeItemState(
                        row_index=row_index,
                        item_key=item_key,
                        required_tickets=required_tickets,
                        current_tickets=matched_item["current_tickets"],
                        button_center=self._match_exchange_button(
                            matched_item["ocr"],
                            button_items,
                        ),
                        is_affordable_by_color=self._detect_exchange_affordable_by_color(
                            screenshot_path,
                            matched_item["ocr"],
                        ),
                    )
                )

            return states
        finally:
            self._cleanup_temp_screenshot(screenshot_path)

    def _can_redeem_fire_tower_item(self, item_state: EventExchangeItemState) -> bool:
        """判断目标物品当前是否可兑换。

        Args:
            item_state: 兑换项状态。

        Returns:
            bool: 当前是否满足兑换条件。
        """
        if item_state.button_center is None:
            return False
        if item_state.current_tickets is not None:
            return item_state.current_tickets >= item_state.required_tickets
        return item_state.is_affordable_by_color is True

    def _attempt_fire_tower_item_exchange(
        self,
        item_state: EventExchangeItemState,
    ) -> bool:
        """尝试兑换指定物品。

        Args:
            item_state: 兑换项状态。

        Returns:
            bool: 是否完成点击并确认。
        """
        if item_state.button_center is None:
            self.logger.warning("⚠️ 兑换项 %s 缺少按钮坐标，跳过", item_state.item_key)
            return False

        touch(item_state.button_center)
        sleep(CLICK_INTERVAL)
        confirmed = bool(
            find_text_and_click_safe(
                "确定",
                regions=[5],
                timeout=3,
                use_cache=False,
            )
        )
        if not confirmed:
            self.logger.warning("⚠️ 兑换项 %s 未出现确认按钮", item_state.item_key)
            return False

        sleep(CLICK_INTERVAL)
        return True

    def _redeem_fire_tower_ticket_items(self) -> bool:
        """按顺序兑换火焰塔前两个奖券物品。

        Returns:
            bool: 本次是否至少成功兑换一个目标物品。
        """
        cycle_id = self.db.get_event_cycle_id() if self.db else None
        redeemed_any = False
        states = {
            state.item_key: state
            for state in self._load_fire_tower_exchange_states()
        }

        purple_completed = bool(
            self.db
            and self.db.is_event_item_completed(
                FIRE_TOWER_EVENT_NAME,
                FIRE_TOWER_PURPLE_ITEM_KEY,
                cycle_id=cycle_id,
            )
        )
        if not purple_completed:
            purple_state = states.get(FIRE_TOWER_PURPLE_ITEM_KEY)
            if purple_state is None or not self._can_redeem_fire_tower_item(purple_state):
                self.logger.info("ℹ️ 火焰塔紫色物品本次不可兑换，停止后续兑换")
                return False
            if not self._attempt_fire_tower_item_exchange(purple_state):
                return False
            if self.db:
                self.db.mark_event_item_completed(
                    FIRE_TOWER_EVENT_NAME,
                    FIRE_TOWER_PURPLE_ITEM_KEY,
                    cycle_id=cycle_id,
                )
            redeemed_any = True
            states = {
                state.item_key: state
                for state in self._load_fire_tower_exchange_states()
            }

        blue_completed = bool(
            self.db
            and self.db.is_event_item_completed(
                FIRE_TOWER_EVENT_NAME,
                FIRE_TOWER_BLUE_ITEM_KEY,
                cycle_id=cycle_id,
            )
        )
        if blue_completed:
            return redeemed_any

        blue_state = states.get(FIRE_TOWER_BLUE_ITEM_KEY)
        if blue_state is None or not self._can_redeem_fire_tower_item(blue_state):
            self.logger.info("ℹ️ 火焰塔蓝色物品本次不可兑换")
            return redeemed_any
        if not self._attempt_fire_tower_item_exchange(blue_state):
            return redeemed_any

        if self.db:
            self.db.mark_event_item_completed(
                FIRE_TOWER_EVENT_NAME,
                FIRE_TOWER_BLUE_ITEM_KEY,
                cycle_id=cycle_id,
            )
        return True

    def collect_daily_rewards(self):
        """执行所有每日收集操作。

        Returns:
            bool: 所有步骤是否全部完成。
        """
        self.logger.info("=" * 60)
        self.logger.info("🎁 开始执行每日收集操作")
        self.logger.info("=" * 60)

        all_steps_completed = True

        try:
            # 1. 领取每日挂机奖励
            all_steps_completed &= self._run_step(
                "idle_rewards",
                self._collect_idle_rewards,
            )

            # 2. 购买商店每日
            all_steps_completed &= self._run_step(
                "buy_market_items",
                self._buy_market_items,
            )

            # 3. 执行随从派遣
            all_steps_completed &= self._run_step(
                "retinue_deployment",
                self._handle_retinue_deployment,
            )

            # 4. 领取每日免费地下城
            all_steps_completed &= self._run_step(
                "free_dungeons",
                self._collect_free_dungeons,
            )

            # 5. 开启宝箱（如果配置了宝箱名称）
            if self.config_loader and self.config_loader.get_chest_name():
                all_steps_completed &= self._run_step(
                    "open_chests",
                    self._open_chests,
                    self.config_loader.get_chest_name(),
                )

            # 6. 打三次世界 boss
            def kill_boss_loop():
                for _ in range(3):
                    self._kill_world_boss()

            all_steps_completed &= self._run_step("world_boss", kill_boss_loop)

            # 7. 领取邮件
            all_steps_completed &= self._run_step("receive_mails", self._receive_mails)

            # 8. 领取各种主题奖励
            all_steps_completed &= self._run_step(
                "small_cookie",
                self._claim_event_rewards,
            )

            # 9. 领取礼包
            all_steps_completed &= self._run_step("collect_gifts", self._collect_gifts)

            # 10. 领取广告奖励
            all_steps_completed &= self._run_step(
                "buy_ads_items",
                self._buy_ads_items,
            )

            # 11. 猎魔试炼
            all_steps_completed &= self._run_step(
                "demonhunter_exam",
                self._demonhunter_exam,
            )

            self.logger.info("=" * 60)
            if all_steps_completed:
                self.logger.info("✅ 每日收集操作全部完成")
            else:
                self.logger.warning("⚠️ 每日收集存在未完成步骤，等待下次继续执行")
            self.logger.info("=" * 60)
            return all_steps_completed

        except Exception as e:
            self.logger.error(f"❌ 每日收集操作失败: {e}")
            raise

    def _collect_gifts(self):
        """领取礼包"""
        self.logger.info("领取礼包")
        back_to_main()
        find_text_and_click("礼包", regions=[3])
        find_text_and_click("旅行日志", regions=[3])
        find_text_and_click("领取奖励", regions=[8])
        back_to_main()

    def _demonhunter_exam(self):
        """猎魔试炼"""
        self.logger.info("猎魔试炼")
        back_to_main()

        try:
            find_text_and_click("猎魔试炼")
            find_text_and_click("签到")
            find_text_and_click("一键签到")
            back_to_main()
        except Exception as e:
            self.logger.error(f"❌ 猎魔试炼失败: {e}, 活动可能已结束")

    def _claim_event_rewards(self) -> bool:
        """领取各种主题奖励。

        Returns:
            bool: 是否至少成功进入到活动奖励流程。
        """
        event_names = [
            "海盗船",
            "法师塔",
            "野蛮角斗场",
            "火焰塔",
            "狗头人世界",
            "冰霜骑士团",
        ]
        self.logger.info("领取各种主题奖励[%s]", ",".join(event_names))
        back_to_main()
        activity_clicked = find_text_and_click_safe(
            "活动",
            regions=[3],
            timeout=10,
            use_cache=False,
        )
        self.logger.info("🔎 主题奖励: 活动入口点击结果=%s", activity_clicked)
        if not activity_clicked:
            self.logger.warning("⚠️ 主题奖励: 未找到“活动”入口，本次不记录完成")
            back_to_main()
            return False

        res = text_exists(
            event_names,
            regions=[2, 3, 5, 6, 8, 9],
            use_cache=False,
        )
        self.logger.info(
            "🔎 主题奖励: 活动卡片搜索结果=%s",
            self._summarize_match_result(res),
        )
        if not res:
            self.logger.warning("⚠️ 主题奖励: 未识别到目标活动卡片，本次不记录完成")
            back_to_main()
            return False

        touch(res["center"])
        self.logger.info("👆 主题奖励: 已点击活动卡片 center=%s", res["center"])
        sleep(CLICK_INTERVAL)

        top_claim_clicked = find_text_and_click_safe(
            "领取",
            regions=[6],
            timeout=3,
            use_cache=False,
        )
        self.logger.info("🔎 主题奖励: 首个领取按钮点击结果=%s", top_claim_clicked)

        donate_button = find_text(
            "上缴",
            regions=[5],
            raise_exception=False,
            use_cache=False,
            timeout=3,
        )
        self.logger.info(
            "🔎 主题奖励: 上缴按钮搜索结果=%s",
            self._summarize_match_result(donate_button),
        )
        if donate_button:
            self.logger.info("👆 主题奖励: 准备连续点击上缴按钮 5 次")
            for _ in range(5):
                touch(donate_button["center"])
                sleep(CLICK_INTERVAL)
        else:
            self.logger.warning("⚠️ 未找到上缴按钮, fallback to position click")
            for _ in range(5):
                touch((360, 640))
                sleep(CLICK_INTERVAL)

        bottom_claim_clicked = find_text_and_click_safe(
            "领取",
            regions=[9],
            timeout=3,
            use_cache=False,
        )
        self.logger.info("🔎 主题奖励: 底部领取按钮点击结果=%s", bottom_claim_clicked)

        exchange_tab_clicked = find_text_and_click_safe(
            "兑换",
            regions=[9],
            timeout=3,
            use_cache=False,
        )
        self.logger.info("🔎 主题奖励: 兑换标签点击结果=%s", exchange_tab_clicked)

        exchange_success = False
        if exchange_tab_clicked:
            try:
                exchange_success = self._redeem_fire_tower_ticket_items()
                if exchange_success:
                    send_notification("火焰塔奖券兑换成功", "目标物品兑换完成, 请检查")
            except Exception as exc:
                self.logger.error("❌ 主题奖励: 兑换碎片失败: %s", exc)
                send_notification("兑换碎片失败", "兑换失败, 请立即检查")
        else:
            self.logger.info("ℹ️ 主题奖励: 未看到兑换标签，跳过碎片兑换流程")

        back_to_main()
        self.logger.info(
            "🧾 主题奖励流程结果: activity_clicked=%s, card_found=%s, "
            "top_claim_clicked=%s, bottom_claim_clicked=%s, "
            "exchange_tab_clicked=%s, exchange_success=%s",
            activity_clicked,
            bool(res),
            top_claim_clicked,
            bottom_claim_clicked,
            exchange_tab_clicked,
            exchange_success,
        )
        return True

    def _collect_idle_rewards(self):
        """
        领取每日挂机奖励
        """
        self.logger.info("📦 开始领取每日挂机奖励")
        back_to_main()

        try:
            res = switch_to("战斗")
            assert res
            # 点击奖励箱子
            touch((res["center"][0], res["center"][1] + DAILY_REWARD_BOX_OFFSET_Y))
            sleep(CLICK_INTERVAL)
            touch(DAILY_REWARD_CONFIRM)
            sleep(CLICK_INTERVAL)
            find_text_and_click("确定", regions=[5])
            self.logger.info("✅ 每日挂机奖励领取成功")
            # 2. 执行快速挂机领取（如果启用）
            self._collect_quick_afk()

            back_to_main()
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到战斗按钮或点击失败: {e}")
            raise

    def _close_ads(self):
        """
        关闭广告
        """
        self.logger.info("点击广告")
        sleep(40)
        touch((654, 114))  # 右上角的关闭按钮

    def _collect_quick_afk(self):
        """
        执行快速挂机领取
        """
        self.logger.info("⚡ 开始快速挂机领取")
        if find_text_and_click_safe("快速挂机", regions=[4, 5, 6, 7, 8, 9]):
            # 多次点击领取按钮，确保领取所有奖励
            if self.config_loader and self.config_loader.is_quick_afk_enabled():
                for i in range(10):
                    touch(QUICK_AFK_COLLECT_BUTTON)
                    sleep(1)
            else:  # 点击广告
                self.logger.info("广告无法点击跳过")
                # for i in range(3):
                #     touch(QUICK_AFK_COLLECT_BUTTON)
                #     self._close_ads()
                #     sleep(3)

            self.logger.info("✅ 快速挂机领取完成")
        else:
            self.logger.warning("⚠️ 未找到快速挂机按钮")

    def _buy_ads_items(self):
        """
        购买广告物品
        """
        self.logger.info("🛒 购买广告物品")
        back_to_main()
        find_text_and_click("主城", regions=[9])
        find_text_and_click("商店", regions=[4])
        first_item_pos = (111, 395)

        for i in range(3):
            for j in range(5):
                touch((first_item_pos[0] + i * 122, first_item_pos[1]))
                sleep(1)
                if text_exists(["已售罄", "已售馨"], use_cache=False, regions=[5]):
                    self.logger.warning("⚠️ 商品已售罄, 跳过")
                    click_back()
                    break
                touch((362, 783))  # 播放广告按钮
                self._close_ads()
                sleep(3)
                click_back()
                sleep(150)  # 2分半才能再点下一个

        back_to_main()
        self.logger.info("✅ 购买广告商品成功")

    def _handle_retinue_deployment(self):
        """
        处理随从派遣操作
        """
        self.logger.info("👥 开始处理随从派遣")
        back_to_main()

        if find_text_and_click_safe("随从", regions=[7]):
            # 领取派遣奖励
            find_text_and_click("派遣", regions=[8])
            touch(ONE_KEY_REWARD)
            back_to_main()

            # 重新派遣
            find_text_and_click("派遣", regions=[8])
            touch(ONE_KEY_DEPLOY)
            sleep(1)
            touch(DEPLOY_CONFIRM_BUTTON)
            back_to_main()

            self.logger.info("✅ 随从派遣处理完成")

            back_to_main()
        else:
            self.logger.warning("⚠️ 未找到随从按钮，跳过派遣操作")

        # 招募
        find_text_and_click("酒馆", regions=[7])
        res = find_text(
            "招募10次",
            regions=[8, 9],
            occurrence=9999,
            raise_exception=False,
            use_cache=False,
        )
        if res:
            for _ in range(4):
                touch(res["center"])
                sleep(1)
        back_to_main()

        # 符文
        find_text_and_click("符文", regions=[9])
        # 这里可能会没有这个按钮, 不应该抛出exception
        find_text_and_click_safe("抽取十次", regions=[8, 9], use_cache=False)
        back_to_main()

    def _collect_free_dungeons(self):
        """
        领取每日免费地下城（试炼塔）
        """
        self.logger.info("🏰 开始领取每日免费地下城")
        back_to_main()
        open_map()

        if find_text_and_click_safe("试炼塔", regions=[9]):
            self.logger.info("✅ 进入试炼塔")

            # 领取消量奖励
            self._sweep_tower_floor("刻印", regions=[7, 8])
            self._sweep_tower_floor("宝石", regions=[8, 8])
            self._sweep_tower_floor("雕文", regions=[9, 8])

            self.logger.info("✅ 每日免费地下城领取完成")
        else:
            self.logger.warning("⚠️ 未找到试炼塔，跳过免费地下城领取")

        back_to_main()

    def _sweep_tower_floor(self, floor_name: str, regions):
        """
        扫荡试炼塔的特定楼层

        Args:
            floor_name: 楼层名称（刻印、宝石、雕文）
            regions: 搜索区域列表 [楼层区域, 按钮区域]
        """
        if find_text_and_click_safe(floor_name, regions=[regions[0]], use_cache=False):
            try:
                find_text_and_click("扫荡一次", regions=[regions[1]])
                find_text_and_click("确定", regions=[5])
                self.logger.info(f"✅ 完成{floor_name}扫荡")
            except Exception as e:
                self.logger.warning(f"⚠️ 扫荡{floor_name}失败: {e}")
        else:
            self.logger.warning(f"⚠️ 未找到{floor_name}楼层")

    def _kill_world_boss(self):
        """
        杀死世界boss
        """
        self.logger.info("💀 开始杀死世界boss")
        back_to_main()
        open_map()
        try:
            find_text_and_click("切换区域", regions=[8])
            find_text_and_click("东部大陆", regions=[5])
            touch((126, 922))
            sleep(1.5)
            find_text_and_click("协助模式", regions=[8])
            find_text_and_click("创建队伍", regions=[4, 5])
            find_text_and_click("开始", regions=[5])
            find_text_and_click("离开", regions=[5], timeout=20)
            self.logger.info("✅ 杀死世界boss成功")
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到世界boss: {e}")
            back_to_main()

    def _buy_market_items(self):
        """
        购买市场商品
        """
        self.logger.info("🛒 开始购买市场商品")
        back_to_main()
        try:
            find_text_and_click("主城", regions=[9])
            find_text_and_click("商店", regions=[4])
            touch((570, 258))
            sleep(1)
            find_text_and_click("购买", regions=[8])
            back_to_main()
            self.logger.info("✅ 购买市场商品成功")
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到商店: {e}")
            back_to_main()

    def _open_chests(self, chest_name: str):
        """
        开启宝箱
        """
        self.logger.info(f"🎁 开始开启{chest_name}")
        back_to_main()
        try:
            find_text_and_click("主城", regions=[9])
            find_text_and_click("宝库", regions=[9])
            find_text_and_click(chest_name, regions=[4, 5, 6, 7, 8])
            res = find_text("开启10次", regions=[8, 9], use_cache=False, timeout=5)
            if res:
                for _ in range(6):
                    touch(res["center"])
                    sleep(0.2)
                    click_back()
                sleep(0.2)
                touch((359, 879))  # 不满 10 个点击一次最后的打开
            back_to_main()

            find_text_and_click("宝库", regions=[9])
            find_text_and_click(chest_name, regions=[4, 5, 6, 7, 8])
            touch((359, 879))  # 不满 10 个点击一次最后的打开
            back_to_main()

            self.logger.info("✅ 打开宝箱成功")
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到宝箱: {e}")
            back_to_main()

    def _receive_mails(self):
        """
        领取邮件
        """
        self.logger.info("✉️ 信件 开始领取邮件")
        back_to_main()
        try:
            find_text_and_click("主城", regions=[9])
            find_text_and_click("邮箱", regions=[5])
            res = find_text("一键领取", regions=[8, 9], timeout=5)
            if res:
                for _ in range(3):
                    touch(res["center"])
                    sleep(1)
            back_to_main()
            self.logger.info("✅ 领取邮件成功")
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到一键领取: {e}")
            back_to_main()

    # 向后兼容的函数名
    def daily_collect(self):
        """
        向后兼容的函数名
        """
        self.collect_daily_rewards()


def execute_daily_collect() -> bool:
    """执行整套每日收集并按结果决定是否记为完成。

    Returns:
        bool: 本次是否完整完成每日收集。
    """
    from database import DungeonProgressDB

    _container = get_container()
    if _container.config_loader is None:
        raise RuntimeError("配置加载器未初始化，无法执行每日收集")

    config_name = _container.config_loader.get_config_name() or "default"
    logger = logging.getLogger(__name__)

    with DungeonProgressDB(config_name=config_name) as db:
        if db.is_daily_collect_completed():
            logger.info("⏭️ 今日每日收集已完成，跳过重复执行")
            return False

        manager = DailyCollectManager(_container.config_loader, db)
        all_steps_completed = manager.collect_daily_rewards()
        if not all_steps_completed:
            logger.warning("⚠️ 今日每日收集存在未完成步骤，本次不记录总完成")
            return False

        db.mark_daily_collect_completed()
        logger.info("💾 已记录今日每日收集完成")
        return True
