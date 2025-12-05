# -*- encoding=utf8 -*-
"""
通用日志配置模块
提供统一的日志配置功能，支持多种日志格式和输出方式
"""

import logging
import os
from typing import Optional, Dict

# 导入 coloredlogs
try:
    import coloredlogs
except ImportError:
    coloredlogs = None

class _ContextFilter(logging.Filter):
    """在 LogRecord 中注入全局上下文（config、emulator）。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.config = GlobalLogContext.context.get("config", "unknown")
        record.emulator = GlobalLogContext.context.get("emulator", "unknown")
        return True


class GlobalLogContext:
    """全局日志上下文，供各模块共享。"""

    context: Dict[str, str] = {}

    @classmethod
    def update(cls, labels: Dict[str, str]):
        if not labels:
            return
        cls.context.update({k: str(v) for k, v in labels.items() if v is not None})


class LoggerConfig:
    """日志配置管理类"""

    _configured_loggers = set()

    @classmethod
    def configure_logger(
        cls,
        logger_name: Optional[str] = None,
        level: str = "INFO",
        log_format: Optional[str] = None,
        date_format: Optional[str] = None,
        use_color: bool = True,
    ) -> logging.Logger:
        """
        配置日志记录器

        Args:
            logger_name: 日志记录器名称，默认为当前模块名
            level: 日志级别
            log_format: 日志格式，默认使用带颜色或普通格式
            date_format: 时间格式
            use_color: 是否使用彩色日志
        """
        import sys

        # 使用默认的模块名
        if logger_name is None:
            logger_name = "root"

        logger = logging.getLogger(logger_name)

        # 如果已经配置过，直接返回
        if logger_name in cls._configured_loggers:
            return logger

        # 设置日志级别
        logger.setLevel(getattr(logging, level.upper()))

        # 保留已存在的文件处理器，避免因二次配置导致文件日志丢失
        existing_file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        logger.handlers = []
        for h in existing_file_handlers:
            logger.addHandler(h)
        logger.propagate = False

        # 默认格式
        if log_format is None:
            log_format = (
                "%(asctime)s.%(msecs)03d %(levelname)s %(config)s %(emulator)s %(filename)s:%(lineno)d %(message)s"
            )

        if date_format is None:
            if use_color and coloredlogs:
                date_format = "%H:%M:%S"
            else:
                date_format = "%Y-%m-%d %H:%M:%S"

        # 使用 coloredlogs 配置彩色日志
        if use_color and coloredlogs:
            try:
                # 使用标准 StreamHandler 配合 ColoredFormatter
                handler = logging.StreamHandler(stream=sys.stdout)
                handler.setLevel(getattr(logging, level.upper()))
                formatter = coloredlogs.ColoredFormatter(
                    fmt=log_format,
                    datefmt=date_format,
                    level_styles={
                        "debug": {"color": "cyan"},
                        "info": {"color": "green"},
                        "warning": {"color": "yellow"},
                        "error": {"color": "red"},
                        "critical": {"color": "red", "bold": True},
                    },
                )
                handler.setFormatter(formatter)
                handler.addFilter(_ContextFilter())
                logger.addHandler(handler)
            except Exception as e:
                print(f"⚠️ 配置彩色日志失败: {e}，使用标准日志")
                # fallback到标准logging
                handler = logging.StreamHandler()
                handler.setLevel(getattr(logging, level.upper()))
                formatter = logging.Formatter(log_format, date_format)
                handler.setFormatter(formatter)
                handler.addFilter(_ContextFilter())
                logger.addHandler(handler)
            else:
                # 创建处理器和格式化器
                handler = logging.StreamHandler()
                handler.setLevel(getattr(logging, level.upper()))
                formatter = logging.Formatter(log_format, date_format)
                handler.setFormatter(formatter)
                handler.addFilter(_ContextFilter())
                logger.addHandler(handler)

        # 继承根与主业务 logger 的文件处理器，确保所有 logger 写入同一文件
        for base_name in (None, "miniwow"):
            base_logger = logging.getLogger(base_name) if base_name else logging.getLogger()
            for fh in base_logger.handlers:
                if isinstance(fh, logging.FileHandler):
                    already = any(
                        isinstance(h, logging.FileHandler)
                        and getattr(h, "_log_file", None) == getattr(fh, "_log_file", None)
                        for h in logger.handlers
                    )
                    if not already:
                        logger.addHandler(fh)

        # 确保日志包含统一的上下文字段（通过过滤器注入）

        # 标记为已配置
        cls._configured_loggers.add(logger_name)

        return logger

    @classmethod
    def get_simple_logger(
        cls, name: Optional[str] = None, level: str = "INFO"
    ) -> logging.Logger:
        """
        获取简单配置的日志记录器（使用basicConfig）
        适用于不需要颜色或复杂格式的脚本

        Args:
            name: 日志记录器名称
            level: 日志级别
        """
        import sys

        # 使用默认的模块名
        if name is None:
            name = "root"

        logger = logging.getLogger(name)

        # 如果已经配置过，直接返回
        if logger.handlers:
            return logger

        # 使用basicConfig配置
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )

        return logger


# 便捷函数
def setup_logger(
    name: Optional[str] = None,
    level: str = "INFO",
    log_format: Optional[str] = None,
    date_format: Optional[str] = None,
    use_color: bool = True,
) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: 日志格式字符串
        date_format: 时间格式
        use_color: 是否使用彩色日志

    Returns:
        配置好的日志记录器

    Note:
        - console 输出中默认不显示 logger name
        - 如需在 console 中显示 logger name，可在 log_format 中添加 %(name)s
    """
    return LoggerConfig.configure_logger(
        logger_name=name,
        level=level,
        log_format=log_format,
        date_format=date_format,
        use_color=use_color,
    )


def setup_simple_logger(
    name: Optional[str] = None, level: str = "INFO"
) -> logging.Logger:
    """
    设置简单的日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别

    Returns:
        配置好的日志记录器
    """
    return LoggerConfig.get_simple_logger(name=name, level=level)


# 兼容性函数，兼容现有的使用方式
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取已配置的日志记录器"""
    return setup_logger(name=name, level="INFO")


# 导出常用的配置常量
DEFAULT_COLOR_FORMAT = (
    "%(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(message)s"
)
DEFAULT_COLOR_DATE_FORMAT = "%H:%M:%S"
DEFAULT_SIMPLE_FORMAT = "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s"

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def setup_logger_from_config(
    config_file: str = "system_config.json",
    use_color: bool = True,
) -> logging.Logger:
    """
    从系统配置文件中加载日志配置并创建日志记录器

    Args:
        config_file: 系统配置文件路径
        use_color: 是否使用彩色日志

    Returns:
        配置好的日志记录器
    """
    try:
        from system_config_loader import load_system_config

        config_loader = load_system_config(config_file)
        logging_config = config_loader.get_logging_config()

        logger_name = logging_config.get("logger_name", "miniwow")
        level = logging_config.get("level", "INFO")

        # 可选：调用方可使用 update_log_context 注入上下文标签（如 config、emulator）

        return setup_logger(
            name=logger_name,
            level=level,
            use_color=use_color,
        )
    except Exception as e:
        print(f"⚠️ 从配置文件加载日志配置失败: {e}，使用默认配置")
        return setup_logger(name="miniwow", level="INFO", use_color=use_color)


def update_log_context(labels: Dict[str, str]) -> None:
    """
    更新所有日志记录器的上下文标签。

    将提供的键值（如 config、emulator）写入全局上下文，
    使后续日志记录行中可通过 %(config)s、%(emulator)s 展示。
    """
    GlobalLogContext.update(labels)


def attach_emulator_file_handler(
    emulator_name: str,
    config_name: Optional[str] = None,
    log_dir: str = "log",
    level: str = "INFO",
) -> str:
    """为当前进程添加 FileHandler，日志文件名统一规则：

    仅使用全局日志上下文中的 `session` 字段作为文件名后缀。
    """
    session_name = GlobalLogContext.context.get("session", "")
    file_key = (session_name or "unknown")

    os.makedirs(log_dir, exist_ok=True)
    file_path = os.path.join(log_dir, f"autodungeon_{file_key}.log")

    if config_name:
        GlobalLogContext.update({"config": config_name})
    GlobalLogContext.update({"emulator": emulator_name or "unknown"})

    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setLevel(getattr(logging, level.upper()))
    file_handler.addFilter(_ContextFilter())
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)s %(config)s %(emulator)s %(filename)s:%(lineno)d %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)

    # 将文件处理器挂在到 root 与主业务 logger（miniwow）上，避免因 propagate=False 丢失
    for target_name in (None, "miniwow"):
        target_logger = logging.getLogger(target_name) if target_name else logging.getLogger()
        already_attached = any(
            isinstance(h, logging.FileHandler) and getattr(h, "_log_file", None) == file_path
            for h in target_logger.handlers
        )
        if not already_attached:
            setattr(file_handler, "_log_file", file_path)
            target_logger.addHandler(file_handler)

    return file_path
