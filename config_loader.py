#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
配置加载器
支持从 JSON 文件加载副本配置
"""

import json
import os
from typing import Dict, List, Optional, TypeVar
from logger_config import setup_logger

# 配置日志
logger = setup_logger()

T = TypeVar("T")


class ConfigLoader:
    """配置加载器类"""

    def __init__(self, config_file: str):
        """
        初始化配置加载器

        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config_name = self._get_config_name()
        self.zone_dungeons = {}
        self.ocr_correction_map = {}
        self.char_class = None
        self.enable_daily_collect = False
        self.enable_quick_afk = False
        self.chest_name = None
        self._load_config()

    def _get_config_name(self) -> str:
        """
        从配置文件路径获取配置名称（不含扩展名）

        Returns:
            配置名称
        """
        basename = os.path.basename(self.config_file)
        name, _ = os.path.splitext(basename)
        return name

    def _load_config(self):
        """加载配置文件"""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"配置文件不存在: {self.config_file}")

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 加载副本配置
            self.zone_dungeons = config.get("zone_dungeons", {})

            # 加载 OCR 纠正映射
            self.ocr_correction_map = config.get("ocr_correction_map", {})

            # 加载角色职业
            self.char_class = config.get("class", None)

            # 加载每日领取选项
            self.enable_daily_collect = config.get("enable_daily_collect", False)

            # 加载快速挂机选项
            self.enable_quick_afk = config.get("enable_quick_afk", False)

            # 加载宝箱名称选项
            self.chest_name = config.get("chestname", None)

            # 验证配置格式
            self._validate_config()

            logger.info(f"✅ 配置加载成功: {self.config_file}")
            logger.info(f"📝 配置名称: {self.config_name}")
            if self.char_class:
                logger.info(f"⚔️ 角色职业: {self.char_class}")
            if self.enable_daily_collect:
                logger.info("🎁 每日领取: 启用")
            if self.enable_quick_afk:
                logger.info("⚡ 快速挂机: 启用")
            if self.chest_name:
                logger.info(f"🎁 指定宝箱: {self.chest_name}")
            logger.info(f"🌍 区域数量: {len(self.zone_dungeons)}")
            logger.info(
                f"🎯 副本总数: {sum(len(dungeons) for dungeons in self.zone_dungeons.values())}"
            )
            selected_count = sum(
                sum(1 for d in dungeons if d.get("selected", True))
                for dungeons in self.zone_dungeons.values()
            )
            logger.info(f"✅ 选定副本: {selected_count}")

        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件格式错误: {e}")
        except Exception as e:
            raise RuntimeError(f"加载配置文件失败: {e}")

    def _validate_config(self):
        """验证配置格式"""
        if not isinstance(self.zone_dungeons, dict):
            raise ValueError("zone_dungeons 必须是字典类型")

        for zone_name, dungeons in self.zone_dungeons.items():
            if not isinstance(zone_name, str):
                raise ValueError(f"区域名称必须是字符串: {zone_name}")

            if not isinstance(dungeons, list):
                raise ValueError(f"区域 {zone_name} 的副本列表必须是数组")

            for dungeon in dungeons:
                if not isinstance(dungeon, dict):
                    raise ValueError(f"区域 {zone_name} 的副本必须是字典类型")

                if "name" not in dungeon:
                    raise ValueError(f"区域 {zone_name} 的副本缺少 name 字段")

                if not isinstance(dungeon["name"], str):
                    raise ValueError(f"区域 {zone_name} 的副本名称必须是字符串")

                # selected 字段是可选的，默认为 True
                if "selected" in dungeon and not isinstance(dungeon["selected"], bool):
                    raise ValueError(
                        f"区域 {zone_name} 的副本 {dungeon['name']} 的 selected 字段必须是布尔值"
                    )

        if not isinstance(self.ocr_correction_map, dict):
            raise ValueError("ocr_correction_map 必须是字典类型")

    def get_zone_dungeons(self) -> Dict[str, List[Dict]]:
        """
        获取副本配置

        Returns:
            副本配置字典
        """
        return self.get_attr("zone_dungeons", {})

    def get_ocr_correction_map(self) -> Dict[str, str]:
        """
        获取 OCR 纠正映射

        Returns:
            OCR 纠正映射字典
        """
        return self.get_attr("ocr_correction_map", {})

    def get_config_name(self) -> str:
        """
        获取配置名称

        Returns:
            配置名称
        """
        return self.get_attr("config_name", "")

    def get_char_class(self) -> Optional[str]:
        """
        获取角色职业

        Returns:
            角色职业，如果未配置则返回 None
        """
        return self.get_attr("char_class", None)

    def get_all_dungeons(self) -> List[str]:
        """
        获取所有副本列表（扁平化）

        Returns:
            所有副本名称的列表
        """
        all_dungeons = []
        for dungeons in self.zone_dungeons.values():
            for dungeon in dungeons:
                all_dungeons.append(dungeon["name"])
        return all_dungeons

    def get_all_selected_dungeons(self) -> List[str]:
        """
        获取所有选定的副本列表（扁平化）

        Returns:
            所有选定的副本名称的列表
        """
        selected_dungeons = []
        for dungeons in self.zone_dungeons.values():
            for dungeon in dungeons:
                if dungeon.get("selected", True):
                    selected_dungeons.append(dungeon["name"])
        return selected_dungeons

    def get_dungeon_count(self) -> int:
        """
        获取副本总数

        Returns:
            副本总数
        """
        return sum(len(dungeons) for dungeons in self.zone_dungeons.values())

    def get_selected_dungeon_count(self) -> int:
        """
        获取选定的副本总数

        Returns:
            选定的副本总数
        """
        count = 0
        for dungeons in self.zone_dungeons.values():
            for dungeon in dungeons:
                if dungeon.get("selected", True):
                    count += 1
        return count

    def correct_ocr_text(self, text: str) -> str:
        """
        纠正 OCR 识别错误的文本

        Args:
            text: OCR 识别的文本

        Returns:
            纠正后的文本
        """
        return self.ocr_correction_map.get(text, text)

    def is_daily_collect_enabled(self) -> bool:
        """
        检查是否启用每日领取

        Returns:
            是否启用每日领取
        """
        return self.get_attr("enable_daily_collect", False)

    def is_quick_afk_enabled(self) -> bool:
        """
        检查是否启用快速挂机

        Returns:
            是否启用快速挂机
        """
        return self.get_attr("enable_quick_afk", False)

    def get_chest_name(self) -> Optional[str]:
        """
        获取宝箱名称

        Returns:
            宝箱名称，如果未配置则返回 None
        """
        return self.get_attr("chest_name", None)

    def get_attr(self, attr_name: str, default: T = None) -> T:
        """
        获取配置属性值

        Args:
            attr_name: 属性名称
            default: 默认值，当属性不存在时返回

        Returns:
            属性值，如果属性不存在则返回默认值
        """
        if not hasattr(self, attr_name):
            return default

        value = getattr(self, attr_name)

        # 如果值为None，返回默认值
        if value is None:
            return default

        # 对于布尔值，如果默认值是布尔类型，确保返回布尔类型
        if isinstance(default, bool) and not isinstance(value, bool):
            return default

        # 对于字典类型，如果默认值是字典，确保返回字典
        if isinstance(default, dict) and not isinstance(value, dict):
            return default

        # 对于字符串类型，如果默认值是字符串，确保返回字符串
        if isinstance(default, str) and not isinstance(value, str):
            return default

        return value  # type: ignore

    def has_attr(self, attr_name: str) -> bool:
        """
        检查是否存在某个属性（且值不为None）

        Args:
            attr_name: 属性名称

        Returns:
            True 如果属性存在且值不为None，否则返回False
        """
        return hasattr(self, attr_name) and getattr(self, attr_name) is not None


def load_config(config_file: str) -> ConfigLoader:
    """
    加载配置文件

    Args:
        config_file: 配置文件路径

    Returns:
        ConfigLoader 实例
    """
    return ConfigLoader(config_file)


# 导出
__all__ = ["ConfigLoader", "load_config"]
