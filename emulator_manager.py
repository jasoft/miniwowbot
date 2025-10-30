# -*- encoding=utf8 -*-
"""
多模拟器管理模块
用于检测、启动和管理多个 BlueStacks 实例
"""

import subprocess
import platform
import time
import logging
import os
from typing import List, Dict, Optional

# 导入 Airtest 的 ADB 模块
try:
    from airtest.core.android.adb import ADB
except ImportError:
    ADB = None

logger = logging.getLogger(__name__)


class EmulatorManager:
    """BlueStacks 多模拟器管理器"""

    # BlueStacks 常见端口映射
    BLUESTACKS_PORTS = {
        "emulator-5554": 5555,  # 主实例
        "emulator-5555": 5556,
        "emulator-5556": 5557,
        "emulator-5557": 5558,
        "emulator-5558": 5559,
        "emulator-5559": 5560,
        "emulator-5560": 5561,
        "emulator-5561": 5562,
    }

    def __init__(self):
        self.system = platform.system()
        self.running_emulators = {}
        self.adb_path = self._get_adb_path()

    @staticmethod
    def _get_adb_path():
        """
        获取 ADB 路径，优先使用 Airtest 内置的 ADB

        优先级：
        1. Airtest 内置 ADB（推荐，避免版本冲突）
        2. 系统 PATH 中的 ADB
        3. ANDROID_HOME 中的 ADB

        Returns:
            ADB 可执行文件的完整路径，如果找不到则返回 adb
        """
        # 首先尝试使用 Airtest 内置的 ADB
        if ADB is not None:
            try:
                airtest_adb_path = ADB.builtin_adb_path()
                if os.path.exists(airtest_adb_path):
                    logger.info(f"✅ 使用 Airtest 内置 ADB: {airtest_adb_path}")
                    return airtest_adb_path
            except Exception as e:
                logger.debug(f"⚠️ 获取 Airtest 内置 ADB 失败: {e}")

        # 备选方案：尝试从系统 PATH 中找到 ADB
        adb_name = "adb.exe" if platform.system() == "Windows" else "adb"
        try:
            result = subprocess.run(
                ["which" if platform.system() != "Windows" else "where", adb_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                adb_path = result.stdout.strip().split("\n")[0]
                logger.info(f"✅ 使用系统 ADB: {adb_path}")
                return adb_path
        except Exception as e:
            logger.debug(f"⚠️ 从系统 PATH 查找 ADB 失败: {e}")

        # 最后尝试 ANDROID_HOME
        android_home = os.environ.get("ANDROID_HOME")
        if android_home:
            adb_path = os.path.join(android_home, "platform-tools", adb_name)
            if os.path.exists(adb_path):
                logger.info(f"✅ 使用 ANDROID_HOME 中的 ADB: {adb_path}")
                return adb_path

        logger.warning("⚠️ 未找到 ADB，将使用默认的 'adb' 命令")
        return "adb"

    def get_bluestacks_path(self) -> Optional[str]:
        """获取 BlueStacks 安装路径"""
        if self.system == "Darwin":  # macOS
            return "/Applications/BlueStacks.app"
        elif self.system == "Windows":
            paths = [
                r"C:\Program Files\BlueStacks_nxt",
                r"C:\Program Files (x86)\BlueStacks_nxt",
                r"C:\Program Files\BlueStacks",
                r"C:\Program Files (x86)\BlueStacks",
            ]
            for path in paths:
                if os.path.exists(path):
                    return path
        return None

    def get_adb_devices(self) -> Dict[str, str]:
        """
        获取所有已连接的 ADB 设备
        返回: {device_name: status}

        使用 Airtest 内置的 ADB 避免版本冲突问题
        """
        try:
            result = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            devices = {}
            for line in result.stdout.strip().split("\n")[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        devices[parts[0]] = parts[1]
            return devices
        except Exception as e:
            logger.error(f"❌ 获取 ADB 设备列表失败: {e}")
            return {}

    def is_emulator_running(self, emulator_name: str) -> bool:
        """检查指定模拟器是否运行"""
        devices = self.get_adb_devices()
        return emulator_name in devices and devices[emulator_name] == "device"

    def start_emulator(self, emulator_name: str) -> bool:
        """
        启动指定的 BlueStacks 实例

        Args:
            emulator_name: 模拟器名称，如 'emulator-5554'

        Returns:
            bool: 启动成功返回 True
        """
        try:
            if self.is_emulator_running(emulator_name):
                logger.info(f"✅ 模拟器 {emulator_name} 已在运行")
                return True

            logger.info(f"🚀 正在启动模拟器: {emulator_name}")

            if self.system == "Darwin":  # macOS
                # macOS 上通过 open 命令启动
                subprocess.Popen(
                    ["open", "-a", "BlueStacks"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif self.system == "Windows":
                # Windows 上启动指定实例
                bs_path = self.get_bluestacks_path()
                if not bs_path:
                    logger.error("❌ 未找到 BlueStacks 安装路径")
                    return False

                # BlueStacks 5 启动指定实例的命令
                hd_player = os.path.join(bs_path, "HD-Player.exe")
                if os.path.exists(hd_player):
                    subprocess.Popen(
                        [hd_player, "--instance", emulator_name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    logger.error(f"❌ 未找到 HD-Player.exe: {hd_player}")
                    return False
            else:  # Linux
                subprocess.Popen(
                    ["bluestacks"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            # 等待模拟器启动
            logger.info(f"⏳ 等待模拟器 {emulator_name} 启动...")
            max_wait = 60
            wait_interval = 5
            elapsed = 0

            while elapsed < max_wait:
                time.sleep(wait_interval)
                elapsed += wait_interval
                if self.is_emulator_running(emulator_name):
                    logger.info(f"✅ 模拟器 {emulator_name} 已启动 (耗时 {elapsed} 秒)")
                    time.sleep(5)  # 额外等待确保完全就绪
                    return True
                logger.info(f"⏳ 继续等待... ({elapsed}/{max_wait}秒)")

            logger.error(f"❌ 模拟器 {emulator_name} 启动超时")
            return False

        except Exception as e:
            logger.error(f"❌ 启动模拟器 {emulator_name} 失败: {e}")
            return False

    def start_multiple_emulators(self, emulator_names: List[str]) -> bool:
        """
        启动多个模拟器

        Args:
            emulator_names: 模拟器名称列表

        Returns:
            bool: 所有模拟器都启动成功返回 True
        """
        logger.info(f"🚀 准备启动 {len(emulator_names)} 个模拟器: {emulator_names}")

        all_success = True
        for emulator_name in emulator_names:
            if not self.start_emulator(emulator_name):
                all_success = False
                logger.warning(f"⚠️ 模拟器 {emulator_name} 启动失败")
            time.sleep(2)  # 模拟器之间间隔启动

        return all_success

    def get_emulator_port(self, emulator_name: str) -> Optional[int]:
        """获取模拟器对应的 ADB 端口"""
        return self.BLUESTACKS_PORTS.get(emulator_name)

    def get_emulator_connection_string(self, emulator_name: str) -> str:
        """
        获取 Airtest 连接字符串

        Args:
            emulator_name: 模拟器名称

        Returns:
            str: Airtest 连接字符串，如 'Android://127.0.0.1:5555/emulator-5554'
        """
        return f"Android://127.0.0.1:5037/{emulator_name}"
