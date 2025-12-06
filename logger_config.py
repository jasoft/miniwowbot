# -*- encoding=utf8 -*-
"""
通用日志配置模块
提供统一的日志配置功能，支持多种日志格式和输出方式
"""

import logging
import os
from typing import Optional, Dict
from project_paths import resolve_project_path

# 导入 coloredlogs
try:
    import coloredlogs
except ImportError:
    coloredlogs = None

class _ContextFilter(logging.Filter):
    """将全局上下文注入到每条日志记录中。

    该过滤器会把 `GlobalLogContext.context` 的键值注入到 `LogRecord`，
    使日志格式中可以直接引用如 `%(config)s`、`%(session)s` 等字段。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        for k, v in GlobalLogContext.context.items():
            setattr(record, k, v)
        if not hasattr(record, "config"):
            setattr(record, "config", "")
        if not hasattr(record, "emulator"):
            setattr(record, "emulator", "")
        return True


class GlobalLogContext:
    """全局日志上下文容器。"""

    context: Dict[str, str] = {}

    @classmethod
    def update(cls, labels: Dict[str, str]) -> None:
        """更新上下文字段。

        Args:
            labels: 待更新的键值对
        """
        if not labels:
            return
        cls.context.update({k: str(v) for k, v in labels.items() if v is not None})

    @classmethod
    def clear(cls) -> None:
        """清空所有上下文字段。"""
        cls.context.clear()


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

        # 默认格式（统一包含 config 与 emulator 字段，便于 Promtail 采集）
        if log_format is None:
            log_format = (
                "%(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(config)s %(emulator)s %(message)s"
            )

        if date_format is None:
            date_format = "%Y-%m-%d %H:%M:%S"

        # 使用 coloredlogs 配置彩色日志，否则使用标准日志处理器
        if use_color and coloredlogs:
            try:
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
            except Exception:
                # 彩色失败时降级为标准处理器
                handler = logging.StreamHandler(stream=sys.stdout)
                handler.setLevel(getattr(logging, level.upper()))
                formatter = logging.Formatter(log_format, date_format)
                handler.setFormatter(formatter)
                handler.addFilter(_ContextFilter())
                logger.addHandler(handler)
        else:
            handler = logging.StreamHandler(stream=sys.stdout)
            handler.setLevel(getattr(logging, level.upper()))
            formatter = logging.Formatter(log_format, date_format)
            handler.setFormatter(formatter)
            handler.addFilter(_ContextFilter())
            logger.addHandler(handler)



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

        # 使用basicConfig配置（与统一格式保持一致）
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(config)s %(emulator)s %(message)s",
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


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取（或创建）指定名称的日志记录器。"""
    return setup_logger(name=name, level="INFO")


# 导出常用的配置常量
DEFAULT_COLOR_FORMAT = (
    "%(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(config)s %(emulator)s %(message)s"
)
DEFAULT_COLOR_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_SIMPLE_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(config)s %(emulator)s %(message)s"

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def setup_logger_from_json(config_file: str, use_color: bool = True) -> logging.Logger:
    """从 JSON 文件加载日志配置并创建日志记录器。

    Args:
        config_file: JSON 配置文件路径
        use_color: 是否使用彩色日志

    Returns:
        配置好的日志记录器
    """
    import json
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
    """兼容旧接口：优先使用环境变量初始化日志。

    Args:
        config_file: 兼容参数，不再强制依赖该文件
        use_color: 是否使用彩色日志

    Returns:
        配置好的日志记录器
    """
    return setup_logger_from_env(use_color=use_color)


def update_log_context(labels: Dict[str, str]) -> None:
    """更新所有日志记录器的上下文标签。"""
    GlobalLogContext.update(labels)


def attach_file_handler(
    log_dir: str = "log",
    filename_prefix: str = "app",
    level: str = "INFO",
    log_format: Optional[str] = None,
    date_format: Optional[str] = "%Y-%m-%d %H:%M:%S",
) -> str:
    """为当前进程添加文件处理器。

    文件名将使用全局上下文中的 `session` 作为后缀，不存在则为 `unknown`。

    Args:
        log_dir: 日志目录
        filename_prefix: 文件名前缀
        level: 文件日志级别
        log_format: 文件日志格式
        date_format: 文件日期格式

    Returns:
        日志文件的绝对路径
    """
    session = GlobalLogContext.context.get("session", "") or "unknown"
    os.makedirs(log_dir, exist_ok=True)
    file_path = os.path.join(log_dir, f"{filename_prefix}_{session}.log")

    if log_format is None:
        log_format = "%(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(config)s %(emulator)s %(message)s"

    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setLevel(getattr(logging, level.upper()))
    file_handler.addFilter(_ContextFilter())
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))

    # 挂载到 root 与指定名称 logger（如存在）
    for target_name in (None,):
        target_logger = logging.getLogger(target_name) if target_name else logging.getLogger()
        already_attached = any(
            isinstance(h, logging.FileHandler) and getattr(h, "_log_file", None) == file_path
            for h in target_logger.handlers
        )
        if not already_attached:
            setattr(file_handler, "_log_file", file_path)
            target_logger.addHandler(file_handler)

    return file_path


def attach_emulator_file_handler(
    emulator_name: str,
    config_name: Optional[str] = None,
    log_dir: str = "log",
    level: str = "INFO",
) -> str:
    """兼容旧接口：为进程添加文件处理器并更新上下文。

    Args:
        emulator_name: 模拟器标识
        config_name: 配置名
        log_dir: 日志目录
        level: 文件日志级别

    Returns:
        文件日志完整路径
    """
    if config_name:
        GlobalLogContext.update({"config": config_name})
    GlobalLogContext.update({"emulator": emulator_name or "unknown"})

    file_path = get_log_file_path(log_dir=log_dir, emulator_name=emulator_name)

    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setLevel(getattr(logging, level.upper()))
    file_handler.addFilter(_ContextFilter())
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(config)s %(emulator)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
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


def _sanitize_component(value: str) -> str:
    """清理文件名片段为安全格式。

    Args:
        value: 待清理字符串

    Returns:
        仅包含字母数字、点和下划线的字符串
    """
    if not value:
        return "unknown"
    return str(value).replace(":", "_").replace("/", "_").replace(" ", "_")


def get_log_file_path(log_dir: str = "log", emulator_name: Optional[str] = None, prefix: str = "autodungeon") -> str:
    """统一生成日志文件路径。

    Args:
        log_dir: 日志目录
        emulator_name: 模拟器标识，为空时读取全局上下文
        prefix: 文件名前缀，默认使用 autodungeon

    Returns:
        完整日志文件路径
    """
    os.makedirs(log_dir, exist_ok=True)

    # 优先从 emulators.json 通过 emulator 映射到 session name
    session_name: Optional[str] = None
    try:
        import json
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


def log_calls(level: str = "DEBUG"):
    """创建一个函数调用日志装饰器。

    Args:
        level: 日志级别字符串

    Returns:
        可用于装饰函数的装饰器，记录入参、耗时、返回值类型，并在异常时输出错误日志
    """
    import time
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import logging as _logging

            target_logger = None
            if args and hasattr(args[0], "logger"):
                target_logger = getattr(args[0], "logger")
            if target_logger is None:
                target_logger = _logging.getLogger(func.__module__)

            try:
                arg_preview = ""
                if args:
                    arg_preview = str(args[:3])
                kw_preview = ""
                if kwargs:
                    kw_preview = ", kwargs=" + str({k: kwargs[k] for k in list(kwargs)[:5]})

                getattr(target_logger, level.lower())(f"➡️ {func.__name__} 开始{(' ' + arg_preview) if arg_preview else ''}{kw_preview}")
                start = time.perf_counter()
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                rtype = type(result).__name__
                getattr(target_logger, level.lower())(f"⬅️ {func.__name__} 结束 用时 {elapsed:.4f}s 返回 {rtype}")
                return result
            except Exception as exc:
                target_logger.error(f"❌ {func.__name__} 异常: {type(exc).__name__}: {exc}")
                raise

        return wrapper

    return decorator


def apply_logging_slice(targets, level: str = "DEBUG") -> None:
    """批量为指定的函数或方法应用日志切面。

    Args:
        targets: 由 (owner, attr_name) 元组构成的列表，owner 可为模块或类对象
        level: 日志级别字符串

    Returns:
        None
    """
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
