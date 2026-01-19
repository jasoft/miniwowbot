"""
auto_dungeon 设备管理模块

本模块提供统一的设备连接和OCR初始化管理。
合并了原 auto_dungeon.py 中的设备初始化逻辑。
"""
import logging
import subprocess
from typing import Optional

from airtest.core.api import auto_setup, snapshot
from vibe_ocr import OCRHelper

from auto_dungeon_config import CLICK_INTERVAL
from device_utils import connect_device_with_timeout
from emulator_manager import EmulatorManager
from game_actions import GameActions
from project_paths import resolve_project_path

logger = logging.getLogger(__name__)


# 设备管理器错误


class DeviceConnectionError(Exception):
    """设备连接错误"""
    pass


class DeviceManager:
    """设备连接管理器 - 统一处理设备连接和OCR初始化"""

    def __init__(self, adb_path: Optional[str] = None):
        """
        初始化设备管理器

        Args:
            adb_path: ADB 可执行文件路径
        """
        self.emulator_manager = EmulatorManager(adb_path=adb_path)
        self.ocr_helper: Optional[OCRHelper] = None
        self.game_actions: Optional[GameActions] = None
        self.connection_string: Optional[str] = None
        self.target_emulator: Optional[str] = None

    def _normalize_emulator_name(self, name: Optional[str]) -> Optional[str]:
        """
        规范化模拟器名称输入：
        - 支持传入完整的 Airtest 连接字符串，如 'Android://127.0.0.1:5037/192.168.1.150:5555'
          将自动提取设备序列 '192.168.1.150:5555'
        - 去除首尾空白
        """
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

    def _ensure_emulator_connected(self, emulator_name: str) -> bool:
        """
        确保模拟器已连接

        Args:
            emulator_name: 模拟器名称

        Returns:
            bool: 是否连接成功
        """
        devices = self.emulator_manager.get_adb_devices()
        if emulator_name not in devices:
            logger.warning(f"⚠️ 模拟器 {emulator_name} 未运行或未连接")
            logger.info(f"   可用设备: {list(devices.keys()) if devices else '无'}")

            if self.emulator_manager.ensure_device_connected(emulator_name):
                logger.info(f"✅ 已通过 adb connect 确认连接: {emulator_name}")
                return True
            else:
                return False
        else:
            logger.info(f"✅ 模拟器 {emulator_name} 已在设备列表中")
            return True

    def _get_connection_string(self, emulator_name: Optional[str] = None) -> str:
        """
        获取设备连接字符串

        Args:
            emulator_name: 模拟器名称

        Returns:
            str: 连接字符串
        """
        if emulator_name:
            return self.emulator_manager.get_emulator_connection_string(emulator_name)
        return "Android:///"

    def _connect_device(self, connection_string: str) -> bool:
        """
        连接设备

        Args:
            connection_string: 连接字符串

        Returns:
            bool: 是否连接成功
        """
        try:
            auto_setup(__file__)
            logger.info("自动配置设备中...")
            if connection_string:
                connect_device_with_timeout(connection_string, timeout=30)
            logger.info("   ✅ 成功连接到设备")
            return True
        except TimeoutError:
            raise  # 抛出让主循环处理重试
        except Exception as e:
            logger.error(f"   ❌ 连接设备失败: {e}")
            return False

    def _retry_connection(self, connection_string: str) -> bool:
        """
        重试连接设备

        Args:
            connection_string: 连接字符串

        Returns:
            bool: 是否重试成功
        """
        try:
            logger.warning("🔁 尝试重置 ADB 并重新连接设备…")
            if self.emulator_manager.adb_path:
                subprocess.run(
                    [self.emulator_manager.adb_path, "kill-server"],
                    timeout=5,
                    capture_output=True,
                )
                subprocess.run(
                    [self.emulator_manager.adb_path, "start-server"],
                    timeout=10,
                    capture_output=True,
                )
                self.emulator_manager.ensure_adb_connection()
                if connection_string:
                    connect_device_with_timeout(connection_string, timeout=30)
                logger.info("   ✅ 重试连接成功")
                return True
            else:
                logger.error("   ❌ EmulatorManager 未正确初始化")
                return False
        except subprocess.TimeoutExpired:
            logger.error("   ❌ ADB 命令超时")
            return False
        except TimeoutError:
            raise  # 抛出让主循环处理重试
        except Exception as retry_err:
            logger.error(f"   ❌ 重试连接失败: {retry_err}")
            return False

    def initialize(
        self,
        emulator_name: Optional[str] = None,
        low_mem: bool = False,
        correction_map: Optional[dict] = None,
    ) -> None:
        """
        统一初始化设备和OCR

        Args:
            emulator_name: 模拟器网络地址，如 '127.0.0.1:5555'
            low_mem: 是否使用低内存模式
            correction_map: OCR 纠错映射表
        """
        # 规范化模拟器名称
        if emulator_name:
            normalized_name = self._normalize_emulator_name(emulator_name)
            if normalized_name is None:
                raise DeviceConnectionError("❌ 模拟器名称规范化失败")
            self.target_emulator = normalized_name
            emulator_name = normalized_name

            # 确保模拟器已连接
            if not self._ensure_emulator_connected(emulator_name):
                raise DeviceConnectionError(
                    f"模拟器 {emulator_name} 未运行或未连接"
                )

            self.connection_string = self._get_connection_string(emulator_name)
            logger.info(f"📱 连接到模拟器: {emulator_name}")
            logger.info(f"   连接字符串: {self.connection_string}")
        else:
            self.connection_string = "Android:///"
            logger.info("📱 使用默认连接字符串")

        # 连接设备
        if not self._connect_device(self.connection_string):
            # 尝试重连
            if not self._retry_connection(self.connection_string):
                raise DeviceConnectionError("无法连接到设备")

        # 初始化 OCR
        self.ocr_helper = OCRHelper(
            output_dir="output",
            max_cache_size=50 if low_mem else 200,
            max_width=640 if low_mem else 960,
            delete_temp_screenshots=True,
            correction_map=correction_map,
            snapshot_func=snapshot,
        )
        logger.info("✅ OCR 助手初始化完成")

        # 初始化 GameActions
        self.game_actions = GameActions(self.ocr_helper, click_interval=CLICK_INTERVAL)
        logger.info("✅ 游戏动作助手初始化完成")

    def get_ocr_helper(self) -> OCRHelper:
        """获取 OCR 助手"""
        if self.ocr_helper is None:
            raise RuntimeError("OCR 助手未初始化，请先调用 initialize()")
        return self.ocr_helper

    def get_game_actions(self) -> GameActions:
        """获取游戏动作助手"""
        if self.game_actions is None:
            raise RuntimeError("游戏动作助手未初始化，请先调用 initialize()")
        return self.game_actions

    def get_target_emulator(self) -> Optional[str]:
        """获取目标模拟器名称"""
        return self.target_emulator


def create_device_manager(
    emulator_name: Optional[str] = None,
    low_mem: bool = False,
    config_loader=None,
) -> DeviceManager:
    """
    创建设备管理器的便捷函数

    Args:
        emulator_name: 模拟器网络地址
        low_mem: 是否使用低内存模式
        config_loader: 配置加载器（用于获取 OCR 纠错映射表）

    Returns:
        DeviceManager: 设备管理器实例
    """
    correction_map = None
    if config_loader:
        correction_map = config_loader.get_ocr_correction_map()

    device_manager = DeviceManager()
    device_manager.initialize(emulator_name, low_mem, correction_map)
    return device_manager
