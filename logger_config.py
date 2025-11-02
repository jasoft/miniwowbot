# -*- encoding=utf8 -*-
"""
通用日志配置模块
提供统一的日志配置功能，支持多种日志格式和输出方式
"""

import logging
from typing import Optional, Dict

# 导入 coloredlogs
try:
    import coloredlogs
except ImportError:
    coloredlogs = None

# 导入 Loki 处理器
try:
    from logstash_logger import LokiHandler
except ImportError:
    LokiHandler = None


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
        enable_loki: bool = False,
        loki_url: Optional[str] = None,
        loki_labels: Optional[Dict] = None,
    ) -> logging.Logger:
        """
        配置日志记录器

        Args:
            logger_name: 日志记录器名称，默认为当前模块名
            level: 日志级别
            log_format: 日志格式，默认使用带颜色或普通格式
            date_format: 时间格式
            use_color: 是否使用彩色日志
            enable_loki: 是否启用 Loki 日志上传
            loki_url: Loki 服务地址，如 http://localhost:3100
            loki_labels: Loki 标签字典，如 {"env": "dev"}
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

        # 清除已有的处理器，避免重复
        logger.handlers.clear()
        logger.propagate = False

        # 默认格式
        if log_format is None:
            log_format = "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s"

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
                logger.addHandler(handler)
            except Exception as e:
                print(f"⚠️ 配置彩色日志失败: {e}，使用标准日志")
                # fallback到标准logging
                handler = logging.StreamHandler()
                handler.setLevel(getattr(logging, level.upper()))
                formatter = logging.Formatter(log_format, date_format)
                handler.setFormatter(formatter)
                logger.addHandler(handler)
        else:
            # 创建处理器和格式化器
            handler = logging.StreamHandler()
            handler.setLevel(getattr(logging, level.upper()))
            formatter = logging.Formatter(log_format, date_format)
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        # 添加 Loki 处理器（可选）
        if enable_loki and LokiHandler:
            try:
                if loki_url is None:
                    loki_url = "http://localhost:3100"

                loki_handler = LokiHandler(
                    loki_url=loki_url,
                    app_name=logger_name or "miniwow",
                    labels=loki_labels,
                )
                loki_handler.setLevel(getattr(logging, level.upper()))
                logger.addHandler(loki_handler)
            except Exception as e:
                print(f"⚠️ 配置 Loki 处理器失败: {e}")

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
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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
    enable_loki: bool = False,
    loki_url: Optional[str] = None,
    loki_labels: Optional[Dict] = None,
) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别
        log_format: 日志格式
        date_format: 时间格式
        use_color: 是否使用彩色日志
        enable_loki: 是否启用 Loki 日志上传
        loki_url: Loki 服务地址，如 http://localhost:3100
        loki_labels: Loki 标签字典，如 {"env": "dev"}

    Returns:
        配置好的日志记录器
    """
    return LoggerConfig.configure_logger(
        logger_name=name,
        level=level,
        log_format=log_format,
        date_format=date_format,
        use_color=use_color,
        enable_loki=enable_loki,
        loki_url=loki_url,
        loki_labels=loki_labels,
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
DEFAULT_COLOR_FORMAT = "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s"
DEFAULT_COLOR_DATE_FORMAT = "%H:%M:%S"
DEFAULT_SIMPLE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
