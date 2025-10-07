#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试配置模块
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from dungeon_config import (
    OCR_CORRECTION_MAP,
    ZONE_DUNGEONS,
    correct_ocr_text,
    get_all_dungeons,
    get_all_selected_dungeons,
    get_dungeon_count,
    get_selected_dungeon_count,
    get_zone_count,
    get_dungeons_by_zone,
    get_selected_dungeons_by_zone,
    is_valid_zone,
    is_valid_dungeon,
    get_zone_by_dungeon,
    is_dungeon_selected,
    set_dungeon_selected,
)


class TestOCRCorrection:
    """测试 OCR 纠正功能"""

    def test_ocr_correction_map_exists(self):
        """测试 OCR 纠正映射表存在"""
        assert isinstance(OCR_CORRECTION_MAP, dict)
        assert len(OCR_CORRECTION_MAP) > 0

    def test_ocr_correction_map_content(self):
        """测试 OCR 纠正映射表内容"""
        assert "梦魔丛林" in OCR_CORRECTION_MAP
        assert OCR_CORRECTION_MAP["梦魔丛林"] == "梦魇丛林"

    def test_correct_ocr_text_with_error(self):
        """测试纠正错误文本"""
        assert correct_ocr_text("梦魔丛林") == "梦魇丛林"

    def test_correct_ocr_text_without_error(self):
        """测试不需要纠正的文本"""
        assert correct_ocr_text("真理之地") == "真理之地"
        assert correct_ocr_text("海底王宫") == "海底王宫"

    def test_correct_ocr_text_unknown(self):
        """测试未知文本"""
        assert correct_ocr_text("未知副本") == "未知副本"


class TestZoneDungeons:
    """测试副本配置"""

    def test_zone_dungeons_exists(self):
        """测试副本字典存在"""
        assert isinstance(ZONE_DUNGEONS, dict)
        assert len(ZONE_DUNGEONS) > 0

    def test_zone_dungeons_structure(self):
        """测试副本字典结构"""
        for zone_name, dungeons in ZONE_DUNGEONS.items():
            assert isinstance(zone_name, str)
            assert isinstance(dungeons, list)
            assert len(dungeons) > 0
            for dungeon in dungeons:
                assert isinstance(dungeon, dict)
                assert "name" in dungeon
                assert "selected" in dungeon
                assert isinstance(dungeon["name"], str)
                assert isinstance(dungeon["selected"], bool)

    def test_specific_zones_exist(self):
        """测试特定区域存在"""
        assert "风暴群岛" in ZONE_DUNGEONS
        assert "军团领域" in ZONE_DUNGEONS

    def test_specific_dungeons_exist(self):
        """测试特定副本存在"""
        storm_dungeons = [d["name"] for d in ZONE_DUNGEONS["风暴群岛"]]
        legion_dungeons = [d["name"] for d in ZONE_DUNGEONS["军团领域"]]
        assert "真理之地" in storm_dungeons
        assert "梦魇丛林" in legion_dungeons


class TestHelperFunctions:
    """测试辅助函数"""

    def test_get_all_dungeons(self):
        """测试获取所有副本"""
        all_dungeons = get_all_dungeons()
        assert isinstance(all_dungeons, list)
        assert len(all_dungeons) > 0
        assert "真理之地" in all_dungeons
        assert "梦魇丛林" in all_dungeons

    def test_get_dungeon_count(self):
        """测试获取副本总数"""
        count = get_dungeon_count()
        assert isinstance(count, int)
        assert count > 0
        # 验证计数正确
        manual_count = sum(len(dungeons) for dungeons in ZONE_DUNGEONS.values())
        assert count == manual_count

    def test_get_zone_count(self):
        """测试获取区域总数"""
        count = get_zone_count()
        assert isinstance(count, int)
        assert count > 0
        assert count == len(ZONE_DUNGEONS)

    def test_get_dungeons_by_zone_valid(self):
        """测试获取指定区域的副本列表（有效区域）"""
        dungeons = get_dungeons_by_zone("风暴群岛")
        assert isinstance(dungeons, list)
        assert len(dungeons) > 0
        # 现在返回的是字典列表，需要检查 name 字段
        dungeon_names = [d["name"] for d in dungeons]
        assert "真理之地" in dungeon_names

    def test_get_dungeons_by_zone_invalid(self):
        """测试获取指定区域的副本列表（无效区域）"""
        dungeons = get_dungeons_by_zone("不存在的区域")
        assert isinstance(dungeons, list)
        assert len(dungeons) == 0

    def test_is_valid_zone_true(self):
        """测试检查区域是否存在（存在）"""
        assert is_valid_zone("风暴群岛") is True
        assert is_valid_zone("军团领域") is True

    def test_is_valid_zone_false(self):
        """测试检查区域是否存在（不存在）"""
        assert is_valid_zone("不存在的区域") is False

    def test_is_valid_dungeon_true(self):
        """测试检查副本是否存在（存在）"""
        assert is_valid_dungeon("真理之地") is True
        assert is_valid_dungeon("梦魇丛林") is True

    def test_is_valid_dungeon_false(self):
        """测试检查副本是否存在（不存在）"""
        assert is_valid_dungeon("不存在的副本") is False

    def test_get_zone_by_dungeon_valid(self):
        """测试根据副本名称获取所属区域（有效副本）"""
        zone = get_zone_by_dungeon("真理之地")
        assert zone == "风暴群岛"

        zone = get_zone_by_dungeon("梦魇丛林")
        assert zone == "军团领域"

    def test_get_zone_by_dungeon_invalid(self):
        """测试根据副本名称获取所属区域（无效副本）"""
        zone = get_zone_by_dungeon("不存在的副本")
        assert zone is None


class TestOCRCorrectionIntegration:
    """测试 OCR 纠正集成"""

    def test_ocr_correction_reverse_lookup(self):
        """测试反向查找 OCR 错误文本"""
        target_text = "梦魇丛林"
        found_ocr_text = None

        for ocr_text, correct_text in OCR_CORRECTION_MAP.items():
            if correct_text == target_text:
                found_ocr_text = ocr_text
                break

        assert found_ocr_text == "梦魔丛林"

    def test_ocr_correction_in_dungeon_list(self):
        """测试 OCR 纠正的副本在副本列表中"""
        for ocr_text, correct_text in OCR_CORRECTION_MAP.items():
            # 正确的文本应该在副本列表中
            assert is_valid_dungeon(correct_text)
            # 错误的文本不应该在副本列表中
            assert not is_valid_dungeon(ocr_text)


class TestDungeonSelection:
    """测试副本选定功能"""

    def test_all_dungeons_have_selected_field(self):
        """测试所有副本都有 selected 字段"""
        for zone_name, dungeons in ZONE_DUNGEONS.items():
            for dungeon in dungeons:
                assert "selected" in dungeon
                assert isinstance(dungeon["selected"], bool)

    def test_get_all_selected_dungeons(self):
        """测试获取所有选定的副本"""
        selected = get_all_selected_dungeons()
        assert isinstance(selected, list)
        # 默认所有副本都应该被选定
        all_dungeons = get_all_dungeons()
        assert len(selected) == len(all_dungeons)

    def test_get_selected_dungeon_count(self):
        """测试获取选定的副本总数"""
        count = get_selected_dungeon_count()
        assert isinstance(count, int)
        assert count > 0
        # 默认应该等于总副本数
        assert count == get_dungeon_count()

    def test_get_selected_dungeons_by_zone(self):
        """测试获取指定区域的选定副本"""
        selected = get_selected_dungeons_by_zone("风暴群岛")
        assert isinstance(selected, list)
        # 默认所有副本都应该被选定
        all_dungeons = get_dungeons_by_zone("风暴群岛")
        assert len(selected) == len(all_dungeons)

    def test_is_dungeon_selected(self):
        """测试检查副本是否被选定"""
        # 默认所有副本都应该被选定
        assert is_dungeon_selected("真理之地") is True
        assert is_dungeon_selected("梦魇丛林") is True
        # 不存在的副本应该返回 False
        assert is_dungeon_selected("不存在的副本") is False

    def test_set_dungeon_selected(self):
        """测试设置副本的选定状态"""
        # 取消选定
        result = set_dungeon_selected("真理之地", False)
        assert result is True
        assert is_dungeon_selected("真理之地") is False

        # 重新选定
        result = set_dungeon_selected("真理之地", True)
        assert result is True
        assert is_dungeon_selected("真理之地") is True

        # 设置不存在的副本应该返回 False
        result = set_dungeon_selected("不存在的副本", False)
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
