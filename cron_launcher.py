#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
Cron 任务启动器
并行启动两个 Terminal 窗口运行副本脚本，支持自动重试
"""

import os
import sys
import subprocess
import logging
import shlex
import time
from datetime import datetime
from pathlib import Path

# 添加项目目录到 Python 路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from loki_logger import create_loki_logger


def build_run_command(config_name: str, emulator_addr: str) -> str:
    """构造运行 run_all_dungeons.sh 的命令"""

    parts = ["./run_all_dungeons.sh"]
    if config_name != "default":
        parts.append(shlex.quote(config_name))
    if emulator_addr:
        parts.extend(["--emulator", shlex.quote(emulator_addr)])
    return " ".join(parts)


def escape_for_osascript(command: str) -> str:
    """转义命令字符串以便在 osascript 中使用"""

    return command.replace("\\", "\\\\").replace('"', r"\"")


def launch_in_terminal(command: str, logger: logging.Logger) -> bool:
    """在 Terminal 中执行命令"""

    escaped = escape_for_osascript(command)
    osascript_cmd = [
        "osascript",
        "-e",
        'tell application "Terminal"',
        "-e",
        "activate",
        "-e",
        f'do script "{escaped}"',
        "-e",
        "end tell",
    ]

    try:
        result = subprocess.run(
            osascript_cmd, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            logger.info("🖥️  Terminal 已启动脚本")
            return True
        logger.error(f"❌ 无法启动 Terminal: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("❌ 启动 Terminal 超时")
    except Exception as exc:
        logger.error(f"❌ 启动 Terminal 失败: {exc}")
    return False


def main():
    """主函数 - 并行启动两个 Terminal 窗口，然后立即退出"""
    # 创建 Loki 日志记录器
    logger = create_loki_logger(
        name="cron_launcher",
        level="INFO",
        loki_url=os.getenv("LOKI_URL", "http://localhost:3100"),
        enable_loki=os.getenv("LOKI_ENABLED", "true").lower() == "true",
    )

    logger.info("=" * 50)
    logger.info("🚀 并行启动两个模拟器的副本脚本（支持自动重试）")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    script_dir = str(SCRIPT_DIR)

    jobs = [
        {"config": "default", "emulator": "192.168.1.150:5555"},
        {"config": "mage_alt", "emulator": "192.168.1.150:5565"},
    ]
    

    # 并行启动两个 Terminal 窗口
    for job in jobs:
        logger.info("")
        logger.info(
            f"📱 启动 Terminal 窗口: {job['config']} (模拟器 {job['emulator']})"
        )

        # 构建脚本命令（带重试逻辑）
        run_command = build_run_command(job["config"], job["emulator"])

        # 构建 Terminal 命令（包含重试逻辑）
        terminal_command = " ; ".join(
            [
                f"cd {shlex.quote(script_dir)}",
                "set -o pipefail",
                # 重试逻辑：最多重试 3 次
                "max_retries=3",
                "retry_count=0",
                "while [ $retry_count -lt $max_retries ]; do",
                f"  {run_command}",
                "  if [ $? -eq 0 ]; then",
                "    echo '✅ 脚本运行成功'",
                "    exit 0",
                "  fi",
                "  ((retry_count++))",
                "  if [ $retry_count -lt $max_retries ]; then",
                "    wait_time=$((retry_count * 10))",
                '    echo "⏳ 等待 ${wait_time} 秒后重新运行... (第 $retry_count/$max_retries 次失败)"',
                "    sleep $wait_time",
                '    echo "🔄 开始第 $((retry_count + 1)) 次重试..."',
                "  fi",
                "done",
                "echo '❌ 脚本在 $max_retries 次重试后仍然失败'",
                "exit 1",
            ]
        )

        if not launch_in_terminal(terminal_command, logger):
            logger.error(f"❌ 无法启动 Terminal 窗口: {job['config']}")
        else:
            logger.info(f"✅ Terminal 窗口已启动: {job['config']}")

        # 两个窗口之间间隔 2 秒
        if job != jobs[-1]:
            time.sleep(2)

    logger.info("")
    logger.info("=" * 50)
    logger.info("✅ 两个 Terminal 窗口已启动，cron_launcher 退出")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
