#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试数据库模块
"""

import sys
import os
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
        expected = datetime.now().strftime("%Y-%m-%d")
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
