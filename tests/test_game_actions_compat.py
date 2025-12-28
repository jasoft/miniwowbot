
import os
import shutil
import pytest
from unittest.mock import MagicMock, patch
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

import auto_dungeon
from game_actions import GameActions
from ocr_helper import OCRHelper
from project_paths import resolve_project_path

@pytest.fixture
def mock_env(request):
    """
    Setup mock environment for AutoDungeon and GameActions
    """
    # Setup paths
    example_image_path = str(resolve_project_path("images", "screenshots", "example.png"))
    if not os.path.exists(example_image_path):
        pytest.fail(f"Test image not found at {example_image_path}")

    # Initialize OCRHelper and GameActions
    # We use a dummy output dir
    output_dir = "output/test_compat"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
        
    ocr_helper = OCRHelper(output_dir=output_dir, delete_temp_screenshots=True)
    game_actions = GameActions(ocr_helper)

    # Inject into auto_dungeon
    original_ocr_helper = auto_dungeon.ocr_helper
    original_game_actions = auto_dungeon.game_actions
    original_touch = None
    
    auto_dungeon.ocr_helper = ocr_helper
    auto_dungeon.game_actions = game_actions
    
    # Mock touch
    mock_touch = MagicMock()
    if hasattr(auto_dungeon.game_actions, 'touch'):
         original_touch = auto_dungeon.game_actions.touch
         auto_dungeon.game_actions.touch = mock_touch

    yield {
        "example_image_path": example_image_path,
        "ocr_helper": ocr_helper,
        "game_actions": game_actions,
        "mock_touch": mock_touch
    }

    # Teardown
    auto_dungeon.ocr_helper = original_ocr_helper
    auto_dungeon.game_actions = original_game_actions
    # Only restore touch if game_actions is not None
    if original_touch and auto_dungeon.game_actions:
        auto_dungeon.game_actions.touch = original_touch
    
    if os.path.exists(output_dir):
        try:
            shutil.rmtree(output_dir)
        except Exception:
            pass

@patch("ocr_helper.snapshot")
def test_find_text_compat(mock_snapshot, mock_env):
    """
    Test that find_text and related functions work correctly with the new GameActions refactor
    and maintain backward compatibility (specifically the 'found' key).
    """
    example_image_path = mock_env["example_image_path"]
    
    def side_effect_snapshot(filename, *args, **kwargs):
        # Copy example.png to filename
        shutil.copy(example_image_path, filename)
    
    mock_snapshot.side_effect = side_effect_snapshot

    # Test 1: find_text "进入游戏"
    print("\nTesting find_text('进入游戏')...")
    result = auto_dungeon.find_text("进入游戏")
    
    assert result is not None, "Should find '进入游戏'"
    # The critical backward compatibility check
    assert result.get("found") is True, "Result should have 'found': True for backward compatibility"
    assert result["found"] is True
    
    # Test 2: Verify other targets mentioned by user
    targets = ["战士", "法师", "盗贼", "术士"]
    for target in targets:
        result = auto_dungeon.find_text(target, similarity_threshold=0.5)
        # Depending on OCR quality, they might or might not be found, 
        # but if found, they must have the 'found' key.
        if result:
             assert result.get("found") is True, f"Result for {target} missing 'found' key"

    # Test 3: find_text_and_click
    mock_env["mock_touch"].reset_mock()
    result = auto_dungeon.find_text_and_click("进入游戏")
    assert result is not None
    assert result.get("found") is True
    mock_env["mock_touch"].assert_called()
    
    # Test 4: text_exists
    result = auto_dungeon.text_exists("进入游戏")
    assert result  # Should be truthy
    assert result.get("found") is True
    
    # Test 5: find_all_texts
    all_texts = auto_dungeon.find_all_texts()
    assert isinstance(all_texts, list)
    assert len(all_texts) > 0
    # verify items in list are also accessible via dict keys
    first = all_texts[0]
    assert "text" in first
    assert "center" in first
