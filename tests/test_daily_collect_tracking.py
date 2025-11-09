#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试每日收集任务的数据库记录与去重逻辑
"""

import os
import sys

import pytest

# 添加父目录到路径，方便导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DungeonProgressDB
import auto_dungeon


class DummyConfig:
    """简单的配置对象，仅提供配置名"""

    def __init__(self, name="test_config"):
        self._name = name

    def get_config_name(self):
        return self._name


class DummyDailyCollectManager:
    """用于替换真实 DailyCollectManager 的假对象"""

    def __init__(self, config):
        self.config_loader = config
        self.call_count = 0

    def collect_daily_rewards(self):
        self.call_count += 1


@pytest.fixture
def setup_daily_collect_env(monkeypatch, tmp_path):
    """
    准备 daily_collect 所需的依赖：
    - 伪造的 config_loader
    - 伪造的 daily_collect_manager
    - 指向临时数据库的 DungeonProgressDB 工厂
    """
    dummy_config = DummyConfig()
    monkeypatch.setattr(auto_dungeon, "config_loader", dummy_config)

    dummy_manager = DummyDailyCollectManager(dummy_config)
    monkeypatch.setattr(auto_dungeon, "daily_collect_manager", dummy_manager)

    db_path = tmp_path / "daily_collect.db"

    def db_factory(*args, **kwargs):
        kwargs.setdefault("db_path", str(db_path))
        return DungeonProgressDB(*args, **kwargs)

    monkeypatch.setattr(auto_dungeon, "DungeonProgressDB", db_factory)

    return dummy_manager, db_path


class TestDailyCollectRecording:
    """daily_collect 去重逻辑测试"""

    def test_daily_collect_runs_once_per_day(self, setup_daily_collect_env):
        """同一天多次调用只执行一次每日收集"""
        dummy_manager, db_path = setup_daily_collect_env

        # 第一次调用应执行每日收集
        result_first = auto_dungeon.daily_collect()
        assert result_first is True
        assert dummy_manager.call_count == 1

        # 第二次调用应直接跳过
        result_second = auto_dungeon.daily_collect()
        assert result_second is False
        assert dummy_manager.call_count == 1

        # 验证数据库确实记录了每日收集状态
        with DungeonProgressDB(db_path=str(db_path), config_name="test_config") as db:
            assert db.is_daily_collect_completed() is True
