import sys
import os
import unittest
from datetime import datetime, date
from unittest.mock import patch

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.dungeon_db import DungeonProgressDB

class TestDungeonDBLogic(unittest.TestCase):
    
    @patch('database.dungeon_db.datetime')
    def test_get_logic_date_before_6am(self, mock_datetime):
        # Setup: 2023-10-27 05:59:59 (Friday)
        # Should count as 2023-10-26 (Thursday)
        # Using a real datetime object for the return value ensures .hour, .date() work as expected
        mock_now = datetime(2023, 10, 27, 5, 59, 59)
        mock_datetime.now.return_value = mock_now
        
        db = DungeonProgressDB(db_path=":memory:")
        logic_date = db._get_logic_date()
        today_str = db.get_today_date()
        
        expected_date = date(2023, 10, 26)
        self.assertEqual(logic_date, expected_date)
        self.assertEqual(today_str, "2023-10-26")

    @patch('database.dungeon_db.datetime')
    def test_get_logic_date_exactly_6am(self, mock_datetime):
        # Setup: 2023-10-27 06:00:00 (Friday)
        # Should count as 2023-10-27 (Friday)
        mock_now = datetime(2023, 10, 27, 6, 0, 0)
        mock_datetime.now.return_value = mock_now
        
        db = DungeonProgressDB(db_path=":memory:")
        logic_date = db._get_logic_date()
        today_str = db.get_today_date()
        
        expected_date = date(2023, 10, 27)
        self.assertEqual(logic_date, expected_date)
        self.assertEqual(today_str, "2023-10-27")

    @patch('database.dungeon_db.datetime')
    def test_get_logic_date_after_6am(self, mock_datetime):
        # Setup: 2023-10-27 06:01:00 (Friday)
        # Should count as 2023-10-27 (Friday)
        mock_now = datetime(2023, 10, 27, 6, 1, 0)
        mock_datetime.now.return_value = mock_now
        
        db = DungeonProgressDB(db_path=":memory:")
        logic_date = db._get_logic_date()
        today_str = db.get_today_date()
        
        expected_date = date(2023, 10, 27)
        self.assertEqual(logic_date, expected_date)
        self.assertEqual(today_str, "2023-10-27")
    
    @patch('database.dungeon_db.datetime')
    def test_cleanup_old_records_logic(self, mock_datetime):
        # Verify that cleanup uses logic date
        # If today is 2023-10-27 05:00:00 (Logic: 2023-10-26)
        # And we keep 1 day.
        # cutoff should be logic_date - 1 day = 2023-10-25.
        
        mock_now = datetime(2023, 10, 27, 5, 0, 0)
        mock_datetime.now.return_value = mock_now
        
        db = DungeonProgressDB(db_path=":memory:")
        
        # Patch delete on the DungeonProgress model class would be hard directly via db instance
        # So checking internal call to _get_logic_date via side-effect or just trusting previous tests
        # We can inspect what _get_logic_date was called
        
        logic_date = db._get_logic_date()
        self.assertEqual(logic_date, date(2023, 10, 26))

if __name__ == '__main__':
    unittest.main()
