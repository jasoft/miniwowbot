#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
Cron 任务启动器
用于从 launchd 启动两个模拟器的副本脚本，在独立的 Terminal 窗口中并行运行
并将日志输出到 Loki
"""

import os
import sys
import subprocess
import time
import logging
from datetime import datetime
from pathlib import Path

# 添加项目目录到 Python 路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from loki_logger import create_loki_logger


def launch_emulator_in_terminal(
    emulator_addr: str,
    config_name: str,
    script_dir: str,
    logger: logging.Logger,
):
    """
    在独立的 Terminal 窗口中启动模拟器脚本

    Args:
        emulator_addr: 模拟器地址，如 127.0.0.1:5555
        config_name: 配置文件名称，如 'default' 或 'mage_alt'
        script_dir: 脚本目录
        logger: 日志记录器
    """
    try:
        logger.info(f"🎮 在 Terminal 中启动模拟器: {emulator_addr}")
        logger.info(f"⚙️  配置文件: {config_name}")

        # 构建命令
        if config_name == "default":
            cmd = (
                f"cd '{script_dir}' && ./run_all_dungeons.sh --emulator {emulator_addr}"
            )
        else:
            cmd = f"cd '{script_dir}' && ./run_all_dungeons.sh {config_name} --emulator {emulator_addr}"

        # 使用 osascript 在 Terminal 中启动
        osascript_cmd = [
            "osascript",
            "-e",
            'tell application "Terminal"',
            "-e",
            "activate",
            "-e",
            f'do script "{cmd}"',
            "-e",
            "end tell",
        ]

        logger.info(f"📝 执行命令: {cmd}")

        # 启动 Terminal 窗口（不等待完成）
        result = subprocess.run(
            osascript_cmd, capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            logger.info(f"✅ Terminal 窗口已启动: {emulator_addr}")
        else:
            logger.error(f"❌ 启动 Terminal 失败: {result.stderr}")

    except subprocess.TimeoutExpired:
        logger.error(f"❌ 启动 Terminal 超时: {emulator_addr}")
    except Exception as e:
        logger.error(f"❌ 启动模拟器 {emulator_addr} 异常: {e}", exc_info=True)


def main():
    """主函数"""
    # 创建 Loki 日志记录器
    logger = create_loki_logger(
        name="cron_launcher",
        level="INFO",
        loki_url=os.getenv("LOKI_URL", "http://localhost:3100"),
        enable_loki=os.getenv("LOKI_ENABLED", "true").lower() == "true",
    )

    logger.info("=" * 50)
    logger.info("🚀 启动两个模拟器的副本脚本")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    script_dir = str(SCRIPT_DIR)

    # 并行启动两个 Terminal 窗口
    logger.info("")
    logger.info("📱 模拟器 1: 127.0.0.1:5555")
    launch_emulator_in_terminal(
        emulator_addr="127.0.0.1:5555",
        config_name="default",
        script_dir=script_dir,
        logger=logger,
    )

    # 间隔 2 秒再启动第二个
    logger.info("⏳ 等待 2 秒...")
    time.sleep(2)

    logger.info("")
    logger.info("📱 模拟器 2: 127.0.0.1:5565")
    launch_emulator_in_terminal(
        emulator_addr="127.0.0.1:5565",
        config_name="mage_alt",
        script_dir=script_dir,
        logger=logger,
    )

    logger.info("")
    logger.info("=" * 50)
    logger.info("✅ 两个 Terminal 窗口已启动")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
