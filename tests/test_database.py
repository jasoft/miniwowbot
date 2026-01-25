#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试数据库模块
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from database import DungeonProgressDB


@pytest.fixture
def temp_db():
    """创建临时数据库用于测试"""
    # 创建临时文件
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # 创建数据库实例
    db = DungeonProgressDB(db_path)

    yield db

    # 清理
    db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


class TestDatabaseBasic:
    """测试数据库基本功能"""

    def test_database_creation(self, temp_db):
        """测试数据库创建"""
        assert temp_db is not None
        assert os.path.exists(temp_db.db_path)

    def test_get_today_date(self, temp_db):
        """测试获取今天日期"""
        today = temp_db.get_today_date()
        # 用相同的逻辑计算期望值
        now = datetime.now()
        if now.hour < 6:
            expected = (now.date() - timedelta(days=1)).isoformat()
        else:
            expected = now.date().isoformat()
        assert today == expected


class TestDungeonCompletion:
    """测试副本通关功能"""

    def test_is_dungeon_completed_false(self, temp_db):
        """测试检查未通关的副本"""
        result = temp_db.is_dungeon_completed("风暴群岛", "真理之地")
        assert result is False

    def test_mark_dungeon_completed(self, temp_db):
        """测试标记副本为已通关"""
        temp_db.mark_dungeon_completed("风暴群岛", "真理之地")
        result = temp_db.is_dungeon_completed("风暴群岛", "真理之地")
        assert result is True

    def test_mark_dungeon_completed_multiple(self, temp_db):
        """测试标记多个副本为已通关"""
        dungeons = [
            ("风暴群岛", "真理之地"),
            ("风暴群岛", "预言神殿"),
            ("军团领域", "梦魇丛林"),
        ]

        for zone, dungeon in dungeons:
            temp_db.mark_dungeon_completed(zone, dungeon)

        for zone, dungeon in dungeons:
            assert temp_db.is_dungeon_completed(zone, dungeon) is True

    def test_mark_dungeon_completed_idempotent(self, temp_db):
        """测试重复标记副本为已通关（幂等性）"""
        temp_db.mark_dungeon_completed("风暴群岛", "真理之地")
        temp_db.mark_dungeon_completed("风暴群岛", "真理之地")
        result = temp_db.is_dungeon_completed("风暴群岛", "真理之地")
        assert result is True


class TestDungeonStatistics:
    """测试副本统计功能"""

    def test_get_today_completed_count_zero(self, temp_db):
        """测试获取今天通关数量（0个）"""
        count = temp_db.get_today_completed_count()
        assert count == 0

    def test_get_today_completed_count_nonzero(self, temp_db):
        """测试获取今天通关数量（多个）"""
        temp_db.mark_dungeon_completed("风暴群岛", "真理之地")
        temp_db.mark_dungeon_completed("风暴群岛", "预言神殿")
        temp_db.mark_dungeon_completed("军团领域", "梦魇丛林")

        count = temp_db.get_today_completed_count()
        assert count == 3

    def test_get_today_completed_dungeons_empty(self, temp_db):
        """测试获取今天通关的副本列表（空）"""
        dungeons = temp_db.get_today_completed_dungeons()
        assert isinstance(dungeons, list)
        assert len(dungeons) == 0

    def test_get_today_completed_dungeons_nonempty(self, temp_db):
        """测试获取今天通关的副本列表（非空）"""
        temp_db.mark_dungeon_completed("风暴群岛", "真理之地")
        temp_db.mark_dungeon_completed("军团领域", "梦魇丛林")

        dungeons = temp_db.get_today_completed_dungeons()
        assert isinstance(dungeons, list)
        assert len(dungeons) == 2

        # 检查返回的数据结构（返回的是元组列表）
        for record in dungeons:
            assert isinstance(record, tuple)
            assert len(record) == 2
            zone_name, dungeon_name = record
            assert isinstance(zone_name, str)
            assert isinstance(dungeon_name, str)


class TestDailyCollectSpecialDungeon:
    """测试每日收集记录逻辑"""

    def test_mark_daily_collect_completed(self, temp_db):
        """测试每日收集标记与查询"""
        assert temp_db.is_daily_collect_completed() is False
        temp_db.mark_daily_collect_completed()
        assert temp_db.is_daily_collect_completed() is True

    def test_daily_collect_excluded_from_counts_by_default(self, temp_db):
        """每日收集默认不计入副本统计"""
        temp_db.mark_daily_collect_completed()
        temp_db.mark_dungeon_completed("风暴群岛", "真理之地")

        assert temp_db.get_today_completed_count() == 1
        assert temp_db.get_today_completed_count(include_special=True) == 2

        dungeons_default = temp_db.get_today_completed_dungeons()
        assert ("风暴群岛", "真理之地") in dungeons_default
        assert all(zone != "__daily_collect__" for zone, _ in dungeons_default)

        dungeons_full = temp_db.get_today_completed_dungeons(include_special=True)
        assert ("__daily_collect__", "daily_collect") in dungeons_full

    def test_daily_collect_excluded_from_zone_stats(self, temp_db):
        """每日收集默认不计入区域统计"""
        temp_db.mark_daily_collect_completed()
        temp_db.mark_dungeon_completed("军团领域", "梦魇丛林")

        zone_stats = temp_db.get_zone_stats()
        assert zone_stats == [("军团领域", 1)]

        zone_stats_full = dict(temp_db.get_zone_stats(include_special=True))
        assert zone_stats_full["军团领域"] == 1
        assert zone_stats_full["__daily_collect__"] == 1


class TestDatabaseCleanup:
    """测试数据库清理功能"""

    def test_cleanup_old_records(self, temp_db):
        """测试清理旧记录"""
        # 标记今天的记录
        temp_db.mark_dungeon_completed("风暴群岛", "真理之地")

        # 清理旧记录（应该不影响今天的记录）
        temp_db.cleanup_old_records(days_to_keep=7)

        # 验证今天的记录还在
        assert temp_db.is_dungeon_completed("风暴群岛", "真理之地") is True


class TestDatabaseContextManager:
    """测试数据库上下文管理器"""

    def test_context_manager(self):
        """测试使用 with 语句"""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            with DungeonProgressDB(db_path) as db:
                db.mark_dungeon_completed("风暴群岛", "真理之地")
                assert db.is_dungeon_completed("风暴群岛", "真理之地") is True
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)


class TestMultiConfig:
    """测试多配置功能"""

    def test_different_configs_isolated(self, temp_db):
        """测试不同配置的数据隔离"""
        db_path = temp_db.db_path

        # 配置1: default
        with DungeonProgressDB(db_path, "default") as db:
            db.mark_dungeon_completed("风暴群岛", "真理之地")
            assert db.get_today_completed_count() == 1

        # 配置2: main_character
        with DungeonProgressDB(db_path, "main_character") as db:
            db.mark_dungeon_completed("军团领域", "大墓地密室")
            assert db.get_today_completed_count() == 1

        # 验证隔离
        with DungeonProgressDB(db_path, "default") as db:
            assert db.get_today_completed_count() == 1
            assert db.is_dungeon_completed("风暴群岛", "真理之地")
            assert not db.is_dungeon_completed("军团领域", "大墓地密室")

        with DungeonProgressDB(db_path, "main_character") as db:
            assert db.get_today_completed_count() == 1
            assert db.is_dungeon_completed("军团领域", "大墓地密室")
            assert not db.is_dungeon_completed("风暴群岛", "真理之地")

    def test_config_name_in_queries(self, temp_db):
        """测试配置名称在查询中的使用"""
        db_path = temp_db.db_path

        # 添加不同配置的数据
        with DungeonProgressDB(db_path, "config1") as db:
            db.mark_dungeon_completed("风暴群岛", "真理之地")
            db.mark_dungeon_completed("风暴群岛", "预言神殿")

        with DungeonProgressDB(db_path, "config2") as db:
            db.mark_dungeon_completed("风暴群岛", "真理之地")

        # 验证统计
        with DungeonProgressDB(db_path, "config1") as db:
            assert db.get_today_completed_count() == 2
            dungeons = db.get_today_completed_dungeons()
            assert len(dungeons) == 2

        with DungeonProgressDB(db_path, "config2") as db:
            assert db.get_today_completed_count() == 1
            dungeons = db.get_today_completed_dungeons()
            assert len(dungeons) == 1

    def test_clear_today_only_affects_current_config(self, temp_db):
        """测试清除今天的记录只影响当前配置"""
        db_path = temp_db.db_path

        # 添加不同配置的数据
        with DungeonProgressDB(db_path, "config1") as db:
            db.mark_dungeon_completed("风暴群岛", "真理之地")

        with DungeonProgressDB(db_path, "config2") as db:
            db.mark_dungeon_completed("军团领域", "大墓地密室")

        # 清除 config1 的数据
        with DungeonProgressDB(db_path, "config1") as db:
            deleted = db.clear_today()
            assert deleted == 1
            assert db.get_today_completed_count() == 0

        # 验证 config2 的数据未受影响
        with DungeonProgressDB(db_path, "config2") as db:
            assert db.get_today_completed_count() == 1

    def test_zone_stats_per_config(self, temp_db):
        """测试区域统计按配置分离"""
        db_path = temp_db.db_path

        # 配置1: 多个区域
        with DungeonProgressDB(db_path, "config1") as db:
            db.mark_dungeon_completed("风暴群岛", "真理之地")
            db.mark_dungeon_completed("风暴群岛", "预言神殿")
            db.mark_dungeon_completed("军团领域", "大墓地密室")

        # 配置2: 单个区域
        with DungeonProgressDB(db_path, "config2") as db:
            db.mark_dungeon_completed("风暴群岛", "真理之地")

        # 验证统计
        with DungeonProgressDB(db_path, "config1") as db:
            stats = db.get_zone_stats()
            assert len(stats) == 2
            zone_dict = dict(stats)
            assert zone_dict["风暴群岛"] == 2
            assert zone_dict["军团领域"] == 1

        with DungeonProgressDB(db_path, "config2") as db:
            stats = db.get_zone_stats()
            assert len(stats) == 1
            assert stats[0] == ("风暴群岛", 1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
