#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
配置加载器测试
"""

import pytest
import json
import tempfile
import os
from project_paths import resolve_project_path
from config_loader import ConfigLoader, load_config


class TestConfigLoader:
    """配置加载器测试"""

    def test_load_default_config(self):
        """测试加载默认配置"""
        config = load_config("configs/default.json")
        assert config.get_config_name() == "default"
        assert config.get_dungeon_count() > 0
        assert config.get_selected_dungeon_count() > 0

    def test_load_warrior_config(self):
        """测试加载战士配置"""
        config = load_config("configs/warrior.json")
        assert config.get_config_name() == "warrior"
        assert config.get_dungeon_count() > 0
        assert config.get_selected_dungeon_count() > 0

    def test_load_mage_config(self):
        """测试加载法师配置"""
        config = load_config("configs/mage.json")
        assert config.get_config_name() == "mage"
        assert config.get_dungeon_count() > 0
        assert config.get_selected_dungeon_count() > 0

    def test_get_config_name(self):
        """测试获取配置名称"""
        config = load_config("configs/default.json")
        assert config.get_config_name() == "default"

        config = load_config("configs/warrior.json")
        assert config.get_config_name() == "warrior"

    def test_get_char_class(self):
        """测试获取角色职业"""
        # 测试有职业配置的
        config = load_config("configs/default.json")
        assert config.get_char_class() == "战士"

        config = load_config("configs/warrior.json")
        assert config.get_char_class() == "战士"

        config = load_config("configs/mage.json")
        assert config.get_char_class() == "法师"

    def test_get_zone_dungeons(self):
        """测试获取副本配置"""
        config = load_config("configs/default.json")
        zone_dungeons = config.get_zone_dungeons()

        assert isinstance(zone_dungeons, dict)
        assert len(zone_dungeons) > 0

        # 检查数据结构
        for zone_name, dungeons in zone_dungeons.items():
            assert isinstance(zone_name, str)
            assert isinstance(dungeons, list)
            for dungeon in dungeons:
                assert isinstance(dungeon, dict)
                assert "name" in dungeon
                assert "selected" in dungeon

    def test_get_ocr_correction_map(self):
        """测试获取OCR纠正映射"""
        config = load_config("configs/warrior.json")
        ocr_map = config.get_ocr_correction_map()

        assert isinstance(ocr_map, dict)
        # 战士配置应该有OCR纠正映射
        assert len(ocr_map) > 0

    def test_correct_ocr_text(self):
        """测试OCR文本纠正"""
        config = load_config("configs/warrior.json")

        # 测试纠正
        corrected = config.correct_ocr_text("梦魔丛林")
        assert corrected == "梦魇丛林"

        # 测试不需要纠正的文本
        original = config.correct_ocr_text("真理之地")
        assert original == "真理之地"

    def test_get_dungeon_count(self):
        """测试获取副本总数"""
        config = load_config("configs/default.json")
        count = config.get_dungeon_count()

        assert isinstance(count, int)
        assert count > 0

    def test_get_selected_dungeon_count(self):
        """测试获取选定副本数"""
        config = load_config("configs/default.json")
        total = config.get_dungeon_count()
        selected = config.get_selected_dungeon_count()

        assert isinstance(selected, int)
        assert selected > 0
        assert selected <= total

        # 默认配置应该所有副本都选定
        assert selected == total

    def test_get_selected_dungeons(self):
        """测试获取选定的副本列表"""
        config = load_config("configs/warrior.json")
        selected = config.get_all_selected_dungeons()

        assert isinstance(selected, list)
        assert len(selected) > 0

        # 检查数据结构 - 应该是副本名称的列表
        for dungeon_name in selected:
            assert isinstance(dungeon_name, str)

    def test_dungeon_selection_status(self):
        """测试副本选定状态"""
        config = load_config("configs/warrior.json")

        # 测试副本的选定状态
        zone_dungeons = config.get_zone_dungeons()
        selected_count = 0
        unselected_count = 0

        for zone_name, dungeons in zone_dungeons.items():
            for dungeon in dungeons:
                if dungeon.get("selected", True):
                    selected_count += 1
                else:
                    unselected_count += 1

        # 战士配置应该有选定和未选定的副本
        assert selected_count > 0
        assert unselected_count > 0

    def test_invalid_config_file(self):
        """测试加载无效的配置文件"""
        with pytest.raises(FileNotFoundError):
            load_config("configs/nonexistent.json")

    def test_invalid_json_format(self):
        """测试加载格式错误的JSON"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json content")
            temp_file = f.name

        try:
            with pytest.raises(ValueError):
                load_config(temp_file)
        finally:
            os.unlink(temp_file)

    def test_missing_required_fields(self):
        """测试缺少必需字段的配置"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"description": "test"}, f)
            temp_file = f.name

        try:
            # 缺少 zone_dungeons 字段时，会使用默认值空字典
            config = load_config(temp_file)
            assert config.get_dungeon_count() == 0
        finally:
            os.unlink(temp_file)

    def test_config_with_minimal_fields(self):
        """测试只包含必需字段的配置"""
        config_data = {
            "zone_dungeons": {"测试区域": [{"name": "测试副本", "selected": True}]}
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name

        try:
            config = load_config(temp_file)
            assert config.get_dungeon_count() == 1
            assert config.get_selected_dungeon_count() == 1
            assert len(config.get_ocr_correction_map()) == 0
        finally:
            os.unlink(temp_file)

    def test_config_with_all_fields(self):
        """测试包含所有字段的配置"""
        config_data = {
            "description": "测试配置",
            "ocr_correction_map": {"错误": "正确"},
            "zone_dungeons": {
                "测试区域": [
                    {"name": "副本1", "selected": True},
                    {"name": "副本2", "selected": False},
                ]
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name

        try:
            config = load_config(temp_file)
            assert config.get_dungeon_count() == 2
            assert config.get_selected_dungeon_count() == 1
            assert len(config.get_ocr_correction_map()) == 1
            assert config.correct_ocr_text("错误") == "正确"
        finally:
            os.unlink(temp_file)


class TestConfigLoaderIntegration:
    """配置加载器集成测试"""

    def test_all_preset_configs_valid(self):
        """测试所有预设配置都有效"""
        configs = [
            "configs/default.json",
            "configs/warrior.json",
            "configs/mage.json",
        ]

        for config_file in configs:
            config = load_config(config_file)
            assert config.get_config_name() is not None
            assert config.get_dungeon_count() > 0
            assert config.get_selected_dungeon_count() > 0
            assert config.get_zone_dungeons() is not None

    def test_config_consistency(self):
        """测试配置一致性"""
        configs = [
            load_config("configs/default.json"),
            load_config("configs/warrior.json"),
            load_config("configs/mage.json"),
        ]

        # 所有配置应该有相同的副本总数
        total_counts = [c.get_dungeon_count() for c in configs]
        assert len(set(total_counts)) == 1

        # 所有配置应该有相同的区域
        zone_sets = [set(c.get_zone_dungeons().keys()) for c in configs]
        assert all(zones == zone_sets[0] for zones in zone_sets)

    def test_selection_differences(self):
        """测试不同配置的选择差异"""
        default = load_config("configs/default.json")
        warrior = load_config("configs/warrior.json")
        mage = load_config("configs/mage.json")

        # 默认配置应该选择所有副本
        assert default.get_selected_dungeon_count() == default.get_dungeon_count()

        # 战士和法师可能选择不同数量的副本
        # 这里只验证它们都有选定的副本
        assert warrior.get_selected_dungeon_count() > 0
        assert mage.get_selected_dungeon_count() > 0

    def test_load_config_after_changing_cwd(self, tmp_path, monkeypatch):
        """切换工作目录后, 相对路径配置仍可加载"""
        monkeypatch.chdir(tmp_path)
        config = load_config("configs/default.json")
        assert config.get_config_name() == "default"
        assert config.config_file == str(
            resolve_project_path("configs", "default.json")
        )
