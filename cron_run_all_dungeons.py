#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""最终入口脚本。

仅读取 JSON 配置以支持多个模拟器会话。
根据每个会话的 ``configs`` 字段决定运行列表或全部：
当 ``configs`` 为空或缺失时运行全部，非空时按列表运行。
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from logger_config import setup_logger


SCRIPT_DIR = Path(__file__).parent
os.environ["PATH"] = f"/opt/homebrew/bin:{os.environ.get('PATH', '')}"


def ensure_log_dir() -> None:
    """确保日志目录存在。"""
    log_dir = SCRIPT_DIR / "log"
    log_dir.mkdir(parents=True, exist_ok=True)


def build_cmd_for_configs(session: str, emulator: str, logfile: Path, configs: Sequence[str]) -> str:
    """构建运行配置列表的命令（通过 uv 调用 Python 入口）。"""
    from shlex import quote
    script_path = str(SCRIPT_DIR / "run_dungeons.py")
    parts = [
        "uv",
        "run",
        quote(script_path),
        "--emulator",
        quote(emulator),
        "--logfile",
        quote(str(logfile)),
    ]
    parts += ["--session", quote(session)]
    for cfg in configs:
        parts += ["--config", quote(cfg)]
    return " ".join(parts)




def load_sessions_from_json(config_path: Path) -> Optional[list[dict]]:
    """加载 JSON 会话配置。"""
    try:
        if not config_path.exists():
            return None
        data = json.loads(config_path.read_text(encoding="utf-8"))
        sessions = data.get("sessions") if isinstance(data, dict) else data
        if not isinstance(sessions, list):
            return None
        return sessions
    except Exception:
        return None


def launch_tmux(session: str, cmd: str, logger) -> bool:
    """启动 tmux 会话执行指定命令。"""
    try:
        has = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True)
        if has.returncode == 0:
            subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
        result = subprocess.run(["tmux", "new-session", "-d", "-s", session, cmd], capture_output=True)
        if result.returncode == 0:
            logger.info(f"🧰 tmux 会话已启动: {session}")
            return True
        stderr = result.stderr.decode() if isinstance(result.stderr, bytes) else str(result.stderr)
        logger.error(f"❌ 启动 tmux 失败: {stderr}")
    except Exception as exc:
        logger.error(f"❌ tmux 异常: {exc}")
    return False


def main() -> int:
    """主入口：加载会话配置并启动各会话。"""
    logger = setup_logger(name="cron_run_all_dungeons", level="INFO", use_color=True)
    ensure_log_dir()

    sessions = load_sessions_from_json(SCRIPT_DIR / "emulators.json")
    if not sessions:
        logger.error("❌ emulators.json 未找到或格式错误，无法继续")
        return 2

    logger.info("=" * 50)
    logger.info("🚀 启动 tmux 会话（JSON 驱动）")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    all_ok = True
    for idx, sess in enumerate(sessions, start=1):
        name = str(sess.get("name", f"dungeon_{idx}"))
        emulator = str(sess.get("emulator", ""))
        configs = sess.get("configs")
        logfile = Path(sess.get("log") or (SCRIPT_DIR / "log" / f"autodungeon_{name}.log"))

        details = ", ".join(configs) if (isinstance(configs, list) and configs) else "全部"
        logger.info(f"🔧 {name}: 配置[{details}] @ {emulator}")
        if isinstance(configs, list) and len(configs) > 0:
            cmd = build_cmd_for_configs(name, emulator, logfile, configs)
            logger.info(f"🖥️  启动命令行: {cmd}")
        else:
            logger.error(f"❌ 会话 {name} 未提供有效的 configs 列表，已跳过")
            all_ok = False
            continue

        ok = launch_tmux(name, cmd, logger)
        all_ok = all_ok and ok
        time.sleep(1)

    if all_ok:
        logger.info("✅ 已并行启动所有 tmux 会话")
        return 0
    logger.error("❌ 部分会话启动失败，请检查配置与环境")
    return 1


if __name__ == "__main__":
    sys.exit(main())
