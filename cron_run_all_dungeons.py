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
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from logger_config import setup_logger


SCRIPT_DIR = Path(__file__).parent
IS_WINDOWS = platform.system() == "Windows"
if not IS_WINDOWS:
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


def launch_powershell(session: str, cmd: str, logger) -> bool:
    """在 Windows 上启动一个新的 PowerShell 窗口执行命令。"""
    try:
        # $Host.UI.RawUI.WindowTitle 用于设置窗口标题
        # -NoExit 保持窗口打开，方便查看日志
        # 使用 Start-Process 启动新的窗口
        pwsh_cmd = f"Start-Process powershell -ArgumentList '-NoExit', '-Command', \"$Host.UI.RawUI.WindowTitle = '{session}'; {cmd}\""
        subprocess.run(["powershell", "-Command", pwsh_cmd], check=True)
        logger.info(f"🧰 PowerShell 窗口已启动: {session}")
        return True
    except Exception as exc:
        logger.error(f"❌ 启动 PowerShell 失败: {exc}")
    return False


def launch_ocr_service(logger) -> bool:
    """启动 OCR Docker 服务（2小时后自动停止）。"""
    session_name = "ocr_service"
    image = "ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlex/paddlex:paddlex3.3.11-paddlepaddle3.2.0-cpu"
    
    if IS_WINDOWS:
        docker_cmd = (
            f"Write-Host '🚀 Starting OCR Service (Docker)...'; "
            f"if (docker ps -a --format '{{{{.Names}}}}' | Select-String -Pattern '^paddlex$') {{ "
            f"  docker start paddlex; "
            f"}} else {{ "
            f"  docker run -d --name paddlex "
            f"  -v \"${{PWD}}:/paddle\" "
            f"  -v \"paddlex_data:/root\" "
            f"  --shm-size=8g "
            f"  --network=host "
            f"  {image} "
            f"  sh -lc \"paddlex --install serving && rm -f OCR.yaml && paddlex --get_pipeline_config OCR --save_path . && sed -i 's/_server_/_mobile_/g' OCR.yaml && paddlex --serve --pipeline OCR.yaml\"; "
            f"}}; "
            f"Write-Host '✅ OCR Service is running. Waiting for 2 hours...'; "
            f"Start-Sleep -Seconds 7200; "
            f"Write-Host '🛑 Time is up. Stopping and Removing OCR Service...'; "
            f"docker rm -f paddlex; "
            f"Write-Host '👋 Bye!'"
        )
        return launch_powershell(session_name, docker_cmd, logger)
    else:
        docker_cmd = (
            f"echo '🚀 Starting OCR Service (Docker)...'; "
            f"if docker ps -a --format '{{{{.Names}}}}' | grep -q '^paddlex$'; then "
            f"  docker start paddlex; "
            f"else "
            f"  docker run -d --name paddlex "
            f"  -v \"$PWD:/paddle\" "
            f"  -v \"paddlex_data:/root\" "
            f"  --shm-size=8g "
            f"  --network=host "
            f"  {image} "
            f"  sh -lc \"paddlex --install serving && rm -f OCR.yaml && paddlex --get_pipeline_config OCR --save_path . && sed -i 's/_server_/_mobile_/g' OCR.yaml && paddlex --serve --pipeline OCR.yaml\"; "
            f"fi; "
            f"echo '✅ OCR Service is running. Waiting for 2 hours...'; "
            f"sleep 7200; "
            f"echo '🛑 Time is up. Stopping and Removing OCR Service...'; "
            f"docker rm -f paddlex; "
            f"echo '👋 Bye!'"
        )
        return launch_tmux(session_name, docker_cmd, logger)


def main() -> int:
    """主入口：加载会话配置并启动各会话。"""
    logger = setup_logger(name="cron_run_all_dungeons", level="INFO", use_color=True)
    ensure_log_dir()

    sessions = load_sessions_from_json(SCRIPT_DIR / "emulators.json")
    if not sessions:
        logger.error("❌ emulators.json 未找到或格式错误，无法继续")
        return 2

    launcher_name = "PowerShell 窗口" if IS_WINDOWS else "tmux 会话"
    logger.info("=" * 50)
    logger.info(f"🚀 启动 {launcher_name}（JSON 驱动）")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    # 1. 优先启动 OCR 服务
    logger.info("🔧 启动 OCR 服务 (PaddleX Docker)...")
    if launch_ocr_service(logger):
        logger.info(f"✅ OCR 服务{launcher_name}已启动 (将在2小时后自动关闭)")
        logger.info("⏳ 等待 30 秒以确保 OCR 服务完全就绪...")
        time.sleep(30)
    else:
        logger.error("❌ OCR 服务启动失败，后续任务可能会受影响")

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
        else:
            logger.error(f"❌ 会话 {name} 未提供有效的 configs 列表，已跳过")
            all_ok = False
            continue

        if IS_WINDOWS:
            ok = launch_powershell(name, cmd, logger)
        else:
            ok = launch_tmux(name, cmd, logger)
        all_ok = all_ok and ok
        time.sleep(1)

    if all_ok:
        logger.info(f"✅ 已并行启动所有 {launcher_name}")
        return 0
    logger.error("❌ 部分会话启动失败，请检查配置与环境")
    return 1


if __name__ == "__main__":
    sys.exit(main())
