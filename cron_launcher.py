#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
Cron 任务启动器
用于从 launchd 启动两个模拟器的副本脚本，并将日志输出到 Loki
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


def launch_emulator(
    emulator_addr: str,
    config_name: str,
    script_dir: str,
    logger: logging.Logger,
):
    """
    启动单个模拟器的副本脚本

    Args:
        emulator_addr: 模拟器地址，如 127.0.0.1:5555
        config_name: 配置文件名称，如 'default' 或 'mage_alt'
        script_dir: 脚本目录
        logger: 日志记录器
    """
    try:
        logger.info(f"🎮 开始启动模拟器: {emulator_addr}")
        logger.info(f"⚙️  配置文件: {config_name}")

        # 构建命令
        if config_name == "default":
            cmd = [
                "./run_all_dungeons.sh",
                "--emulator",
                emulator_addr,
            ]
        else:
            cmd = [
                "./run_all_dungeons.sh",
                config_name,
                "--emulator",
                emulator_addr,
            ]

        logger.info(f"📝 执行命令: {' '.join(cmd)}")

        # 启动子进程
        process = subprocess.Popen(
            cmd,
            cwd=script_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # 行缓冲
        )

        # 实时读取输出并记录到日志
        for line in iter(process.stdout.readline, ""):
            if line:
                line = line.rstrip("\n")
                logger.info(f"[{emulator_addr}] {line}")

        # 等待进程完成
        return_code = process.wait()

        if return_code == 0:
            logger.info(f"✅ 模拟器 {emulator_addr} 完成")
        else:
            logger.error(f"❌ 模拟器 {emulator_addr} 失败，返回码: {return_code}")

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

    # 模拟器 1: 127.0.0.1:5555 (默认配置)
    logger.info("")
    logger.info("📱 模拟器 1: 127.0.0.1:5555")
    launch_emulator(
        emulator_addr="127.0.0.1:5555",
        config_name="default",
        script_dir=script_dir,
        logger=logger,
    )

    # 间隔 2 秒
    logger.info("⏳ 等待 2 秒...")
    time.sleep(2)

    # 模拟器 2: 127.0.0.1:5565 (mage_alt 配置)
    logger.info("")
    logger.info("📱 模拟器 2: 127.0.0.1:5565")
    launch_emulator(
        emulator_addr="127.0.0.1:5565",
        config_name="mage_alt",
        script_dir=script_dir,
        logger=logger,
    )

    logger.info("")
    logger.info("=" * 50)
    logger.info("✅ 两个模拟器已完成")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()

