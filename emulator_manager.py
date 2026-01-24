"""
简化的模拟器管理器

统一管理模拟器连接、启动和设备初始化。
从 system_config.json 读取启动命令，提供简洁的接口获取可用的模拟器连接。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from shutil import which
from typing import Optional

from airtest.core.api import auto_setup, connect_device, snapshot
from vibe_ocr import OCRHelper

from auto_dungeon_config import CLICK_INTERVAL
from game_actions import GameActions
from logger_config import setup_logger_from_config
from project_paths import ensure_project_path

logger = setup_logger_from_config(use_color=True)


class EmulatorError(Exception):
    """模拟器相关错误"""
    pass


class EmulatorManager:
    """模拟器管理器 - 统一处理设备连接和OCR初始化"""

    def __init__(self, config_file: str = "system_config.json"):
        """
        初始化模拟器管理器

        Args:
            config_file: 系统配置文件路径
        """
        self.config_file = str(ensure_project_path(config_file))
        self.adb_path = self._resolve_adb_path()
        self.start_cmd = self._load_start_cmd()

        # 初始化状态
        self.target_emulator: Optional[str] = None
        self.connection_string: Optional[str] = None
        self.ocr_helper: Optional[OCRHelper] = None
        self.game_actions: Optional[GameActions] = None

    def _resolve_adb_path(self) -> str:
        """解析 ADB 路径"""
        adb_name = "adb.exe" if os.name == "nt" else "adb"
        adb_path = which(adb_name)
        if adb_path:
            logger.info(f"[ADB] 使用系统 ADB: {adb_path}")
            return adb_path
        logger.warning("[ADB] 未找到 ADB，使用默认命令")
        return "adb"

    def _load_start_cmd(self) -> Optional[str]:
        """从配置文件加载启动命令"""
        if not os.path.exists(self.config_file):
            logger.warning(f"[Config] 配置文件不存在: {self.config_file}")
            return None
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            start_cmd = config.get("emulators", {}).get("startCmd")
            if not start_cmd:
                logger.warning("[Config] 未配置 emulators.startCmd")
                return None
            logger.info(f"[Config] 加载启动命令: {start_cmd}")
            return str(start_cmd)
        except Exception as exc:
            logger.error(f"[Config] 读取配置失败: {exc}")
            return None

    def _run_start_cmd(self) -> bool:
        """执行启动命令"""
        if not self.start_cmd:
            logger.error("[Start] 未配置启动命令")
            return False
        try:
            logger.info(f"[Start] 执行: {self.start_cmd}")
            subprocess.Popen(
                self.start_cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as exc:
            logger.error(f"[Start] 执行失败: {exc}")
            return False

    def _connect_airtest(self, conn_str: str, timeout: int = 30) -> None:
        """使用超时机制连接 Airtest 设备"""
        result = {"success": False, "error": None}

        def connect():
            try:
                auto_setup(__file__)
                connect_device(conn_str)
                result["success"] = True
            except Exception as e:
                result["error"] = e

        thread = threading.Thread(target=connect)
        thread.daemon = True
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            raise EmulatorError(f"连接设备超时 ({timeout}秒)")
        if result["error"]:
            raise result["error"]

    # ==================== 设备列表操作 ====================

    def get_devices(self) -> dict[str, str]:
        """获取已连接的 ADB 设备列表"""
        try:
            result = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.error(f"[ADB] devices 失败: {result.stderr}")
                return {}
            devices = {}
            for line in result.stdout.strip().split("\n")[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        devices[parts[0]] = parts[1]
            return devices
        except Exception as exc:
            logger.error(f"[ADB] 获取设备列表失败: {exc}")
            return {}

    def is_connected(self, emulator: str) -> bool:
        """检查模拟器是否已连接"""
        devices = self.get_devices()
        return emulator in devices and devices[emulator] == "device"

    def connect(self, emulator: str) -> bool:
        """尝试通过 adb connect 连接模拟器"""
        try:
            result = subprocess.run(
                [self.adb_path, "connect", emulator],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.warning(f"[ADB] 连接失败: {result.stdout.strip()}")
                return False
            output = result.stdout.strip().lower()
            if "connected" in output or "already connected" in output:
                logger.info(f"[ADB] 已连接: {emulator}")
                return True
            logger.warning(f"[ADB] 连接失败: {result.stdout.strip()}")
            return False
        except Exception as exc:
            logger.warning(f"[ADB] 连接异常: {exc}")
            return False

    # ==================== 模拟器生命周期 ====================

    def ensure_connected(self, emulator: str, max_retries: int = 3) -> bool:
        """
        确保模拟器已连接

        Args:
            emulator: 模拟器地址，如 '192.168.1.150:5555'
            max_retries: 最大重试次数

        Returns:
            bool: 连接成功返回 True
        """
        # 快速检查是否已连接
        if self.is_connected(emulator):
            logger.info(f"[Emulator] {emulator} 已连接")
            return True

        # 尝试直接连接
        for attempt in range(max_retries):
            logger.info(f"[Emulator] 第 {attempt + 1}/{max_retries} 次尝试连接 {emulator}")

            if self.connect(emulator):
                # 验证连接
                if self.is_connected(emulator):
                    logger.info(f"[Emulator] {emulator} 连接验证成功")
                    return True

            # 如果还有重试次数，尝试启动模拟器
            if attempt < max_retries - 1:
                if self.start_cmd:
                    logger.info("[Emulator] 连接失败，尝试启动模拟器...")
                    self._run_start_cmd()
                    wait_time = (attempt + 1) * 10
                    logger.info(f"[Emulator] 等待 {wait_time} 秒...")
                    import time
                    time.sleep(wait_time)
                else:
                    import time
                    time.sleep(5)

        # 最后检查一次
        if self.is_connected(emulator):
            return True

        logger.error(f"[Emulator] 无法连接 {emulator}")
        return False

    # ==================== 初始化接口 ====================

    def initialize(
        self,
        emulator_name: Optional[str] = None,
        correction_map: Optional[dict] = None,
    ) -> None:
        """
        初始化模拟器和 OCR

        Args:
            emulator_name: 模拟器地址，如 '192.168.1.150:5555'
            correction_map: OCR 纠错映射表

        Raises:
            EmulatorError: 初始化失败
        """
        # 规范化模拟器地址
        if emulator_name:
            emulator_name = self._normalize_emulator(emulator_name)
            self.target_emulator = emulator_name
            self.connection_string = f"Android://127.0.0.1:5037/{emulator_name}"

            # 确保模拟器已连接
            if not self.ensure_connected(emulator_name):
                raise EmulatorError(f"无法连接模拟器: {emulator_name}")

            # 连接 Airtest 设备
            logger.info(f"[Device] 连接设备: {self.connection_string}")
            try:
                self._connect_airtest(self.connection_string, timeout=30)
                logger.info("[Device] 设备连接成功")
            except Exception as exc:
                raise EmulatorError(f"设备连接失败: {exc}")
        else:
            self.connection_string = "Android:///"
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

    def _normalize_emulator(self, name: str) -> str:
        """规范化模拟器地址"""
        name = str(name).strip()
        if name.lower().startswith("android://"):
            try:
                return name.split("/")[-1].strip()
            except Exception:
                pass
        return name

    # ==================== Getter 方法 ====================

    @property
    def emulator_manager(self) -> "EmulatorManager":
        """返回自身，用于向后兼容"""
        return self

    def get_ocr(self) -> OCRHelper:
        """获取 OCR 助手"""
        if self.ocr_helper is None:
            raise EmulatorError("OCR 未初始化，请先调用 initialize()")
        return self.ocr_helper

    def get_ocr_helper(self) -> OCRHelper:
        """获取 OCR 助手（向后兼容别名）"""
        return self.get_ocr()

    def get_game_actions(self) -> GameActions:
        """获取游戏动作助手"""
        if self.game_actions is None:
            raise EmulatorError("GameActions 未初始化，请先调用 initialize()")
        return self.game_actions

    def get_target_emulator(self) -> Optional[str]:
        """获取目标模拟器地址"""
        return self.target_emulator

    def get_connection_string(self) -> Optional[str]:
        """获取连接字符串"""
        return self.connection_string


# 便捷函数
def create_emulator_manager(
    emulator: Optional[str] = None,
    correction_map: Optional[dict] = None,
) -> EmulatorManager:
    """
    创建设备管理器的便捷函数

    Args:
        emulator: 模拟器地址
        correction_map: OCR 纠错映射

    Returns:
        EmulatorManager: 初始化后的管理器
    """
    manager = EmulatorManager()
    manager.initialize(emulator, correction_map=correction_map)
    return manager


__all__ = ["EmulatorManager", "EmulatorError", "create_emulator_manager"]
