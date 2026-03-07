"""auto_dungeon 每日收集模块。

本模块提供每日收集相关的操作管理。
"""

import logging
from typing import Any, Optional

from airtest.core.api import touch

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
            timeout=5,
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
            game_actions = get_container().game_actions
            if game_actions is None:
                self.logger.warning("⚠️ 主题奖励: GameActions 未初始化，跳过兑换动作")
            else:
                try:
                    button = game_actions.find_all().equals("兑换").first()
                    button.click()
                    self.logger.info("👆 主题奖励: 已点击兑换按钮")

                    game_actions.find_all(regions=[5]).equals("确定").first().click()
                    self.logger.info("👆 主题奖励: 已点击兑换确认按钮")
                    if find_text_and_click_safe(
                        "确定",
                        regions=[5],
                        timeout=3,
                        use_cache=False,
                    ):
                        send_notification("兑换紫色碎片成功", "兑换成功, 请立即检查")
                    exchange_success = True
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
