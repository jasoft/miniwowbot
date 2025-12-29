#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试每日收集的持久化功能
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_dungeon import DailyCollectManager
from database.dungeon_db import DungeonProgressDB

class TestDailyCollectPersistence:
    
    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=DungeonProgressDB)
        # Default behavior: step not completed
        db.is_daily_step_completed.return_value = False
        return db

    @pytest.fixture
    def manager(self):
        # Mock config_loader
        config_loader = MagicMock()
        config_loader.get_chest_name.return_value = "TestChest"
        
        manager = DailyCollectManager(config_loader=config_loader)
        # Mock logging to avoid clutter
        manager.logger = MagicMock()
        return manager

    def test_run_step_execute_and_save(self, manager, mock_db):
        """测试 _run_step: 未完成时执行并保存"""
        mock_func = MagicMock()
        
        manager._run_step(mock_db, "test_step", mock_func, "arg1", key="value")
        
        # Verify execution
        mock_func.assert_called_once_with("arg1", key="value")
        # Verify check
        mock_db.is_daily_step_completed.assert_called_once_with("test_step")
        # Verify save
        mock_db.mark_daily_step_completed.assert_called_once_with("test_step")

    def test_run_step_skip_if_completed(self, manager, mock_db):
        """测试 _run_step: 已完成时跳过"""
        mock_db.is_daily_step_completed.return_value = True
        mock_func = MagicMock()
        
        manager._run_step(mock_db, "test_step", mock_func)
        
        # Verify NO execution
        mock_func.assert_not_called()
        # Verify check
        mock_db.is_daily_step_completed.assert_called_once_with("test_step")
        # Verify NO save (already done)
        mock_db.mark_daily_step_completed.assert_not_called()

    def test_run_step_no_db(self, manager):
        """测试 _run_step: 无 DB 时直接执行"""
        mock_func = MagicMock()
        
        manager._run_step(None, "test_step", mock_func)
        
        mock_func.assert_called_once()

    def test_collect_daily_rewards_all_steps(self, manager, mock_db):
        """测试 collect_daily_rewards: 所有步骤都应被检查"""
        # Mock all internal methods to avoid side effects
        with patch.object(manager, '_collect_idle_rewards') as m1, \
             patch.object(manager, '_buy_market_items') as m2, \
             patch.object(manager, '_handle_retinue_deployment') as m3, \
             patch.object(manager, '_collect_free_dungeons') as m4, \
             patch.object(manager, '_open_chests') as m5, \
             patch.object(manager, '_kill_world_boss') as m6, \
             patch.object(manager, '_receive_mails') as m7, \
             patch.object(manager, '_small_cookie') as m8, \
             patch.object(manager, '_collect_gifts') as m9, \
             patch.object(manager, '_buy_ads_items') as m10, \
             patch.object(manager, '_demonhunter_exam') as m11:
            
            manager.collect_daily_rewards(db=mock_db)
            
            # Verify checking of steps
            steps = [
                "idle_rewards", "buy_market_items", "retinue_deployment", 
                "free_dungeons", "open_chests", "world_boss", 
                "receive_mails", "small_cookie", "collect_gifts", 
                "buy_ads_items", "demonhunter_exam"
            ]
            
            for step in steps:
                mock_db.is_daily_step_completed.assert_any_call(step)
                mock_db.mark_daily_step_completed.assert_any_call(step)

    def test_collect_daily_rewards_partial_completion(self, manager, mock_db):
        """测试 collect_daily_rewards: 部分完成后只执行剩下的"""
        
        # Simulate 'idle_rewards' is already done
        def side_effect(step_name):
            return step_name == "idle_rewards"
        mock_db.is_daily_step_completed.side_effect = side_effect
        
        with patch.object(manager, '_collect_idle_rewards') as m1, \
             patch.object(manager, '_buy_market_items') as m2:
            
            # Mock other methods to avoid errors
            manager._handle_retinue_deployment = MagicMock()
            manager._collect_free_dungeons = MagicMock()
            manager._open_chests = MagicMock()
            manager._kill_world_boss = MagicMock()
            manager._receive_mails = MagicMock()
            manager._small_cookie = MagicMock()
            manager._collect_gifts = MagicMock()
            manager._buy_ads_items = MagicMock()
            manager._demonhunter_exam = MagicMock()

            manager.collect_daily_rewards(db=mock_db)
            
            # m1 (idle_rewards) should NOT be called
            m1.assert_not_called()
            # m2 (buy_market_items) SHOULD be called
            m2.assert_called_once()
            mock_db.mark_daily_step_completed.assert_any_call("buy_market_items")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
