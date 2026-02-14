#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""最终入口脚本。

基于 ``emulators.json`` 启动多个副本会话，并在运行期监控每个会话日志：
当某个会话在 1 分钟内无日志更新时，自动重启该会话并重跑命令。
当所有会话结束后执行 ``poe stats`` 校验是否全部完成，不通过则重试整轮流程。
"""

import json
import logging
import os
import platform
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence

import dotenv

from logger_config import setup_logger

SCRIPT_DIR = Path(__file__).parent
IS_WINDOWS = platform.system() == "Windows"
LOG_IDLE_TIMEOUT_SECONDS = 60
MONITOR_POLL_INTERVAL_SECONDS = 5
FLOW_MAX_RETRIES = 5
SESSION_START_GAP_SECONDS = 1

if not IS_WINDOWS:
    os.environ["PATH"] = f"/opt/homebrew/bin:{os.environ.get('PATH', '')}"

dotenv.load_dotenv()


@dataclass
class SessionTask:
    """单个副本会话配置。

    Attributes:
        name: 会话名称。
        emulator: 模拟器地址。
        logfile: 会话日志文件路径。
        cmd: 启动会话执行的命令行。
    """

    name: str
    emulator: str
    logfile: Path
    cmd: str


@dataclass
class SessionRuntime:
    """单个会话的运行态。

    Attributes:
        task: 会话配置。
        process: Windows 下对应的 PowerShell 进程句柄。
        last_log_signature: 最近一次日志签名，格式为 ``(mtime, size)``。
        last_activity_ts: 最近一次日志活跃时间戳。
        restart_count: 当前会话累计重启次数。
        finished_exit_code: 会话最终退出码，未结束时为 ``None``。
    """

    task: SessionTask
    process: Optional[subprocess.Popen[str]] = None
    last_log_signature: tuple[float, int] = (0.0, 0)
    last_activity_ts: float = field(default_factory=time.time)
    restart_count: int = 0
    finished_exit_code: Optional[int] = None


def ensure_log_dir() -> None:
    """确保日志目录存在。

    Returns:
        None
    """
    log_dir = SCRIPT_DIR / "log"
    log_dir.mkdir(parents=True, exist_ok=True)


def build_cmd_for_configs(
    session: str, emulator: str, logfile: Path, configs: Sequence[str]
) -> str:
    """构建运行配置列表的命令（通过 uv 调用 Python 入口）。

    Args:
        session: 会话名称。
        emulator: 模拟器地址。
        logfile: 输出日志文件路径。
        configs: 需要运行的配置列表。

    Returns:
        拼接好的命令字符串。
    """
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


def load_sessions_from_json(config_path: Path) -> Optional[list[dict[str, Any]]]:
    """加载 JSON 会话配置。

    Args:
        config_path: 会话配置文件路径。

    Returns:
        会话配置字典列表；当文件不存在或格式无效时返回 ``None``。
    """
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


def parse_session_tasks(
    sessions: Sequence[dict[str, Any]], logger: logging.Logger
) -> list[SessionTask]:
    """把原始配置解析为可执行会话任务。

    Args:
        sessions: JSON 中读取到的会话配置。
        logger: 日志对象。

    Returns:
        解析后可执行的会话任务列表。
    """
    tasks: list[SessionTask] = []
    for idx, sess in enumerate(sessions, start=1):
        name = str(sess.get("name", f"dungeon_{idx}")).strip()
        emulator = str(sess.get("emulator", "")).strip()
        configs = sess.get("configs")
        logfile = Path(sess.get("log") or (SCRIPT_DIR / "log" / f"autodungeon_{name}.log"))

        if not emulator:
            logger.error(f"❌ 会话 {name} 未提供 emulator，已跳过")
            continue

        if not isinstance(configs, list) or len(configs) == 0:
            logger.error(f"❌ 会话 {name} 未提供有效的 configs 列表，已跳过")
            continue

        details = ", ".join(str(item) for item in configs)
        logger.info(f"🔧 {name}: 配置[{details}] @ {emulator}")
        cmd = build_cmd_for_configs(name, emulator, logfile, [str(item) for item in configs])
        logger.info(f"🖥️  启动命令行: {cmd}")
        tasks.append(SessionTask(name=name, emulator=emulator, logfile=logfile, cmd=cmd))

    return tasks


def launch_tmux(session: str, cmd: str, logger: logging.Logger) -> bool:
    """启动 tmux 会话执行指定命令。

    Args:
        session: tmux 会话名称。
        cmd: 需要执行的命令。
        logger: 日志对象。

    Returns:
        是否启动成功。
    """
    try:
        has = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True)
        if has.returncode == 0:
            subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
        result = subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                session,
                "-c",
                str(SCRIPT_DIR),
                cmd,
            ],
            capture_output=True,
        )
        if result.returncode == 0:
            logger.info(f"🧰 tmux 会话已启动: {session}")
            return True
        stderr = result.stderr.decode() if isinstance(result.stderr, bytes) else str(result.stderr)
        logger.error(f"❌ 启动 tmux 失败: {stderr}")
    except Exception as exc:
        logger.error(f"❌ tmux 异常: {exc}")
    return False


def kill_tmux_session(session: str, logger: logging.Logger) -> None:
    """停止 tmux 会话。

    Args:
        session: tmux 会话名称。
        logger: 日志对象。

    Returns:
        None
    """
    try:
        subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
    except Exception as exc:
        logger.warning(f"⚠️ 停止 tmux 会话 {session} 失败: {exc}")


def is_tmux_session_alive(session: str) -> bool:
    """检查 tmux 会话是否存活。

    Args:
        session: tmux 会话名称。

    Returns:
        会话是否存在。
    """
    result = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True)
    return result.returncode == 0


def launch_powershell(
    session: str, cmd: str, logger: logging.Logger
) -> Optional[subprocess.Popen[str]]:
    """在 Windows 上启动一个新的 PowerShell 窗口执行命令。

    Args:
        session: 窗口标题（会话名）。
        cmd: 需要执行的命令。
        logger: 日志对象。

    Returns:
        成功时返回进程句柄，失败时返回 ``None``。
    """
    try:
        full_cmd = (
            f"$Host.UI.RawUI.WindowTitle = '{session}'; "
            f"Set-Location '{SCRIPT_DIR}'; "
            f"{cmd}; "
            "if ($LASTEXITCODE -eq 0) { exit }"
        )
        process = subprocess.Popen(
            ["pwsh", "-NoExit", "-Command", full_cmd],
            creationflags=subprocess.CREATE_NEW_CONSOLE if IS_WINDOWS else 0,
            text=True,
        )
        logger.info(f"🧰 PowerShell 窗口已启动: {session} (pid={process.pid})")
        return process
    except Exception as exc:
        logger.error(f"❌ 启动 PowerShell 失败: {exc}")
        return None


def stop_powershell(
    process: Optional[subprocess.Popen[str]], session: str, logger: logging.Logger
) -> None:
    """停止 PowerShell 进程。

    Args:
        process: 进程句柄。
        session: 会话名称。
        logger: 日志对象。

    Returns:
        None
    """
    if process is None:
        return
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        logger.warning(f"⚠️ 会话 {session} 终止超时，执行 kill")
        process.kill()
    except Exception as exc:
        logger.warning(f"⚠️ 停止会话 {session} 异常: {exc}")


def read_log_signature(logfile: Path) -> tuple[float, int]:
    """读取日志签名（修改时间+大小）。

    Args:
        logfile: 日志文件路径。

    Returns:
        二元组 ``(mtime, size)``；文件不存在时返回 ``(0.0, 0)``。
    """
    try:
        stat_result = logfile.stat()
    except OSError:
        return (0.0, 0)
    return (stat_result.st_mtime, stat_result.st_size)


def start_session(runtime: SessionRuntime, logger: logging.Logger) -> bool:
    """启动一个会话任务。

    Args:
        runtime: 会话运行态对象。
        logger: 日志对象。

    Returns:
        是否启动成功。
    """
    runtime.task.logfile.parent.mkdir(parents=True, exist_ok=True)
    runtime.task.logfile.touch(exist_ok=True)
    runtime.finished_exit_code = None

    if IS_WINDOWS:
        process = launch_powershell(runtime.task.name, runtime.task.cmd, logger)
        if process is None:
            return False
        runtime.process = process
    else:
        if not launch_tmux(runtime.task.name, runtime.task.cmd, logger):
            return False
        runtime.process = None

    runtime.last_log_signature = read_log_signature(runtime.task.logfile)
    runtime.last_activity_ts = time.time()
    return True


def restart_session(runtime: SessionRuntime, logger: logging.Logger) -> bool:
    """重启一个运行中的会话。

    Args:
        runtime: 会话运行态对象。
        logger: 日志对象。

    Returns:
        是否重启成功。
    """
    runtime.restart_count += 1
    logger.warning(
        f"⚠️ 会话 {runtime.task.name} 连续 {LOG_IDLE_TIMEOUT_SECONDS} 秒无日志更新，"
        f"准备重启（第 {runtime.restart_count} 次）"
    )

    if IS_WINDOWS:
        stop_powershell(runtime.process, runtime.task.name, logger)
    else:
        kill_tmux_session(runtime.task.name, logger)

    return start_session(runtime, logger)


def is_session_alive(runtime: SessionRuntime) -> bool:
    """判断会话是否仍在运行。

    Args:
        runtime: 会话运行态对象。

    Returns:
        会话是否运行中。
    """
    if IS_WINDOWS:
        if runtime.process is None:
            return False
        return runtime.process.poll() is None
    return is_tmux_session_alive(runtime.task.name)


def get_session_exit_code(runtime: SessionRuntime) -> int:
    """获取会话退出码。

    Args:
        runtime: 会话运行态对象。

    Returns:
        会话退出码，无法获取时返回 ``1``。
    """
    if IS_WINDOWS:
        if runtime.process is None:
            return 1
        return_code = runtime.process.poll()
        if return_code is None:
            return 1
        return return_code
    return 0


def monitor_sessions(runtimes: Sequence[SessionRuntime], logger: logging.Logger) -> None:
    """监控所有会话，发现日志停滞即重启。

    Args:
        runtimes: 会话运行态列表。
        logger: 日志对象。

    Returns:
        None
    """
    logger.info("👀 进入会话监控循环，等待所有 shell 窗口结束...")
    while True:
        alive_count = 0
        now_ts = time.time()

        for runtime in runtimes:
            if is_session_alive(runtime):
                alive_count += 1
                current_signature = read_log_signature(runtime.task.logfile)
                if current_signature != runtime.last_log_signature:
                    runtime.last_log_signature = current_signature
                    runtime.last_activity_ts = now_ts
                elif now_ts - runtime.last_activity_ts >= LOG_IDLE_TIMEOUT_SECONDS:
                    if not restart_session(runtime, logger):
                        runtime.finished_exit_code = 1
                        logger.error(f"❌ 会话 {runtime.task.name} 重启失败")
            else:
                if runtime.finished_exit_code is None:
                    runtime.finished_exit_code = get_session_exit_code(runtime)
                    logger.info(
                        f"🏁 会话 {runtime.task.name} 已结束，"
                        f"exit code={runtime.finished_exit_code}"
                    )

        if alive_count == 0:
            logger.info("✅ 所有 shell 窗口均已结束")
            return

        time.sleep(MONITOR_POLL_INTERVAL_SECONDS)


def run_poe_stats(logger: logging.Logger) -> bool:
    """执行 ``poe stats`` 并校验退出码。

    Args:
        logger: 日志对象。

    Returns:
        当退出码为 0 时返回 ``True``，否则返回 ``False``。
    """
    logger.info("📊 执行 `poe stats` 校验副本是否全部完成...")
    try:
        result = subprocess.run(
            ["poe", "stats"],
            cwd=str(SCRIPT_DIR),
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        logger.error(f"❌ 执行 `poe stats` 异常: {exc}")
        return False

    if result.stdout.strip():
        logger.info(f"`poe stats` 输出:\n{result.stdout.strip()}")
    if result.stderr.strip():
        logger.warning(f"`poe stats` 错误输出:\n{result.stderr.strip()}")

    if result.returncode == 0:
        logger.info("✅ `poe stats` 返回 0，判定全部完成")
        return True

    logger.warning(f"⚠️ `poe stats` 返回 {result.returncode}，存在未完成副本")
    return False


def check_ocr_health(logger: logging.Logger) -> bool:
    """检查 OCR 服务健康状态。

    Args:
        logger: 日志对象（保留参数便于后续扩展日志输出）。

    Returns:
        OCR 服务是否健康。
    """
    url = os.getenv("OCR_HEALTH_URL", "http://localhost:8081/health")
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            if response.status == 200:
                return True
    except Exception:
        pass
    return False


def launch_ocr_service(logger: logging.Logger) -> bool:
    """启动 OCR Docker 服务（如果未就绪）。

    Args:
        logger: 日志对象。

    Returns:
        启动流程是否成功执行。
    """
    if check_ocr_health(logger):
        logger.info("✅ OCR 服务 (/health) 响应正常，跳过启动")
        return True

    logger.info("🔧 OCR 服务未就绪，尝试调用脚本启动...")
    script_dir = SCRIPT_DIR / "scripts"

    try:
        if IS_WINDOWS:
            script_path = script_dir / "start_ocr_docker.ps1"
            cmd = ["pwsh", "-File", str(script_path)]
        else:
            script_path = script_dir / "start_ocr_docker.sh"
            cmd = ["bash", str(script_path)]

        if not script_path.exists():
            logger.error(f"❌ 启动脚本不存在: {script_path}")
            return False

        logger.info(f"🚀 执行脚本: {script_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPT_DIR))

        if result.returncode == 0:
            logger.info(f"✅ 启动脚本执行成功\n{result.stdout.strip()}")
            return True
        else:
            logger.error(
                f"❌ 启动脚本失败 (Exit {result.returncode}):\nStdout: {result.stdout}\nStderr: {result.stderr}"
            )
            return False

    except Exception as exc:
        logger.error(f"❌ 启动 OCR 服务异常: {exc}")
        return False


def prepare_ocr_service(logger: logging.Logger) -> None:
    """确保 OCR 服务可用。

    Args:
        logger: 日志对象。

    Returns:
        None
    """
    logger.info("🔧 启动 OCR 服务 (PaddleX Docker)...")
    is_already_healthy = check_ocr_health(logger)

    if launch_ocr_service(logger):
        logger.info("✅ OCR 服务已启动")
        if is_already_healthy:
            logger.info("⚡ OCR 服务 (/health) 已正常，跳过等待")
            return

        logger.info("⏳ 新启动的服务，等待就绪 (最多 30 秒)...")
        start_time = time.time()
        while time.time() - start_time < 30:
            if check_ocr_health(logger):
                logger.info(f"✅ OCR 服务已就绪 (耗时 {time.time() - start_time:.1f}s)")
                return
            time.sleep(1)
        logger.warning("⚠️ 等待超时，服务可能仍在启动中...")
        return

    logger.error("❌ OCR 服务启动失败，后续任务可能会受影响")


def run_single_flow(tasks: Sequence[SessionTask], logger: logging.Logger) -> bool:
    """执行一次完整流程并返回是否成功完成。

    Args:
        tasks: 当前需要执行的会话任务列表。
        logger: 日志对象。

    Returns:
        ``poe stats`` 返回 0 时为 ``True``，否则为 ``False``。
    """
    runtimes = [SessionRuntime(task=task) for task in tasks]
    started_count = 0

    for runtime in runtimes:
        if start_session(runtime, logger):
            started_count += 1
        else:
            runtime.finished_exit_code = 1
            logger.error(f"❌ 会话 {runtime.task.name} 启动失败")
        time.sleep(SESSION_START_GAP_SECONDS)

    if started_count == 0:
        logger.error("❌ 本轮没有任何会话成功启动")
        return False

    monitor_sessions(runtimes, logger)
    return run_poe_stats(logger)


def main() -> int:
    """主入口。

    Returns:
        进程退出码。``0`` 表示全部完成，非 ``0`` 表示失败。
    """
    logger = setup_logger(name="cron_run_all_dungeons", level="INFO", use_color=True)
    ensure_log_dir()

    sessions = load_sessions_from_json(SCRIPT_DIR / "emulators.json")
    if not sessions:
        logger.error("❌ emulators.json 未找到或格式错误，无法继续")
        return 2

    launcher_name = "PowerShell 窗口" if IS_WINDOWS else "tmux 会话"
    logger.info("=" * 50)
    logger.info(f"🚀 准备启动 {launcher_name}（JSON 驱动）")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    tasks = parse_session_tasks(sessions, logger)
    if not tasks:
        logger.error("❌ 未解析到可执行会话，无法继续")
        return 2

    prepare_ocr_service(logger)

    for attempt in range(1, FLOW_MAX_RETRIES + 1):
        logger.info(
            f"🔁 开始第 {attempt}/{FLOW_MAX_RETRIES} 次全流程执行，"
            f"当前会话数: {len(tasks)}"
        )
        if run_single_flow(tasks, logger):
            logger.info("🎉 所有副本已完成，本次流程成功")
            return 0

        if attempt < FLOW_MAX_RETRIES:
            logger.warning("⚠️ 仍有未完成副本，将重试整轮流程")
        else:
            logger.error("❌ 达到最大重试次数，仍未全部完成")

    return 1


if __name__ == "__main__":
    sys.exit(main())
