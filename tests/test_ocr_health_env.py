
import os
import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from cron_run_all_dungeons import check_ocr_health

class TestOCRHealthEnv(unittest.TestCase):
    @patch('urllib.request.urlopen')
    def test_check_ocr_health_uses_env_var(self, mock_urlopen):
        # Setup
        test_url = "http://test-server:9999/health"
        os.environ["OCR_HEALTH_URL"] = test_url
        logger = MagicMock()
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Action
        result = check_ocr_health(logger)
        
        # Assert
        mock_urlopen.assert_called_with(test_url, timeout=2)
        self.assertTrue(result)
        
        # Cleanup
        del os.environ["OCR_HEALTH_URL"]

    @patch('urllib.request.urlopen')
    def test_check_ocr_health_default(self, mock_urlopen):
        # Setup - ensure env var is not set
        if "OCR_HEALTH_URL" in os.environ:
            del os.environ["OCR_HEALTH_URL"]
        
        expected_default = "http://localhost:8080/health"
        logger = MagicMock()
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Action
        result = check_ocr_health(logger)
        
        # Assert
        mock_urlopen.assert_called_with(expected_default, timeout=2)
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
