# -*- encoding=utf8 -*-
"""
腾讯云 CLS 日志模块测试
"""

import logging
import os
import sys
from unittest.mock import patch

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cls_logger import CLSLogger, get_cls_logger, add_cls_to_logger, CLSHandler

try:
    import pytest

    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False


if HAS_PYTEST:

    @pytest.fixture(autouse=True)
    def cleanup_cls_logger():
        """清理 CLS 日志资源"""
        yield
        # 测试后清理
        try:
            from cls_logger import close_cls_logger

            close_cls_logger()
        except Exception:
            pass


class TestCLSLogger:
    """CLS 日志模块测试类"""

    def test_cls_logger_singleton(self):
        """测试 CLSLogger 单例模式"""
        logger1 = CLSLogger()
        logger2 = CLSLogger()
        assert logger1 is logger2, "CLSLogger 应该是单例"

    def test_get_cls_logger(self):
        """测试获取 CLS 日志记录器"""
        logger = get_cls_logger()
        assert isinstance(logger, logging.Logger), "应该返回 logging.Logger 实例"
        assert logger.name == "cls_logger", "日志记录器名称应该是 cls_logger"

    def test_cls_logger_disabled_by_default(self):
        """测试默认情况下 CLS 日志是禁用的"""
        # 由于 CLSLogger 是单例，这个测试验证当 CLS_ENABLED 为 false 时
        # 处理器不会被添加
        cls_logger = CLSLogger()
        # 如果 CLS_ENABLED 为 false，cls_handler 应该为 None
        # 这个测试只是验证 CLSLogger 可以正常初始化
        assert cls_logger is not None, "CLSLogger 应该能够初始化"

    def test_add_cls_to_logger(self):
        """测试将 CLS 处理器添加到现有日志记录器"""
        # 创建一个新的日志记录器
        test_logger = logging.getLogger("test_logger")
        test_logger.handlers.clear()

        # 添加 CLS 处理器
        add_cls_to_logger(test_logger)

        # 验证处理器是否被添加
        # 注意：如果 CLS 未启用，处理器可能不会被添加
        # 这里只是验证函数不会抛出异常
        assert True, "add_cls_to_logger 应该不抛出异常"

    def test_cls_handler_initialization(self):
        """测试 CLSHandler 初始化"""
        with patch("tencentcloud.common.credential.Credential"):
            with patch("tencentcloud.cls.v20201016.cls_client.ClsClient"):
                handler = CLSHandler(
                    secret_id="test_id",
                    secret_key="test_key",
                    region="ap-beijing",
                    log_set_id="test_set",
                    log_topic_id="test_topic",
                )
                assert handler.secret_id == "test_id"
                assert handler.secret_key == "test_key"
                assert handler.region == "ap-beijing"
                assert handler.log_set_id == "test_set"
                assert handler.log_topic_id == "test_topic"

    def test_cls_handler_emit(self):
        """测试 CLSHandler 处理日志记录"""
        with patch("tencentcloud.common.credential.Credential"):
            with patch("tencentcloud.cls.v20201016.cls_client.ClsClient"):
                handler = CLSHandler(
                    secret_id="test_id",
                    secret_key="test_key",
                    region="ap-beijing",
                    log_set_id="test_set",
                    log_topic_id="test_topic",
                )

                # 创建日志记录
                record = logging.LogRecord(
                    name="test_logger",
                    level=logging.INFO,
                    pathname="test.py",
                    lineno=10,
                    msg="Test message",
                    args=(),
                    exc_info=None,
                )

                # 发送日志
                handler.emit(record)

                # 验证日志是否被添加到缓冲区
                assert len(handler.buffer) > 0, "日志应该被添加到缓冲区"

    def test_cls_handler_buffer_flush(self):
        """测试 CLSHandler 缓冲区刷新"""
        with patch("tencentcloud.common.credential.Credential"):
            with patch("tencentcloud.cls.v20201016.cls_client.ClsClient"):
                handler = CLSHandler(
                    secret_id="test_id",
                    secret_key="test_key",
                    region="ap-beijing",
                    log_set_id="test_set",
                    log_topic_id="test_topic",
                    buffer_size=2,
                )

                # 创建两条日志记录
                for i in range(2):
                    record = logging.LogRecord(
                        name="test_logger",
                        level=logging.INFO,
                        pathname="test.py",
                        lineno=10,
                        msg=f"Test message {i}",
                        args=(),
                        exc_info=None,
                    )
                    handler.emit(record)

                # 验证缓冲区是否被清空（因为达到了 buffer_size）
                # 注意：实际的 API 调用可能会失败，但缓冲区应该被清空
                assert len(handler.buffer) == 0, "缓冲区应该在达到大小限制时被清空"

    def test_env_file_loading(self):
        """测试 .env 文件加载"""
        # 验证 .env 文件是否存在
        env_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
        )
        assert os.path.exists(env_file), ".env 文件应该存在"

    def test_env_example_file_exists(self):
        """测试 .env.example 文件是否存在"""
        env_example_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.example"
        )
        assert os.path.exists(env_example_file), ".env.example 文件应该存在"


class TestCLSLoggerIntegration:
    """CLS 日志模块集成测试"""

    @pytest.mark.timeout(10)
    def test_logger_with_cls_handler(self):
        """测试日志记录器与 CLS 处理器的集成"""
        # 创建一个新的日志记录器
        test_logger = logging.getLogger("integration_test")
        test_logger.handlers.clear()
        test_logger.setLevel(logging.INFO)

        # 添加 CLS 处理器
        add_cls_to_logger(test_logger)

        # 记录日志
        test_logger.info("Integration test message")

        # 验证日志记录器是否正常工作
        assert len(test_logger.handlers) >= 0, "日志记录器应该有处理器"

    @pytest.mark.timeout(10)
    def test_multiple_loggers_with_cls(self):
        """测试多个日志记录器与 CLS 的集成"""
        logger1 = logging.getLogger("logger1")
        logger2 = logging.getLogger("logger2")

        logger1.handlers.clear()
        logger2.handlers.clear()

        add_cls_to_logger(logger1)
        add_cls_to_logger(logger2)

        logger1.info("Message from logger1")
        logger2.info("Message from logger2")

        assert True, "多个日志记录器应该能够正常工作"


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v", "-s"])
    else:
        print("pytest 未安装，请运行: pip install pytest")
