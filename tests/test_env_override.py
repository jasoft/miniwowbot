#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试环境变量覆盖功能
"""

import sys
import os
import json
import tempfile
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_loader import load_config
from auto_dungeon import apply_env_overrides


class TestEnvOverride:
    """测试环境变量覆盖功能"""

    def test_apply_env_overrides_boolean_true(self):
        """测试布尔值 true 的转换"""
        overrides = apply_env_overrides(["enable_daily_collect=true"])
        assert overrides["enable_daily_collect"] is True
        assert isinstance(overrides["enable_daily_collect"], bool)

    def test_apply_env_overrides_boolean_false(self):
        """测试布尔值 false 的转换"""
        overrides = apply_env_overrides(["enable_daily_collect=false"])
        assert overrides["enable_daily_collect"] is False
        assert isinstance(overrides["enable_daily_collect"], bool)

    def test_apply_env_overrides_integer(self):
        """测试整数的转换"""
        overrides = apply_env_overrides(["some_number=42"])
        assert overrides["some_number"] == 42
        assert isinstance(overrides["some_number"], int)

    def test_apply_env_overrides_string(self):
        """测试字符串的保留"""
        overrides = apply_env_overrides(["chest_name=风暴宝箱"])
        assert overrides["chest_name"] == "风暴宝箱"
        assert isinstance(overrides["chest_name"], str)

    def test_apply_env_overrides_multiple(self):
        """测试多个覆盖参数"""
        overrides = apply_env_overrides([
            "enable_daily_collect=false",
            "enable_quick_afk=true",
            "chest_name=测试宝箱"
        ])
        assert overrides["enable_daily_collect"] is False
        assert overrides["enable_quick_afk"] is True
        assert overrides["chest_name"] == "测试宝箱"

    def test_apply_env_overrides_invalid_format(self):
        """测试无效格式的处理"""
        overrides = apply_env_overrides(["invalid_format"])
        assert len(overrides) == 0

    def test_apply_env_overrides_empty(self):
        """测试空列表"""
        overrides = apply_env_overrides([])
        assert len(overrides) == 0

    def test_apply_env_overrides_none(self):
        """测试 None 输入"""
        overrides = apply_env_overrides(None)
        assert len(overrides) == 0

    def test_config_override_with_env(self):
        """测试配置覆盖功能"""
        # 创建临时配置文件
        config_data = {
            "class": "战士",
            "enable_daily_collect": True,
            "enable_quick_afk": False,
            "chestname": "原始宝箱",
            "zone_dungeons": {}
        }
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        
        try:
            # 加载配置
            config = load_config(temp_file)
            
            # 验证原始值
            assert config.is_daily_collect_enabled() is True
            assert config.is_quick_afk_enabled() is False
            assert config.get_chest_name() == "原始宝箱"
            
            # 应用覆盖
            overrides = apply_env_overrides([
                "enable_daily_collect=false",
                "enable_quick_afk=true",
                "chest_name=新宝箱"
            ])
            
            # 手动应用覆盖（模拟 initialize_configs 的行为）
            for key, value in overrides.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            # 验证覆盖后的值
            assert config.is_daily_collect_enabled() is False
            assert config.is_quick_afk_enabled() is True
            assert config.get_chest_name() == "新宝箱"
            
        finally:
            os.unlink(temp_file)

    def test_env_override_with_spaces(self):
        """测试带空格的环境变量覆盖"""
        overrides = apply_env_overrides(["  enable_daily_collect  =  false  "])
        assert overrides["enable_daily_collect"] is False

    def test_env_override_with_equals_in_value(self):
        """测试值中包含等号的情况"""
        overrides = apply_env_overrides(["some_key=value=with=equals"])
        assert overrides["some_key"] == "value=with=equals"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

