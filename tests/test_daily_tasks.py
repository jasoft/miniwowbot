
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_dungeon_runner import DungeonBot, DungeonBotConfig

class TestDailyTasksIntegration(unittest.TestCase):
    def setUp(self):
        self.config = DungeonBotConfig()
        self.bot = DungeonBot(self.config)
        
        # Mock dependencies
        self.bot._db = MagicMock()
        self.bot._config_loader = MagicMock()
        self.bot._state_machine = MagicMock()
        self.bot._device_manager = MagicMock()
        
        # Mock DailyCollectManager
        self.mock_daily_manager = MagicMock()
        # Patch the property to return our mock
        with patch('auto_dungeon_runner.DungeonBot.daily_collect_manager', new_callable=lambda: self.mock_daily_manager):
            pass # We'll patch it in the test method or use side_effect
            
    def test_daily_tasks_execution(self):
        """Test that daily tasks in zone_dungeons are executed via execute_task"""
        # Setup config with "日常任务"
        self.bot._config_loader.get_zone_dungeons.return_value = {
            "日常任务": [
                {"name": "领取挂机奖励", "selected": True},
                {"name": "购买商店每日", "selected": True}
            ],
            "其他区域": [
                {"name": "普通副本", "selected": True}
            ]
        }
        self.bot._config_loader.is_daily_collect_enabled.return_value = True
        
        # Mock DB to say nothing is completed
        self.bot._db.is_dungeon_completed.return_value = False
        self.bot._db.is_daily_collect_completed.return_value = False
        self.bot._db.get_today_completed_count.return_value = 0
        
        # Mock execute_task to return True
        self.mock_daily_manager.execute_task.return_value = True

        # Run traversal
        # We need to patch the property on the instance or class
        with patch.object(DungeonBot, 'daily_collect_manager', self.mock_daily_manager):
            # Also mock process_dungeon of the bot to use the real method but with mocked dependencies?
            # No, we want to test run_dungeon_traversal calling process_dungeon.
            # But process_dungeon calls state_machine.
            
            # We also need to mock state_machine.prepare_dungeon_state for the normal dungeon
            self.bot._state_machine.prepare_dungeon_state.return_value = True
            self.bot._state_machine.start_battle_state.return_value = True
            
            # Call the method under test
            processed = self.bot.run_dungeon_traversal()
            
            # Verify results
            # Should have processed 3 items (2 daily + 1 normal)
            self.assertEqual(processed, 3)
            
            # Verify execute_task was called for daily tasks
            self.mock_daily_manager.execute_task.assert_any_call("领取挂机奖励")
            self.mock_daily_manager.execute_task.assert_any_call("购买商店每日")
            
            # Verify normal dungeon did NOT call execute_task (implicit, but good to check)
            # We can check call count
            self.assertEqual(self.mock_daily_manager.execute_task.call_count, 2)
            
            # Verify DB marking
            self.bot._db.mark_dungeon_completed.assert_any_call("日常任务", "领取挂机奖励")
            self.bot._db.mark_dungeon_completed.assert_any_call("日常任务", "购买商店每日")
            self.bot._db.mark_dungeon_completed.assert_any_call("其他区域", "普通副本")

if __name__ == '__main__':
    unittest.main()
