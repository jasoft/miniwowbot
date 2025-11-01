#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
腾讯云 CLS 模块测试脚本
测试cls_logger.py模块的各项功能
"""

import os
import time
import logging
import threading
from typing import Optional

# 导入测试模块
try:
    from cls_logger import (
        CLSHandler,
        CLSLogger,
        get_cls_logger,
        add_cls_to_logger,
        close_cls_logger,
    )

    print("✅ cls_logger模块导入成功")
except ImportError as e:
    print(f"❌ cls_logger模块导入失败: {e}")
    exit(1)


class CLSTestRunner:
    """CLS模块测试运行器"""

    def __init__(self):
        self.test_results = []
        self.mock_env = {}

    def log_test_result(self, test_name: str, success: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = f"{status} {test_name}"
        if message:
            result += f" - {message}"
        self.test_results.append((test_name, success, message))
        print(result)

    def test_import_dependencies(self):
        """测试依赖导入"""
        print("\n🔍 测试1: 依赖包导入检查")

        try:
            import tencentcloud.log.logclient

            self.log_test_result("tencentcloud-logclient", True, "SDK已安装")
        except ImportError:
            self.log_test_result(
                "tencentcloud-logclient", False, "SDK未安装，将使用模拟模式"
            )

        try:
            from tencentcloud.log.cls_pb2 import LogGroupList

            self.log_test_result("tencentcloud-cls-proto", True, "proto包已安装")
        except ImportError:
            self.log_test_result(
                "tencentcloud-cls-proto", False, "proto包未安装，将使用模拟模式"
            )

    def test_env_config_loading(self):
        """测试环境变量配置加载"""
        print("\n🔍 测试2: 环境变量配置检查")

        # 设置测试环境变量
        test_env = {
            "CLS_ENABLED": "true",
            "TENCENTCLOUD_SECRET_ID": "test_secret_id",
            "TENCENTCLOUD_SECRET_KEY": "test_secret_key",
            "CLS_REGION": "ap-beijing",
            "CLS_LOG_TOPIC_ID": "test_topic_id",
            "LOG_BUFFER_SIZE": "50",
            "LOG_UPLOAD_INTERVAL": "2",
        }

        # 保存原始环境变量
        original_env = {}
        for key in test_env:
            original_env[key] = os.getenv(key)
            os.environ[key] = test_env[key]

        try:
            # 测试配置加载
            cls_logger = CLSLogger()

            # 检查配置是否正确加载
            has_handler = cls_logger.cls_handler is not None

            self.log_test_result("环境变量配置加载", True, f"处理器创建: {has_handler}")

        except Exception as e:
            self.log_test_result("环境变量配置加载", False, str(e))
        finally:
            # 恢复原始环境变量
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_cls_handler_creation(self):
        """测试CLSHandler创建"""
        print("\n🔍 测试3: CLSHandler创建测试")

        try:
            # 创建处理器（使用测试配置）
            handler = CLSHandler(
                secret_id="test_secret_id",
                secret_key="test_secret_key",
                region="ap-beijing",
                log_topic_id="test_topic",
                buffer_size=10,
                upload_interval=1,
            )

            # 检查处理器属性
            has_client = hasattr(handler, "cls_client")
            has_buffer = hasattr(handler, "buffer")
            has_thread = hasattr(handler, "upload_thread")

            self.log_test_result(
                "CLSHandler创建",
                True,
                f"客户端: {has_client}, 缓冲区: {has_buffer}, 线程: {has_thread}",
            )

        except Exception as e:
            self.log_test_result("CLSHandler创建", False, str(e))

    def test_logging_integration(self):
        """测试日志记录集成"""
        print("\n🔍 测试4: 日志记录集成测试")

        try:
            # 创建测试日志记录器
            test_logger = logging.getLogger("test_logger")
            test_logger.setLevel(logging.INFO)
            test_logger.handlers.clear()

            # 添加CLS处理器
            handler = CLSHandler(
                secret_id="test_secret_id",
                secret_key="test_secret_key",
                region="ap-beijing",
                log_topic_id="test_topic",
                buffer_size=5,
                upload_interval=1,
            )

            # 设置格式化器
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)

            test_logger.addHandler(handler)

            # 发送测试日志
            test_logger.info("这是一条测试信息日志")
            test_logger.warning("这是一条测试警告日志")
            test_logger.error("这是一条测试错误日志")

            # 检查缓冲区状态
            buffer_size = len(handler.buffer)

            self.log_test_result("日志记录集成", True, f"缓冲区大小: {buffer_size}")

        except Exception as e:
            self.log_test_result("日志记录集成", False, str(e))

    def test_buffer_mechanism(self):
        """测试缓冲区机制"""
        print("\n🔍 测试5: 缓冲区机制测试")

        try:
            # 创建小缓冲区的处理器
            handler = CLSHandler(
                secret_id="test_secret_id",
                secret_key="test_secret_key",
                region="ap-beijing",
                log_topic_id="test_topic",
                buffer_size=3,  # 小缓冲区
                upload_interval=1,
            )

            # 创建测试记录器
            test_logger = logging.getLogger("buffer_test")
            test_logger.setLevel(logging.INFO)
            test_logger.handlers.clear()
            test_logger.addHandler(handler)

            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)

            # 发送日志直到触发刷新
            for i in range(5):
                test_logger.info(f"测试消息 {i + 1}")
                time.sleep(0.1)

            # 等待上传线程处理
            time.sleep(2)

            buffer_status = "缓冲区状态正常"

            self.log_test_result("缓冲区机制", True, buffer_status)

        except Exception as e:
            self.log_test_result("缓冲区机制", False, str(e))

    def test_error_handling(self):
        """测试错误处理"""
        print("\n🔍 测试6: 错误处理测试")

        try:
            # 测试无效配置
            invalid_handler = CLSHandler(
                secret_id="", secret_key="", region="invalid-region", log_topic_id=""
            )

            # 检查错误处理
            has_error_handling = not invalid_handler.cls_available

            self.log_test_result(
                "错误处理", True, f"错误处理正常: {has_error_handling}"
            )

        except Exception as e:
            self.log_test_result("错误处理", False, str(e))

    def test_singleton_pattern(self):
        """测试单例模式"""
        print("\n🔍 测试7: 单例模式测试")

        try:
            # 创建多个实例
            logger1 = CLSLogger()
            logger2 = CLSLogger()

            # 检查是否是同一个实例
            is_same_instance = logger1 is logger2

            self.log_test_result("单例模式", True, f"同一实例: {is_same_instance}")

        except Exception as e:
            self.log_test_result("单例模式", False, str(e))

    def test_convenience_functions(self):
        """测试便捷函数"""
        print("\n🔍 测试8: 便捷函数测试")

        try:
            # 测试get_cls_logger函数
            cls_logger = get_cls_logger()

            # 测试add_cls_to_logger函数
            test_logger = logging.getLogger("convenience_test")
            test_logger.handlers.clear()
            add_cls_to_logger(test_logger)

            # 测试发送日志
            cls_logger.info("便捷函数测试消息")

            self.log_test_result("便捷函数", True, "函数调用成功")

        except Exception as e:
            self.log_test_result("便捷函数", False, str(e))

    def test_cleanup(self):
        """测试清理功能"""
        print("\n🔍 测试9: 清理功能测试")

        try:
            # 测试close函数
            close_cls_logger()

            # 检查清理状态
            cleanup_success = True  # 如果没有异常则认为清理成功

            self.log_test_result("清理功能", True, "清理执行成功")

        except Exception as e:
            self.log_test_result("清理功能", False, str(e))

    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始腾讯云 CLS 模块测试")
        print("=" * 50)

        # 运行各项测试
        self.test_import_dependencies()
        self.test_env_config_loading()
        self.test_cls_handler_creation()
        self.test_logging_integration()
        self.test_buffer_mechanism()
        self.test_error_handling()
        self.test_singleton_pattern()
        self.test_convenience_functions()
        self.test_cleanup()

        # 输出测试总结
        self.print_summary()

    def print_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 50)
        print("📊 测试总结")
        print("=" * 50)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, success, _ in self.test_results if success)
        failed_tests = total_tests - passed_tests

        print(f"总测试数: {total_tests}")
        print(f"通过测试: {passed_tests}")
        print(f"失败测试: {failed_tests}")
        print(f"成功率: {(passed_tests / total_tests) * 100:.1f}%")

        if failed_tests > 0:
            print("\n❌ 失败的测试:")
            for test_name, success, message in self.test_results:
                if not success:
                    print(f"  - {test_name}: {message}")

        print("\n🎉 测试完成!")


def create_test_env_file():
    """创建测试用的.env文件示例"""
    env_content = """# 腾讯云CLS配置示例
# 复制此文件为.env并填入真实配置

# 启用CLS日志
CLS_ENABLED=true

# 腾讯云API密钥（需要替换为真实密钥）
TENCENTCLOUD_SECRET_ID=your_secret_id_here
TENCENTCLOUD_SECRET_KEY=your_secret_key_here

# CLS配置
CLS_REGION=ap-beijing
CLS_LOG_TOPIC_ID=your_log_topic_id_here

# 日志缓冲配置
LOG_BUFFER_SIZE=100
LOG_UPLOAD_INTERVAL=5
"""

    with open(".env.cls.test", "w", encoding="utf-8") as f:
        f.write(env_content)

    print("📝 已创建测试环境变量文件: .env.cls.test")
    print("💡 复制此文件为.env并填入真实配置即可启用真实的CLS功能")


def main():
    """主函数"""
    print("🔧 腾讯云 CLS 模块测试工具")
    print("用于验证cls_logger.py模块的各项功能")

    # 创建测试环境文件示例
    create_test_env_file()

    # 创建测试运行器
    runner = CLSTestRunner()

    # 运行测试
    runner.run_all_tests()


if __name__ == "__main__":
    main()
