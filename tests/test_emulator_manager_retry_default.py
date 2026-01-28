"""Tests for emulator connection retry defaults."""

from __future__ import annotations

import inspect

from emulator_manager import EmulatorConnectionManager


def test_ensure_connected_default_retry_count() -> None:
    """Ensure default retry count matches expected value."""
    signature = inspect.signature(EmulatorConnectionManager.ensure_connected)
    assert signature.parameters["max_retries"].default == 100
