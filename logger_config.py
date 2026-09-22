# -*- encoding=utf8 -*-
"""
通用日志配置模块
提供统一的日志配置功能，支持多种日志格式和输出方式
"""

import json
import io
import logging
import os
import sys
from typing import Dict, Optional, Sequence

from vibe_logger import (
    DEFAULT_DATE_FORMAT,
    DEFAULT_LOG_FORMAT,
    GlobalLogContext,
    LoggerConfig as BaseLoggerConfig,
    _ContextFilter,
    attach_file_handler,
    log_calls,
    setup_logger,
)

from project_paths import resolve_project_path


def _is_windows() -> bool:
    return os.name == "nt"


def ensure_utf8_output() -> None:
    """在 Windows 上强制标准输出/错误为 UTF-8，避免 GBK 编码错误。"""
    if not _is_windows():
        return

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for attr in ("stdout", "stderr"):
        stream = getattr(sys, attr, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
            continue
        except Exception:
            pass
        try:
            stream = io.TextIOWrapper(
                stream.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
            setattr(sys, attr, stream)
        except Exception:
            continue

# Re-export these
__all__ = [
    "GlobalLogContext",
    "LoggerConfig",
    "setup_logger",
    "log_calls",
    "attach_file_handler",
    "setup_simple_logger",
    "get_logger",
    "setup_logger_from_json",
    "setup_logger_from_env",
    "setup_logger_from_config",
    "update_log_context",
    "attach_emulator_file_handler",
    "attach_file_handler_to_loggers",
    "get_log_file_path",
    "DEFAULT_COLOR_FORMAT",
    "DEFAULT_COLOR_DATE_FORMAT",
    "DEFAULT_SIMPLE_FORMAT",
    "LOG_LEVELS",
    "apply_logging_slice",
    "ensure_utf8_output",
]

DEFAULT_COLOR_FORMAT = DEFAULT_LOG_FORMAT
DEFAULT_COLOR_DATE_FORMAT = DEFAULT_DATE_FORMAT
DEFAULT_SIMPLE_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(config)s %(emulator)s %(message)s"

ensure_utf8_output()
GlobalLogContext.set_defaults({"config": "unknown", "emulator": "unknown"})

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

class LoggerConfig(BaseLoggerConfig):
    @classmethod
    def get_simple_logger(
        cls, name: Optional[str] = None, level: str = "INFO"
    ) -> logging.Logger:
        """
        获取简单配置的日志记录器（使用basicConfig）
        适用于不需要颜色或复杂格式的脚本
        """
        import sys

        if name is None:
            name = "root"

        logger = logging.getLogger(name)

        if logger.handlers:
            return logger

        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format=DEFAULT_SIMPLE_FORMAT,
            handlers=[logging.StreamHandler(sys.stdout)],
        )

        # 格式串里含 `%(config)s %(emulator)s`（值由 GlobalLogContext 提供），
        # 而 basicConfig 不会自动挂注入用的 filter —— 不挂的话每打一条日志都抛
        # `ValueError: Formatting field not found in record: 'config'`，
        # 控制台上只留一堆 traceback、看不到真正想打的内容。
        for handler in logging.getLogger().handlers:
            if not any(isinstance(f, _ContextFilter) for f in handler.filters):
                handler.addFilter(_ContextFilter())

        return logger

def setup_simple_logger(
    name: Optional[str] = None, level: str = "INFO"
) -> logging.Logger:
    return LoggerConfig.get_simple_logger(name=name, level=level)

def get_logger(name: Optional[str] = None) -> logging.Logger:
    return setup_logger(name=name, level="INFO")

def setup_logger_from_json(config_file: str, use_color: bool = True) -> logging.Logger:
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        logging_cfg = data.get("logging", {})
        name = logging_cfg.get("logger_name", "root")
        level = logging_cfg.get("level", "INFO")
        fmt = logging_cfg.get("format")
        datefmt = logging_cfg.get("date_format")
        return setup_logger(name=name, level=level, log_format=fmt, date_format=datefmt, use_color=use_color)
    except Exception:
        return setup_logger(name="root", level="INFO", use_color=use_color)

def setup_logger_from_env(use_color: bool = True) -> logging.Logger:
    name = os.environ.get("LOGGER_NAME", "root")
    level = os.environ.get("LOG_LEVEL", "INFO")
    fmt = os.environ.get("LOG_FORMAT")
    datefmt = os.environ.get("LOG_DATE_FORMAT")
    return setup_logger(name=name, level=level, log_format=fmt, date_format=datefmt, use_color=use_color)

def setup_logger_from_config(config_file: str = "system_config.json", use_color: bool = True) -> logging.Logger:
    """从系统环境配置初始化日志，使用包含 config 和 emulator 的格式。"""
    name = os.environ.get("LOGGER_NAME", "root")
    level = os.environ.get("LOG_LEVEL", "INFO")
    # 使用包含 config 和 emulator 的格式
    log_format = os.environ.get("LOG_FORMAT") or DEFAULT_SIMPLE_FORMAT
    datefmt = os.environ.get("LOG_DATE_FORMAT") or DEFAULT_DATE_FORMAT
    return setup_logger(name=name, level=level, log_format=log_format, date_format=datefmt, use_color=use_color)

def update_log_context(labels: Dict[str, str]) -> None:
    GlobalLogContext.update(labels)

def _sanitize_component(value: str) -> str:
    if not value:
        return "unknown"
    return str(value).replace(":", "_").replace("/", "_").replace(" ", "_")

def get_log_file_path(log_dir: str = "log", emulator_name: Optional[str] = None, prefix: str = "autodungeon") -> str:
    os.makedirs(log_dir, exist_ok=True)
    session_name: Optional[str] = None
    try:
        emulators_path = resolve_project_path("emulators.json")
        if os.path.exists(emulators_path):
            with open(emulators_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sessions = data.get("sessions", [])
            target_emulator = (emulator_name or GlobalLogContext.context.get("emulator") or "").strip()
            for s in sessions:
                if str(s.get("emulator", "")).strip() == target_emulator:
                    session_name = s.get("name")
                    break
    except Exception:
        session_name = None

    base_name = session_name or emulator_name or GlobalLogContext.context.get("emulator") or "unknown"
    safe = _sanitize_component(base_name)
    return os.path.join(log_dir, f"{prefix}_{safe}.log")

def attach_emulator_file_handler(
    emulator_name: str,
    config_name: Optional[str] = None,
    log_dir: str = "log",
    level: str = "DEBUG",
) -> str:
    if config_name:
        GlobalLogContext.update({"config": config_name})
    GlobalLogContext.update({"emulator": emulator_name or "unknown"})

    file_path = get_log_file_path(log_dir=log_dir, emulator_name=emulator_name)

    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setLevel(getattr(logging, level.upper()))
    file_handler.addFilter(_ContextFilter())
    file_handler.setFormatter(
        logging.Formatter(
            DEFAULT_COLOR_FORMAT,
            datefmt=DEFAULT_COLOR_DATE_FORMAT,
        )
    )

    target_logger = logging.getLogger()
    already_attached = any(
        isinstance(h, logging.FileHandler) and getattr(h, "_log_file", None) == file_path
        for h in target_logger.handlers
    )
    if not already_attached:
        setattr(file_handler, "_log_file", file_path)
        target_logger.addHandler(file_handler)

    return file_path

def attach_file_handler_to_loggers(
    filename: str,
    log_dir: str = "log",
    level: str = "INFO",
    logger_names: Sequence[Optional[str]] = (None,),
) -> str:
    """把同一个日志文件挂到多个 logger 上（``None`` 表示 root logger）。

    背景（2026-09-22 实测）：vibe_logger 的 ``configure_logger`` 会把**具名**
    logger 的 ``propagate`` 置为 ``False``（防止控制台重复输出），而本项目的
    文件 handler 习惯挂在 root 上。两者叠加的结果是——**具名 logger 的日志
    永远进不了文件**，只有其它模块（走 root）的日志能落盘。

    ``cron_run_all_dungeons``（编排器）与 ``run_dungeons``（单会话入口）都踩了
    这个坑：整轮重试、每轮耗时、汇总推送、模拟器准备失败这些**最关键的线索**
    只进控制台，进程一结束就没了。因此这里显式地把 handler 分别挂到 root 与
    具名 logger 上：两棵 logger 树各写各的，同一条记录不会被写两遍。

    Args:
        filename: 日志文件名（如 ``cron_2026-09-22.log``）。
        log_dir: 日志目录。
        level: 文件 handler 级别。
        logger_names: 需要挂载 handler 的 logger 名；``None`` 表示 root。

    Returns:
        str: 日志文件路径。
    """
    path = ""
    for logger_name in logger_names:
        path = attach_file_handler(
            logger_name=logger_name,
            log_dir=log_dir,
            filename=filename,
            level=level,
        )
    return path


def apply_logging_slice(targets, level: str = "DEBUG") -> None:
    dec = log_calls(level=level)
    for owner, attr in targets:
        try:
            original = getattr(owner, attr)
        except Exception:
            continue
        try:
            wrapped = dec(original)
            setattr(owner, attr, wrapped)
        except Exception:
            pass
