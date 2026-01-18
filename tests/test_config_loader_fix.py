
import unittest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_loader import ConfigLoader

class TestConfigLoaderFix(unittest.TestCase):
    def test_get_attr_boolean_true(self):
        """Test that get_attr returns True when value is True and default is False"""
        loader = ConfigLoader.__new__(ConfigLoader)
        loader.test_bool = True
        
        # This should return True, but with the bug it might return False (default)
        result = loader.get_attr("test_bool", False)
        self.assertTrue(result)

    def test_get_attr_boolean_false(self):
        """Test that get_attr returns False when value is False and default is True"""
        loader = ConfigLoader.__new__(ConfigLoader)
        loader.test_bool = False
        
        result = loader.get_attr("test_bool", True)
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
