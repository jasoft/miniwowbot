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
from typing import Dict, Optional

# 导入 Airtest 的 ADB 模块
try:
    from airtest.core.android.adb import ADB
except ImportError:
    ADB = None

# 导入 coloredlogs 用于彩色日志输出
try:
    import coloredlogs
except ImportError:
    coloredlogs = None

logger = logging.getLogger(__name__)

# 配置 logger（如果还没有配置过）
if not logger.handlers:
    logger.setLevel(logging.INFO)

    if coloredlogs:
        # 使用 coloredlogs 配置
        coloredlogs.install(
            level="INFO",
            logger=logger,
            fmt="%(asctime)s %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
            level_styles={
                "debug": {"color": "cyan"},
                "info": {"color": "green"},
                "warning": {"color": "yellow"},
                "error": {"color": "red"},
                "critical": {"color": "red", "bold": True},
            },
            field_styles={
                "asctime": {"color": "blue"},
                "levelname": {"color": "white", "bold": True},
            },
        )
    else:
        # 备选方案：使用标准 logging
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)


class EmulatorManager:
    """BlueStacks 多模拟器管理器"""

    # 模拟器名称到 BlueStacks 实例名称的映射
    EMULATOR_TO_INSTANCE = {
        "127.0.0.1:5555": "Tiramisu64",  # 主实例，网络连接端口 5555
        "127.0.0.1:5565": "Tiramisu64_1",  # 第二个实例，网络连接端口 5565
        "127.0.0.1:5575": "Tiramisu64_2",  # 第三个实例，网络连接端口 5575
        "127.0.0.1:5585": "Tiramisu64_3",  # 第四个实例，网络连接端口 5585
    }

    # 网络连接端口到 BlueStacks 实例名称的映射（用于启动时检查）
    PORT_TO_INSTANCE = {
        5555: "Tiramisu64",
        5565: "Tiramisu64_1",
        5575: "Tiramisu64_2",
        5585: "Tiramisu64_3",
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
                logger.error(f"⚠️ 获取 Airtest 内置 ADB 失败: {e}")

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

    def try_adb_connect(self, emulator_name: str) -> bool:
        """
        尝试通过 adb connect 连接到模拟器

        Args:
            emulator_name: 模拟器网络地址，如 '127.0.0.1:5555'

        Returns:
            bool: 连接成功返回 True
        """
        try:
            logger.info(f"📡 尝试连接到 {emulator_name}...")
            result = subprocess.run(
                [self.adb_path, "connect", emulator_name],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # 检查连接结果
            if result.returncode == 0:
                output = result.stdout.strip()
                if "connected" in output.lower():
                    logger.info(f"✅ 成功连接到 {emulator_name}")
                    # 等待一下确保连接稳定
                    time.sleep(2)
                    # 再次检查设备状态
                    devices = self.get_adb_devices()
                    if emulator_name in devices and devices[emulator_name] == "device":
                        logger.info(f"✅ 模拟器 {emulator_name} 已就绪")
                        return True

            logger.warning(f"⚠️ 连接到 {emulator_name} 失败: {result.stdout}")
            return False
        except Exception as e:
            logger.warning(f"⚠️ adb connect 失败: {e}")
            return False

    def is_emulator_running(self, emulator_name: str) -> bool:
        """
        检查指定模拟器是否运行

        Args:
            emulator_name: 模拟器名称，如 '127.0.0.1:5555'

        Returns:
            bool: 模拟器是否在线
        """
        devices = self.get_adb_devices()
        return emulator_name in devices and devices[emulator_name] == "device"

    def start_bluestacks_instance(self, emulator_name: str) -> bool:
        """
        启动指定的 BlueStacks 实例（当模拟器不在设备列表中时调用）

        流程：
        1. 检查模拟器是否已经运行
        2. 如果未运行，先尝试 adb connect
        3. 如果 adb connect 成功，直接返回
        4. 如果 adb connect 失败，启动对应的 BlueStacks 实例

        Args:
            emulator_name: 模拟器名称，如 '127.0.0.1:5555'

        Returns:
            bool: 启动成功返回 True
        """
        try:
            # 先检查模拟器是否已经运行
            if self.is_emulator_running(emulator_name):
                logger.info(f"✅ 模拟器 {emulator_name} 已在运行")
                return True

            instance_name = self.EMULATOR_TO_INSTANCE.get(emulator_name)
            if not instance_name:
                logger.error(f"❌ 未找到模拟器 {emulator_name} 对应的 BlueStacks 实例")
                return False

            # 验证模拟器地址格式
            try:
                int(emulator_name.split(":")[1])
            except (IndexError, ValueError):
                logger.error(f"❌ 无效的模拟器地址格式: {emulator_name}")
                return False

            # 第一步：尝试 adb connect
            logger.info(f"📡 第一步：尝试通过 adb connect 连接到 {emulator_name}...")
            if self.try_adb_connect(emulator_name):
                logger.info(
                    f"✅ 通过 adb connect 成功连接到 {emulator_name}，无需启动模拟器"
                )
                return True

            # 第二步：如果 adb connect 失败，启动 BlueStacks 实例
            logger.info("📱 第二步：adb connect 失败，准备启动 BlueStacks 实例...")

            logger.info(
                f"🚀 正在启动 BlueStacks 实例: {instance_name} (对应 {emulator_name})"
            )

            if self.system == "Darwin":  # macOS
                # macOS 上直接启动 BlueStacks 可执行文件并传递 --instance 参数
                bluestacks_exe = (
                    "/Applications/BlueStacks.app/Contents/MacOS/BlueStacks"
                )
                if not os.path.exists(bluestacks_exe):
                    logger.error(f"❌ 未找到 BlueStacks 可执行文件: {bluestacks_exe}")
                    return False

                subprocess.Popen(
                    [bluestacks_exe, "--instance", instance_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                logger.info(f"⏳ 等待 BlueStacks 实例 {instance_name} 启动...")
            elif self.system == "Windows":
                # Windows 上启动指定实例
                bs_path = self.get_bluestacks_path()
                if not bs_path:
                    logger.error("❌ 未找到 BlueStacks 安装路径")
                    return False

                hd_player = os.path.join(bs_path, "HD-Player.exe")
                if os.path.exists(hd_player):
                    subprocess.Popen(
                        [hd_player, "--instance", instance_name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    logger.info(f"⏳ 等待 BlueStacks 实例 {instance_name} 启动...")
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
            logger.error(f"❌ 启动 BlueStacks 实例失败: {e}")
            return False

    def get_emulator_connection_string(self, emulator_name: str) -> str:
        """
        获取 Airtest 连接字符串（网络连接方式）

        Airtest 连接字符串格式：
        Android://<adbhost>:<adbport>/<emulator_address>

        例如：Android://127.0.0.1:5037/127.0.0.1:5555
        其中：
        - 127.0.0.1:5037 是 ADB 服务器地址（默认）
        - 127.0.0.1:5555 是模拟器网络地址

        Args:
            emulator_name: 模拟器网络地址，如 '127.0.0.1:5555'

        Returns:
            str: Airtest 连接字符串，如 'Android://127.0.0.1:5037/127.0.0.1:5555'
        """
        # Airtest 需要完整的连接字符串格式：ADB服务器地址/模拟器地址
        # ADB 服务器默认在 127.0.0.1:5037
        return f"Android://127.0.0.1:5037/{emulator_name}"

    def ensure_device_connected(self, emulator_name: str) -> bool:
        """
        确保设备连接正常，如果连接断开则尝试重新连接

        Args:
            emulator_name: 模拟器网络地址，如 '127.0.0.1:5555'

        Returns:
            bool: 设备连接正常返回 True，否则返回 False
        """
        try:
            # 检查设备是否在列表中
            devices = self.get_adb_devices()
            if emulator_name in devices and devices[emulator_name] == "device":
                logger.info(f"✅ 设备 {emulator_name} 连接正常")
                return True

            # 设备不在列表中，尝试重新连接
            logger.warning(f"⚠️ 设备 {emulator_name} 连接断开，尝试重新连接...")
            if self.try_adb_connect(emulator_name):
                logger.info(f"✅ 成功重新连接到 {emulator_name}")
                return True
            else:
                logger.error(f"❌ 无法重新连接到 {emulator_name}")
                return False

        except Exception as e:
            logger.error(f"❌ 检查设备连接失败: {e}")
            return False
