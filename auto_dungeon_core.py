"""
auto_dungeon 核心功能模块

包含所有核心功能函数，消除全局变量。
"""
import logging
import os
import subprocess
import sys
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import requests
from airtest.core.api import (
    exists,
    keyevent,
    log as airtest_log,
    shell,
    sleep as airtest_sleep,
    start_app,
    stop_app,
    swipe,
    touch,
    wait,
)
from airtest.core.error import TargetNotFoundError
from airtest.core.settings import Settings as ST
from tqdm import tqdm
from transitions import Machine, MachineError
from vibe_ocr import OCRHelper

# 初始化模块级 logger
logger = logging.getLogger(__name__)

from auto_dungeon_config import (
    AUTOCOMBAT_TEMPLATE,
    CLICK_INTERVAL,
    ENTER_GAME_BUTTON_TEMPLATE,
    FIND_TIMEOUT,
    FIND_TIMEOUT_TMP,
    GIFTS_TEMPLATE,
    LAST_OCCURRENCE,
    MAP_DUNGEON_TEMPLATE,
    OCR_STRATEGY,
    STOP_FILE,
)
from coordinates import (
    ACCOUNT_AVATAR,
    ACCOUNT_DROPDOWN_ARROW,
    ACCOUNT_LIST_SWIPE_END,
    ACCOUNT_LIST_SWIPE_START,
    BACK_BUTTON,
    CLOSE_ZONE_MENU,
    DAILY_REWARD_BOX_OFFSET_Y,
    DAILY_REWARD_CONFIRM,
    DEPLOY_CONFIRM_BUTTON,
    LOGIN_BUTTON,
    MAP_BUTTON,
    ONE_KEY_DEPLOY,
    ONE_KEY_REWARD,
    QUICK_AFK_COLLECT_BUTTON,
    SKILL_POSITIONS,
)
from database import DungeonProgressDB
from emulator_manager import EmulatorManager
from error_dialog_monitor import ErrorDialogMonitor
from game_actions import GameActions
from logger_config import GlobalLogContext, setup_logger_from_config
from system_config_loader import load_system_config

# 配置 Airtest 图像识别策略
ST.CVSTRATEGY = OCR_STRATEGY
airtest_logger = logging.getLogger("airtest")
airtest_logger.setLevel(logging.ERROR)
ST.FIND_TIMEOUT = FIND_TIMEOUT
ST.FIND_TIMEOUT_TMP = FIND_TIMEOUT_TMP

# 设置 OCR 日志级别
logging.getLogger("ocr_helper").setLevel(logging.DEBUG)


# ====== 依赖容器 ======

class DependencyContainer:
    """依赖注入容器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._config_loader = None
        self._system_config = None
        self._ocr_helper = None
        self._game_actions = None
        self._emulator_manager = None
        self._target_emulator = None
        self._config_name = None
        self._error_dialog_monitor = None
        self._initialized = True

    @property
    def config_loader(self):
        return self._config_loader

    @config_loader.setter
    def config_loader(self, value):
        self._config_loader = value

    @property
    def system_config(self):
        return self._system_config

    @system_config.setter
    def system_config(self, value):
        self._system_config = value

    @property
    def ocr_helper(self):
        return self._ocr_helper

    @ocr_helper.setter
    def ocr_helper(self, value):
        self._ocr_helper = value

    @property
    def game_actions(self):
        return self._game_actions

    @game_actions.setter
    def game_actions(self, value):
        self._game_actions = value

    @property
    def emulator_manager(self):
        return self._emulator_manager

    @emulator_manager.setter
    def emulator_manager(self, value):
        self._emulator_manager = value

    @property
    def target_emulator(self):
        return self._target_emulator

    @target_emulator.setter
    def target_emulator(self, value):
        self._target_emulator = value

    @property
    def config_name(self):
        return self._config_name

    @config_name.setter
    def config_name(self, value):
        self._config_name = value

    @property
    def error_dialog_monitor(self):
        return self._error_dialog_monitor

    @error_dialog_monitor.setter
    def error_dialog_monitor(self, value):
        self._error_dialog_monitor = value

    def reset(self):
        """重置所有依赖"""
        self._config_loader = None
        self._system_config = None
        self._ocr_helper = None
        self._game_actions = None
        self._emulator_manager = None
        self._target_emulator = None
        self._config_name = None
        self._error_dialog_monitor = None


# 全局依赖容器
_container = DependencyContainer()


def get_container() -> DependencyContainer:
    """获取依赖容器"""
    return _container


# ====== 基础工具函数 ======

def sleep(seconds: float, reason: str = "[需要填写原因]") -> None:
    """sleep 的封装"""
    logger.info(f"💤 等待 {seconds} 秒, 原因是: {reason}")
    airtest_sleep(seconds)


def normalize_emulator_name(name: Optional[str]) -> Optional[str]:
    """规范化模拟器名称"""
    if not name:
        return name
    name = str(name).strip()
    if name.lower().startswith("android://"):
        try:
            parts = name.split("/")
            if parts:
                return parts[-1].strip()
        except Exception:
            return name
    return name


def check_stop_signal() -> bool:
    """检查停止信号文件"""
    if os.path.exists(STOP_FILE):
        logger.warning(f"\n⛔ 检测到停止信号文件: {STOP_FILE}")
        logger.warning("⛔ 正在优雅地停止执行...")
        try:
            os.remove(STOP_FILE)
            logger.info("✅ 已删除停止信号文件")
        except Exception as e:
            logger.error(f"❌ 删除停止文件失败: {e}")
        return True
    return False


# ====== 文本查找函数 ======

def find_text(*args, **kwargs) -> Optional[Dict[str, Any]]:
    """文本查找"""
    ga = _container.game_actions
    if ga:
        return ga.find_text(*args, **kwargs)
    logger.error("❌ GameActions 未初始化")
    return None


def text_exists(*args, **kwargs) -> Optional[Dict[str, Any]]:
    """检查文本是否存在"""
    ga = _container.game_actions
    if ga:
        return ga.text_exists(*args, **kwargs)
    logger.error("❌ GameActions 未初始化")
    return None


def find_text_and_click(*args, **kwargs) -> bool:
    """文本查找并点击"""
    ga = _container.game_actions
    if ga:
        return ga.find_text_and_click(*args, **kwargs)
    raise RuntimeError("GameActions 未初始化")


def find_text_and_click_safe(*args, **kwargs) -> bool:
    """文本查找并点击（安全版本）"""
    ga = _container.game_actions
    if ga:
        return ga.find_text_and_click_safe(*args, **kwargs)
    return kwargs.get("default_return", False)


def find_all_texts(*args, **kwargs) -> List[Dict[str, Any]]:
    """查找所有匹配的文本"""
    ga = _container.game_actions
    if ga:
        return ga.find_all_texts(*args, **kwargs)
    logger.error("❌ GameActions 未初始化")
    return []


def find_all(*args, **kwargs):
    """查找所有匹配的元素"""
    ga = _container.game_actions
    if ga:
        return ga.find_all(*args, **kwargs)
    logger.error("❌ GameActions 未初始化")
    return []


# ====== UI 交互函数 ======

def click_back() -> bool:
    """点击返回按钮"""
    try:
        touch(BACK_BUTTON)
        sleep(CLICK_INTERVAL)
        logger.info("🔙 点击返回按钮")
        return True
    except Exception as e:
        logger.error(f"❌ 返回失败: {e}")
        return False


def click_free_button() -> bool:
    """点击免费按钮"""
    free_words = ["免费"]
    for word in free_words:
        if find_text_and_click_safe(word, timeout=3, use_cache=False, regions=[8]):
            logger.info(f"💰 点击了免费按钮: {word}")
            return True
    logger.warning("⚠️ 未找到免费按钮")
    return False


def switch_to(section_name: str) -> Optional[Dict[str, Any]]:
    """切换到指定区域"""
    logger.info(f"🌍 切换到: {section_name}")
    return find_text_and_click(section_name, regions=[7, 8, 9])


# ====== 地图和导航函数 ======

def open_map() -> None:
    """打开地图"""
    back_to_main()
    touch(MAP_BUTTON)
    logger.info("🗺️ 打开地图")
    sleep(2, "等待地图加载完毕")


def is_on_map() -> bool:
    """检查是否在地图界面"""
    return exists(MAP_DUNGEON_TEMPLATE)


def is_main_world() -> bool:
    """检查是否在主世界"""
    try:
        result = wait(GIFTS_TEMPLATE, timeout=0.3, interval=0.1)
        return bool(result)
    except Exception:
        return False


def is_on_character_selection(timeout: int = 30) -> bool:
    """检查是否在角色选择界面"""
    try:
        logger.info("🔍 等待进入角色选择界面...")
        wait(ENTER_GAME_BUTTON_TEMPLATE, timeout=timeout, interval=0.1)
        return True
    except TargetNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"检测角色选择界面时发生异常: {e}")
    return False


def back_to_main(max_duration: float = 15, backoff_interval: float = 0.2) -> None:
    """返回主界面"""
    logger.info("🔙 返回主界面")
    start_time = time.time()
    attempt = 0

    while True:
        if is_main_world():
            logger.info("✅ 已回到主界面")
            return

        elapsed = time.time() - start_time
        if elapsed >= max_duration:
            message = f"back_to_main 超时，已等待 {elapsed:.1f} 秒仍未检测到主界面"
            logger.error(message)
            raise TimeoutError(message)

        attempt += 1

        for _ in range(3):
            try:
                touch(BACK_BUTTON)
            except Exception as e:
                logger.warning(f"⚠️ 发送返回点击失败: {e}")
                break
            sleep(0.1)

        if attempt % 3 == 0:
            try:
                keyevent("BACK")
            except Exception as e:
                logger.warning(f"⚠️ 系统返回键发送失败: {e}")

        if attempt % 5 == 0:
            try:
                shell("input keyevent 4")
            except Exception as e:
                logger.debug(f"ADB 返回指令失败: {e}")

        sleep(backoff_interval)


def switch_to_zone(zone_name: str) -> bool:
    """切换到指定区域"""
    logger.info(f"\n{'=' * 50}")
    logger.info(f"🌍 切换区域: {zone_name}")
    logger.info(f"{'=' * 50}")

    find_text_and_click_safe("切换区域", timeout=10)

    if find_text_and_click_safe(zone_name, timeout=10, occurrence=2):
        logger.info(f"✅ 成功切换到: {zone_name}")
        touch(CLOSE_ZONE_MENU)
        return True

    logger.error(f"❌ 切换失败: {zone_name}")
    return False


def sell_trashes() -> None:
    """卖垃圾"""
    logger.info("💰 卖垃圾")
    click_back()
    if find_text_and_click_safe("装备", regions=[7, 8, 9]):
        if find_text_and_click_safe("整理售卖", regions=[7, 8, 9]):
            touch((462, 958))
            sleep(1)
        else:
            raise Exception("❌ 点击'整理售卖'按钮失败")
    else:
        raise Exception("❌ 点击'装备'按钮失败")
    click_back()
    click_back()


def switch_account(account_name: str) -> None:
    """切换账号"""
    logger.info(f"切换账号: {account_name}")
    stop_app("com.ms.ysjyzr")
    sleep(2)
    start_app("com.ms.ysjyzr")
    try:
        find_text("进入游戏", timeout=120, regions=[5])
        touch(ACCOUNT_AVATAR)
        sleep(2)
        find_text_and_click_safe("切换账号", regions=[2, 3])
    except Exception:
        logger.warning("⚠️ 未找到切换账号按钮，可能处于登录界面")
    find_text("最近登录", timeout=20, regions=[5])
    touch(ACCOUNT_DROPDOWN_ARROW)

    success = False
    for _ in range(10):
        if find_text_and_click_safe(
            account_name, occurrence=2, use_cache=False, regions=[4, 5, 6, 7, 8, 9]
        ):
            success = True
            break
        swipe(ACCOUNT_LIST_SWIPE_START, ACCOUNT_LIST_SWIPE_END)

    if not success:
        raise Exception(f"Failed to find and click account '{account_name}' after 10 tries")
    touch(LOGIN_BUTTON)


def select_character(char_class: str) -> None:
    """选择角色"""
    logger.info(f"⚔️ 选择角色: {char_class}")

    em = _container.error_dialog_monitor
    if em:
        em.handle_once()

    in_selection = is_on_character_selection(timeout=120)
    if not in_selection:
        logger.error("❌ 未在角色选择界面，无法选择角色")
        raise RuntimeError("未在角色选择界面，无法选择角色")

    sleep(3, "等待角色选择界面加载完毕")
    logger.info(f"🔍 查找职业: {char_class}")
    result = find_text(char_class, similarity_threshold=0.8, use_cache=False)

    if result and result.get("found"):
        pos = result["center"]
        click_x = pos[0]
        click_y = pos[1] - 60
        logger.info(f"👆 点击角色位置: ({click_x}, {click_y})")
        touch((click_x, click_y))
        sleep(1)
        logger.info(f"✅ 成功选择角色: {char_class}")
    else:
        logger.error(f"❌ 未找到职业: {char_class}")
        raise RuntimeError(f"无法找到职业: {char_class}")

    find_text_and_click("进入游戏", regions=[5])
    wait_for_main()


def wait_for_main(timeout: int = 300) -> None:
    """等待回到主界面"""
    logger.info("⏳ 等待战斗结束...")
    start_time = time.time()
    try:
        result = wait(GIFTS_TEMPLATE, timeout=timeout, interval=0.5)
        if result:
            elapsed = time.time() - start_time
            logger.info(f"✅ 战斗结束，用时 {elapsed:.1f} 秒")
    except Exception as e:
        logger.error(f"⏱️ 等待 GIFTS_TEMPLATE 超时或出错: {e}")
        raise TimeoutError("等待主界面超时")


# ====== 战斗函数 ======

def auto_combat(completed_dungeons: int = 0, total_dungeons: int = 0) -> None:
    """自动战斗"""
    logger.info("⚔️ 开始自动战斗")
    find_text_and_click_safe("战斗", regions=[8])

    try:
        builtin_auto_combat_activated = bool(wait(AUTOCOMBAT_TEMPLATE, timeout=2, interval=0.1))
    except Exception:
        builtin_auto_combat_activated = False

    logger.info(f"内置自动战斗: {builtin_auto_combat_activated}")

    if total_dungeons > 0:
        desc = f"⚔️ 战斗进度 [{completed_dungeons}/{total_dungeons}]"
        bar_format = "{desc} |{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
        total_value = total_dungeons
    else:
        desc = "⚔️ 战斗进度"
        bar_format = "{desc} |{bar}| {n_fmt}/{total_fmt}s [{elapsed}<{remaining}]"
        total_value = 60

    with tqdm(
        total=total_value,
        desc=desc,
        unit="" if total_dungeons > 0 else "s",
        ncols=80,
        bar_format=bar_format,
        initial=completed_dungeons if total_dungeons > 0 else 0,
    ) as pbar:
        start_time = time.time()
        last_update = start_time

        while not is_main_world():
            if check_stop_signal():
                pbar.close()
                raise KeyboardInterrupt("检测到停止信号，退出自动战斗")

            current_time = time.time()

            if current_time - last_update >= 0.5:
                if total_dungeons > 0:
                    pass
                else:
                    update_amount = current_time - last_update
                    pbar.update(update_amount)
                last_update = current_time

            if builtin_auto_combat_activated:
                sleep(1)
                continue

            positions = SKILL_POSITIONS.copy()
            touch(positions[4])
            sleep(0.5)

        if total_dungeons > 0:
            pbar.update(1)
        else:
            remaining = total_value - (time.time() - start_time)
            if remaining > 0:
                pbar.update(remaining)
        pbar.close()

    logger.info("✅ 战斗完成")


# ====== 通知函数 ======

def send_bark_notification(title: str, message: str, level: str = "active") -> bool:
    """发送 Bark 通知"""
    sc = _container.system_config
    if not sc or not sc.is_bark_enabled():
        logger.debug("🔕 Bark 通知未启用，跳过发送")
        return False

    bark_config = sc.get_bark_config()
    server = bark_config.get("server")

    if not server:
        logger.warning("⚠️ Bark 服务器地址未配置")
        return False

    try:
        cfg = GlobalLogContext.context.get("config") or (_container.config_name or "unknown")
        emu = GlobalLogContext.context.get("emulator") or (_container.target_emulator or "unknown")
        enriched_title = f"[{cfg} | {emu}] {title}"
        enriched_message = f"{message}\n配置: {cfg}\n模拟器: {emu}"

        encoded_title = urllib.parse.quote(enriched_title, safe="")
        encoded_message = urllib.parse.quote(enriched_message, safe="")

        if "?" in server or server.endswith("/"):
            url = f"{server.rstrip('/')}/{encoded_title}/{encoded_message}"
        else:
            url = f"{server}/{encoded_title}/{encoded_message}"

        params = {}
        if bark_config.get("group"):
            params["group"] = bark_config["group"]
        if level:
            params["level"] = level

        logger.info(f"📱 发送 Bark 通知: {enriched_title}")
        logger.info(f"📄 Bark 内容: {enriched_message}")
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            logger.info("✅ Bark 通知发送成功")
            return True
        else:
            logger.warning(f"⚠️ Bark 通知发送失败，状态码: {response.status_code}")
            return False

    except requests.exceptions.Timeout:
        logger.warning("⚠️ Bark 通知发送超时")
        return False
    except Exception as e:
        logger.error(f"❌ 发送 Bark 通知失败: {e}")
        return False


# ====== 设备管理 ======

class DeviceManager:
    """设备连接管理器"""

    def __init__(self, emulator_name: Optional[str] = None, low_mem: bool = False):
        self.emulator_name = emulator_name
        self.low_mem = low_mem
        self.connection_string: Optional[str] = None
        self._emulator_manager: Optional[EmulatorManager] = None

    def initialize(self) -> None:
        """初始化设备连接"""
        emulator_name = self.emulator_name
        low_mem = self.low_mem

        if emulator_name:
            normalized = normalize_emulator_name(emulator_name)
            if normalized is None:
                raise RuntimeError("❌ 模拟器名称规范化失败")
            emulator_name = normalized
            _container.target_emulator = emulator_name

            self._emulator_manager = EmulatorManager()
            _container.emulator_manager = self._emulator_manager

            devices = self._emulator_manager.get_adb_devices()
            if emulator_name not in devices:
                logger.warning(f"⚠️ 模拟器 {emulator_name} 未运行或未连接")
                if not self._emulator_manager.ensure_device_connected(emulator_name):
                    send_bark_notification(
                        "副本助手 - 错误",
                        f"模拟器 {emulator_name} 未运行或未连接",
                        level="timeSensitive",
                    )
                    raise RuntimeError(f"模拟器 {emulator_name} 未运行或未连接")
            else:
                logger.info(f"✅ 模拟器 {emulator_name} 已在设备列表中")

            self.connection_string = self._emulator_manager.get_emulator_connection_string(emulator_name)
            logger.info(f"📱 连接到模拟器: {emulator_name}")
        else:
            self.connection_string = "Android:///"
            logger.info("📱 使用默认连接字符串")

        # 连接设备
        try:
            from airtest.core.api import auto_setup, connect_device, snapshot

            auto_setup(__file__)
            if self.connection_string:
                connect_device(self.connection_string)
            logger.info("   ✅ 成功连接到设备")
        except Exception as e:
            logger.error(f"   ❌ 连接设备失败: {e}")
            # 重试
            try:
                logger.warning("🔁 尝试重置 ADB 并重新连接设备…")
                if self._emulator_manager and self._emulator_manager.adb_path:
                    subprocess.run(
                        [self._emulator_manager.adb_path, "kill-server"],
                        timeout=5,
                        capture_output=True,
                    )
                    subprocess.run(
                        [self._emulator_manager.adb_path, "start-server"],
                        timeout=10,
                        capture_output=True,
                    )
                    self._emulator_manager.ensure_adb_connection()
                    if self.connection_string:
                        connect_device(self.connection_string)
                    logger.info("   ✅ 重试连接成功")
                else:
                    raise RuntimeError("EmulatorManager 未正确初始化")
            except Exception as retry_err:
                logger.error(f"   ❌ 重试连接失败: {retry_err}")
                raise

        # 初始化 OCR
        correction_map = None
        if _container.config_loader:
            correction_map = _container.config_loader.get_ocr_correction_map()

        _container.ocr_helper = OCRHelper(
            output_dir="output",
            max_cache_size=50 if low_mem else 200,
            max_width=640 if low_mem else 960,
            delete_temp_screenshots=True,
            correction_map=correction_map,
            snapshot_func=snapshot,
        )

        # 初始化 GameActions
        _container.game_actions = GameActions(_container.ocr_helper, click_interval=CLICK_INTERVAL)


# ====== 状态机 ======

STATES = [
    "character_selection",
    "main_menu",
    "dungeon_selection",
    "dungeon_battle",
    "reward_claim",
    "sell_loot",
]


class DungeonStateMachine:
    """副本状态机"""

    def __init__(self):
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
        return self._state

    @state.setter
    def state(self, value: str):
        self._state = value

    def _register_transitions(self):
        self._machine.add_transition(
            trigger="trigger_select_character",
            source="character_selection",
            dest="main_menu",
            before="_on_select_character",
        )
        self._machine.add_transition(
            trigger="ensure_main_menu",
            source="*",
            dest="main_menu",
            before="_on_return_to_main",
        )
        self._machine.add_transition(
            trigger="prepare_dungeon",
            source="main_menu",
            dest="dungeon_selection",
            conditions="_prepare_dungeon_selection",
        )
        self._machine.add_transition(
            trigger="start_battle",
            source="dungeon_selection",
            dest="dungeon_battle",
            conditions="_start_battle_sequence",
        )
        self._machine.add_transition(
            trigger="complete_battle",
            source="dungeon_battle",
            dest="reward_claim",
            before="_on_reward_state",
        )
        self._machine.add_transition(
            trigger="claim_rewards",
            source="main_menu",
            dest="reward_claim",
            before="_on_reward_state",
        )
        self._machine.add_transition(
            trigger="return_to_main",
            source=["reward_claim", "dungeon_selection"],
            dest="main_menu",
            before="_on_return_to_main",
        )
        self._machine.add_transition(
            trigger="start_selling",
            source="main_menu",
            dest="sell_loot",
            before="_on_sell_loot",
        )
        self._machine.add_transition(
            trigger="finish_selling",
            source="sell_loot",
            dest="main_menu",
            before="_on_return_to_main",
        )

    def _safe_trigger(self, trigger_name: str, **kwargs) -> bool:
        try:
            trigger = getattr(self, trigger_name)
            return trigger(**kwargs)
        except (AttributeError, MachineError) as exc:
            logger.error(f"⚠️ 状态机触发失败: {trigger_name} - {exc}")
            return False

    def select_character_state(self, char_class: Optional[str] = None) -> bool:
        if char_class:
            self._safe_trigger("trigger_select_character", char_class=char_class)
            return self.state == "main_menu"
        return self.ensure_main()

    def ensure_main(self) -> bool:
        self._safe_trigger("ensure_main_menu")
        return self.state == "main_menu"

    def prepare_dungeon_state(self, zone_name: str, dungeon_name: str, max_attempts: int = 3) -> bool:
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
        self._safe_trigger(
            "start_battle",
            dungeon_name=dungeon_name,
            completed_dungeons=completed_dungeons,
            total_dungeons=total_dungeons,
        )
        return self.state == "dungeon_battle"

    def complete_battle_state(self) -> bool:
        self._safe_trigger("complete_battle", reward_type="battle")
        return self.state == "reward_claim"

    def claim_daily_rewards(self) -> bool:
        self._safe_trigger("claim_rewards", reward_type="daily_collect")
        return self.state == "reward_claim"

    def return_to_main_state(self) -> bool:
        self._safe_trigger("return_to_main")
        return self.state == "main_menu"

    def sell_loot(self) -> bool:
        self._safe_trigger("start_selling")
        return self.state == "sell_loot"

    def finish_sell_loot(self) -> bool:
        self._safe_trigger("finish_selling")
        return self.state == "main_menu"

    def _on_select_character(self, event):
        char_class = event.kwargs.get("char_class")
        if not char_class:
            logger.warning("⚠️ 未提供职业信息，保持在主界面")
            return
        logger.info(f"🎭 状态机: 选择职业 {char_class}")
        select_character(char_class)

    def _prepare_dungeon_selection(self, event) -> bool:
        zone_name = event.kwargs.get("zone_name")
        dungeon_name = event.kwargs.get("dungeon_name")
        max_attempts = event.kwargs.get("max_attempts", 3)

        if not zone_name or not dungeon_name:
            logger.warning("⚠️ 状态机缺少区域或副本信息，无法进入选取状态")
            return False

        logger.info(f"🗺️ 状态机: 前往区域 {zone_name}，寻找副本 {dungeon_name}")
        open_map()
        if self.current_zone != zone_name:
            if not switch_to_zone(zone_name):
                logger.warning(f"⚠️ 状态机无法切换到区域: {zone_name}")
                return False
            self.current_zone = zone_name

        success = focus_and_click_dungeon(dungeon_name, zone_name, max_attempts=max_attempts)

        if success:
            self.active_dungeon = dungeon_name
        else:
            logger.warning(f"⚠️ 状态机无法定位副本: {dungeon_name}")

        return success

    def _start_battle_sequence(self, event) -> bool:
        dungeon_name = event.kwargs.get("dungeon_name") or self.active_dungeon
        completed = event.kwargs.get("completed_dungeons", 0)
        total = event.kwargs.get("total_dungeons", 0)

        if not dungeon_name:
            logger.warning("⚠️ 状态机未记录当前副本，无法进入战斗")
            return False

        if not click_free_button():
            logger.info(f"ℹ️ 副本 {dungeon_name} 今日已完成或无免费次数")
            return False

        logger.info(f"⚔️ 状态机: 进入副本战斗 - {dungeon_name}")
        find_text_and_click_safe("战斗", regions=[8])
        auto_combat(completed_dungeons=completed, total_dungeons=total)
        return True

    def _on_reward_state(self, event):
        reward_type = event.kwargs.get("reward_type", "battle")

        if reward_type == "daily_collect":
            logger.info("🎁 状态机: 执行每日领取流程")
            try:
                daily_collect()
            except Exception as exc:
                logger.error(f"❌ 每日领取失败: {exc}")
                raise
        else:
            logger.info("🎁 状态机: 处理副本奖励")

    def _on_return_to_main(self, event):
        logger.info("🏠 状态机: 返回主界面")
        back_to_main()
        self.current_zone = None
        self.active_dungeon = None

    def _on_sell_loot(self, event):
        logger.info("🧹 状态机: 卖出垃圾道具")
        sell_trashes()


# ====== 每日收集 ======

class DailyCollectManager:
    """每日收集管理器"""

    def __init__(self, config_loader=None, db=None):
        self.config_loader = config_loader
        self.db = db
        self.logger = logger

    def collect_daily_rewards(self) -> None:
        """执行所有每日收集操作"""
        self.logger.info("=" * 60)
        self.logger.info("🎁 开始执行每日收集操作")
        self.logger.info("=" * 60)

        try:
            self._run_step("idle_rewards", self._collect_idle_rewards)
            self._run_step("buy_market_items", self._buy_market_items)
            self._run_step("retinue_deployment", self._handle_retinue_deployment)
            self._run_step("free_dungeons", self._collect_free_dungeons)

            if self.config_loader and self.config_loader.get_chest_name():
                self._run_step("open_chests", self._open_chests, self.config_loader.get_chest_name())

            def kill_boss_loop():
                for _ in range(3):
                    self._kill_world_boss()

            self._run_step("world_boss", kill_boss_loop)
            self._run_step("receive_mails", self._receive_mails)
            self._run_step("small_cookie", self._small_cookie)
            self._run_step("collect_gifts", self._collect_gifts)
            self._run_step("buy_ads_items", self._buy_ads_items)
            self._run_step("demonhunter_exam", self._demonhunter_exam)

            self.logger.info("=" * 60)
            self.logger.info("✅ 每日收集操作全部完成")
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"❌ 每日收集操作失败: {e}")
            raise

    def _run_step(self, step_name: str, func, *args, **kwargs):
        if self.db and self.db.is_daily_step_completed(step_name):
            self.logger.info(f"⏭️ 步骤 {step_name} 已完成，跳过")
            return
        func(*args, **kwargs)
        if self.db:
            self.db.mark_daily_step_completed(step_name)

    def _collect_gifts(self):
        self.logger.info("领取礼包")
        back_to_main()
        find_text_and_click("礼包", regions=[3])
        find_text_and_click("旅行日志", regions=[3])
        find_text_and_click("领取奖励", regions=[8])
        back_to_main()

    def _demonhunter_exam(self):
        self.logger.info("猎魔试炼")
        back_to_main()
        try:
            find_text_and_click("猎魔试炼")
            find_text_and_click("签到")
            find_text_and_click("一键签到")
            back_to_main()
        except Exception as e:
            self.logger.error(f"❌ 猎魔试炼失败: {e}, 活动可能已结束")

    def _small_cookie(self):
        self.logger.info("领取各种主题奖励[海盗船,法师塔]")
        back_to_main()
        find_text_and_click("活动", regions=[3])
        res = text_exists(
            ["海盗船", "法师塔", "野蛮角斗场", "火焰塔", "狗头人世界", "冰霜骑士团"],
            regions=[2, 3, 5, 6],
        )
        if res:
            touch(res["center"])
            sleep(CLICK_INTERVAL)
            find_text_and_click("领取", regions=[6])
            res = find_text("上缴", regions=[5])
            if res:
                for _ in range(5):
                    touch(res["center"])
                    sleep(CLICK_INTERVAL)
            find_text_and_click("领取", regions=[9])
            find_text_and_click("兑换", regions=[9])

            # 兑换随从碎片
            buttons = _container.game_actions.find_all().equals("兑换")
            try:
                for button in buttons:
                    button.click()
                    _container.game_actions.find_all(regions=[5]).equals("确定").first().click()
                    if find_text_and_click_safe("确定", regions=[5], timeout=3):
                        send_bark_notification("兑换碎片成功", "兑换成功, 请立即检查")
            except Exception as e:
                self.logger.error(f"❌ 兑换碎片失败: {e}")
                send_bark_notification("兑换碎片失败", "兑换失败, 请立即检查")
        back_to_main()

    def _collect_idle_rewards(self):
        self.logger.info("📦 开始领取每日挂机奖励")
        back_to_main()
        try:
            res = switch_to("战斗")
            assert res
            touch((res["center"][0], res["center"][1] + DAILY_REWARD_BOX_OFFSET_Y))
            sleep(CLICK_INTERVAL)
            touch(DAILY_REWARD_CONFIRM)
            sleep(CLICK_INTERVAL)
            find_text_and_click("确定", regions=[5])
            self.logger.info("✅ 每日挂机奖励领取成功")
            self._collect_quick_afk()
            back_to_main()
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到战斗按钮或点击失败: {e}")
            raise

    def _close_ads(self):
        self.logger.info("点击广告")
        sleep(40)
        touch((654, 114))

    def _collect_quick_afk(self):
        self.logger.info("⚡ 开始快速挂机领取")
        if find_text_and_click_safe("快速挂机", regions=[4, 5, 6, 7, 8, 9]):
            if self.config_loader and self.config_loader.is_quick_afk_enabled():
                for _ in range(10):
                    touch(QUICK_AFK_COLLECT_BUTTON)
                    sleep(1)
            else:
                for _ in range(3):
                    touch(QUICK_AFK_COLLECT_BUTTON)
                    self._close_ads()
                    sleep(3)
            self.logger.info("✅ 快速挂机领取完成")
        else:
            self.logger.warning("⚠️ 未找到快速挂机按钮")

    def _buy_ads_items(self):
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
                touch((362, 783))
                self._close_ads()
                sleep(3)
                click_back()
                sleep(150)
        back_to_main()
        self.logger.info("✅ 购买广告商品成功")

    def _handle_retinue_deployment(self):
        self.logger.info("👥 开始处理随从派遣")
        back_to_main()
        if find_text_and_click_safe("随从", regions=[7]):
            find_text_and_click("派遣", regions=[8])
            touch(ONE_KEY_REWARD)
            back_to_main()
            find_text_and_click("派遣", regions=[8])
            touch(ONE_KEY_DEPLOY)
            sleep(1)
            touch(DEPLOY_CONFIRM_BUTTON)
            back_to_main()
            self.logger.info("✅ 随从派遣处理完成")
            back_to_main()
        else:
            self.logger.warning("⚠️ 未找到随从按钮，跳过派遣操作")

        find_text_and_click("酒馆", regions=[7])
        res = find_text("招募10次", regions=[8, 9], occurrence=LAST_OCCURRENCE, raise_exception=False, use_cache=False)
        if res:
            for _ in range(4):
                touch(res["center"])
                sleep(1)
        back_to_main()

        find_text_and_click("符文", regions=[9])
        find_text_and_click_safe("抽取十次", regions=[8, 9], use_cache=False)
        back_to_main()

    def _collect_free_dungeons(self):
        self.logger.info("🏰 开始领取每日免费地下城")
        back_to_main()
        open_map()
        if find_text_and_click_safe("试炼塔", regions=[9]):
            self.logger.info("✅ 进入试炼塔")
            self._sweep_tower_floor("刻印", regions=[7, 8])
            self._sweep_tower_floor("宝石", regions=[8, 8])
            self._sweep_tower_floor("雕文", regions=[9, 8])
            self.logger.info("✅ 每日免费地下城领取完成")
        else:
            self.logger.warning("⚠️ 未找到试炼塔，跳过免费地下城领取")
        back_to_main()

    def _sweep_tower_floor(self, floor_name: str, regions):
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
                touch((359, 879))
            back_to_main()
            find_text_and_click("宝库", regions=[9])
            find_text_and_click(chest_name, regions=[4, 5, 6, 7, 8])
            touch((359, 879))
            back_to_main()
            self.logger.info("✅ 打开宝箱成功")
        except Exception as e:
            self.logger.warning(f"⚠️ 未找到宝箱: {e}")
            back_to_main()

    def _receive_mails(self):
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


# ====== 核心业务函数 ======

def focus_and_click_dungeon(dungeon_name: str, zone_name: str, max_attempts: int = 2) -> bool:
    """尝试聚焦到指定副本并点击"""
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
        logger.warning(f"⚠️ 未能找到副本: {dungeon_name} (第 {attempt + 1}/{max_attempts} 次尝试)")
        if attempt < max_attempts - 1:
            logger.info("🔄 重新打开地图并刷新区域后再试")
            open_map()
            if not switch_to_zone(zone_name):
                logger.warning(f"⚠️ 刷新区域失败: {zone_name}")
                continue
            sleep(1)
    return False


def process_dungeon(
    dungeon_name: str,
    zone_name: str,
    index: int,
    total: int,
    db: DungeonProgressDB,
    completed_dungeons: int = 0,
    remaining_dungeons: int = 0,
    state_machine: Optional[DungeonStateMachine] = None,
) -> bool:
    """处理单个副本"""
    logger.info(f"\n🎯 [{index}/{total}] 处理副本: {dungeon_name}")

    if state_machine is None:
        logger.error("❌ 状态机未初始化，无法处理副本")
        return False

    if not state_machine.prepare_dungeon_state(
        zone_name=zone_name, dungeon_name=dungeon_name, max_attempts=3
    ):
        state_machine.ensure_main()
        return False

    battle_started = state_machine.start_battle_state(
        dungeon_name=dungeon_name,
        completed_dungeons=completed_dungeons,
        total_dungeons=remaining_dungeons,
    )

    if not battle_started:
        logger.warning("⚠️ 无免费按钮，标记为已完成")
        db.mark_dungeon_completed(zone_name, dungeon_name)
        click_back()
        state_machine.return_to_main_state()
        return True

    logger.info(f"✅ 完成: {dungeon_name}")
    state_machine.complete_battle_state()
    db.mark_dungeon_completed(zone_name, dungeon_name)
    sleep(CLICK_INTERVAL)
    state_machine.return_to_main_state()
    return True


def daily_collect() -> bool:
    """领取每日挂机奖励"""
    if _container.config_loader is None:
        raise RuntimeError("配置加载器未初始化，无法执行每日收集")

    config_name = _container.config_loader.get_config_name() or "default"

    with DungeonProgressDB(config_name=config_name) as db:
        if db.is_daily_collect_completed():
            logger.info("⏭️ 今日每日收集已完成，跳过重复执行")
            return False

        manager = DailyCollectManager(_container.config_loader, db)
        manager.collect_daily_rewards()
        db.mark_daily_collect_completed()
        logger.info("💾 已记录今日每日收集完成")
        return True


def count_remaining_selected_dungeons(db: DungeonProgressDB) -> int:
    """统计未完成的选定副本数量"""
    zone_dungeons = _container.config_loader.get_zone_dungeons() if _container.config_loader else None
    if zone_dungeons is None:
        logger.warning("⚠️ 配置未初始化，无法计算剩余副本")
        return 0

    remaining = 0
    for zone_name, dungeons in zone_dungeons.items():
        for dungeon_dict in dungeons:
            if not dungeon_dict.get("selected", True):
                continue
            if not db.is_dungeon_completed(zone_name, dungeon_dict["name"]):
                remaining += 1
    return remaining


def show_progress_statistics(db: DungeonProgressDB) -> Tuple[int, int, int]:
    """显示进度统计信息"""
    db.cleanup_old_records(days_to_keep=7)

    completed_count = db.get_today_completed_count()
    if completed_count > 0:
        logger.info(f"📊 今天已通关 {completed_count} 个副本")
        completed_dungeons = db.get_today_completed_dungeons()
        for zone, dungeon in completed_dungeons[:5]:
            logger.info(f"  ✅ {zone} - {dungeon}")
        if len(completed_dungeons) > 5:
            logger.info(f"  ... 还有 {len(completed_dungeons) - 5} 个")
        logger.info("")

    zone_dungeons = _container.config_loader.get_zone_dungeons() if _container.config_loader else {}
    total_selected_dungeons = sum(
        sum(1 for d in dungeons if d.get("selected", True))
        for dungeons in zone_dungeons.values()
    )
    total_dungeons = sum(len(dungeons) for dungeons in zone_dungeons.values())

    remaining_dungeons_detail = []
    for zone_name, dungeons in zone_dungeons.items():
        for dungeon in dungeons:
            if not dungeon.get("selected", True):
                continue
            if not db.is_dungeon_completed(zone_name, dungeon["name"]):
                remaining_dungeons_detail.append((zone_name, dungeon["name"]))

    logger.info(f"📊 总计: {len(zone_dungeons)} 个区域, {total_dungeons} 个副本")
    logger.info(f"📊 选定: {total_selected_dungeons} 个副本")
    logger.info(f"📊 已完成: {completed_count} 个副本")

    if completed_count >= total_selected_dungeons:
        logger.info("\n" + "=" * 60)
        logger.info("🎉 今天所有选定的副本都已完成！")
        logger.info("=" * 60)
        logger.info("💤 无需执行任何操作，脚本退出")
        return completed_count, total_selected_dungeons, total_dungeons

    remaining = len(remaining_dungeons_detail)
    logger.info(f"📊 剩余: {remaining} 个副本待通关")
    if remaining_dungeons_detail:
        logger.info("📋 待通关副本清单:")
        for zone_name, dungeon_name in remaining_dungeons_detail:
            logger.info(f"  • {zone_name} - {dungeon_name}")
    logger.info("")

    return completed_count, total_selected_dungeons, total_dungeons


def run_dungeon_traversal(db: DungeonProgressDB, total_dungeons: int, state_machine: DungeonStateMachine) -> int:
    """执行副本遍历主循环"""
    if _container.config_loader is None or state_machine is None:
        logger.error("❌ 配置未初始化")
        return 0

    zone_dungeons = _container.config_loader.get_zone_dungeons()
    if zone_dungeons is None:
        logger.error("❌ 区域副本配置未初始化")
        return 0

    dungeon_index = 0
    processed_dungeons = 0
    remaining_dungeons = count_remaining_selected_dungeons(db)

    logger.info(f"📊 需要完成的副本总数: {remaining_dungeons}")
    completed_today = db.get_today_completed_count()
    logger.info(f"📊 今天已完成的副本数: {completed_today}")

    state_machine.ensure_main()

    for zone_idx, (zone_name, dungeons) in enumerate(zone_dungeons.items(), 1):
        logger.info(f"\n{'#' * 60}")
        logger.info(f"# 🌍 [{zone_idx}/{len(zone_dungeons)}] 区域: {zone_name}")
        logger.info(f"# 🎯 副本数: {len(dungeons)}")
        logger.info(f"{'#' * 60}")

        for dungeon_dict in dungeons:
            if check_stop_signal():
                logger.info(f"\n📊 统计: 本次运行完成 {processed_dungeons} 个副本")
                logger.info("👋 已停止执行")
                state_machine.ensure_main()
                return processed_dungeons

            dungeon_name = dungeon_dict["name"]
            is_selected = dungeon_dict["selected"]
            dungeon_index += 1

            if not is_selected:
                logger.info(f"⏭️ [{dungeon_index}/{total_dungeons}] 未选定，跳过: {dungeon_name}")
                continue

            if db.is_dungeon_completed(zone_name, dungeon_name):
                logger.info(f"⏭️ [{dungeon_index}/{total_dungeons}] 已通关，跳过: {dungeon_name}")
                continue

            if process_dungeon(
                dungeon_name,
                zone_name,
                dungeon_index,
                total_dungeons,
                db,
                completed_today + processed_dungeons,
                remaining_dungeons,
                state_machine=state_machine,
            ):
                processed_dungeons += 1
                if processed_dungeons % 3 == 0:
                    if state_machine.sell_loot():
                        state_machine.finish_sell_loot()
                    else:
                        sell_trashes()
                        back_to_main()
                        state_machine.ensure_main()

        logger.info(f"\n✅ 完成区域: {zone_name}")

    return processed_dungeons


# ====== 命令行参数解析 ======

def parse_arguments():
    """解析命令行参数"""
    import argparse

    parser = argparse.ArgumentParser(description="副本自动遍历脚本")
    parser.add_argument("-c", "--config", type=str, default="configs/default.json", help="配置文件路径")
    parser.add_argument("--load-account", type=str, help="加载指定账号后退出")
    parser.add_argument("--emulator", type=str, help="指定模拟器网络地址")
    parser.add_argument("--memlog", action="store_true", help="启用内存监控日志")
    parser.add_argument("--low-mem", action="store_true", help="启用低内存模式")
    parser.add_argument("-e", "--env", type=str, action="append", dest="env_overrides", help="环境变量覆盖")
    parser.add_argument("--max-iterations", type=int, default=1, help="限制副本遍历的最大轮数")
    return parser.parse_args()


def apply_env_overrides(env_overrides: List[str]) -> Dict[str, Any]:
    """应用命令行环境变量覆盖"""
    overrides = {}
    if not env_overrides:
        return overrides

    for override in env_overrides:
        if "=" not in override:
            logger.warning(f"⚠️ 无效的环境变量格式: {override}，应为 key=value")
            continue
        key, value = override.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value.lower() == "true":
            overrides[key] = True
        elif value.lower() == "false":
            overrides[key] = False
        elif value.isdigit():
            overrides[key] = int(value)
        else:
            overrides[key] = value

        logger.info(f"📝 环境变量覆盖: {key} = {overrides[key]}")

    return overrides


def handle_load_account_mode(account_name: str, emulator_name: Optional[str] = None, low_mem: bool = False):
    """处理账号加载模式"""
    logger.info("\n" + "=" * 60)
    logger.info("🔄 账号加载模式")
    logger.info("=" * 60 + "\n")
    logger.info(f"📱 目标账号: {account_name}")

    try:
        device_manager = DeviceManager(emulator_name, low_mem)
        device_manager.initialize()
    except Exception as e:
        logger.error(f"❌ {e}")
        send_bark_notification(
            "副本助手 - 错误",
            f"模拟器 {emulator_name} 未运行或未连接",
            level="timeSensitive",
        )
        sys.exit(1)

    try:
        switch_account(account_name)
        logger.info(f"✅ 成功加载账号: {account_name}")
        logger.info("=" * 60 + "\n")
    except Exception as e:
        logger.error(f"❌ 加载账号失败: {e}")
        sys.exit(1)


def initialize_configs(config_path: str, env_overrides: Optional[List[str]] = None):
    """初始化系统配置和用户配置"""
    # 加载系统配置
    try:
        _container.system_config = load_system_config()
    except Exception as e:
        logger.warning(f"⚠️ 加载系统配置失败: {e}，使用默认配置")
        _container.system_config = None

    # 加载用户配置
    try:
        from config_loader import load_config

        _container.config_loader = load_config(config_path)
        _container.config_name = _container.config_loader.get_config_name()

        # 重新初始化日志
        new_logger = setup_logger_from_config(use_color=True)
        globals()['logger'] = new_logger

        # 更新全局日志上下文
        from logger_config import update_log_context

        update_log_context({"config": _container.config_name})

        # 应用环境变量覆盖
        if env_overrides:
            overrides = apply_env_overrides(env_overrides)
            for key, value in overrides.items():
                if hasattr(_container.config_loader, key):
                    logger.info(f"🔄 覆盖配置: {key} = {value}")
                    setattr(_container.config_loader, key, value)
                else:
                    logger.warning(f"⚠️ 配置中不存在属性: {key}")

    except Exception as e:
        logger.error(f"❌ 加载配置失败: {e}")
        sys.exit(1)


def attach_file_logger(emulator_name: str):
    """附加文件日志处理器"""
    from logger_config import attach_emulator_file_handler

    try:
        attach_emulator_file_handler(
            emulator_name=emulator_name or "unknown",
            config_name=_container.config_name or "unknown",
            log_dir="log",
            level="DEBUG",
        )
    except Exception as e:
        logger.warning(f"⚠️ 初始化文件日志处理器失败: {e}")


def start_error_monitor():
    """启动错误对话框监控器"""
    _container.error_dialog_monitor = ErrorDialogMonitor(logger)
    _container.error_dialog_monitor.start()


def stop_error_monitor():
    """停止错误对话框监控器"""
    if _container.error_dialog_monitor:
        _container.error_dialog_monitor.stop()
        _container.error_dialog_monitor = None


# ====== 主函数 ======

def main():
    """主函数"""
    args = parse_arguments()

    if not args.load_account:
        logger.info("\n" + "=" * 60)
        logger.info("🎮 副本自动遍历脚本")
        logger.info("=" * 60 + "\n")

    if args.memlog:
        try:
            from memory_monitor import start_memory_monitor

            start_memory_monitor(logger, interval_sec=10.0, enable_tracemalloc=True)
            logger.info("已启用内存监控")
        except Exception as e:
            logger.warning(f"启用内存监控失败: {e}")

    attach_file_logger(args.emulator)

    # 处理加载账号模式
    if args.load_account:
        handle_load_account_mode(args.load_account, args.emulator, low_mem=args.low_mem)
        return

    # 初始化配置
    initialize_configs(args.config, args.env_overrides)

    if _container.config_loader is None:
        logger.error("❌ 配置加载器未初始化")
        sys.exit(1)

    with DungeonProgressDB(config_name=_container.config_loader.get_config_name()) as db:
        completed_count, total_selected, total = show_progress_statistics(db)

        daily_collect_finished = db.is_daily_collect_completed()
        daily_collect_enabled = _container.config_loader.is_daily_collect_enabled()

        if completed_count >= total_selected and (not daily_collect_enabled or daily_collect_finished):
            logger.info("✅ 无需启动模拟器，脚本退出")
            return

    # 初始化设备
    device_manager = DeviceManager(args.emulator, args.low_mem)
    device_manager.initialize()

    state_machine = DungeonStateMachine()

    # 启动游戏
    logger.info("关闭游戏...")
    stop_app("com.ms.ysjyzr")
    sleep(2, "关闭游戏")

    logger.info("启动游戏")
    start_app("com.ms.ysjyzr")

    # 等待进入角色选择界面
    if is_on_character_selection(120):
        logger.info("已在角色选择界面")

    # 选择角色
    char_class = _container.config_loader.get_char_class()
    if char_class:
        logger.info(f"开始选择角色: {char_class}")
        state_machine.select_character_state(char_class=char_class)
    else:
        logger.info("⚠️ 未配置角色职业，跳过角色选择")
        state_machine.ensure_main()

    # 执行每日收集
    if _container.config_loader.is_daily_collect_enabled():
        logger.info("🚀 检查每日收集任务")
        if state_machine.claim_daily_rewards():
            state_machine.return_to_main_state()

    # 执行副本遍历
    with DungeonProgressDB(config_name=_container.config_loader.get_config_name()) as db:
        iteration = 1
        max_iterations = args.max_iterations or 1

        while iteration <= max_iterations:
            logger.info(f"\n🔁 开始第 {iteration} 轮副本遍历…")
            run_dungeon_traversal(db, total, state_machine)

            remaining = count_remaining_selected_dungeons(db)
            if remaining <= 0:
                break

            logger.warning(f"⚠️ 第 {iteration} 轮结束后仍有 {remaining} 个副本未完成，准备继续")
            iteration += 1

        if iteration > max_iterations:
            remaining = count_remaining_selected_dungeons(db)
            if remaining > 0:
                logger.warning(
                    f"⚠️ 已达到最大轮数 {max_iterations}，仍有 {remaining} 个副本未完成；为避免卡住已优雅退出"
                )

        logger.info("\n" + "=" * 60)
        logger.info(f"🎉 全部完成！今天共通关 {db.get_today_completed_count()} 个副本")
        logger.info("=" * 60 + "\n")
        state_machine.ensure_main()


def main_wrapper():
    """主函数包装器 - 处理超时和重启逻辑"""
    global logger

    max_restarts = 10
    restart_count = 0

    while restart_count < max_restarts:
        try:
            start_error_monitor()
            main()
            return

        except TimeoutError as e:
            restart_count += 1
            logger.error(f"\n❌ 检测到超时错误: {e}")
            logger.error("⏱️ 操作超时，可能是网络错误或识别失败导致的卡死")
            airtest_log("超时错误" + str(e), snapshot=True)

            if restart_count < max_restarts:
                logger.warning(f"\n🔄 正在重启程序... (第 {restart_count}/{max_restarts} 次重启)")
                send_bark_notification(
                    "副本助手 - 超时重启",
                    f"程序因超时重启 ({restart_count}/{max_restarts})",
                    level="timeSensitive",
                )
                _container.reset()
                time.sleep(5)
                continue
            else:
                logger.error(f"\n❌ 已达到最大重启次数 ({max_restarts})，程序退出")
                send_bark_notification(
                    "副本助手 - 严重错误",
                    "程序因多次超时失败退出",
                    level="timeSensitive",
                )
                sys.exit(1)

        except KeyboardInterrupt:
            logger.info("\n\n⛔ 用户中断，程序退出")
            sys.exit(0)

        except Exception as e:
            import traceback

            logger.error(f"\n❌ 发生未预期的错误: {e}")
            error_traceback = traceback.format_exc()
            logger.error(error_traceback)
            logger.critical(f"脚本异常退出: {type(e).__name__}: {str(e)}\n{error_traceback}")
            send_bark_notification(
                "副本助手 - 错误", f"程序发生错误: {str(e)}", level="timeSensitive"
            )
            sys.exit(1)

        finally:
            stop_error_monitor()


# ====== 日志切面 ======

def setup_logging_slices():
    """设置日志切面"""
    from logger_config import apply_logging_slice

    apply_logging_slice(
        [
            (sys.modules[__name__], "find_text"),
            (sys.modules[__name__], "text_exists"),
            (sys.modules[__name__], "find_text_and_click"),
            (sys.modules[__name__], "find_text_and_click_safe"),
            (sys.modules[__name__], "is_main_world"),
            (sys.modules[__name__], "open_map"),
            (sys.modules[__name__], "auto_combat"),
            (sys.modules[__name__], "select_character"),
            (sys.modules[__name__], "wait_for_main"),
            (sys.modules[__name__], "switch_to_zone"),
            (sys.modules[__name__], "sell_trashes"),
            (sys.modules[__name__], "switch_account"),
            (sys.modules[__name__], "back_to_main"),
            (sys.modules[__name__], "focus_and_click_dungeon"),
            (sys.modules[__name__], "process_dungeon"),
            (sys.modules[__name__], "run_dungeon_traversal"),
            (sys.modules[__name__], "initialize_configs"),
            (sys.modules[__name__], "show_progress_statistics"),
            (sys.modules[__name__], "apply_env_overrides"),
            (sys.modules[__name__], "handle_load_account_mode"),
            (sys.modules[__name__], "main_wrapper"),
            (sys.modules[__name__], "main"),
        ],
        level="DEBUG",
    )


if __name__ == "__main__":
    main_wrapper()
