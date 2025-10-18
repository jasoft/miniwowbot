#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
系统配置加载器
用于加载系统级配置，如 Bark 通知等
"""

import json
import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class SystemConfigLoader:
    """系统配置加载器类"""

    def __init__(self, config_file: str = "system_config.json"):
        """
        初始化系统配置加载器

        Args:
            config_file: 系统配置文件路径，默认为 system_config.json
        """
        self.config_file = config_file
        self.bark_config = {}
        self.timeout_config = {}
        self._load_config()

    def _load_config(self):
        """加载系统配置文件"""
        if not os.path.exists(self.config_file):
            logger.warning(f"⚠️ 系统配置文件不存在: {self.config_file}，使用默认配置")
            self._use_default_config()
            return

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 加载 Bark 通知配置
            self.bark_config = config.get("bark", {})

            # 加载超时配置
            self.timeout_config = config.get("timeout", {})

            logger.info(f"✅ 系统配置加载成功: {self.config_file}")
            if self.bark_config.get("enabled"):
                logger.info("📱 Bark 通知已启用")

        except json.JSONDecodeError as e:
            logger.error(f"❌ 系统配置文件格式错误: {e}")
            self._use_default_config()
        except Exception as e:
            logger.error(f"❌ 加载系统配置文件失败: {e}")
            self._use_default_config()

    def _use_default_config(self):
        """使用默认配置"""
        self.bark_config = {
            "enabled": False,
            "server": "",
            "title": "副本助手通知",
            "group": "dungeon_helper",
        }
        self.timeout_config = {"wait_for_main": 300}

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
