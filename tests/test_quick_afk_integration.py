#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试快速挂机功能的集成
"""

import logging
import os

import pytest

pytest.importorskip("airtest.core.api")
pytest.importorskip("vibe_ocr")

from airtest.core.api import connect_device, auto_setup  # noqa: E402
from auto_dungeon import (
    DailyCollectManager,
)  # noqa: E402
from config_loader import load_config  # noqa: E402
import auto_dungeon  # noqa: E402
from vibe_ocr import OCRHelper  # noqa: E402

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def setup_device():
    """
    设置设备连接和 OCR Helper
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
class TestQuickAFKIntegration:
    """测试快速挂机功能集成"""

    def test_collect_daily_rewards_with_quick_afk_enabled(self, setup_device):
        """
        测试启用快速挂机配置时，collect_daily_rewards 会调用 _collect_quick_afk
        """
        try:
            # 加载启用快速挂机的测试配置
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "configs",
                "test_quick_afk.json",
            )
            config_loader = load_config(config_path)

            # 验证配置已启用快速挂机
            assert config_loader.is_quick_afk_enabled(), "测试配置应该启用快速挂机"

            # 创建 DailyCollectManager 实例
            manager = DailyCollectManager(config_loader=config_loader)

            logger.info("🧪 开始测试启用快速挂机的每日收集")

            # 执行每日收集（应该包含快速挂机）
            manager.collect_daily_rewards()

            logger.info("✅ 启用快速挂机的每日收集测试完成")

        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            pytest.fail(f"测试失败: {e}")

    def test_collect_daily_rewards_with_quick_afk_disabled(self, setup_device):
        """
        测试未启用快速挂机配置时，collect_daily_rewards 不会调用 _collect_quick_afk
        """
        try:
            # 加载默认配置（未启用快速挂机）
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "configs",
                "default.json",
            )
            config_loader = load_config(config_path)

            # 验证配置未启用快速挂机
            assert not config_loader.is_quick_afk_enabled(), (
                "默认配置应该未启用快速挂机"
            )

            # 创建 DailyCollectManager 实例
            manager = DailyCollectManager(config_loader=config_loader)

            logger.info("🧪 开始测试未启用快速挂机的每日收集")

            # 执行每日收集（不应该包含快速挂机）
            manager.collect_daily_rewards()

            logger.info("✅ 未启用快速挂机的每日收集测试完成")

        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            pytest.fail(f"测试失败: {e}")

    def test_collect_quick_afk_direct_call(self, setup_device):
        """
        测试直接调用 _collect_quick_afk 方法
        验证方法内部不再判断配置
        """
        try:
            # 使用默认配置（未启用快速挂机）
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "configs",
                "default.json",
            )
            config_loader = load_config(config_path)

            # 创建 DailyCollectManager 实例
            manager = DailyCollectManager(config_loader=config_loader)

            logger.info("🧪 开始测试直接调用 _collect_quick_afk")

            # 直接调用 _collect_quick_afk，应该执行而不检查配置
            manager._collect_idle_rewards()
            manager._collect_quick_afk()

            logger.info("✅ 直接调用 _collect_quick_afk 测试完成")

        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            pytest.fail(f"测试失败: {e}")
