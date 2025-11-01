#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版Logging功能测试
专注于测试重构后的logging配置功能
"""

import sys
import os
import logging

# 添加当前目录到path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_basic_logging():
    """测试基础logging功能"""
    print("🔧 基础Logging功能测试")

    # 测试导入logger_config
    try:
        from logger_config import setup_logger

        print("✅ logger_config 模块导入成功")
    except ImportError as e:
        print(f"❌ logger_config 模块导入失败: {e}")
        return False

    # 测试创建logger
    try:
        logger = setup_logger("test_logger", level="INFO")
        logger.info("这是一条测试信息")
        logger.warning("这是一条警告信息")
        logger.error("这是一条错误信息")
        print("✅ Logger创建和日志记录功能正常")
    except Exception as e:
        print(f"❌ Logger创建失败: {e}")
        return False

    return True


def test_cls_logger_import():
    """测试cls_logger导入"""
    print("\n🔧 CLS Logger导入测试")

    try:
        from cls_logger import get_cls_logger, close_cls_logger

        print("✅ cls_logger 模块导入成功")

        # 测试获取logger（不发送实际请求）
        try:
            _ = get_cls_logger()
            print("✅ CLS Logger获取成功")
        except Exception as e:
            print(f"⚠️ CLS Logger获取出现问题，但模块导入正常: {e}")

        return True
    except ImportError as e:
        print(f"❌ cls_logger 模块导入失败: {e}")
        return False


def test_integration():
    """测试集成功能"""
    print("\n🔧 集成功能测试")

    try:
        from logger_config import setup_logger
        from cls_logger import add_cls_to_logger

        # 创建主logger
        main_logger = setup_logger("integration_test", level="INFO")

        # 添加CLS处理器（如果有的话）
        try:
            add_cls_to_logger(main_logger)
            print("✅ CLS处理器添加成功")
        except Exception as e:
            print(f"⚠️ CLS处理器添加出现问题: {e}")

        # 测试日志记录
        main_logger.info("集成测试 - 信息")
        main_logger.warning("集成测试 - 警告")
        main_logger.error("集成测试 - 错误")
        print("✅ 集成日志记录功能正常")

        return True

    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🚀 开始简化版Logging测试")
    print("=" * 50)

    tests = [
        ("基础Logging功能", test_basic_logging),
        ("CLS Logger导入", test_cls_logger_import),
        ("集成功能", test_integration),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results.append((test_name, False))

    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")
    all_passed = True
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 所有测试通过！Logging重构成功！")
    else:
        print("\n⚠️ 部分测试失败，请检查相关功能")

    return all_passed


if __name__ == "__main__":
    main()
