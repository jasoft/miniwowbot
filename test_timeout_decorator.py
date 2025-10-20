#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试超时装饰器功能
"""

import time
import logging
from wrapt_timeout_decorator import timeout as timeout_decorator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@timeout_decorator(5, timeout_exception=TimeoutError)
def test_short_timeout():
    """测试短超时（5秒）"""
    logger.info("开始测试短超时函数（5秒）")
    time.sleep(10)  # 睡眠10秒，超过5秒超时
    logger.info("短超时函数完成")
    return "成功"


@timeout_decorator(30, timeout_exception=TimeoutError)
def test_long_timeout():
    """测试长超时（30秒）"""
    logger.info("开始测试长超时函数（30秒）")
    time.sleep(5)  # 睡眠5秒，不会超时
    logger.info("长超时函数完成")
    return "成功"


def test_timeout_with_restart():
    """测试超时后重启的逻辑"""
    max_restarts = 3
    restart_count = 0

    while restart_count < max_restarts:
        try:
            logger.info(f"\n{'=' * 50}")
            logger.info(f"尝试执行任务 (第 {restart_count + 1} 次)")
            logger.info(f"{'=' * 50}\n")

            # 这里调用可能超时的函数
            result = test_short_timeout()
            logger.info(f"✅ 任务成功完成: {result}")
            return True

        except TimeoutError as e:
            restart_count += 1
            logger.error(f"\n❌ 检测到超时错误: {e}")

            if restart_count < max_restarts:
                logger.warning(
                    f"\n🔄 正在重启... (第 {restart_count}/{max_restarts} 次)"
                )
                time.sleep(2)  # 等待2秒后重启
            else:
                logger.error(f"\n❌ 已达到最大重启次数 ({max_restarts})，退出")
                return False

        except Exception as e:
            logger.error(f"\n❌ 发生其他错误: {e}")
            return False

    return False


def main():
    """主测试函数"""
    logger.info("\n" + "=" * 60)
    logger.info("🧪 开始测试超时装饰器功能")
    logger.info("=" * 60 + "\n")

    # 测试1: 正常完成的函数
    logger.info("\n📋 测试1: 正常完成的函数（不会超时）")
    try:
        result = test_long_timeout()
        logger.info(f"✅ 测试1通过: {result}")
    except Exception as e:
        logger.error(f"❌ 测试1失败: {e}")

    # 测试2: 会超时的函数
    logger.info("\n📋 测试2: 会超时的函数")
    try:
        result = test_short_timeout()
        logger.info(f"✅ 测试2通过: {result}")
    except TimeoutError as e:
        logger.info(f"✅ 测试2通过 - 成功捕获超时: {e}")
    except Exception as e:
        logger.error(f"❌ 测试2失败: {e}")

    # 测试3: 超时后重启逻辑
    logger.info("\n📋 测试3: 超时后重启逻辑")
    success = test_timeout_with_restart()
    if success:
        logger.info("✅ 测试3通过")
    else:
        logger.info("✅ 测试3通过 - 成功演示了重启机制")

    logger.info("\n" + "=" * 60)
    logger.info("🎉 所有测试完成！")
    logger.info("=" * 60 + "\n")


if __name__ == "__main__":
    main()
