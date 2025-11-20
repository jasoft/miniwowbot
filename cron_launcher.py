#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
Cron 任务启动器
顺序运行两个副本脚本实例，记录日志并在每次运行结束后发送 Bark 通知
"""

import os
import sys
import subprocess
import logging
import re
import shlex
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

# 添加项目目录到 Python 路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from loki_logger import create_loki_logger
from send_cron_notification import send_bark_notification


ANSI_ESCAPE_PATTERN = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")
LOG_OUTPUT_DIR = SCRIPT_DIR / "log" / "cron_launcher"
LOG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def strip_ansi_codes(text: str) -> str:
    """移除 ANSI 颜色编码，便于解析统计信息"""

    return ANSI_ESCAPE_PATTERN.sub("", text)


def parse_run_statistics(log_output: str) -> Dict[str, Optional[int]]:
    """从 run_all_dungeons 输出中解析统计信息"""

    cleaned = strip_ansi_codes(log_output)
    stats = {"total": None, "success": None, "failed": None}

    total_match = re.search(r"总共运行:\s*(\d+)", cleaned)
    success_match = re.search(r"成功:\s*(\d+)", cleaned)
    failed_match = re.search(r"失败:\s*(\d+)", cleaned)

    if total_match:
        stats["total"] = int(total_match.group(1))
    if success_match:
        stats["success"] = int(success_match.group(1))
    if failed_match:
        stats["failed"] = int(failed_match.group(1))
    elif stats["total"] is not None and stats["success"] is not None:
        stats["failed"] = stats["total"] - stats["success"]
    else:
        stats["failed"] = 0

    return stats


def format_duration(duration: timedelta) -> str:
    """格式化运行耗时"""

    seconds = int(duration.total_seconds())
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"耗时: {hours}小时 {minutes}分钟 {seconds}秒"
    if minutes:
        return f"耗时: {minutes}分钟 {seconds}秒"
    return f"耗时: {seconds}秒"


def build_notification_content(
    config_name: str,
    emulator_addr: str,
    stats: Dict[str, Optional[int]],
    success: bool,
    duration: Optional[timedelta] = None,
):
    """构造 Bark 通知的标题、内容和级别"""

    config_display = "默认配置" if config_name == "default" else config_name
    status_text = "运行成功" if success else "运行失败"
    title = f"异世界勇者 - {config_display}{status_text}"

    lines = [f"配置: {config_display}", f"模拟器: {emulator_addr}"]
    if stats.get("total") is not None:
        lines.append(f"总计: {stats['total']} 个角色")
        if stats.get("success") is not None:
            lines.append(f"✅ 成功: {stats['success']} 个")
        if stats.get("failed") is not None:
            lines.append(f"❌ 失败: {stats['failed']} 个")
    else:
        lines.append("统计数据: 无法解析")

    if duration is not None:
        lines.append(format_duration(duration))

    level = "active" if success else "timeSensitive"
    message = "\n".join(lines)
    return title, message, level


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


def wait_for_status_file(
    status_file: Path,
    logger: logging.Logger,
    timeout_hours: int = 12,
    poll_interval: int = 5,
) -> Optional[int]:
    """等待 Terminal 任务写入状态文件"""

    deadline = datetime.now() + timedelta(hours=timeout_hours)
    while datetime.now() < deadline:
        if status_file.exists():
            try:
                content = status_file.read_text(encoding="utf-8").strip()
                if content:
                    exit_code = int(content)
                    logger.info(f"📄 读取到退出码: {exit_code}")
                    return exit_code
            except ValueError:
                logger.warning("⚠️ 状态文件内容异常，稍后重试")
        time.sleep(poll_interval)

    logger.error("⏰ 等待状态文件超时")
    return None


def run_dungeons_once(
    config_name: str,
    emulator_addr: str,
    script_dir: str,
    logger: logging.Logger,
):
    """运行单个副本脚本并返回执行结果及统计信息"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{config_name}_{timestamp}"
    log_file = LOG_OUTPUT_DIR / f"{base_name}.log"
    status_file = LOG_OUTPUT_DIR / f"{base_name}.status"

    run_command = build_run_command(config_name, emulator_addr)
    logger.info("🚀 开始运行副本脚本")
    logger.info(f"⚙️  配置: {config_name}")
    logger.info(f"📱 模拟器: {emulator_addr}")
    logger.info(f"📝 执行命令: cd '{script_dir}' && {run_command}")

    terminal_command = " ; ".join(
        [
            f"cd {shlex.quote(script_dir)}",
            "set -o pipefail",
            f"rm -f {shlex.quote(str(status_file))}",
            f"{run_command} | tee {shlex.quote(str(log_file))}",
            "exit_code=$?",
            f"echo $exit_code > {shlex.quote(str(status_file))}",
            "exit $exit_code",
        ]
    )

    start_time = datetime.now()

    if not launch_in_terminal(terminal_command, logger):
        return False, {"total": None, "success": None, "failed": None}, timedelta(0)

    exit_code = wait_for_status_file(status_file, logger)

    duration = datetime.now() - start_time

    if log_file.exists():
        output_text = log_file.read_text(encoding="utf-8", errors="ignore")
    else:
        logger.warning("⚠️ 日志文件不存在，无法解析统计")
        output_text = ""

    stats = parse_run_statistics(output_text)
    success = exit_code == 0 if exit_code is not None else False
    return success, stats, duration


def run_dungeons_with_retry(
    config_name: str,
    emulator_addr: str,
    script_dir: str,
    logger: logging.Logger,
    max_retries: int = 3,
) -> tuple[bool, Dict[str, Optional[int]], timedelta]:
    """
    运行副本脚本，失败时自动重试

    Args:
        config_name: 配置名称
        emulator_addr: 模拟器地址
        script_dir: 脚本目录
        logger: 日志记录器
        max_retries: 最大重试次数（默认 3 次）

    Returns:
        (成功标志, 统计信息, 总耗时)
    """
    retry_count = 0
    total_duration = timedelta(0)

    while retry_count < max_retries:
        logger.info("")
        if retry_count > 0:
            wait_time = (
                retry_count * 10
            )  # 第1次失败等待10秒，第2次等待20秒，第3次等待30秒
            logger.warning(
                f"⏳ 等待 {wait_time} 秒后重新运行... (第 {retry_count}/{max_retries} 次失败)"
            )
            time.sleep(wait_time)
            logger.info(f"🔄 开始第 {retry_count + 1} 次重试...")

        success, stats, duration = run_dungeons_once(
            config_name=config_name,
            emulator_addr=emulator_addr,
            script_dir=script_dir,
            logger=logger,
        )

        total_duration += duration

        if success:
            logger.info(f"✅ 配置 {config_name} 运行成功！")
            return success, stats, total_duration

        retry_count += 1
        if retry_count < max_retries:
            logger.error(
                f"❌ 配置 {config_name} 运行失败！(第 {retry_count}/{max_retries} 次失败)"
            )
        else:
            logger.error(f"❌ 配置 {config_name} 在 {max_retries} 次重试后仍然失败！")

    # 所有重试都失败了
    return False, {"total": None, "success": None, "failed": None}, total_duration


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
    logger.info("🚀 顺序运行两个模拟器的副本脚本（支持自动重试）")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    script_dir = str(SCRIPT_DIR)

    jobs = [
        {"config": "default", "emulator": "127.0.0.1:5555"},
        {"config": "mage_alt", "emulator": "127.0.0.1:5565"},
    ]

    for job in jobs:
        logger.info("")
        logger.info(f"📱 开始运行配置: {job['config']} (模拟器 {job['emulator']})")
        success, stats, duration = run_dungeons_with_retry(
            config_name=job["config"],
            emulator_addr=job["emulator"],
            script_dir=script_dir,
            logger=logger,
            max_retries=3,
        )

        title, message, level = build_notification_content(
            config_name=job["config"],
            emulator_addr=job["emulator"],
            stats=stats,
            success=success,
            duration=duration,
        )

        if send_bark_notification(title, message, level):
            logger.info("✅ Bark 通知发送成功")
        else:
            logger.warning("⚠️ Bark 通知发送失败或未启用")

        if not success:
            logger.error("❌ 本次运行失败（已重试 3 次），继续下一个配置...")

    logger.info("")
    logger.info("=" * 50)
    logger.info("✅ 顺序运行流程结束")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
