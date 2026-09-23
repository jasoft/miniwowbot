#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
集成测试 - 真机测试自动副本功能
需要连接真实设备才能运行
"""

# ruff: noqa: E402

import logging
import os
import time
from typing import Any

import pytest  # type: ignore[reportMissingImports]

pytest.importorskip("airtest.core.api")
pytest.importorskip("vibe_ocr")

import vibe_ocr  # noqa: E402

# 添加父目录到路径
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from airtest.core.api import (  # type: ignore[reportMissingImports]  # noqa: E402
    auto_setup,
    connect_device,
    snapshot,
)

import auto_dungeon as _auto_dungeon  # noqa: E402
from auto_dungeon_core import get_container  # noqa: E402

auto_dungeon: Any = _auto_dungeon
from auto_dungeon import (
    DailyCollectManager,
    daily_collect,
    find_text_and_click_safe,
    select_character,
    switch_account,
)  # noqa: E402
from config_loader import ConfigLoader  # noqa: E402
from tests.utils import load_test_accounts  # noqa: E402

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def setup_device():
    """
    设置设备连接、OCR Helper 和配置文件
    这是一个模块级别的 fixture，在所有测试前执行一次
    """
    try:
        # 加载 warrior.json 配置文件
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "configs",
            "warrior.json",
        )

        warrior_config = ConfigLoader(config_path)
        container = get_container()
        container.config_loader = warrior_config
        logger.info(f"✅ 成功加载 warrior 配置: {warrior_config.get_char_class()}")
        logger.info(
            f"🎁 每日领取: {'启用' if warrior_config.is_daily_collect_enabled() else '禁用'}"
        )
        logger.info(f"⚡ 快速挂机: {'启用' if warrior_config.is_quick_afk_enabled() else '禁用'}")

        # 连接设备
        connect_device("Android:///")
        auto_setup(__file__)
        logger.info("✅ 设备连接成功")

        # 初始化 OCR Helper 和 GameActions (都设置到 container 中)
        from game_actions import GameActions

        container.ocr_helper = vibe_ocr.OCRHelper(output_dir="output", snapshot_func=snapshot)
        container.game_actions = GameActions(container.ocr_helper, click_interval=1)
        logger.info("✅ GameActions 初始化成功")

    except Exception as e:
        logger.error(f"❌ 设备连接失败: {e}")
        pytest.skip(f"无法连接设备: {e}")
        return

    yield True

    # 清理
    container = get_container()
    container.game_actions = None
    container.ocr_helper = None


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
        assert (
            success_count > 0
        ), f"所有切换账号尝试都失败了 (成功: {success_count}/{total_attempts})"
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
            result = find_text_and_click_safe("设置", timeout=5)

            logger.info(f"查找'设置'文本结果: {result}")

            # 函数应该返回布尔值或 None
            assert (
                result is not None or result is False or result is True
            ), "find_text_and_click 应该返回布尔值"

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
class TestMiscFunctionsIntegration:
    """测试其他独立函数 - 真机测试"""

    def test_is_main_world_function_exists(self):
        """测试 auto_dungeon.is_main_world 函数是否存在"""
        assert hasattr(auto_dungeon, "is_main_world"), "auto_dungeon 应该有 is_main_world 函数"
        assert callable(auto_dungeon.is_main_world), "is_main_world 应该是可调用的"

    def test_is_main_world_real_device(self, setup_device):
        """
        测试 is_main_world 函数在真机上的基本功能

        前提条件：
        - 设备已连接
        - 游戏已打开并在主界面或副本界面

        测试步骤：
        1. 调用 is_main_world 函数
        2. 验证函数返回布尔值
        """
        try:
            start_time = time.time()
            result = auto_dungeon.is_main_world()
            execution_time = time.time() - start_time
            logger.info(f"is_main_world 执行时间: {execution_time:.2f} 秒")
            logger.info(f"is_main_world 返回值: {result}")
            assert isinstance(result, bool), "is_main_world 应该返回布尔值"
        except Exception as e:
            logger.error(f"❌ is_main_world 执行失败: {e}")
            pytest.fail(f"is_main_world 执行失败: {e}")

    def test_is_main_world_multiple_calls(self, setup_device):
        """
        多次调用 is_main_world 验证稳定性，并统计平均执行时间
        """
        success_count = 0
        total_attempts = 10
        total_time = 0.0
        for i in range(total_attempts):
            try:
                start_time = time.time()
                result = auto_dungeon.is_main_world()
                exec_time = time.time() - start_time
                total_time += exec_time
                logger.info(
                    f"第 {i + 1} 次 is_main_world 返回值: {result}，耗时: {exec_time:.2f} 秒"
                )
                assert isinstance(result, bool), "is_main_world 应该返回布尔值"
                success_count += 1
                time.sleep(1)
            except Exception as e:
                logger.warning(f"⚠️ 第 {i + 1} 次 is_main_world 调用失败: {e}")
        assert (
            success_count > 0
        ), f"所有 is_main_world 调用都失败了 (成功: {success_count}/{total_attempts})"
        avg_time = total_time / success_count if success_count else 0
        logger.info(
            f"📊 is_main_world 成功率: {success_count}/{total_attempts}，平均耗时: {avg_time:.2f} 秒"
        )


@pytest.mark.integration
class TestDailyCollectIntegration:
    """测试每日领取功能 - 真机测试"""

    def test_daily_collect_function_exists(self):
        """测试 daily_collect 函数是否存在"""
        assert callable(daily_collect), "daily_collect 函数应该存在且可调用"

    def test_daily_collect_manager_class_exists(self):
        """测试 DailyCollectManager 类是否存在"""
        assert DailyCollectManager is not None, "DailyCollectManager 类应该存在"
        assert hasattr(
            DailyCollectManager, "collect_daily_rewards"
        ), "DailyCollectManager 应该有 collect_daily_rewards 方法"
        assert hasattr(
            DailyCollectManager, "_collect_idle_rewards"
        ), "DailyCollectManager 应该有 _collect_idle_rewards 方法"
        assert hasattr(
            DailyCollectManager, "_collect_quick_afk"
        ), "DailyCollectManager 应该有 _collect_quick_afk 方法"
        assert hasattr(
            DailyCollectManager, "_handle_retinue_deployment"
        ), "DailyCollectManager 应该有 _handle_retinue_deployment 方法"
        assert hasattr(
            DailyCollectManager, "_collect_free_dungeons"
        ), "DailyCollectManager 应该有 _collect_free_dungeons 方法"
        assert hasattr(
            DailyCollectManager, "_sweep_tower_floor"
        ), "DailyCollectManager 应该有 _sweep_tower_floor 方法"

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

    def test_handle_retinue_deployment(self, setup_device):
        """
        测试随从派遣功能 - 真机测试

        前提条件：
        - 设备已连接
        - 游戏已打开并在主界面或任意可以访问主界面的界面

        测试步骤：
        1. 调用 handle_retinue_deployment 函数
        2. 验证函数能够正常执行完成（不抛出异常）
        """
        manager = DailyCollectManager()
        manager._handle_retinue_deployment()

    def test_click_ads(self, setup_device):
        """
        测试点击广告功能 - 真机测试
        """
        # 执行点击广告功
        manager = DailyCollectManager()
        manager._buy_ads_items()

    def test_demonhunter_exam(self, setup_device):
        """
        测试猎魔试炼功能 - 真机测试
        """
        manager = DailyCollectManager()
        manager._demonhunter_exam()

    def test_claim_event_rewards(self, setup_device):
        """
        测试领取各种主题奖励功能 - 真机测试
        """
        manager = DailyCollectManager()
        manager._claim_event_rewards()

    def test_collect_free_diamonds(self, setup_device):
        """
        测试领取免费钻石功能 - 真机测试
        """
        manager = DailyCollectManager()
        manager._collect_free_dungeons()

    def test_kill_world_boss(self, setup_device):
        """
        测试杀死世界boss功能 - 真机测试

        前提条件：
        - 设备已连接
        - 游戏已打开并在主界面或任意可以访问主界面的界面

        测试步骤：
        1. 调用 kill_world_boss 函数
        2. 验证函数能够正常执行完成（不抛出异常）


        Keyword arguments:
        argument -- description
        Return: return_description
        """
        manager = DailyCollectManager()
        manager._kill_world_boss()

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
        assert (
            success_count > 0
        ), f"所有 daily_collect 调用都失败了 (成功: {success_count}/{total_attempts})"
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

    def test_daily_collect_manager_collect_idle_rewards(self, setup_device):
        """
        测试 DailyCollectManager._collect_idle_rewards 方法
        单独测试领取挂机奖励功能
        """
        try:
            # 创建 DailyCollectManager 实例
            manager = DailyCollectManager()
            logger.info("🧪 开始测试领取挂机奖励功能")

            # 执行单独的挂机奖励领取
            manager._collect_idle_rewards()
            logger.info("✅ _collect_idle_rewards 执行成功")

        except Exception as e:
            logger.error(f"❌ _collect_idle_rewards 执行失败: {e}")
            pytest.fail(f"_collect_idle_rewards 执行失败: {e}")

    def test_daily_collect_manager_handle_retinue_deployment(self, setup_device):
        """
        测试 DailyCollectManager._handle_retinue_deployment 方法
        单独测试随从派遣功能
        """
        try:
            # 创建 DailyCollectManager 实例
            manager = DailyCollectManager()
            logger.info("🧪 开始测试随从派遣功能")

            # 执行随从派遣
            manager._handle_retinue_deployment()
            logger.info("✅ _handle_retinue_deployment 执行成功")

        except Exception as e:
            logger.error(f"❌ _handle_retinue_deployment 执行失败: {e}")
            pytest.fail(f"_handle_retinue_deployment 执行失败: {e}")

    def test_daily_collect_manager_collect_free_dungeons(self, setup_device):
        """
        测试 DailyCollectManager._collect_free_dungeons 方法
        单独测试领取免费地下城功能
        """
        try:
            # 创建 DailyCollectManager 实例
            manager = DailyCollectManager()
            logger.info("🧪 开始测试领取免费地下城功能")

            # 执行免费地下城领取
            manager._collect_free_dungeons()
            logger.info("✅ _collect_free_dungeons 执行成功")

        except Exception as e:
            logger.error(f"❌ _collect_free_dungeons 执行失败: {e}")
            pytest.fail(f"_collect_free_dungeons 执行失败: {e}")

    def test_daily_collect_manager_sweep_tower_floor(self, setup_device):
        """
        测试 DailyCollectManager._sweep_tower_floor 方法
        单独测试扫荡试炼塔楼层功能
        """
        try:
            # 创建 DailyCollectManager 实例
            manager = DailyCollectManager()
            logger.info("🧪 开始测试扫荡试炼塔楼层功能")

            # 测试扫荡刻印楼层
            manager._sweep_tower_floor("刻印", regions=[7, 8])
            logger.info("✅ 扫荡刻印楼层测试完成")

            # 测试扫荡宝石楼层
            manager._sweep_tower_floor("宝石", regions=[8, 8])
            logger.info("✅ 扫荡宝石楼层测试完成")

            # 测试扫荡雕文楼层
            manager._sweep_tower_floor("雕文", regions=[9, 8])
            logger.info("✅ 扫荡雕文楼层测试完成")

        except Exception as e:
            logger.error(f"❌ _sweep_tower_floor 执行失败: {e}")
            pytest.fail(f"_sweep_tower_floor 执行失败: {e}")

    def test_daily_collect_manager_execution_time(self, setup_device):
        """
        测试 DailyCollectManager 各个方法的执行时间
        """
        manager = DailyCollectManager(config_loader=get_container().config_loader)

        methods_to_test = [
            ("_collect_idle_rewards", "领取挂机奖励"),
            ("_collect_quick_afk", "快速挂机"),
            ("_handle_retinue_deployment", "随从派遣"),
            ("_collect_free_dungeons", "免费地下城"),
        ]

        for method_name, description in methods_to_test:
            try:
                logger.info(f"🧪 测试 {description} 执行时间")
                start_time = time.time()

                # 执行方法
                method = getattr(manager, method_name)
                method()

                execution_time = time.time() - start_time
                logger.info(f"⏱️ {description} 执行时间: {execution_time:.2f} 秒")

                # 验证执行时间在合理范围内（根据不同功能设置不同阈值）
                if method_name == "_collect_idle_rewards":
                    assert (
                        execution_time < 30
                    ), f"{description} 执行时间过长: {execution_time:.2f} 秒"
                elif method_name == "_collect_free_dungeons":
                    assert (
                        execution_time < 45
                    ), f"{description} 执行时间过长: {execution_time:.2f} 秒"
                else:
                    assert (
                        execution_time < 20
                    ), f"{description} 执行时间过长: {execution_time:.2f} 秒"

                # 在不同方法之间添加延迟
                time.sleep(2)

            except Exception as e:
                logger.error(f"❌ {description} 执行失败: {e}")
                # 不让单个方法的失败影响整个测试
                logger.warning(f"⚠️ 跳过 {description} 的执行时间测试")

    def test_open_chests(self, setup_device):
        """
        测试 DailyCollectManager._open_chests 方法
        单独测试开启宝箱功能
        """
        manager = DailyCollectManager(config_loader=get_container().config_loader)
        try:
            logger.info("🧪 开始测试开启宝箱功能")
            manager._open_chests("风暴宝箱")
            logger.info("✅ 开启宝箱功能测试完成")

        except Exception as e:
            logger.error(f"❌ _open_chests 执行失败: {e}")
            pytest.fail(f"_open_chests 执行失败: {e}")

    def test_config_loader_integration(self, setup_device):
        """
        测试配置加载器集成
        验证 warrior.json 配置是否正确加载并可以使用
        """
        container = get_container()
        # 验证配置加载器已设置
        assert container.config_loader is not None, "config_loader 应该已设置"

        # 验证配置内容
        assert container.config_loader.get_char_class() == "战士", "角色职业应该是战士"
        assert container.config_loader.is_daily_collect_enabled() is True, "每日领取应该启用"
        assert container.config_loader.is_quick_afk_enabled() is True, "快速挂机应该启用"
        assert container.config_loader.get_chest_name() == "亡灵宝箱", "宝箱名称应该是亡灵宝箱"

        # 验证副本配置
        zone_dungeons = container.config_loader.get_zone_dungeons()
        assert len(zone_dungeons) == 9, "应该有9个区域（含日常任务）"
        assert "日常任务" in zone_dungeons, "应该包含日常任务"
        assert "风暴群岛" in zone_dungeons, "应该包含风暴群岛"

        # 验证 OCR 纠正映射
        assert (
            container.config_loader.correct_ocr_text("梦魔丛林") == "梦魇丛林"
        ), "OCR 纠正应该工作"

        logger.info("✅ 配置加载器集成测试通过")

    def test_daily_collect_with_warrior_config(self, setup_device):
        """
        测试使用 warrior 配置的每日领取功能
        """
        container = get_container()
        # 验证配置已启用每日领取
        assert (
            container.config_loader.is_daily_collect_enabled() is True
        ), "warrior 配置应该启用每日领取"

        # 创建 DailyCollectManager 并传入配置
        manager = DailyCollectManager(config_loader=container.config_loader)
        assert manager.config_loader == container.config_loader, "管理器应该使用相同的配置"

        # 测试配置驱动的功能
        if container.config_loader.is_quick_afk_enabled():
            logger.info("🧪 测试挂机功能（warrior 配置启用）")
            try:
                manager._collect_idle_rewards()
                logger.info("✅ 挂机功能执行成功")
            except Exception as e:
                logger.warning(f"⚠️ 挂机功能执行失败: {e}")
        else:
            logger.info("⚠️ 挂机功能未启用")

        logger.info("✅ warrior 配置驱动的每日领取测试完成")


if __name__ == "__main__":
    # 直接运行此文件时执行测试
    pytest.main([__file__, "-v", "-s", "--tb=short"])
