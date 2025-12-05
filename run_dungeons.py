#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""运行指定配置列表的副本脚本。

使用 Typer 提供命令行入口，支持显式会话名驱动统一日志命名。
"""

import os
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional
import typer

from logger_config import setup_logger, update_log_context, attach_emulator_file_handler
from auto_dungeon import send_bark_notification


SCRIPT_DIR = Path(__file__).parent
os.environ["PATH"] = f"/opt/homebrew/bin:{os.environ.get('PATH', '')}"


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


def run_configs(configs: Iterable[str], emulator: str, session: str, retries: int = 3, logfile: Optional[Path] = None) -> int:
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
        attach_emulator_file_handler(emulator_name=emulator, config_name=None, log_dir=str(logfile.parent))
    except Exception:
        pass
    logger = setup_logger(name="run_dungeons", level="INFO", use_color=False)

    cfgs: List[str] = [c for c in configs if str(c).strip()]
    if not cfgs:
        logger = setup_logger(name="run_dungeons", level="INFO", use_color=False)
        logger.error("❌ 未提供任何配置，必须显式传入 --config")
        try:
            send_bark_notification("副本运行汇总", "未提供任何配置，任务未执行")
        except Exception:
            pass
        return 2
    total = len(cfgs)
    success = 0
    failed = 0
    start_ts = int(time.time())
    per_durations: List[tuple[str, float]] = []

    logger.info("=" * 50)
    logger.info(f"🎮 目标模拟器: {emulator}")
    logger.info(f"📋 将顺序运行 {total} 个配置: {', '.join(cfgs) if cfgs else '全部(空列表)'}")
    logger.info("=" * 50)

    for idx, cfg in enumerate(cfgs, start=1):
        logger.info("")
        logger.info(f"▶️ [{idx}/{total}] 运行配置: {cfg}")
        attempt = 0
        cfg_start = time.time()
        while attempt < max(1, retries):
            rc = _invoke_auto_dungeon_once(cfg, emulator, session)
            if rc == 0:
                success += 1
                logger.info(f"✅ 配置 {cfg} 运行成功")
                break
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
        summary_lines.append(f"• {name}: {dur:.1f}s")
    summary_lines.append(f"总耗时: {duration}s")
    try:
        send_bark_notification("副本运行汇总", "\n".join(summary_lines))
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
) -> None:
    """运行指定的配置列表。"""
    rc = run_configs(config, emulator, session, retries=max(1, retries), logfile=logfile)
    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
