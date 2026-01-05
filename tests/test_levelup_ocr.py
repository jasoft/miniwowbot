import sys
import os
from unittest.mock import patch

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def test_levelup_ocr_instantiation():
    """Test that vibe_ocr.OCRHelper is instantiated correctly in levelup.py"""
    
    # Add levelup.air to sys.path so we can import levelup
    levelup_path = os.path.join(PROJECT_ROOT, 'levelup.air')
    sys.path.insert(0, levelup_path)
    
    # Mock airtest and other dependencies that might cause side effects on import
    with patch('airtest.core.api.auto_setup'), \
         patch('airtest.core.api.connect_device'), \
         patch('airtest.core.api.Template'), \
         patch('airtest.core.api.exists'), \
         patch('airtest.core.api.touch'), \
         patch('airtest.core.api.sleep'):
         
        import levelup
        
        # Check if ocr object exists and is initialized
        assert hasattr(levelup, 'ocr')
        assert levelup.ocr is not None
        assert levelup.ocr.__class__.__name__ == 'OCRHelper'
