"""
设备管理模块

提供统一的设备连接和OCR初始化管理。
DeviceManager 负责组合 EmulatorConnectionManager 和设备初始化（OCR、GameActions）。
"""

from __future__ import annotations

import os
from typing import Optional

from airtest.core.api import auto_setup, connect_device, snapshot
from vibe_ocr import OCRHelper

from auto_dungeon_config import CLICK_INTERVAL
from emulator_manager import (
    EmulatorConnectionManager,
    EmulatorConnectionError,
    create_connection_manager,
)
from game_actions import GameActions
from logger_config import setup_logger_from_config
from project_paths import ensure_project_path

logger = setup_logger_from_config(use_color=True)


class DeviceManager:
    """
    设备管理器

    职责：
    1. 使用 EmulatorConnectionManager 检测 ADB 连接
    2. 初始化 OCRHelper
    3. 初始化 GameActions

    这样职责分离：
    - EmulatorConnectionManager 只负责 ADB 连接检测
    - DeviceManager 负责设备相关的完整初始化
    """

    def __init__(self, config_file: str = "system_config.json"):
        """
        初始化设备管理器

        Args:
            config_file: 系统配置文件路径
        """
        self.config_file = str(ensure_project_path(config_file))
        self.connection_manager = EmulatorConnectionManager(
            start_cmd=self._load_emulator_start_cmd()
        )

        # 初始化状态
        self.ocr_helper: Optional[OCRHelper] = None
        self.game_actions: Optional[GameActions] = None
        self._emulator_name: Optional[str] = None

    def initialize(
        self,
        emulator_name: Optional[str] = None,
        correction_map: Optional[dict] = None,
    ) -> None:
        """
        初始化设备（连接模拟器、OCR、GameActions）

        Args:
            emulator_name: 模拟器地址，如 '192.168.1.150:5555'
            correction_map: OCR 纠错映射表

        Raises:
            EmulatorConnectionError: 连接失败
        """
        # 规范化模拟器地址并连接
        if emulator_name:
            emulator_name = self.connection_manager._normalize_emulator(emulator_name)
            self._emulator_name = emulator_name
            self.connection_manager.target_emulator = emulator_name
            self.connection_manager.connection_string = f"Android://127.0.0.1:5037/{emulator_name}"

            # 确保模拟器已连接
            if not self.connection_manager.ensure_connected(emulator_name):
                raise EmulatorConnectionError(f"无法连接模拟器: {emulator_name}")

            # 连接 Airtest 设备
            connection_string = self.connection_manager.connection_string
            logger.info(f"[Device] 连接设备: {connection_string}")
            try:
                auto_setup(__file__)
                connect_device(connection_string)
                logger.info("[Device] 设备连接成功")
            except Exception as exc:
                raise EmulatorConnectionError(f"设备连接失败: {exc}")
        else:
            self.connection_manager.connection_string = "Android:///"
            auto_setup(__file__)

        # 初始化 OCR
        self.ocr_helper = OCRHelper(
            output_dir="output",
            max_cache_size=200,
            max_width=960,
            delete_temp_screenshots=True,
            correction_map=correction_map,
            snapshot_func=snapshot,
        )
        logger.info("[OCR] 初始化完成")

        # 初始化 GameActions
        self.game_actions = GameActions(self.ocr_helper, click_interval=CLICK_INTERVAL)
        logger.info("[GameActions] 初始化完成")

    def get_ocr_helper(self) -> OCRHelper:
        """获取 OCR 助手"""
        if self.ocr_helper is None:
            raise EmulatorConnectionError("OCR 未初始化，请先调用 initialize()")
        return self.ocr_helper

    def get_game_actions(self) -> GameActions:
        """获取游戏动作助手"""
        if self.game_actions is None:
            raise EmulatorConnectionError("GameActions 未初始化，请先调用 initialize()")
        return self.game_actions

    def get_target_emulator(self) -> Optional[str]:
        """获取目标模拟器地址"""
        return self._emulator_name

    @property
    def emulator_manager(self) -> EmulatorConnectionManager:
        """返回内部连接管理器"""
        return self.connection_manager

    def _load_emulator_start_cmd(self) -> Optional[str]:
        """从环境变量中读取模拟器启动命令"""
        self._load_env()
        start_cmd = os.environ.get("EMULATOR_START_CMD")
        if start_cmd:
            logger.info(f"[Device] 读取到模拟器启动命令: {start_cmd}")
        else:
            logger.warning("[Device] 未配置 EMULATOR_START_CMD，自动启动不可用")
        return start_cmd

    def _load_env(self) -> None:
        """加载 .env 环境变量（尽量避免额外依赖）"""
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv()
            return
        except Exception as exc:
            logger.debug(f"[Device] dotenv 不可用，尝试解析 .env: {exc}")

        env_path = ensure_project_path(".env")
        if not os.path.exists(env_path):
            return
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
        except Exception as exc:
            logger.debug(f"[Device] 解析 .env 失败: {exc}")


# 向后兼容的别名
EmulatorManager = DeviceManager
DeviceConnectionError = EmulatorConnectionError
create_device_manager = DeviceManager


__all__ = [
    "DeviceManager",
    "EmulatorManager",
    "EmulatorConnectionManager",
    "EmulatorConnectionError",
    "DeviceConnectionError",
    "create_device_manager",
    "create_connection_manager",
]
