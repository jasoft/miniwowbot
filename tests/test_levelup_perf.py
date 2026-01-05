import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add root dir and levelup.air to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'levelup.air'))

# Mock airtest and other dependencies before importing levelup
sys.modules["airtest"] = MagicMock()
sys.modules["airtest.core"] = MagicMock()
sys.modules["airtest.core.api"] = MagicMock()
sys.modules["airtest.core.settings"] = MagicMock()
sys.modules["requests"] = MagicMock()

# We need to mock OCRHelper and GameActions before importing levelup
# because it imports them at module level. 
# Actually it imports them after sys.path hack.
# But we can patch them in sys.modules.

sys.modules["ocr_helper"] = MagicMock()
sys.modules["game_actions"] = MagicMock()

from levelup import LevelUpEngine, logger  # noqa: E402

@pytest.mark.asyncio
async def test_workflow_producer_loop_logging():
    # Setup
    with patch("levelup.vibe_ocr.OCRHelper"), \
         patch("levelup.GameActions"):
        engine = LevelUpEngine()
    
    engine.running = True
    
    # Mock detect_workflow and check_status to simulate work
    engine.detect_workflow = AsyncMock()
    # Simulate some delay
    async def fake_work():
        await asyncio.sleep(0.01)
    engine.detect_workflow.side_effect = fake_work
    
    engine.check_status = AsyncMock()
    
    # Stop the loop after a short delay
    async def stop_engine():
        await asyncio.sleep(0.05)
        engine.running = False
        
    # Run the loop
    # We patch the logger to verify calls
    with patch.object(logger, "info") as mock_info:
        await asyncio.gather(
            engine.workflow_producer_loop(),
            stop_engine()
        )
        
        # Verify
        found = False
        for call in mock_info.call_args_list:
            args, _ = call
            if isinstance(args[0], str) and "workflow_producer_loop cycle cost" in args[0]:
                found = True
                print(f"Found log: {args[0]}")
                break
        
        assert found, "Did not find expected log message for loop cycle cost"
