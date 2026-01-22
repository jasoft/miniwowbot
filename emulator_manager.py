# -*- encoding=utf8 -*-
"""
多模拟器管理模块
用于检测、启动和管理多个 BlueStacks 实例
"""

import subprocess
import platform
import time

import os
from typing import Dict, Optional

# 导入通用日志配置模块
from logger_config import setup_logger_from_config  # noqa: E402

logger = setup_logger_from_config(use_color=True)


class EmulatorManager:
    """BlueStacks 多模拟器管理器"""

    # 模拟器名称到 BlueStacks 实例名称的映射
    EMULATOR_TO_INSTANCE = {
        "127.0.0.1:5555": "Tiramisu64",  # 主实例，网络连接端口 5555
        "127.0.0.1:5565": "Tiramisu64_1",  # 第二个实例，网络连接端口 5565
        "127.0.0.1:5575": "Tiramisu64_2",  # 第三个实例，网络连接端口 5575
        "127.0.0.1:5585": "Tiramisu64_3",  # 第四个实例，网络连接端口 5585
    }

    def __init__(self):
        self.system = platform.system()
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

    def is_emulator_running(self, emulator_name: str, retry_count: int = 2) -> bool:
        """
        检查指定模拟器是否运行

        Args:
            emulator_name: 模拟器名称，如 '127.0.0.1:5555'
            retry_count: 重试次数，默认 2 次

        Returns:
            bool: 模拟器是否在线
        """
        # 尝试多次获取设备列表，以应对 ADB 缓存或延迟问题
        for attempt in range(retry_count):
            devices = self.get_adb_devices()
            if emulator_name in devices and devices[emulator_name] == "device":
                return True

            # 如果不是最后一次尝试，等待后重试
            if attempt < retry_count - 1:
                time.sleep(0.5)  # 短暂等待后重试

        return False

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

            # 验证模拟器地址格式
            try:
                int(emulator_name.split(":")[1])
            except (IndexError, ValueError):
                logger.error(f"❌ 无效的模拟器地址格式: {emulator_name}")
                return False

            # 第一步：尝试 adb connect
            logger.info(f"📡 第一步：尝试通过 adb connect 连接到 {emulator_name}...")
            if self.try_adb_connect(emulator_name):
                logger.info(f"✅ 通过 adb connect 成功连接到 {emulator_name}，无需启动模拟器")
                return True

            instance_name = self.EMULATOR_TO_INSTANCE.get(emulator_name)
            if not instance_name:
                logger.error(
                    f"❌ 未找到模拟器 {emulator_name} 对应的 BlueStacks 实例，且 adb connect 失败"
                )
                return False

            # 第二步：如果 adb connect 失败，启动 BlueStacks 实例
            logger.info("📱 第二步：adb connect 失败，准备启动 BlueStacks 实例...")

            logger.info(f"🚀 正在启动 BlueStacks 实例: {instance_name} (对应 {emulator_name})")

            if self.system == "Darwin":  # macOS
                # macOS 上直接启动 BlueStacks 可执行文件并传递 --instance 参数
                bluestacks_exe = "/Applications/BlueStacks.app/Contents/MacOS/BlueStacks"
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

            # 等待模拟器启动并尝试连接
            max_wait = 60
            wait_interval = 1  # 改为 1 秒，更快的响应
            elapsed = 0

            while elapsed < max_wait:
                # 先尝试 adb connect，这是最直接的连接方式
                if self.try_adb_connect(emulator_name):
                    logger.info(f"✅ 模拟器 {emulator_name} 已连接 (耗时 {elapsed} 秒)")
                    return True

                # 如果连接失败，检查模拟器是否在运行
                if self.is_emulator_running(emulator_name):
                    logger.info(f"✅ 模拟器 {emulator_name} 已启动 (耗时 {elapsed} 秒)")
                    time.sleep(1)  # 短暂等待后再尝试连接
                    if self.try_adb_connect(emulator_name):
                        return True

                # 如果未连接，再等待
                time.sleep(wait_interval)
                elapsed += wait_interval
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

    def check_bluestacks_running(self) -> bool:
        """
        检查BlueStacks模拟器是否正在运行

        Returns:
            bool: 如果BlueStacks正在运行返回True，否则返回False
        """
        try:
            if self.system == "Darwin":  # macOS
                result = subprocess.run(
                    ["pgrep", "-f", "BlueStacks"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return result.returncode == 0
            elif self.system == "Windows":
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq HD-Player.exe"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return "HD-Player.exe" in result.stdout
            else:  # Linux
                result = subprocess.run(
                    ["pgrep", "-f", "bluestacks"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return result.returncode == 0
        except Exception as e:
            logger.warning(f"⚠️ 检查BlueStacks状态失败: {e}")
            return False

    def start_bluestacks(self) -> bool:
        """
        启动BlueStacks模拟器（默认实例）

        Returns:
            bool: 启动成功返回True，失败返回False
        """
        try:
            logger.info("🚀 正在启动BlueStacks模拟器...")

            if self.system == "Darwin":  # macOS
                # macOS上通过open命令启动应用
                subprocess.Popen(
                    ["open", "-a", "BlueStacks"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif self.system == "Windows":
                # Windows上启动BlueStacks
                # 常见安装路径
                paths = [
                    r"C:\Program Files\BlueStacks_nxt\HD-Player.exe",
                    r"C:\Program Files (x86)\BlueStacks_nxt\HD-Player.exe",
                    r"C:\Program Files\BlueStacks\HD-Player.exe",
                    r"C:\Program Files (x86)\BlueStacks\HD-Player.exe",
                ]
                for path in paths:
                    if os.path.exists(path):
                        subprocess.Popen(
                            [path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                        break
                else:
                    logger.error("❌ 未找到BlueStacks安装路径")
                    return False
            else:  # Linux
                # Linux上通过命令启动
                subprocess.Popen(
                    ["bluestacks"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

            # 等待模拟器启动
            logger.info("⏳ 等待模拟器启动...")
            max_wait_time = 60  # 最多等待60秒
            wait_interval = 5
            elapsed = 0

            while elapsed < max_wait_time:
                time.sleep(wait_interval)
                elapsed += wait_interval
                if self.check_bluestacks_running():
                    logger.info(f"✅ BlueStacks已启动 (耗时 {elapsed} 秒)")
                    # 额外等待一段时间让模拟器完全就绪
                    logger.info("⏳ 等待模拟器完全就绪...")
                    time.sleep(10)
                    return True
                logger.info(f"⏳ 继续等待... ({elapsed}/{max_wait_time}秒)")

            logger.error("❌ BlueStacks启动超时")
            return False

        except Exception as e:
            logger.error(f"❌ 启动BlueStacks失败: {e}")
            return False

    def ensure_adb_connection(self) -> bool:
        """
        确保ADB连接已建立
        无论模拟器是否刚启动，都执行一次adb devices来建立连接

        Returns:
            bool: 连接成功返回True，失败返回False
        """
        try:
            logger.info("🔌 执行 adb devices 建立连接...")
            result = subprocess.run(
                [self.adb_path, "devices"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                # 检查是否有设备连接
                lines = result.stdout.strip().split("\n")
                devices = [line for line in lines if "\tdevice" in line]

                if devices:
                    logger.info(f"✅ 发现 {len(devices)} 个设备:")
                    for device in devices:
                        logger.info(f"  📱 {device}")
                    return True
                else:
                    logger.warning("⚠️ 未发现已连接的设备")
                    # 即使没有设备，也返回True，让后续的connect_device处理
                    return True
            else:
                logger.error(f"❌ adb devices 执行失败: {result.stderr}")
                return False

        except FileNotFoundError:
            logger.error("❌ 未找到adb命令，请确保Android SDK已安装并配置环境变量")
            return False
        except Exception as e:
            logger.error(f"❌ 执行adb devices失败: {e}")
            return False
