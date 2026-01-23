# -*- encoding=utf8 -*-
"""
简化的模拟器管理器
只负责通过 adb 连接设备，连接失败时执行 system_config.json 中的启动命令。
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from shutil import which
from typing import Dict, Optional

from logger_config import setup_logger_from_config
from project_paths import ensure_project_path

logger = setup_logger_from_config(use_color=True)


class EmulatorManager:
    """简化版模拟器管理器"""

    def __init__(self, config_file: str = "system_config.json"):
        self.config_file = str(ensure_project_path(config_file))
        self.adb_path = self._resolve_adb_path()
        self.start_cmd = self._load_start_cmd()

    @staticmethod
    def _resolve_adb_path() -> str:
        adb_name = "adb.exe" if os.name == "nt" else "adb"
        adb_path = which(adb_name)
        if adb_path:
            logger.info(f"✅ 使用系统 ADB: {adb_path}")
            return adb_path
        logger.warning("⚠️ 未找到 ADB，将使用默认的 'adb' 命令")
        return "adb"

    def _load_start_cmd(self) -> Optional[str]:
        if not os.path.exists(self.config_file):
            logger.warning(f"⚠️ 未找到系统配置文件: {self.config_file}")
            return None
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            start_cmd = config.get("emulators", {}).get("startCmd")
            if not start_cmd:
                logger.warning("⚠️ system_config.json 未配置 emulators.startCmd")
                return None
            return str(start_cmd)
        except json.JSONDecodeError as exc:
            logger.error(f"❌ 系统配置文件格式错误: {exc}")
            return None
        except Exception as exc:
            logger.error(f"❌ 读取系统配置文件失败: {exc}")
            return None

    def _run_start_cmd(self) -> bool:
        if not self.start_cmd:
            logger.error("❌ 未配置启动命令，无法启动模拟器")
            return False
        try:
            logger.info(f"🚀 执行模拟器启动命令: {self.start_cmd}")
            subprocess.Popen(
                self.start_cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as exc:
            logger.error(f"❌ 执行启动命令失败: {exc}")
            return False

    def get_adb_devices(self) -> Dict[str, str]:
        try:
            result = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.error(f"❌ adb devices 执行失败: {result.stderr}")
                return {}
            devices = {}
            for line in result.stdout.strip().split("\n")[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        devices[parts[0]] = parts[1]
            return devices
        except Exception as exc:
            logger.error(f"❌ 获取 ADB 设备列表失败: {exc}")
            return {}

    def try_adb_connect(self, emulator_name: str) -> bool:
        try:
            logger.info(f"📡 尝试连接到 {emulator_name}...")
            result = subprocess.run(
                [self.adb_path, "connect", emulator_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.warning(f"⚠️ 连接失败: {result.stdout.strip()}")
                return False
            output = result.stdout.strip().lower()
            if "connected" in output or "already connected" in output:
                logger.info(f"✅ 连接到 {emulator_name}: {result.stdout.strip()}")
                return True
            logger.warning(f"⚠️ 连接到 {emulator_name} 失败: {result.stdout.strip()}")
            return False
        except Exception as exc:
            logger.warning(f"⚠️ adb connect 失败: {exc}")
            return False

    def is_emulator_running(self, emulator_name: str, retry_count: int = 2) -> bool:
        for attempt in range(retry_count):
            devices = self.get_adb_devices()
            if emulator_name in devices and devices[emulator_name] == "device":
                return True
            if attempt < retry_count - 1:
                time.sleep(0.5)
        return False

    def start_bluestacks_instance(self, emulator_name: str) -> bool:
        if self.try_adb_connect(emulator_name):
            return True

        logger.warning("⚠️ 连接失败，准备启动模拟器...")
        if not self._run_start_cmd():
            return False

        logger.info("⏳ 等待 30 秒后重试连接...")
        time.sleep(30)
        if self.try_adb_connect(emulator_name):
            logger.info(f"✅ 模拟器 {emulator_name} 已连接")
            return True
        logger.error(f"❌ 模拟器 {emulator_name} 连接失败")
        return False

    def get_emulator_connection_string(self, emulator_name: str) -> str:
        return f"Android://127.0.0.1:5037/{emulator_name}"

    def ensure_device_connected(self, emulator_name: str) -> bool:
        return self.start_bluestacks_instance(emulator_name)

    def ensure_adb_connection(self) -> bool:
        try:
            logger.info("🔌 执行 adb devices 建立连接...")
            result = subprocess.run(
                [self.adb_path, "devices"], capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.error(f"❌ adb devices 执行失败: {result.stderr}")
                return False
            return True
        except FileNotFoundError:
            logger.error("❌ 未找到adb命令，请确保Android SDK已安装并配置环境变量")
            return False
        except Exception as exc:
            logger.error(f"❌ 执行adb devices失败: {exc}")
            return False


__all__ = ["EmulatorManager"]
