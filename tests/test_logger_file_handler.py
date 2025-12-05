#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试日志文件处理器功能

确保日志在配置初始化后尽早写入文件，而不是等到模拟器连接后。
"""

import sys
import os
import tempfile
import shutil
import logging
import pytest

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger_config import (
    setup_logger_from_config,
    attach_emulator_file_handler,
    GlobalLogContext,
    LoggerConfig,
)


@pytest.fixture
def temp_log_dir():
    """创建临时日志目录用于测试"""
    temp_dir = tempfile.mkdtemp(prefix="test_log_")
    yield temp_dir
    # 清理
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture(autouse=True)
def reset_logger_state():
    """每个测试前重置 logger 状态"""
    # 清除已配置的 logger 集合
    LoggerConfig._configured_loggers.clear()
    # 清除全局上下文
    GlobalLogContext.context.clear()
    # 移除 miniwow logger 的所有 handlers
    miniwow_logger = logging.getLogger("miniwow")
    for handler in miniwow_logger.handlers[:]:
        miniwow_logger.removeHandler(handler)
    # 移除 root logger 的 FileHandler
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            root_logger.removeHandler(handler)
    yield


class TestLoggerFileHandler:
    """测试日志文件处理器功能"""

    def test_attach_file_handler_creates_log_file(self, temp_log_dir):
        """测试 attach_emulator_file_handler 创建日志文件"""
        # 先初始化 console logger
        setup_logger_from_config(use_color=True)
        
        # 附加文件处理器
        log_path = attach_emulator_file_handler(
            emulator_name="test_emulator",
            config_name="test_config",
            log_dir=temp_log_dir,
            level="INFO",
        )
        
        # 验证日志文件路径
        assert log_path == os.path.join(temp_log_dir, "autodungeon_test_emulator.log")
        
        # 写入测试日志
        logging.getLogger("miniwow").info("测试日志消息")
        
        # 刷新并检查文件内容
        for handler in logging.getLogger("miniwow").handlers:
            if isinstance(handler, logging.FileHandler):
                handler.flush()
        
        # 验证日志文件存在且有内容
        assert os.path.exists(log_path)
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "测试日志消息" in content
            assert "test_config" in content
            assert "test_emulator" in content

    def test_file_handler_with_colon_in_emulator_name(self, temp_log_dir):
        """测试 emulator 名称包含冒号时的文件名处理"""
        setup_logger_from_config(use_color=True)
        
        log_path = attach_emulator_file_handler(
            emulator_name="192.168.1.150:5555",
            config_name="mage",
            log_dir=temp_log_dir,
            level="INFO",
        )
        
        # 验证冒号被替换为下划线
        expected_path = os.path.join(temp_log_dir, "autodungeon_192.168.1.150_5555.log")
        assert log_path == expected_path
        
        logging.getLogger("miniwow").info("带冒号的 emulator 测试")
        
        for handler in logging.getLogger("miniwow").handlers:
            if isinstance(handler, logging.FileHandler):
                handler.flush()
        
        assert os.path.exists(expected_path)

    def test_file_handler_no_duplicate_on_same_path(self, temp_log_dir):
        """测试相同路径不会重复添加文件处理器"""
        setup_logger_from_config(use_color=True)
        
        # 第一次附加
        attach_emulator_file_handler(
            emulator_name="test_emulator",
            config_name="config1",
            log_dir=temp_log_dir,
        )
        
        handlers_before = len([
            h for h in logging.getLogger("miniwow").handlers
            if isinstance(h, logging.FileHandler)
        ])
        
        # 第二次附加相同 emulator
        attach_emulator_file_handler(
            emulator_name="test_emulator",
            config_name="config2",
            log_dir=temp_log_dir,
        )
        
        handlers_after = len([
            h for h in logging.getLogger("miniwow").handlers
            if isinstance(h, logging.FileHandler)
        ])
        
        # 应该只有一个文件处理器
        assert handlers_before == handlers_after

    def test_global_context_updated(self, temp_log_dir):
        """测试全局上下文被正确更新"""
        setup_logger_from_config(use_color=True)
        
        attach_emulator_file_handler(
            emulator_name="my_emulator",
            config_name="my_config",
            log_dir=temp_log_dir,
        )
        
        assert GlobalLogContext.context.get("emulator") == "my_emulator"
        assert GlobalLogContext.context.get("config") == "my_config"
