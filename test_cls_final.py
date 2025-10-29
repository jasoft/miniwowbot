#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
CLS 日志模块最终测试脚本
用于验证 CLS 日志功能是否正常工作
"""

import logging
import time
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cls_logger import get_cls_logger, add_cls_to_logger, close_cls_logger


def test_cls_logger_basic():
    """测试基本的 CLS 日志功能"""
    print("=" * 60)
    print("测试 1: 基本 CLS 日志功能")
    print("=" * 60)

    try:
        # 获取 CLS 日志记录器
        logger = get_cls_logger()
        print(f"✅ 成功获取 CLS 日志记录器: {logger}")

        # 发送测试日志
        logger.info("这是一条测试日志 - 基本功能测试")
        logger.warning("这是一条警告日志")
        logger.error("这是一条错误日志")

        print("✅ 日志已发送")

        # 等待日志上传
        print("⏳ 等待日志上传...")
        time.sleep(2)

        print("✅ 测试 1 完成")
        return True

    except Exception as e:
        print(f"❌ 测试 1 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_add_cls_to_logger():
    """测试将 CLS 处理器添加到现有日志记录器"""
    print("\n" + "=" * 60)
    print("测试 2: 将 CLS 添加到现有日志记录器")
    print("=" * 60)

    try:
        # 创建现有的日志记录器
        logger = logging.getLogger("test_app")
        logger.setLevel(logging.INFO)

        # 添加 CLS 处理器
        add_cls_to_logger(logger)
        print("✅ 成功添加 CLS 处理器到现有日志记录器")

        # 发送测试日志
        logger.info("这是一条测试日志 - 添加到现有日志记录器")
        logger.warning("这是一条警告日志 - 添加到现有日志记录器")

        print("✅ 日志已发送")

        # 等待日志上传
        print("⏳ 等待日志上传...")
        time.sleep(2)

        print("✅ 测试 2 完成")
        return True

    except Exception as e:
        print(f"❌ 测试 2 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_logs():
    """测试发送多条日志"""
    print("\n" + "=" * 60)
    print("测试 3: 发送多条日志")
    print("=" * 60)

    try:
        logger = get_cls_logger()

        # 发送多条日志
        for i in range(10):
            logger.info(f"这是第 {i+1} 条测试日志")

        print("✅ 已发送 10 条日志")

        # 等待日志上传
        print("⏳ 等待日志上传...")
        time.sleep(3)

        print("✅ 测试 3 完成")
        return True

    except Exception as e:
        print(f"❌ 测试 3 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  腾讯云 CLS 日志模块最终测试".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    results = []

    # 运行测试
    results.append(("基本功能测试", test_cls_logger_basic()))
    results.append(("添加到现有日志记录器", test_add_cls_to_logger()))
    results.append(("多条日志测试", test_multiple_logs()))

    # 关闭 CLS 日志处理器
    print("\n" + "=" * 60)
    print("关闭 CLS 日志处理器...")
    print("=" * 60)
    close_cls_logger()
    print("✅ CLS 日志处理器已关闭")

    # 打印测试结果
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)

    passed = 0
    failed = 0

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print("=" * 60)
    print(f"总计: {passed} 个通过, {failed} 个失败")
    print("=" * 60)

    # 提示用户检查腾讯云控制台
    print("\n📋 下一步:")
    print("1. 登录腾讯云控制台")
    print("2. 进入日志服务 (CLS)")
    print("3. 查看日志主题中的日志")
    print("4. 验证测试日志是否已上传")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

