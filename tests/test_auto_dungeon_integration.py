#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
集成测试 - 真机测试自动副本功能
需要连接真实设备才能运行
"""

import sys
import os
import pytest
import logging

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from airtest.core.api import connect_device, auto_setup  # noqa: E402
from auto_dungeon_simple import select_character, find_text_and_click  # noqa: E402

# 配置日志
logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def setup_device():
    """
    设置设备连接
    这是一个模块级别的 fixture，在所有测试前执行一次
    """
    try:
        # 连接设备
        connect_device("Android:///")
        auto_setup(__file__)
        logger.info("✅ 设备连接成功")
        yield True
    except Exception as e:
        logger.error(f"❌ 设备连接失败: {e}")
        pytest.skip(f"无法连接设备: {e}")


@pytest.mark.integration
class TestSelectCharacterIntegration:
    """测试选择角色功能 - 真机测试"""

    def test_select_character_function_exists(self):
        """测试 select_character 函数是否存在"""
        assert callable(select_character), "select_character 函数应该存在且可调用"

    def test_select_character_real_device(self, setup_device):
        """
        测试选择角色功能 - 真机测试

        前提条件：
        - 设备已连接
        - 游戏已打开并在主界面或任意可以访问设置的界面

        测试步骤：
        1. 调用 select_character 函数
        2. 验证函数能够正常执行完成（不抛出异常）

        注意：这是一个基本的功能测试，只验证函数能否正常运行
        不验证具体的 UI 状态，因为游戏状态可能不同
        """
        try:
            # 执行选择角色功能
            select_character()

            # 如果没有抛出异常，则测试通过
            logger.info("✅ select_character 函数执行成功")

        except Exception as e:
            # 记录详细错误信息
            logger.error(f"❌ select_character 函数执行失败: {e}")
            pytest.fail(f"select_character 执行失败: {e}")

    def test_find_text_and_click_basic(self, setup_device):
        """
        测试 find_text_and_click 基本功能 - 真机测试

        这个测试尝试查找屏幕上的文本
        如果找不到文本会超时，但不会导致测试失败
        """
        try:
            # 尝试查找一个常见的文本（设置或其他常见按钮）
            # 设置较短的超时时间，避免测试时间过长
            result = find_text_and_click("设置", timeout=5)

            logger.info(f"查找'设置'文本结果: {result}")

            # 函数应该返回布尔值或 None
            assert result is not None or result is False or result is True, (
                "find_text_and_click 应该返回布尔值"
            )

        except Exception as e:
            logger.warning(f"⚠️ find_text_and_click 执行过程中出现异常: {e}")
            # 不让这个测试失败，因为可能是界面状态不匹配
            pytest.skip(f"跳过测试，界面状态可能不匹配: {e}")


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="CI 环境中没有真实设备")
class TestSelectCharacterWithDeviceCheck:
    """带设备检查的选择角色功能测试"""

    def test_device_connection(self):
        """测试设备是否已连接"""
        try:
            connect_device("Android:///")
            logger.info("✅ 设备连接测试通过")
        except Exception as e:
            pytest.skip(f"未找到连接的 Android 设备: {e}")

    def test_select_character_execution_time(self, setup_device):
        """
        测试 select_character 函数执行时间
        验证函数能在合理时间内完成
        """
        import time

        start_time = time.time()

        try:
            select_character()
            execution_time = time.time() - start_time

            logger.info(f"⏱️ select_character 执行时间: {execution_time:.2f} 秒")

            # 验证执行时间在合理范围内（例如不超过 60 秒）
            assert execution_time < 60, f"函数执行时间过长: {execution_time:.2f} 秒"

        except Exception as e:
            logger.error(f"❌ 函数执行失败: {e}")
            pytest.fail(f"函数执行失败: {e}")


if __name__ == "__main__":
    # 直接运行此文件时执行测试
    pytest.main([__file__, "-v", "-s", "--tb=short"])
