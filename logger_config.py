# -*- encoding=utf8 -*-
"""
通用日志配置模块
提供统一的日志配置功能，支持多种日志格式和输出方式
"""

import logging
import os
import json
from typing import Optional, Dict
from project_paths import resolve_project_path

# Import from the installed package
from colored_context_logger import (
    GlobalLogContext,
    LoggerConfig as BaseLoggerConfig,
    setup_logger,
    log_calls,
    attach_file_handler,
    DEFAULT_LOG_FORMAT,
    DEFAULT_DATE_FORMAT,
    _ContextFilter,
)

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
    "get_log_file_path",
    "DEFAULT_COLOR_FORMAT",
    "DEFAULT_COLOR_DATE_FORMAT",
    "DEFAULT_SIMPLE_FORMAT",
    "LOG_LEVELS",
    "apply_logging_slice",
]

DEFAULT_COLOR_FORMAT = DEFAULT_LOG_FORMAT
DEFAULT_COLOR_DATE_FORMAT = DEFAULT_DATE_FORMAT
DEFAULT_SIMPLE_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(config)s %(emulator)s %(message)s"

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
    return setup_logger_from_env(use_color=use_color)

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