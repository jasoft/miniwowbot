"""
auto_dungeon 运行器模块

本模块封装副本自动遍历的核心运行逻辑，使用依赖注入提高可测试性。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from auto_dungeon_config import CLICK_INTERVAL
from auto_dungeon_core import (
    back_to_main,
    find_text_and_click_safe,
    open_map,
    switch_to_zone,
)
from auto_dungeon_daily import DailyCollectManager
from auto_dungeon_device import DeviceManager
from auto_dungeon_state_machine import DungeonStateMachine
from database import DungeonProgressDB

import logging
logger = logging.getLogger(__name__)



@dataclass
class DungeonBotConfig:
    """副本机器人配置"""

    config_path: str = "configs/default.json"
    emulator_name: Optional[str] = None
    env_overrides: List[str] = field(default_factory=list)
    max_iterations: int = 1


class DungeonBot:
    """
    副本机器人主类

    使用依赖注入模式，封装所有核心功能。
    """

    def __init__(
        self,
        config: DungeonBotConfig,
        device_manager: Optional[DeviceManager] = None,
        db: Optional[DungeonProgressDB] = None,
        state_machine: Optional[DungeonStateMachine] = None,
    ):
        """
        初始化副本机器人

        Args:
            config: 机器人配置
            device_manager: 设备管理器（可选，懒加载）
            db: 数据库实例（可选，懒加载）
            state_machine: 状态机实例（可选，懒加载）
        """
        self.config = config
        self.logger = logger
        self._device_manager = device_manager
        self._db = db
        self._state_machine = state_machine

        # 延迟导入的模块
        self._config_loader = None
        self._system_config = None

    @property
    def device_manager(self) -> DeviceManager:
        """获取设备管理器（懒加载）"""
        if self._device_manager is None:
            self._device_manager = DeviceManager()
            self._device_manager.initialize(
                self.config.emulator_name,
                correction_map=self._config_loader,
            )
        return self._device_manager

    @property
    def db(self) -> DungeonProgressDB:
        """获取数据库实例（懒加载）"""
        if self._db is None:
            config_name = self.config_loader.get_config_name() or "default"
            self._db = DungeonProgressDB(config_name=config_name)
        return self._db

    @property
    def config_loader(self):
        """获取配置加载器（懒加载）"""
        if self._config_loader is None:
            from config_loader import load_config
            from system_config_loader import load_system_config

            self._config_loader = load_config(self.config.config_path)
            self._system_config = load_system_config()
        return self._config_loader

    @property
    def state_machine(self) -> DungeonStateMachine:
        """获取状态机（懒加载）"""
        if self._state_machine is None:
            self._state_machine = DungeonStateMachine(
                config_loader=self._config_loader,
                game_actions=self.device_manager.get_game_actions(),
                logger=self.logger,
            )
        return self._state_machine

    @property
    def daily_collect_manager(self) -> DailyCollectManager:
        """获取每日收集管理器"""
        return DailyCollectManager(
            config_loader=self._config_loader,
            db=self.db,
        )

    def check_stop_signal(self) -> bool:
        """检查停止信号"""
        from auto_dungeon_core import check_stop_signal

        return check_stop_signal()

    def focus_and_click_dungeon(
        self, dungeon_name: str, zone_name: str, max_attempts: int = 2
    ) -> bool:
        """
        尝试聚焦到指定副本并点击

        Args:
            dungeon_name: 副本名称
            zone_name: 区域名称
            max_attempts: 最大尝试次数

        Returns:
            bool: 是否成功点击副本入口
        """
        from auto_dungeon_config import LAST_OCCURRENCE

        for attempt in range(max_attempts):
            use_cache = attempt == 0
            result = find_text_and_click_safe(
                dungeon_name,
                timeout=6,
                occurrence=LAST_OCCURRENCE,
                use_cache=use_cache,
            )
            if result:
                return True

            self.logger.warning(
                f"⚠️ 未能找到副本: {dungeon_name} (第 {attempt + 1}/{max_attempts} 次尝试)"
            )

            if attempt < max_attempts - 1:
                self.logger.info("🔄 重新打开地图并刷新区域后再试")
                open_map()
                if not switch_to_zone(zone_name):
                    self.logger.warning(f"⚠️ 刷新区域失败: {zone_name}")
                    continue
                from auto_dungeon_core import sleep

                sleep(1)

        return False

    def process_dungeon(
        self,
        dungeon_name: str,
        zone_name: str,
        index: int,
        total: int,
        completed_dungeons: int = 0,
        remaining_dungeons: int = 0,
    ) -> bool:
        """
        处理单个副本

        Args:
            dungeon_name: 副本名称
            zone_name: 区域名称
            index: 当前副本在所有副本中的索引
            total: 总副本数
            completed_dungeons: 已完成的副本数
            remaining_dungeons: 需要完成的副本总数

        Returns:
            bool: 是否成功完成
        """
        self.logger.info(f"\n🎯 [{index}/{total}] 处理副本: {dungeon_name}")

        # 处理日常任务
        if zone_name == "日常任务":
            self.logger.info(f"📋 执行日常任务: {dungeon_name}")
            if self.daily_collect_manager.execute_task(dungeon_name):
                self.db.mark_dungeon_completed(zone_name, dungeon_name)
                return True
            return False

        if not self.state_machine.prepare_dungeon_state(
            zone_name=zone_name, dungeon_name=dungeon_name, max_attempts=3
        ):
            self.state_machine.ensure_main()
            return False

        battle_started = self.state_machine.start_battle_state(
            dungeon_name=dungeon_name,
            completed_dungeons=completed_dungeons,
            total_dungeons=remaining_dungeons,
        )

        if not battle_started:
            # 没有「免费」按钮 = 本角色当天的免费次数已被消耗，即今天已经打过了，
            # 标记完成是**正确语义**，不是「把失败当成功」（同 auto_dungeon_core）。
            self.logger.warning("⚠️ 无免费按钮，标记为已完成")
            self.db.mark_dungeon_completed(zone_name, dungeon_name)
            from auto_dungeon_core import click_back

            click_back()
            self.state_machine.return_to_main_state()
            return True

        self.logger.info(f"✅ 完成: {dungeon_name}")
        self.state_machine.complete_battle_state()

        # 记录通关状态
        self.db.mark_dungeon_completed(zone_name, dungeon_name)

        from auto_dungeon_core import sleep

        sleep(CLICK_INTERVAL)
        self.state_machine.return_to_main_state()
        return True

    def run_dungeon_traversal(self) -> int:
        """
        执行副本遍历主循环

        Returns:
            int: 本次运行完成的副本数量
        """
        zone_dungeons = self.config_loader.get_zone_dungeons()
        if zone_dungeons is None:
            self.logger.error("❌ 区域副本配置未初始化")
            return 0

        dungeon_index = 0
        processed_dungeons = 0

        # 计算需要完成的副本总数
        remaining_dungeons = self._count_remaining_selected_dungeons()
        self.logger.info(f"📊 需要完成的副本总数: {remaining_dungeons}")

        # 获取今天已完成的副本数
        completed_today = self.db.get_today_completed_count()
        self.logger.info(f"📊 今天已完成的副本数: {completed_today}")

        self.state_machine.ensure_main()

        # 遍历所有区域
        for zone_idx, (zone_name, dungeons) in enumerate(zone_dungeons.items(), 1):
            self.logger.info(f"\n{'#' * 60}")
            self.logger.info(f"# 🌍 [{zone_idx}/{len(zone_dungeons)}] 区域: {zone_name}")
            self.logger.info(f"# 🎯 副本数: {len(dungeons)}")
            self.logger.info(f"{'#' * 60}")

            # 遍历副本
            for dungeon_dict in dungeons:
                # 在每个副本开始前检查停止信号
                if self.check_stop_signal():
                    self.logger.info(f"\n📊 统计: 本次运行完成 {processed_dungeons} 个副本")
                    self.logger.info("👋 已停止执行")
                    self.state_machine.ensure_main()
                    return processed_dungeons

                dungeon_name = dungeon_dict["name"]
                is_selected = dungeon_dict["selected"]
                dungeon_index += 1

                # 检查是否选定该副本
                if not is_selected:
                    self.logger.info(
                        f"⏭️ [{dungeon_index}/{len(zone_dungeons)}] 未选定，跳过: {dungeon_name}"
                    )
                    continue

                # 先检查是否已通关
                if self.db.is_dungeon_completed(zone_name, dungeon_name):
                    self.logger.info(
                        f"⏭️ [{dungeon_index}/{len(zone_dungeons)}] 已通关，跳过: {dungeon_name}"
                    )
                    continue

                # 完成副本
                if self.process_dungeon(
                    dungeon_name,
                    zone_name,
                    dungeon_index,
                    len(zone_dungeons),
                    completed_today + processed_dungeons,
                    remaining_dungeons,
                ):
                    processed_dungeons += 1
                    # 每完成3个副本就卖垃圾
                    if processed_dungeons % 3 == 0:
                        if self.state_machine.sell_loot():
                            self.state_machine.finish_sell_loot()
                        else:
                            from auto_dungeon_core import sell_trashes

                            sell_trashes()
                            back_to_main()
                            self.state_machine.ensure_main()

            self.logger.info(f"\n✅ 完成区域: {zone_name}")

        return processed_dungeons

    def _count_remaining_selected_dungeons(self) -> int:
        """统计未完成的选定副本数量"""
        zone_dungeons = self.config_loader.get_zone_dungeons()
        if zone_dungeons is None:
            return 0

        remaining = 0
        for zone_name, dungeons in zone_dungeons.items():
            for dungeon_dict in dungeons:
                if not dungeon_dict.get("selected", True):
                    continue
                if not self.db.is_dungeon_completed(zone_name, dungeon_dict["name"]):
                    remaining += 1
        return remaining

    def show_progress_statistics(self) -> Tuple[int, int, int]:
        """显示进度统计信息"""
        # 清理旧记录
        self.db.cleanup_old_records(days_to_keep=7)

        # 显示今天已通关的副本
        completed_count = self.db.get_today_completed_count()
        if completed_count > 0:
            self.logger.info(f"📊 今天已通关 {completed_count} 个副本")
            completed_dungeons = self.db.get_today_completed_dungeons()
            for zone, dungeon in completed_dungeons[:5]:
                self.logger.info(f"  ✅ {zone} - {dungeon}")
            if len(completed_dungeons) > 5:
                self.logger.info(f"  ... 还有 {len(completed_dungeons) - 5} 个")
            self.logger.info("")

        # 计算选定的副本总数
        zone_dungeons = self.config_loader.get_zone_dungeons()
        total_selected_dungeons = sum(
            sum(1 for d in dungeons if d.get("selected", True))
            for dungeons in zone_dungeons.values()
        )
        total_dungeons = sum(len(dungeons) for dungeons in zone_dungeons.values())

        # 汇总所有待通关的副本
        remaining_dungeons_detail = []
        for zone_name, dungeons in zone_dungeons.items():
            for dungeon in dungeons:
                if not dungeon.get("selected", True):
                    continue
                if not self.db.is_dungeon_completed(zone_name, dungeon["name"]):
                    remaining_dungeons_detail.append((zone_name, dungeon["name"]))

        self.logger.info(f"📊 总计: {len(zone_dungeons)} 个区域, {total_dungeons} 个副本")
        self.logger.info(f"📊 选定: {total_selected_dungeons} 个副本")
        self.logger.info(f"📊 已完成: {completed_count} 个副本")

        # 检查是否所有选定的副本都已完成
        if completed_count >= total_selected_dungeons:
            self.logger.info("\n" + "=" * 60)
            self.logger.info("🎉 今天所有选定的副本都已完成！")
            self.logger.info("=" * 60)
            self.logger.info("💤 无需执行任何操作，脚本退出")
            return completed_count, total_selected_dungeons, total_dungeons

        remaining_dungeons = len(remaining_dungeons_detail)
        self.logger.info(f"📊 剩余: {remaining_dungeons} 个副本待通关")
        if remaining_dungeons_detail:
            self.logger.info("📋 待通关副本清单:")
            for zone_name, dungeon_name in remaining_dungeons_detail:
                self.logger.info(f"  • {zone_name} - {dungeon_name}")
        self.logger.info("")

        return completed_count, total_selected_dungeons, total_dungeons

    def run(self) -> None:
        """运行副本机器人"""
        from airtest.core.api import start_app, stop_app

        self.logger.info("\n" + "=" * 60)
        self.logger.info("🎮 副本自动遍历脚本")
        self.logger.info("=" * 60 + "\n")

        # 显示进度统计
        completed_count, total_selected, total = self.show_progress_statistics()

        # 检查是否需要启动游戏（副本未完成）
        if completed_count >= total_selected:
            self.logger.info("✅ 所有任务都已完成，无需启动模拟器，脚本退出")
            return

        # 启动游戏
        self.logger.info("关闭游戏...")
        stop_app("com.ms.ysjyzr")
        from auto_dungeon_core import sleep

        sleep(2, "关闭游戏")

        self.logger.info("启动游戏")
        start_app("com.ms.ysjyzr")

        # 等待进入角色选择界面
        from auto_dungeon import is_on_character_selection

        if is_on_character_selection(120):
            self.logger.info("已在角色选择界面")

        # 选择角色
        char_class = self.config_loader.get_char_class()
        if char_class:
            self.logger.info(f"开始选择角色: {char_class}")
            self.state_machine.select_character_state(char_class=char_class)
        else:
            self.logger.info("⚠️ 未配置角色职业，跳过角色选择")
            self.state_machine.ensure_main()

        # 执行副本遍历
        iteration = 1
        while iteration <= self.config.max_iterations:
            self.logger.info(f"\n🔁 开始第 {iteration} 轮副本遍历…")
            self.run_dungeon_traversal()

            remaining_after_run = self._count_remaining_selected_dungeons()
            if remaining_after_run <= 0:
                break

            self.logger.warning(
                f"⚠️ 第 {iteration} 轮结束后仍有 {remaining_after_run} 个副本未完成，准备继续"
            )
            iteration += 1

        if iteration > self.config.max_iterations:
            remaining_after_run = self._count_remaining_selected_dungeons()
            if remaining_after_run > 0:
                self.logger.warning(
                    f"⚠️ 已达到最大轮数 {self.config.max_iterations}，仍有 {remaining_after_run} 个副本未完成"
                )

        # 显示完成信息
        self.logger.info("\n" + "=" * 60)
        self.logger.info(f"🎉 全部完成！今天共通关 {self.db.get_today_completed_count()} 个副本")
        self.logger.info("=" * 60 + "\n")
        self.state_machine.ensure_main()


def run_dungeon_bot(config: DungeonBotConfig) -> None:
    """
    运行副本机器人的便捷函数

    Args:
        config: 机器人配置
    """
    bot = DungeonBot(config)
    bot.run()
