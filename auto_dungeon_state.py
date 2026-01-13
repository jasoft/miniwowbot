"""
auto_dungeon 状态机模块

本模块提供副本执行状态机，使用 transitions 管理游戏状态流转。
"""
import logging
from typing import Optional

from transitions import Machine, MachineError

# ====== 状态定义 ======

STATES = [
    "character_selection",
    "main_menu",
    "dungeon_selection",
    "dungeon_battle",
    "reward_claim",
    "sell_loot",
]


class DungeonStateMachine:
    """副本状态机 - 负责管理游戏状态流转"""

    def __init__(
        self,
        config_loader=None,
        game_actions=None,
        logger=None,
    ):
        """
        初始化状态机

        Args:
            config_loader: 配置加载器实例
            game_actions: 游戏动作助手实例
            logger: 日志记录器
        """
        self.config_loader = config_loader
        self.game_actions = game_actions
        self.logger = logger or logging.getLogger(__name__)
        self.current_zone = None
        self.active_dungeon = None

        self._state = "character_selection"
        self._machine = Machine(
            model=self,
            states=STATES,
            initial="character_selection",
            auto_transitions=False,
            send_event=True,
            queued=True,
        )
        self._register_transitions()

    @property
    def state(self) -> str:
        """获取当前状态"""
        return self._state

    @state.setter
    def state(self, value: str):
        """设置当前状态"""
        self._state = value

    def _register_transitions(self):
        """注册所有状态转换"""
        # 角色选择 -> 主菜单
        self._machine.add_transition(
            trigger="trigger_select_character",
            source="character_selection",
            dest="main_menu",
            before="_on_select_character",
        )
        # 任意状态 -> 主菜单
        self._machine.add_transition(
            trigger="ensure_main_menu",
            source="*",
            dest="main_menu",
            before="_on_return_to_main",
        )
        # 主菜单 -> 副本选择
        self._machine.add_transition(
            trigger="prepare_dungeon",
            source="main_menu",
            dest="dungeon_selection",
            conditions="_prepare_dungeon_selection",
        )
        # 副本选择 -> 战斗
        self._machine.add_transition(
            trigger="start_battle",
            source="dungeon_selection",
            dest="dungeon_battle",
            conditions="_start_battle_sequence",
        )
        # 战斗 -> 奖励
        self._machine.add_transition(
            trigger="complete_battle",
            source="dungeon_battle",
            dest="reward_claim",
            before="_on_reward_state",
        )
        # 主菜单 -> 奖励（每日领取）
        self._machine.add_transition(
            trigger="claim_rewards",
            source="main_menu",
            dest="reward_claim",
            before="_on_reward_state",
        )
        # 奖励/选择 -> 主菜单
        self._machine.add_transition(
            trigger="return_to_main",
            source=["reward_claim", "dungeon_selection"],
            dest="main_menu",
            before="_on_return_to_main",
        )
        # 主菜单 -> 卖出
        self._machine.add_transition(
            trigger="start_selling",
            source="main_menu",
            dest="sell_loot",
            before="_on_sell_loot",
        )
        # 卖出 -> 主菜单
        self._machine.add_transition(
            trigger="finish_selling",
            source="sell_loot",
            dest="main_menu",
            before="_on_return_to_main",
        )

    def _safe_trigger(self, trigger_name: str, **kwargs) -> bool:
        """安全触发状态转换"""
        try:
            trigger = getattr(self, trigger_name)
            return trigger(**kwargs)
        except (AttributeError, MachineError) as exc:
            self.logger.error(f"⚠️ 状态机触发失败: {trigger_name} - {exc}")
            return False

    # ====== 公共状态方法 ======

    def select_character_state(self, char_class: Optional[str] = None) -> bool:
        """选择角色状态"""
        if char_class:
            self._safe_trigger("trigger_select_character", char_class=char_class)
            return self.state == "main_menu"
        return self.ensure_main()

    def ensure_main(self) -> bool:
        """确保回到主界面"""
        self._safe_trigger("ensure_main_menu")
        return self.state == "main_menu"

    def prepare_dungeon_state(self, zone_name: str, dungeon_name: str, max_attempts: int = 3) -> bool:
        """准备副本选择状态"""
        self._safe_trigger(
            "prepare_dungeon",
            zone_name=zone_name,
            dungeon_name=dungeon_name,
            max_attempts=max_attempts,
        )
        return self.state == "dungeon_selection"

    def start_battle_state(
        self, dungeon_name: str, completed_dungeons: int = 0, total_dungeons: int = 0
    ) -> bool:
        """开始战斗状态"""
        self._safe_trigger(
            "start_battle",
            dungeon_name=dungeon_name,
            completed_dungeons=completed_dungeons,
            total_dungeons=total_dungeons,
        )
        return self.state == "dungeon_battle"

    def complete_battle_state(self) -> bool:
        """完成战斗状态"""
        self._safe_trigger("complete_battle", reward_type="battle")
        return self.state == "reward_claim"

    def claim_daily_rewards(self) -> bool:
        """领取每日奖励"""
        self._safe_trigger("claim_rewards", reward_type="daily_collect")
        return self.state == "reward_claim"

    def return_to_main_state(self) -> bool:
        """返回主界面状态"""
        self._safe_trigger("return_to_main")
        return self.state == "main_menu"

    def sell_loot(self) -> bool:
        """卖出物品"""
        self._safe_trigger("start_selling")
        return self.state == "sell_loot"

    def finish_sell_loot(self) -> bool:
        """完成卖出"""
        self._safe_trigger("finish_selling")
        return self.state == "main_menu"

    # ====== 状态动作方法 ======

    def _on_select_character(self, event):
        """选择角色动作"""
        char_class = event.kwargs.get("char_class")
        if not char_class:
            self.logger.warning("⚠️ 未提供职业信息，保持在主界面")
            return

        self.logger.info(f"🎭 状态机: 选择职业 {char_class}")

        # 延迟导入以避免循环依赖
        from auto_dungeon import select_character

        select_character(char_class)

    def _prepare_dungeon_selection(self, event) -> bool:
        """准备副本选择条件"""
        zone_name = event.kwargs.get("zone_name")
        dungeon_name = event.kwargs.get("dungeon_name")
        max_attempts = event.kwargs.get("max_attempts", 3)

        if not zone_name or not dungeon_name:
            self.logger.warning("⚠️ 状态机缺少区域或副本信息，无法进入选取状态")
            return False

        self.logger.info(f"🗺️ 状态机: 前往区域 {zone_name}，寻找副本 {dungeon_name}")

        # 延迟导入以避免循环依赖
        from auto_dungeon import open_map, switch_to_zone, focus_and_click_dungeon

        open_map()
        if self.current_zone != zone_name:
            if not switch_to_zone(zone_name):
                self.logger.warning(f"⚠️ 状态机无法切换到区域: {zone_name}")
                return False
            self.current_zone = zone_name

        success = focus_and_click_dungeon(dungeon_name, zone_name, max_attempts=max_attempts)

        if success:
            self.active_dungeon = dungeon_name
        else:
            self.logger.warning(f"⚠️ 状态机无法定位副本: {dungeon_name}")

        return success

    def _start_battle_sequence(self, event) -> bool:
        """开始战斗条件"""
        from auto_dungeon import (
            click_free_button,
            find_text_and_click_safe,
            auto_combat,
        )

        dungeon_name = event.kwargs.get("dungeon_name") or self.active_dungeon
        completed = event.kwargs.get("completed_dungeons", 0)
        total = event.kwargs.get("total_dungeons", 0)

        if not dungeon_name:
            self.logger.warning("⚠️ 状态机未记录当前副本，无法进入战斗")
            return False

        if not click_free_button():
            self.logger.info(f"ℹ️ 副本 {dungeon_name} 今日已完成或无免费次数")
            return False

        self.logger.info(f"⚔️ 状态机: 进入副本战斗 - {dungeon_name}")
        find_text_and_click_safe("战斗", regions=[8])
        auto_combat(completed_dungeons=completed, total_dungeons=total)
        return True

    def _on_reward_state(self, event):
        """奖励状态动作"""
        reward_type = event.kwargs.get("reward_type", "battle")

        if reward_type == "daily_collect":
            self.logger.info("🎁 状态机: 执行每日领取流程")

            # 延迟导入以避免循环依赖
            from auto_dungeon import daily_collect

            try:
                daily_collect()
            except Exception as exc:
                self.logger.error(f"❌ 每日领取失败: {exc}")
                raise
        else:
            self.logger.info("🎁 状态机: 处理副本奖励")

    def _on_return_to_main(self, event):
        """返回主界面动作"""
        self.logger.info("🏠 状态机: 返回主界面")

        # 延迟导入以避免循环依赖
        from auto_dungeon import back_to_main

        back_to_main()
        self.current_zone = None
        self.active_dungeon = None

    def _on_sell_loot(self, event):
        """卖出物品动作"""
        self.logger.info("🧹 状态机: 卖出垃圾道具")

        # 延迟导入以避免循环依赖
        from auto_dungeon import sell_trashes

        sell_trashes()
