"""
模拟器连接管理器

职责：
- 检测用户要求的连接是否是一个有效的 ADB 连接
- 如果连接失败则尝试重启模拟器并等待重试
- 确保交给调用者的端口是可用的（需要用 ADB 命令测试通过）
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from shutil import which
from typing import Any, Optional, Protocol


class LoggerLike(Protocol):
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass


def _create_default_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(module)s %(filename)s:%(lineno)d - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


_DEFAULT_LOGGER = _create_default_logger()


class EmulatorConnectionError(Exception):
    """模拟器连接相关错误"""
    pass


class EmulatorConnectionManager:
    """
    模拟器连接管理器

    职责：
    1. 检测用户要求的连接是否是一个有效的 ADB 连接
    2. 如果连接失败则尝试重启模拟器并等待重试
    3. 确保交给调用者的端口是可用的（用 ADB 命令测试通过）
    """

    def __init__(
        self,
        start_cmd: Optional[str] = None,
        logger: Optional[LoggerLike] = None,
    ):
        """
        初始化模拟器连接管理器

        Args:
            start_cmd: 启动模拟器的命令行字符串
            logger: 标准 logger 接口（info/warning/debug/error），可覆盖默认格式
        """
        self.logger = logger or _DEFAULT_LOGGER
        self.adb_path = self._resolve_adb_path()
        self.start_cmd = start_cmd

        # 初始化状态
        self.target_emulator: Optional[str] = None
        self.connection_string: Optional[str] = None

    def _resolve_adb_path(self) -> str:
        """解析 ADB 路径"""
        adb_name = "adb.exe" if os.name == "nt" else "adb"
        adb_path = which(adb_name)
        if adb_path:
            self.logger.info(f"[ADB] 使用系统 ADB: {adb_path}")
            return adb_path
        self.logger.warning("[ADB] 未找到 ADB，使用默认命令")
        return "adb"

    def _run_start_cmd(self) -> bool:
        """执行启动命令"""
        if not self.start_cmd:
            self.logger.error("[Start] 未配置启动命令")
            return False
        try:
            self.logger.info(f"[Start] 执行: {self.start_cmd}")
            subprocess.Popen(
                self.start_cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as exc:
            self.logger.error(f"[Start] 执行失败: {exc}")
            return False

    # ==================== ADB 设备列表操作 ====================

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
                error_detail = result.stderr.strip() or result.stdout.strip()
                self.logger.error(f"[ADB] devices 失败: {error_detail}")
                return {}
            devices = {}
            for line in result.stdout.strip().split("\n")[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        devices[parts[0]] = parts[1]
            return devices
        except Exception as exc:
            self.logger.error(f"[ADB] 获取设备列表失败: {exc}")
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
                error_detail = result.stderr.strip() or result.stdout.strip()
                self.logger.warning(f"[ADB] 连接失败: {error_detail}")
                return False
            output = result.stdout.strip().lower()
            if "connected" in output or "already connected" in output:
                self.logger.info(f"[ADB] 已连接: {emulator}")
                return True
            error_detail = result.stderr.strip() or result.stdout.strip()
            self.logger.warning(f"[ADB] 连接失败: {error_detail}")
            return False
        except Exception as exc:
            self.logger.warning(f"[ADB] 连接异常: {exc}")
            return False

    # ==================== 模拟器连接保障 ====================

    def ensure_connected(self, emulator: str, max_retries: int = 3) -> bool:
        """
        确保模拟器已连接

        Args:
            emulator: 模拟器地址，如 '192.168.1.150:5555'
            max_retries: 最大重试次数

        Returns:
            bool: 连接成功返回 True

        Raises:
            EmulatorConnectionError: 启动命令为空或执行失败（不可恢复的错误）
        """
        # 快速检查是否已连接
        if self.is_connected(emulator):
            self.logger.info(f"[Emulator] {emulator} 已连接")
            return True

        # 尝试直接连接
        for attempt in range(max_retries):
            self.logger.info(
                f"[Emulator] 第 {attempt + 1}/{max_retries} 次尝试连接 {emulator}"
            )

            if self.connect(emulator):
                # 验证连接
                if self.is_connected(emulator):
                    self.logger.info(f"[Emulator] {emulator} 连接验证成功")
                    return True

            # 如果还有重试次数，尝试启动模拟器
            if attempt < max_retries - 1:
                if not self.start_cmd:
                    self.logger.error("[Emulator] 未配置启动模拟器命令，无法自动恢复")
                    raise EmulatorConnectionError("启动模拟器命令未配置，无法自动连接模拟器")

                self.logger.info("[Emulator] 连接失败，尝试启动模拟器...")
                if not self._run_start_cmd():
                    self.logger.error(f"[Emulator] 启动模拟器命令执行失败: {self.start_cmd}")
                    raise EmulatorConnectionError(f"无法启动模拟器: {self.start_cmd}")

                wait_time = (attempt + 1) * 10
                self.logger.info(f"[Emulator] 等待 {wait_time} 秒...")
                time.sleep(wait_time)

        # 最后检查一次
        if self.is_connected(emulator):
            return True

        self.logger.error(f"[Emulator] 无法连接 {emulator}")
        return False

    def test_connection(self, emulator: str) -> bool:
        """
        测试模拟器连接是否可用（使用 ADB 命令）

        Args:
            emulator: 模拟器地址

        Returns:
            bool: 连接可用返回 True
        """
        try:
            result = subprocess.run(
                [self.adb_path, "-s", emulator, "shell", "echo", "test"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                self.logger.info(f"[ADB] 连接测试成功: {emulator}")
                return True
            self.logger.warning(f"[ADB] 连接测试失败: {emulator}, 输出: {result.stderr}")
            return False
        except Exception as exc:
            self.logger.warning(f"[ADB] 连接测试异常: {exc}")
            return False

    def _normalize_emulator(self, name: str) -> str:
        """规范化模拟器地址"""
        name = str(name).strip()
        if name.lower().startswith("android://"):
            try:
                return name.split("/")[-1].strip()
            except Exception:
                pass
        return name

    def get_target_emulator(self) -> Optional[str]:
        """获取目标模拟器地址"""
        return self.target_emulator

    def get_connection_string(self) -> Optional[str]:
        """获取连接字符串"""
        return self.connection_string


# 向后兼容的别名
EmulatorManager = EmulatorConnectionManager


def create_connection_manager(
    emulator: Optional[str] = None,
    logger: Optional[LoggerLike] = None,
) -> EmulatorConnectionManager:
    """
    创建模拟器连接管理器的便捷函数

    Args:
        emulator: 模拟器地址
        logger: 标准 logger 接口（info/warning/debug/error），可覆盖默认格式

    Returns:
        EmulatorConnectionManager: 初始化后的管理器
    """
    manager = EmulatorConnectionManager(logger=logger)
    if emulator:
        manager.target_emulator = manager._normalize_emulator(emulator)
    return manager


__all__ = [
    "EmulatorConnectionManager",
    "EmulatorManager",
    "EmulatorConnectionError",
    "create_connection_manager",
]
