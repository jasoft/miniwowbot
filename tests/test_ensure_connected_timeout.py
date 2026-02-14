# -*- encoding=utf8 -*-
"""
测试 ensure_connected 不会长时间卡住

验证修复后:
1. 默认重试次数应该在合理范围内（3-5次）
2. 总等待时间应该有限制
3. 不会长时间卡住（超过几分钟）
"""

import inspect
import time
from unittest.mock import patch

import pytest

from emulator_manager import EmulatorConnectionManager


class TestEnsureConnectedTimeout:
    """测试 ensure_connected 不会卡住"""

    def test_default_max_retries_is_reasonable(self):
        """验证默认重试次数是否合理"""
        manager = EmulatorConnectionManager()
        sig = inspect.signature(manager.ensure_connected)
        max_retries_default = sig.parameters["max_retries"].default

        # 之前是 100 次，太多了，应该 <= 5
        print(f"当前默认重试次数: {max_retries_default}")
        assert max_retries_default <= 5, f"默认重试次数 {max_retries_default} 太大，会导致长时间卡住"

    @patch("time.sleep")
    def test_total_wait_time_is_limited(self, mock_sleep):
        """验证总等待时间有限制，不会无限累加"""
        manager = EmulatorConnectionManager(start_cmd="start.cmd")

        # 模拟每次都失败
        with patch.object(manager, "is_connected", return_value=False), \
             patch.object(manager, "connect", return_value=False), \
             patch.object(manager, "_run_start_cmd", return_value=True):

            start = time.time()
            result = manager.ensure_connected("127.0.0.1:5555", max_retries=5)
            elapsed = time.time() - start

            assert result is False

            # 5次重试，总等待时间应该 <= 60秒（之前是 10+20+30+40+50=150秒）
            total_wait = sum(mock_sleep.call_args_list[i][0][0] for i in range(len(mock_sleep.call_args_list)))
            print(f"总等待时间: {total_wait}秒")
            assert total_wait <= 60, f"总等待时间 {total_wait}秒 太大，会导致长时间卡住"


class TestEnsureConnectedBehavior:
    """测试修复后的行为"""

    @patch("time.sleep")
    def test_connect_success_after_some_retries(self, mock_sleep):
        """测试连接成功的情况"""
        manager = EmulatorConnectionManager(start_cmd="start.cmd")

        # 模拟前2次失败，第3次成功（connect返回True后is_connected也返回True）
        with patch.object(manager, "is_connected", side_effect=[False, True]), \
             patch.object(manager, "connect", return_value=True) as mock_connect, \
             patch.object(manager, "_run_start_cmd", return_value=True):

            result = manager.ensure_connected("127.0.0.1:5555", max_retries=5)
            assert result is True

    def test_no_start_cmd_raises_quickly(self):
        """测试没有启动命令时快速抛出异常"""
        manager = EmulatorConnectionManager(start_cmd=None)

        with patch.object(manager, "is_connected", return_value=False), \
             patch.object(manager, "connect", return_value=False):

            # 应该很快抛出异常，而不是无限重试
            start = time.time()
            with pytest.raises(Exception):  # EmulatorConnectionError
                manager.ensure_connected("127.0.0.1:5555", max_retries=3)
            elapsed = time.time() - start

            # 没有启动命令时，应该在1秒内抛出异常
            assert elapsed < 1, f"抛出异常耗时 {elapsed}秒，太慢了"
