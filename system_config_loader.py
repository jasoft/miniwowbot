#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
系统配置加载器
用于加载系统级配置，如 Bark 通知等
"""

import json
import os
from typing import Dict
from project_paths import ensure_project_path
from logger_config import setup_logger

# 配置日志（使用 setup_logger 避免循环依赖）
logger = setup_logger(name="miniwow.system_config_loader", use_color=True)


class SystemConfigLoader:
    """系统配置加载器类"""

    def __init__(self, config_file: str = "system_config.json"):
        """
        初始化系统配置加载器

        Args:
            config_file: 系统配置文件路径，默认为 system_config.json
        """
        resolved_config = ensure_project_path(config_file)
        self.config_file = str(resolved_config)
        self.bark_config = {}
        self.timeout_config = {}
        self.logging_config = {}
        self.grafana_config = {}
        self._init_defaults()
        self._load_config()

    def _load_config(self) -> None:
        self._load_env()
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                self.bark_config.update(config.get("bark", {}))
                self.timeout_config.update(config.get("timeout", {}))
                self.logging_config.update(config.get("logging", {}))
                self.grafana_config.update(config.get("grafana", {}))
                logger.info(f"✅ 已加载 JSON 配置: {self.config_file}")
            except json.JSONDecodeError as e:
                logger.error(f"❌ 系统配置文件格式错误: {e}")
            except Exception as e:
                logger.error(f"❌ 加载系统配置文件失败: {e}")
        self._apply_env_overrides()

    def _init_defaults(self) -> None:
        self.bark_config = {
            "enabled": False,
            "server": "",
            "title": "副本助手通知",
            "group": "dungeon_helper",
        }
        self.timeout_config = {"wait_for_main": 300}
        self.logging_config = {
            "logger_name": "miniwow",
            "level": "INFO",
        }
        self.grafana_config = {
            "enabled": False,
            "server": "http://localhost:3000",
            "username": "admin",
            "password": "admin",
        }

    def _load_env(self) -> None:
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv()
            logger.info("✅ 已加载 .env 环境变量")
        except Exception:
            env_path = ensure_project_path(".env")
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if "=" in line:
                                k, v = line.split("=", 1)
                                os.environ.setdefault(k.strip(), v.strip())
                    logger.info("✅ 已解析 .env（无依赖模式）")
                except Exception:
                    pass

    def _apply_env_overrides(self) -> None:
        def as_bool(val: str) -> bool:
            return str(val).lower() in {"1", "true", "yes", "on"}

        def as_int(val: str, default: int) -> int:
            try:
                return int(val)
            except Exception:
                return default

        # Bark
        if os.environ.get("BARK_ENABLED") is not None:
            self.bark_config["enabled"] = as_bool(os.environ.get("BARK_ENABLED", "false"))
        if os.environ.get("BARK_SERVER"):
            self.bark_config["server"] = os.environ["BARK_SERVER"]
        if os.environ.get("BARK_TITLE"):
            self.bark_config["title"] = os.environ["BARK_TITLE"]
        if os.environ.get("BARK_GROUP"):
            self.bark_config["group"] = os.environ["BARK_GROUP"]

        # Timeout
        if os.environ.get("WAIT_FOR_MAIN"):
            self.timeout_config["wait_for_main"] = as_int(os.environ["WAIT_FOR_MAIN"], self.timeout_config["wait_for_main"])

        # Logging
        if os.environ.get("LOGGER_NAME"):
            self.logging_config["logger_name"] = os.environ["LOGGER_NAME"]
        if os.environ.get("LOG_LEVEL"):
            self.logging_config["level"] = os.environ["LOG_LEVEL"].upper()

        # Grafana
        if os.environ.get("GRAFANA_ENABLED") is not None:
            self.grafana_config["enabled"] = as_bool(os.environ.get("GRAFANA_ENABLED", "false"))
        if os.environ.get("GRAFANA_SERVER"):
            self.grafana_config["server"] = os.environ["GRAFANA_SERVER"]
        if os.environ.get("GRAFANA_USERNAME"):
            self.grafana_config["username"] = os.environ["GRAFANA_USERNAME"]
        if os.environ.get("GRAFANA_PASSWORD"):
            self.grafana_config["password"] = os.environ["GRAFANA_PASSWORD"]

    def get_bark_config(self) -> Dict:
        """
        获取 Bark 通知配置

        Returns:
            Bark 配置字典
        """
        return self.bark_config

    def is_bark_enabled(self) -> bool:
        """
        检查是否启用了 Bark 通知

        Returns:
            如果启用返回 True，否则返回 False
        """
        return self.bark_config.get("enabled", False)

    def get_timeout_config(self) -> Dict:
        """
        获取超时配置

        Returns:
            超时配置字典
        """
        return self.timeout_config

    def get_wait_for_main_timeout(self) -> int:
        """
        获取等待主界面的超时时间（秒）

        Returns:
            超时时间（秒），默认为 300 秒（5 分钟）
        """
        return self.timeout_config.get("wait_for_main", 300)

    def get_logging_config(self) -> Dict:
        """
        获取日志配置

        Returns:
            日志配置字典
        """
        return self.logging_config

    # 已移除 Loki 配置相关方法，系统不再关心具体日志后端

    def get_grafana_config(self) -> Dict:
        """
        获取 Grafana 可视化配置

        Returns:
            Grafana 配置字典
        """
        return self.grafana_config

    def is_grafana_enabled(self) -> bool:
        """
        检查是否启用了 Grafana 可视化

        Returns:
            如果启用返回 True，否则返回 False
        """
        return self.grafana_config.get("enabled", False)


def load_system_config(config_file: str = "system_config.json") -> SystemConfigLoader:
    """
    加载系统配置文件

    Args:
        config_file: 系统配置文件路径

    Returns:
        SystemConfigLoader 实例
    """
    return SystemConfigLoader(config_file)


# 导出
__all__ = ["SystemConfigLoader", "load_system_config"]
