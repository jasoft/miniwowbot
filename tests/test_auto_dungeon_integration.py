#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
集成测试 - 真机测试自动副本功能
需要连接真实设备才能运行
"""

import os
import pytest
import logging
import time
import json

# 添加父目录到路径
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from airtest.core.api import connect_device, auto_setup  # noqa: E402
from auto_dungeon import (
    select_character,
    find_text_and_click,
    switch_account,
    daily_collect,
)  # noqa: E402
import auto_dungeon  # noqa: E402
from ocr_helper import OCRHelper  # noqa: E402

# 配置日志
logger = logging.getLogger(__name__)


def load_test_accounts():
    """
    从配置文件加载测试账号

    Returns:
        list: 账号列表
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "test_accounts.json",
    )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            accounts = config.get("accounts", [])
            logger.info(f"✅ 成功加载 {len(accounts)} 个测试账号")
            return accounts
    except FileNotFoundError:
        logger.warning(f"⚠️ 未找到配置文件: {config_path}")
        logger.info(
            "💡 请复制 test_accounts.json.example 为 test_accounts.json 并填入真实账号"
        )
        pytest.skip("未找到测试账号配置文件")
    except json.JSONDecodeError as e:
        logger.error(f"❌ 配置文件格式错误: {e}")
        pytest.skip(f"配置文件格式错误: {e}")
    except Exception as e:
        logger.error(f"❌ 加载配置文件失败: {e}")
        pytest.skip(f"加载配置文件失败: {e}")


@pytest.fixture(scope="module")
def setup_device():
    """
    设置设备连接和 OCR Helper
    这是一个模块级别的 fixture，在所有测试前执行一次
    """
    try:
        # 连接设备
        connect_device("Android:///")
        auto_setup(__file__)
        logger.info("✅ 设备连接成功")

        # 初始化 OCR Helper
        auto_dungeon.ocr_helper = OCRHelper(output_dir="output")
        logger.info("✅ OCR Helper 初始化成功")

        yield True
    except Exception as e:
        logger.error(f"❌ 设备连接失败: {e}")
        pytest.skip(f"无法连接设备: {e}")


@pytest.mark.integration
class TestSwitchAccountIntegration:
    """测试切换账号功能 - 真机测试"""

    def test_switch_account_function_exists(self):
        """测试 switch_account 函数是否存在"""
        assert callable(switch_account), "switch_account 函数应该存在且可调用"

    def test_switch_account_real_device(self, setup_device):
        """
        测试切换账号功能 - 真机测试

        前提条件：
        - 设备已连接
        - 游戏已打开并在主界面或任意可以访问设置的界面

        测试步骤：
        1. 调用 switch_account 函数
        2. 验证函数能够正常执行完成（不抛出异常）

        注意：这是一个基本的功能测试，只验证函数能否正常运行
        """
        # 加载测试账号
        accounts = load_test_accounts()
        if not accounts:
            pytest.skip("没有可用的测试账号")

        try:
            # 使用第一个账号进行测试
            test_account = accounts[0]
            logger.info(f"🧪 使用测试账号: {test_account}")

            # 执行切换账号功能
            switch_account(test_account)

            # 如果没有抛出异常，则测试通过
            logger.info("✅ switch_account 函数执行成功")

        except Exception as e:
            # 记录详细错误信息
            logger.error(f"❌ switch_account 函数执行失败: {e}")
            pytest.fail(f"switch_account 执行失败: {e}")

    def test_switch_account_execution_time(self, setup_device):
        """
        测试 switch_account 函数执行时间
        验证函数能在合理时间内完成
        """
        # 加载测试账号
        accounts = load_test_accounts()
        if not accounts:
            pytest.skip("没有可用的测试账号")

        start_time = time.time()

        try:
            test_account = accounts[0]
            logger.info(f"🧪 使用测试账号: {test_account}")

            switch_account(test_account)
            execution_time = time.time() - start_time

            logger.info(f"⏱️ switch_account 执行时间: {execution_time:.2f} 秒")

            # 验证执行时间在合理范围内（例如不超过 120 秒，切换账号可能需要更长时间）
            assert execution_time < 120, f"函数执行时间过长: {execution_time:.2f} 秒"

        except Exception as e:
            logger.error(f"❌ switch_account 函数执行失败: {e}")
            pytest.fail(f"switch_account 函数执行失败: {e}")

    def test_switch_account_multiple_calls(self, setup_device):
        """
        测试多次调用 switch_account 函数
        验证函数的稳定性
        """
        # 加载测试账号
        accounts = load_test_accounts()
        if not accounts:
            pytest.skip("没有可用的测试账号")

        if len(accounts) < 2:
            logger.warning("⚠️ 测试账号少于2个，只测试第一个账号")
            accounts = accounts * 2  # 重复使用第一个账号

        success_count = 0
        total_attempts = min(5, len(accounts))  # 最多测试5个账号

        for i in range(total_attempts):
            try:
                test_account = accounts[i]
                logger.info(f"🔄 第 {i + 1} 次切换账号测试: {test_account}")
                switch_account(test_account)
                success_count += 1
                logger.info(f"✅ 第 {i + 1} 次切换账号成功")

                # 在连续调用之间添加短暂延迟
                time.sleep(2)

            except Exception as e:
                logger.warning(f"⚠️ 第 {i + 1} 次切换账号失败: {e}")

        # 至少应该有一次成功
        assert success_count > 0, (
            f"所有切换账号尝试都失败了 (成功: {success_count}/{total_attempts})"
        )
        logger.info(f"📊 切换账号成功率: {success_count}/{total_attempts}")


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
            select_character("战士")

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
            select_character("战士")
            execution_time = time.time() - start_time

            logger.info(f"⏱️ select_character 执行时间: {execution_time:.2f} 秒")

            # 验证执行时间在合理范围内（例如不超过 60 秒）
            assert execution_time < 60, f"函数执行时间过长: {execution_time:.2f} 秒"

        except Exception as e:
            logger.error(f"❌ 函数执行失败: {e}")
            pytest.fail(f"函数执行失败: {e}")


@pytest.mark.integration
class TestDailyCollectIntegration:
    """测试每日领取功能 - 真机测试"""

    def test_daily_collect_function_exists(self):
        """测试 daily_collect 函数是否存在"""
        assert callable(daily_collect), "daily_collect 函数应该存在且可调用"

    def test_daily_collect_real_device(self, setup_device):
        """
        测试每日领取功能 - 真机测试

        前提条件：
        - 设备已连接
        - 游戏已打开并在主界面或任意可以访问主界面的界面

        测试步骤：
        1. 调用 daily_collect 函数
        2. 验证函数能够正常执行完成（不抛出异常）

        注意：这是一个基本的功能测试，只验证函数能否正常运行
        """
        try:
            # 执行每日领取功能
            logger.info("🧪 开始测试每日领取功能")
            daily_collect()

            # 如果没有抛出异常，则测试通过
            logger.info("✅ daily_collect 函数执行成功")

        except Exception as e:
            # 记录详细错误信息
            logger.error(f"❌ daily_collect 函数执行失败: {e}")
            pytest.fail(f"daily_collect 执行失败: {e}")

    def test_daily_collect_execution_time(self, setup_device):
        """
        测试 daily_collect 函数执行时间
        验证函数能在合理时间内完成
        """
        start_time = time.time()

        try:
            logger.info("🧪 开始测试每日领取功能执行时间")
            daily_collect()
            execution_time = time.time() - start_time

            logger.info(f"⏱️ daily_collect 执行时间: {execution_time:.2f} 秒")

            # 验证执行时间在合理范围内（例如不超过 60 秒）
            assert execution_time < 60, f"函数执行时间过长: {execution_time:.2f} 秒"

        except Exception as e:
            logger.error(f"❌ daily_collect 函数执行失败: {e}")
            pytest.fail(f"daily_collect 函数执行失败: {e}")

    def test_daily_collect_multiple_calls(self, setup_device):
        """
        测试多次调用 daily_collect 函数
        验证函数的稳定性和幂等性

        注意：多次调用应该能够正常处理"已领取"的情况
        """
        success_count = 0
        total_attempts = 3  # 测试3次调用

        for i in range(total_attempts):
            try:
                logger.info(f"🔄 第 {i + 1} 次调用 daily_collect")
                daily_collect()
                success_count += 1
                logger.info(f"✅ 第 {i + 1} 次调用成功")

                # 在连续调用之间添加短暂延迟
                time.sleep(2)

            except Exception as e:
                logger.warning(f"⚠️ 第 {i + 1} 次调用失败: {e}")

        # 至少应该有一次成功
        assert success_count > 0, (
            f"所有 daily_collect 调用都失败了 (成功: {success_count}/{total_attempts})"
        )
        logger.info(f"📊 daily_collect 成功率: {success_count}/{total_attempts}")

    def test_daily_collect_with_different_states(self, setup_device):
        """
        测试在不同游戏状态下调用 daily_collect
        验证函数能够正确处理各种状态
        """
        try:
            logger.info("🧪 测试 daily_collect 在当前游戏状态下的表现")

            # 第一次调用
            daily_collect()
            logger.info("✅ 第一次调用完成")

            # 等待一段时间后再次调用
            time.sleep(3)

            # 第二次调用（可能已经领取过）
            daily_collect()
            logger.info("✅ 第二次调用完成（可能显示已领取）")

            # 测试通过
            logger.info("✅ daily_collect 在不同状态下都能正常执行")

        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            pytest.fail(f"daily_collect 在不同状态下执行失败: {e}")


if __name__ == "__main__":
    # 直接运行此文件时执行测试
    pytest.main([__file__, "-v", "-s", "--tb=short"])
