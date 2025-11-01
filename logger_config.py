# -*- encoding=utf8 -*-
"""
通用日志配置模块
提供统一的日志配置功能，支持多种日志格式和输出方式
"""

import logging
import os
from typing import Optional

# 导入 coloredlogs 和 cls_logger
try:
    import coloredlogs
except ImportError:
    coloredlogs = None


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
        use_cls: Optional[bool] = None,
    ) -> logging.Logger:
        """
        配置日志记录器

        Args:
            logger_name: 日志记录器名称，默认为当前模块名
            level: 日志级别
            log_format: 日志格式，默认使用带颜色或普通格式
            date_format: 时间格式
            use_color: 是否使用彩色日志
            use_cls: 是否使用腾讯云CLS，None表示自动检测环境变量
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
                coloredlogs.install(
                    level=level,
                    logger=logger,
                    fmt=log_format,
                    datefmt=date_format,
                    level_styles={
                        "debug": {"color": "cyan"},
                        "info": {"color": "green"},
                        "warning": {"color": "yellow"},
                        "error": {"color": "red"},
                        "critical": {"color": "red", "bold": True},
                    },
                    stream=sys.stdout,
                )
            except Exception as e:
                print(f"配置彩色日志失败: {e}，使用标准日志")
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

        # 配置腾讯云CLS（可选）
        if use_cls is None:
            use_cls = os.getenv("CLS_ENABLED", "false").lower() == "true"

        if use_cls:
            try:
                add_cls_to_logger(logger)
            except Exception as e:
                print(f"配置CLS日志失败: {e}")

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
    use_cls: Optional[bool] = None,
) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别
        log_format: 日志格式
        date_format: 时间格式
        use_color: 是否使用彩色日志
        use_cls: 是否使用腾讯云CLS

    Returns:
        配置好的日志记录器
    """
    return LoggerConfig.configure_logger(
        logger_name=name,
        level=level,
        log_format=log_format,
        date_format=date_format,
        use_color=use_color,
        use_cls=use_cls,
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


def close_loggers():
    """关闭所有日志处理器（用于程序退出时）"""
    close_cls_logger()


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
