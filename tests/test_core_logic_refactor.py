import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auto_dungeon_core

class TestCoreLogicRefactor(unittest.TestCase):

    def setUp(self):
        self.mock_container = patch('auto_dungeon_core._container').start()
        self.mock_db_cls = patch('auto_dungeon_core.DungeonProgressDB').start()
        self.mock_db = self.mock_db_cls.return_value.__enter__.return_value
        self.mock_show_stats = patch('auto_dungeon_core.show_progress_statistics').start()
        self.mock_device_manager_cls = patch('auto_dungeon_core.DeviceManager').start()
        self.mock_logger = patch('auto_dungeon_core.logger').start()
        
        # Default config mocks
        self.mock_container.config_loader.get_config_name.return_value = "test_config"
        self.mock_container.config_loader.is_daily_collect_enabled.return_value = False
        
        # Default db mocks
        self.mock_db.is_daily_collect_completed.return_value = False
        
        # Default stats: everything completed
        self.mock_show_stats.return_value = (10, 10, 10) # completed, selected, total

    def tearDown(self):
        patch.stopall()

    def test_main_exits_when_all_done_and_no_daily_collect(self):
        """Test that main exits if dungeons done and daily collect not needed"""
        # Setup: Dungeons done (10/10), Daily collect disabled
        self.mock_show_stats.return_value = (10, 10, 10)
        self.mock_container.config_loader.is_daily_collect_enabled.return_value = False
        
        # Run main
        # We need to mock parse_arguments to avoid sys.exit or argument errors
        with patch('auto_dungeon_core.parse_arguments') as mock_args:
            mock_args.return_value.load_account = None
            mock_args.return_value.memlog = False
            mock_args.return_value.emulator = None
            mock_args.return_value.config = "test.json"
            mock_args.return_value.env_overrides = None
            mock_args.return_value.max_iterations = 1

            with patch('auto_dungeon_core.initialize_configs'): 
                auto_dungeon_core.main()
        
        # Assert: DeviceManager was NOT initialized
        self.mock_device_manager_cls.assert_not_called()
        self.mock_logger.info.assert_any_call("✅ 无需启动模拟器，脚本退出")

    def test_main_proceeds_when_daily_collect_needed(self):
        """Test that main proceeds if dungeons done but daily collect needed"""
        # Setup: Dungeons done (10/10), Daily collect enabled and NOT done
        self.mock_show_stats.return_value = (9, 10, 10)
        self.mock_container.config_loader.is_daily_collect_enabled.return_value = True
        self.mock_db.is_daily_collect_completed.return_value = False
        
        # Mock other calls in main
        with patch('auto_dungeon_core.parse_arguments') as mock_args, \
             patch('auto_dungeon_core.initialize_configs'), \
             patch('auto_dungeon_core.attach_file_logger'), \
             patch('auto_dungeon_core.stop_app'), \
             patch('auto_dungeon_core.start_app'), \
             patch('auto_dungeon_core.sleep'), \
             patch('auto_dungeon_core.is_on_character_selection', return_value=False), \
             patch('auto_dungeon_core.DungeonStateMachine') as mock_sm_cls, \
             patch('auto_dungeon_core.run_dungeon_traversal'), \
             patch('auto_dungeon_core.count_remaining_selected_dungeons', return_value=0):

            mock_args.return_value.load_account = None
            mock_args.return_value.memlog = False
            mock_args.return_value.emulator = None
            mock_args.return_value.config = "test.json"
            mock_args.return_value.env_overrides = None
            mock_args.return_value.max_iterations = 1

            auto_dungeon_core.main()
        
        # Assert: DeviceManager WAS initialized
        self.mock_device_manager_cls.assert_called()

    def test_main_exits_when_daily_collect_done_and_dungeons_done(self):
        """Test that main exits if dungeons done and daily collect already done"""
        # Setup: Dungeons done (10/10), Daily collect enabled AND done
        self.mock_show_stats.return_value = (10, 10, 10)
        self.mock_container.config_loader.is_daily_collect_enabled.return_value = True
        self.mock_db.is_daily_collect_completed.return_value = True
        
        # Run main
        with patch('auto_dungeon_core.parse_arguments') as mock_args, \
             patch('auto_dungeon_core.initialize_configs'):
            
            mock_args.return_value.load_account = None
            mock_args.return_value.memlog = False
            mock_args.return_value.emulator = None
            mock_args.return_value.config = "test.json"
            mock_args.return_value.env_overrides = None
            mock_args.return_value.max_iterations = 1

            auto_dungeon_core.main()

        # Assert: DeviceManager NOT initialized
        self.mock_device_manager_cls.assert_not_called()
        self.mock_logger.info.assert_any_call("✅ 无需启动模拟器，脚本退出")

if __name__ == '__main__':
    unittest.main()
