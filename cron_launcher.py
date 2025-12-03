#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
Cron 任务启动器
并行启动两个 Terminal 窗口运行副本脚本，支持自动重试
"""

import logging
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path
from logger_config import setup_logger

# 添加项目目录到 Python 路径
SCRIPT_DIR = Path(__file__).parent

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
        result = subprocess.run(osascript_cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info("🖥️  Terminal 已启动脚本")
            return True
        logger.error(f"❌ 无法启动 Terminal: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("❌ 启动 Terminal 超时")
    except Exception as exc:
        logger.error(f"❌ 启动 Terminal 失败: {exc}")
    return False


def tmux_session_name(emulator_addr: str) -> str:
    base = emulator_addr.replace(":", "_")
    return f"dungeon_{base}"


def _write_tmux_script(session: str, command: str) -> Path:
    """将要执行的多行命令写入可执行脚本文件并返回路径。

    为避免在 tmux 中通过 shell -lc 传递多行命令的转义问题，这里使用临时脚本。

    Args:
        session: tmux 会话名称，用于生成脚本文件名
        command: 多行 shell 命令文本

    Returns:
        Path: 生成的脚本文件路径
    """

    scripts_dir = SCRIPT_DIR / "log" / "tmux_commands"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script_path = scripts_dir / f"{session}.sh"
    script_content = "#!/bin/zsh\nset -o pipefail\n" + command + "\n"
    script_path.write_text(script_content, encoding="utf-8")
    try:
        script_path.chmod(0o755)
    except Exception:
        pass
    return script_path


def launch_in_tmux(session: str, command: str, logger: logging.Logger) -> bool:
    """在 tmux 中执行命令，程序自身写入 log，不使用 pipe。

    - 清理已存在的同名会话
    - 将命令写入脚本文件以避免转义问题
    - 使用 tmux new-session 后直接运行脚本

    Args:
        session: tmux 会话名称
        command: 多行 shell 命令文本
        logger: 日志记录器

    Returns:
        bool: 启动成功返回 True，否则返回 False
    """

    try:
        has = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True)
        if has.returncode == 0:
            subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)

        script_path = _write_tmux_script(session, command)
        logger.info(f"📝 tmux 会话脚本: {script_path}")
        logger.info("📜 执行内容如下:\n" + command)

        result = subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                session,
                str(script_path),
            ],
            capture_output=True,
        )
        if result.returncode == 0:
            # 使用 pipe-pane 捕获 shell 输出到 log 目录下的独立文件
            log_dir = SCRIPT_DIR / "log"
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            shell_logfile = str((log_dir / f"shell_{session}.log").resolve())
            subprocess.run(
                [
                    "tmux",
                    "pipe-pane",
                    "-o",
                    "-t",
                    session,
                    f"cat >> {shell_logfile}",
                ],
                capture_output=True,
            )
            logger.info(f"🧰 tmux 会话已启动: {session}")
            logger.info(f"🧾 Shell 输出已记录: {shell_logfile}")
            return True
        logger.error(
            f"❌ 启动 tmux 失败: {result.stderr.decode() if isinstance(result.stderr, bytes) else result.stderr}"
        )
    except Exception as exc:
        logger.error(f"❌ tmux 异常: {exc}")
    return False


def main():
    """主函数 - 并行启动两个 Terminal 窗口，然后立即退出"""
    # 创建本地日志记录器（控制台输出）
    logger = setup_logger(name="cron_launcher", level="INFO", use_color=True)

    logger.info("=" * 50)
    logger.info("🚀 并行启动两个模拟器的副本脚本（tmux 会话，支持自动重试）")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    script_dir = str(SCRIPT_DIR)

    jobs = [
        {"config": "-a", "emulator": "192.168.1.150:5555"},
        {"config": "mage_alt", "emulator": "192.168.1.150:5565"},
    ]

    logger.info("🛑 先终止已有相关 tmux 会话以避免脚本重复")
    for job in jobs:
        session = tmux_session_name(job["emulator"])
        try:
            has = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True)
            if has.returncode == 0:
                subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
                logger.info(f"🛑 已终止: {session}")
        except Exception as exc:
            logger.error(f"❌ 终止 {session} 失败: {exc}")

    # 并行启动两个 tmux 会话
    for job in jobs:
        logger.info("")
        logger.info(f"📱 启动 tmux 会话: {job['config']} (模拟器 {job['emulator']})")

        # 构建脚本命令（带重试逻辑）
        run_command = build_run_command(job["config"], job["emulator"])

        # 构建会话命令（包含重试逻辑），程序自身按 emulator 写入 log/*.log
        terminal_command = "\n".join(
            [
                f"cd {shlex.quote(script_dir)}",
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

        session = tmux_session_name(job["emulator"])
        if not launch_in_tmux(session, terminal_command, logger):
            logger.error(f"❌ 无法启动 tmux 会话: {job['config']}")
        else:
            logger.info(f"✅ tmux 会话已启动: {session}")

        # 两个窗口之间间隔 2 秒
        if job != jobs[-1]:
            time.sleep(2)

    logger.info("")
    logger.info("=" * 50)
    logger.info("✅ 两个 tmux 会话已启动，cron_launcher 退出")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
