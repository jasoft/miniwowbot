"""Tests for timeout job behavior in levelup."""

# ruff: noqa: E402

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import patch

# Add the levelup.air directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Also add the project root to sys.path for other modules
BASE_ROOT = Path(__file__).resolve().parents[2]
if str(BASE_ROOT) not in sys.path:
    sys.path.insert(0, str(BASE_ROOT))

import levelup
from levelup import build_timeout_job, detect_first_match


def test_timeout_job_triggers():
    # Setup: mock dependencies
    with (
        patch("levelup.follow_task_to_next_place") as mock_follow,
        patch("levelup.send_notification") as mock_notify,
        patch("levelup.TASK_TIMEOUT", -1),
    ):  # Force immediate timeout
        # Initialize last_task_time
        levelup.last_task_time = time.time()

        # Create the timeout job
        timeout_job = build_timeout_job()

        async def run_test():
            return await detect_first_match([timeout_job])

        matched = asyncio.run(run_test())

        assert matched is not None
        assert matched.name == "task_timeout"
        mock_follow.assert_called_once()
        mock_notify.assert_called_once()


def test_timeout_job_does_not_block():
    # Setup: mock dependencies
    with patch("levelup.TASK_TIMEOUT", 100):
        levelup.last_task_time = time.time()
        timeout_job = build_timeout_job()

        async def run_test():
            start_time = time.time()
            matched = await detect_first_match([timeout_job])
            end_time = time.time()
            return matched, end_time - start_time

        matched, duration = asyncio.run(run_test())

        assert matched is None
        assert duration < 0.1  # Should return almost immediately


def test_timeout_job_does_not_trigger_when_reset():
    # Setup: mock dependencies
    with (
        patch("levelup.follow_task_to_next_place") as mock_follow,
        patch("levelup.send_notification") as mock_notify,
        patch("levelup.TASK_TIMEOUT", 0.2),
    ):  # Set a 0.2s timeout
        levelup.last_task_time = time.time()
        timeout_job = build_timeout_job()

        async def other_fast_job_detector():
            await asyncio.sleep(0.1)  # Faster than 0.2s
            return "ok"

        other_job = levelup.DetectionJob("other", other_fast_job_detector, lambda _: None)

        async def run_test():
            return await detect_first_match([timeout_job, other_job])

        matched = asyncio.run(run_test())

        assert matched is not None
        assert matched.name == "other"
        mock_follow.assert_not_called()
        mock_notify.assert_not_called()


if __name__ == "__main__":
    # Simple manual run
    test_timeout_job_triggers()
    test_timeout_job_does_not_trigger_when_reset()
    print("Tests passed!")
