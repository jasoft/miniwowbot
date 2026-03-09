#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""运行指定配置列表的副本脚本。

使用 Typer 提供命令行入口，支持显式会话名驱动统一日志命名。
"""

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, List, Optional

import typer

from logger_config import setup_logger, update_log_context, attach_emulator_file_handler
from auto_dungeon_notification import send_notification
from auto_dungeon_device import DeviceManager
from config_loader import load_config
from database import DungeonProgressDB

SCRIPT_DIR = Path(__file__).parent
os.environ["PATH"] = f"/opt/homebrew/bin:{os.environ.get('PATH', '')}"

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _is_windows() -> bool:
    return os.name == "nt"


def _get_kernel32():
    import ctypes

    return ctypes.windll.kernel32


def _set_windows_sleep_state(keep_awake: bool) -> bool:
    if not _is_windows():
        return True
    try:
        kernel32 = _get_kernel32()
        flags = ES_CONTINUOUS
        if keep_awake:
            flags |= ES_SYSTEM_REQUIRED
        return bool(kernel32.SetThreadExecutionState(flags))
    except Exception:
        return False


@contextmanager
def prevent_system_sleep(logger=None):
    ok = _set_windows_sleep_state(True)
    if logger and not ok:
        logger.warning("⚠️ 无法设置系统休眠抑制，运行期间可能进入休眠")
    try:
        yield
    finally:
        _set_windows_sleep_state(False)


def format_duration_zh(seconds: float) -> str:
    """将秒数格式化为中文的小时与分钟描述。

    Args:
        seconds: 时长（秒）。

    Returns:
        中文格式的时长描述，例如 "3 小时 2 分钟"；小于一分钟返回 "小于一分钟"。
    """
    try:
        total = int(seconds)
    except Exception:
        total = 0
    if total < 60:
        return "小于一分钟"
    hours = total // 3600
    minutes = (total % 3600) // 60
    if hours > 0 and minutes > 0:
        return f"{hours} 小时 {minutes} 分钟"
    if hours > 0:
        return f"{hours} 小时"
    return f"{minutes} 分钟"


def _get_config_path(config_name: str) -> Path:
    """获取配置文件路径。

    Args:
        config_name: 配置名称（不含扩展名）。

    Returns:
        配置文件的绝对路径。
    """
    return SCRIPT_DIR / "configs" / f"{config_name}.json"


def _is_config_completed(config_name: str, logger) -> Optional[bool]:
    """检查指定配置当日任务是否已完成。

    Args:
        config_name: 配置名称（不含扩展名）。
        logger: 日志记录器。

    Returns:
        True 表示已完成或无选定副本；False 表示仍有未完成任务；None 表示检查失败。
    """
    try:
        config_path = _get_config_path(config_name)
        config_loader = load_config(str(config_path))
        total_selected = config_loader.get_selected_dungeon_count()

        if total_selected <= 0:
            logger.info(f"ℹ️ 配置 {config_name} 未选定任何副本，跳过执行")
            return True

        with DungeonProgressDB(config_name=config_loader.get_config_name()) as db:
            db.cleanup_old_records(days_to_keep=7)
            completed = db.get_today_completed_count()

        if completed >= total_selected:
            logger.info(f"✅ 配置 {config_name} 今日已完成 {completed}/{total_selected}")
            return True

        remaining = total_selected - completed
        logger.info(f"📌 配置 {config_name} 今日剩余 {remaining}/{total_selected}")
        return False
    except Exception as exc:
        logger.warning(f"⚠️ 预检查配置 {config_name} 失败: {exc}，将继续执行以避免误判")
        return None


def filter_pending_configs(configs: Iterable[str], logger) -> List[str]:
    """过滤出仍需执行的配置列表。

    Args:
        configs: 待检查的配置名称列表。
        logger: 日志记录器。

    Returns:
        仍需执行的配置名称列表。检查失败的配置会保守地保留在结果中。
    """
    pending_cfgs: List[str] = []
    for cfg in configs:
        normalized_cfg = str(cfg).strip()
        if not normalized_cfg:
            continue
        completed = _is_config_completed(normalized_cfg, logger)
        if completed is True:
            continue
        pending_cfgs.append(normalized_cfg)
    return pending_cfgs


def _invoke_auto_dungeon_once(config_name: str, emulator: str, session: str) -> int:
    """执行一次 auto_dungeon 对应配置。

    通过导入 `auto_dungeon` 并调用其入口，避免外部命令拼接。

    Args:
        config_name: 配置名称（字符职业），对应 `configs/<name>.json`
        emulator: 模拟器地址，如 `192.168.1.150:5555`

    Returns:
        退出码，0 表示成功，其它表示失败
    """
    import importlib

    config_file = SCRIPT_DIR / "configs" / f"{config_name}.json"
    argv_backup = sys.argv[:]
    try:
        # 注入会话名到全局日志上下文
        update_log_context({"session": session})
        sys.argv = [
            "auto_dungeon.py",
            "-c",
            str(config_file),
            "--emulator",
            emulator,
            "--max-iterations",
            "1",
        ]
        mod = importlib.import_module("auto_dungeon")
        # main_wrapper 会根据内部状态抛出 SystemExit；捕获后转化为退出码
        try:
            mod.main_wrapper()
            return 0
        except SystemExit as se:  # type: ignore[no-redef]
            code = se.code if isinstance(se.code, int) else 1
            return int(code)
    except Exception:
        return 1
    finally:
        sys.argv = argv_backup


def _ensure_emulator_ready(emulator: str, logger) -> bool:
    """确保模拟器已就绪。

    使用 DeviceManager 检查并启动模拟器。
    """
    try:
        logger.info(f"🛠️ 检查模拟器状态: {emulator}")
        device_manager = DeviceManager()
        # initialize 会自动处理连接和启动
        device_manager.initialize(emulator_name=emulator)
        logger.info(f"✅ 模拟器 {emulator} 已就绪")
        return True
    except Exception as e:
        logger.error(f"❌ 模拟器准备失败: {e}")
        return False


def run_configs(
    configs: Iterable[str],
    emulator: str,
    session: str,
    retries: int = 3,
    logfile: Optional[Path] = None,
    dryrun: bool = False,
) -> int:
    """按顺序运行配置列表（带重试与汇总）。

    Args:
        configs: 配置名称列表
        emulator: 模拟器地址
        retries: 最大重试次数（每个配置）
        logfile: 日志文件路径（追加）

    Returns:
        总体退出码：全部成功为 0，否则为 1
    """
    update_log_context({"session": session})
    if logfile is None:
        logfile = SCRIPT_DIR / "log" / f"autodungeon_{session}.log"
    try:
        attach_emulator_file_handler(
            emulator_name=emulator, config_name=None, log_dir=str(logfile.parent)
        )
    except Exception:
        pass
    logger = setup_logger(name="run_dungeons", level="INFO", use_color=False)

    cfgs: List[str] = [c for c in configs if str(c).strip()]
    if not cfgs:
        logger = setup_logger(name="run_dungeons", level="INFO", use_color=False)
        logger.error("❌ 未提供任何配置，必须显式传入 --config")
        try:
            send_notification("副本运行汇总", "未提供任何配置，任务未执行")
        except Exception:
            pass
        return 2

    pending_cfgs = filter_pending_configs(cfgs, logger)

    if not pending_cfgs:
        logger.info("✅ 所有配置当日任务已完成，无需启动模拟器，脚本退出")
        return 0

    with prevent_system_sleep(logger):
        # 确保模拟器已启动
        if not _ensure_emulator_ready(emulator, logger):
            logger.error("❌ 无法启动或连接模拟器，任务终止")
            try:
                send_notification("副本运行错误", f"无法启动模拟器 {emulator}")
            except Exception:
                pass
            return 1

        total = len(pending_cfgs)
        success = 0
        failed = 0
        start_ts = int(time.time())
        per_durations: List[tuple[str, float]] = []

        logger.info("=" * 50)
        logger.info(f"🎮 目标模拟器: {emulator}")
        logger.info(
            f"📋 将顺序运行 {total} 个配置: {', '.join(pending_cfgs) if pending_cfgs else '全部(空列表)'}"
        )
        logger.info("=" * 50)

        for idx, cfg in enumerate(pending_cfgs, start=1):
            logger.info("")
            logger.info(f"▶️ [{idx}/{total}] 运行配置: {cfg}")
            attempt = 0
            cfg_start = time.time()
            if dryrun:
                logger.info("🧪 dryrun 模式：跳过实际脚本执行，模拟成功")
                success += 1
                per_durations.append((cfg, time.time() - cfg_start))
                continue
            while attempt < max(1, retries):
                rc = _invoke_auto_dungeon_once(cfg, emulator, session)
                if rc == 0:
                    success += 1
                    logger.info(f"✅ 配置 {cfg} 运行成功")
                    break
                if attempt == 0:
                    # 第一次失败尝试重新检查模拟器状态
                    _ensure_emulator_ready(emulator, logger)
                attempt += 1
                if attempt < retries:
                    wait_sec = attempt * 10
                    logger.warning(f"⏳ 配置 {cfg} 失败，{wait_sec}s 后重试… ({attempt}/{retries})")
                    time.sleep(wait_sec)
            else:
                failed += 1
                logger.error(f"❌ 配置 {cfg} 多次重试仍失败")
            per_durations.append((cfg, time.time() - cfg_start))

        duration = int(time.time()) - start_ts
        logger.info("")
        logger.info("=" * 50)
        logger.info(f"📊 总计: {total}，成功: {success}，失败: {failed}，耗时: {duration}s")
        logger.info("=" * 50)

        summary_lines = [
            f"成功: {success}/{total}",
            f"失败: {failed}",
            "配置耗时:",
        ]
        for name, dur in per_durations:
            summary_lines.append(f"• {name}: {format_duration_zh(dur)}")
        summary_lines.append(f"总耗时: {format_duration_zh(duration)}")
        try:
            send_notification("副本运行汇总", "\n".join(summary_lines))
        except Exception:
            pass

        return 0 if failed == 0 else 1


app = typer.Typer(add_completion=False)


@app.command()
def run(
    emulator: str = typer.Option(..., "--emulator", help="模拟器地址，如 192.168.1.150:5555"),
    session: str = typer.Option(..., "--session", help="会话名称，用于统一日志命名"),
    config: List[str] = typer.Option(..., "--config", help="配置名称，可重复"),
    retries: int = typer.Option(3, "--retries", min=1, help="失败重试次数（每配置）"),
    logfile: Optional[Path] = typer.Option(None, "--logfile", help="日志文件路径（追加写入）"),
    dryrun: bool = typer.Option(False, "--dryrun", help="只检查模拟器连接，后续流程模拟执行"),
) -> None:
    """运行指定的配置列表。"""
    try:
        rc = run_configs(
            config,
            emulator,
            session,
            retries=max(1, retries),
            logfile=logfile,
            dryrun=dryrun,
        )
    except KeyboardInterrupt:
        _set_windows_sleep_state(False)
        raise
    finally:
        _set_windows_sleep_state(False)
    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
