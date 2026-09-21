"""Tests for emulator connection retry defaults."""

from __future__ import annotations

import inspect

from emulator_manager import EmulatorConnectionManager


def test_ensure_connected_default_retry_count() -> None:
    """Ensure default retry count matches expected value.

    期望值 6，不是历史值 100：
    - ``027a833`` 曾把默认重试调到 100 并建了本测试；
    - 随后 ``8d70d25``（2026-09-15）把默认值改回 **6**，理由是 BlueStacks
      冷启动通常只要 60~120 秒，100 次重试会把「真掉线」也拖成极长等待 ——
      但当时漏改了本测试，导致用例长期失败。

    这里改成断言代码里**有明确理由**的 6。若将来又要调整重试次数，
    请连同 ``emulator_manager.ensure_connected`` 的 docstring 一起改。
    """
    signature = inspect.signature(EmulatorConnectionManager.ensure_connected)
    assert signature.parameters["max_retries"].default == 6
