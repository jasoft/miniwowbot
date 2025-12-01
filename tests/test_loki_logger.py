# -*- coding: utf-8 -*-
"""
测试 Loki 日志模块
"""

import json
import logging
import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loki_logger import LokiHandler, create_loki_logger


class TestLokiHandler:
    """测试 LokiHandler 类"""

    def test_handler_creation(self):
        """测试 LokiHandler 创建"""
        handler = LokiHandler(
            loki_url="http://localhost:3100",
            app_name="test_app",
        )
        assert handler is not None
        assert handler.loki_url == "http://localhost:3100"
        assert handler.app_name == "test_app"
        handler.close()

    def test_handler_labels(self):
        """测试 LokiHandler 标签"""
        handler = LokiHandler(
            loki_url="http://localhost:3100",
            app_name="test_app",
            labels={"env": "test", "version": "1.0"},
        )
        assert handler.labels["app"] == "test_app"
        assert handler.labels["env"] == "test"
        assert handler.labels["version"] == "1.0"
        handler.close()

    def test_handler_url_trailing_slash_removed(self):
        """测试 LokiHandler URL 尾部斜杠被移除"""
        handler = LokiHandler(
            loki_url="http://localhost:3100/",
            app_name="test_app",
        )
        assert handler.loki_url == "http://localhost:3100"
        handler.close()

    def test_handler_buffer_size(self):
        """测试 LokiHandler 缓冲区大小"""
        handler = LokiHandler(
            loki_url="http://localhost:3100",
            app_name="test_app",
            buffer_size=100,
        )
        assert handler.buffer_size == 100
        handler.close()

    def test_handler_upload_interval(self):
        """测试 LokiHandler 上传间隔"""
        handler = LokiHandler(
            loki_url="http://localhost:3100",
            app_name="test_app",
            upload_interval=10,
        )
        assert handler.upload_interval == 10
        handler.close()

    def test_handler_session_proxy_disabled(self):
        """测试 LokiHandler Session 禁用代理"""
        handler = LokiHandler(
            loki_url="http://localhost:3100",
            app_name="test_app",
        )
        # 验证 Session 的 trust_env 被设置为 False
        assert handler._session.trust_env is False
        handler.close()

    def test_handler_emit_log_record(self):
        """测试 LokiHandler 处理日志记录"""
        handler = LokiHandler(
            loki_url="http://localhost:3100",
            app_name="test_app",
        )
        
        # 创建一个日志记录
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        # 发送日志记录
        handler.emit(record)
        
        # 验证日志已入队
        assert not handler.queue.empty()
        
        handler.close()


class TestCreateLokiLogger:
    """测试 create_loki_logger 函数"""

    def test_create_logger_basic(self):
        """测试创建基本日志记录器"""
        logger = create_loki_logger(
            name="test_logger",
            level="INFO",
            enable_loki=False,
        )
        assert logger is not None
        assert logger.name == "test_logger"
        assert logger.level == logging.INFO

    def test_create_logger_with_loki_disabled(self):
        """测试创建禁用 Loki 的日志记录器"""
        logger = create_loki_logger(
            name="test_logger_no_loki",
            level="DEBUG",
            enable_loki=False,
        )
        
        # 应该只有一个 StreamHandler
        loki_handlers = [h for h in logger.handlers if isinstance(h, LokiHandler)]
        assert len(loki_handlers) == 0

    def test_create_logger_with_loki_enabled(self):
        """测试创建启用 Loki 的日志记录器"""
        logger = create_loki_logger(
            name="test_logger_with_loki",
            level="INFO",
            loki_url="http://localhost:3100",
            enable_loki=True,
        )
        
        # 应该有一个 LokiHandler
        loki_handlers = [h for h in logger.handlers if isinstance(h, LokiHandler)]
        assert len(loki_handlers) == 1
        
        # 清理
        for handler in logger.handlers:
            handler.close()

    def test_create_logger_level(self):
        """测试日志级别设置"""
        for level_name in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            logger = create_loki_logger(
                name=f"test_logger_{level_name.lower()}",
                level=level_name,
                enable_loki=False,
            )
            expected_level = getattr(logging, level_name)
            assert logger.level == expected_level


class TestLokiHandlerUpload:
    """测试 LokiHandler 上传功能"""

    def test_do_upload_builds_correct_payload(self):
        """测试 _do_upload 构建正确的 payload"""
        handler = LokiHandler(
            loki_url="http://localhost:3100",
            app_name="test_app",
        )
        
        # Mock session.post
        mock_response = MagicMock()
        mock_response.status_code = 204
        handler._session.post = MagicMock(return_value=mock_response)
        
        # 准备日志数据
        logs = [
            {
                "timestamp": 1733050000000000000,
                "level": "INFO",
                "logger": "test",
                "message": "Test message",
                "module": "test_module",
                "function": "test_func",
                "line": 10,
            }
        ]
        
        # 执行上传
        handler._do_upload(logs)
        
        # 验证调用
        handler._session.post.assert_called_once()
        call_args = handler._session.post.call_args
        
        # 验证 URL
        assert call_args[0][0] == "http://localhost:3100/loki/api/v1/push"
        
        # 验证 payload 结构
        payload = call_args[1]["json"]
        assert "streams" in payload
        assert len(payload["streams"]) == 1
        
        stream = payload["streams"][0]
        assert "stream" in stream
        assert "values" in stream
        assert stream["stream"]["app"] == "test_app"
        
        handler.close()

    def test_do_upload_handles_empty_logs(self):
        """测试 _do_upload 处理空日志列表"""
        handler = LokiHandler(
            loki_url="http://localhost:3100",
            app_name="test_app",
        )
        
        # Mock session.post
        handler._session.post = MagicMock()
        
        # 执行上传（空列表）
        handler._do_upload([])
        
        # 验证没有调用 post
        handler._session.post.assert_not_called()
        
        handler.close()


class TestLokiHandlerProxyBypass:
    """测试 LokiHandler 代理绕过功能"""

    def test_session_does_not_use_env_proxy(self):
        """测试 Session 不使用环境变量中的代理"""
        # 设置环境变量代理
        original_http_proxy = os.environ.get("http_proxy")
        original_https_proxy = os.environ.get("https_proxy")
        
        try:
            os.environ["http_proxy"] = "http://127.0.0.1:8888"
            os.environ["https_proxy"] = "http://127.0.0.1:8888"
            
            handler = LokiHandler(
                loki_url="http://localhost:3100",
                app_name="test_app",
            )
            
            # 验证 trust_env 被禁用
            assert handler._session.trust_env is False
            
            handler.close()
        finally:
            # 恢复环境变量
            if original_http_proxy is not None:
                os.environ["http_proxy"] = original_http_proxy
            elif "http_proxy" in os.environ:
                del os.environ["http_proxy"]
                
            if original_https_proxy is not None:
                os.environ["https_proxy"] = original_https_proxy
            elif "https_proxy" in os.environ:
                del os.environ["https_proxy"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

