#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""测试 cron_launcher 中的命令构建逻辑"""

import cron_launcher


class TestBuildRunCommand:
    """测试运行命令构建"""

    def test_build_run_command_default_config(self):
        """默认配置的命令构建"""
        cmd = cron_launcher.build_run_command("default", "127.0.0.1:5555")
        assert cmd == "./run_all_dungeons.sh --emulator 127.0.0.1:5555"

    def test_build_run_command_custom_config(self):
        """自定义配置的命令构建"""
        cmd = cron_launcher.build_run_command("mage_alt", "127.0.0.1:5565")
        assert "mage_alt" in cmd
        assert "127.0.0.1:5565" in cmd
        assert "./run_all_dungeons.sh" in cmd

    def test_build_run_command_with_special_chars(self):
        """包含特殊字符的配置名称"""
        cmd = cron_launcher.build_run_command("test-config", "127.0.0.1:5555")
        assert "test-config" in cmd


class TestEscapeForOsascript:
    """测试 osascript 转义"""

    def test_escape_double_quotes(self):
        """双引号转义"""
        result = cron_launcher.escape_for_osascript('echo "hello"')
        assert '\\"' in result

    def test_escape_backslash(self):
        """反斜杠转义"""
        result = cron_launcher.escape_for_osascript("path\\to\\file")
        assert "\\\\" in result

    def test_escape_combined(self):
        """组合转义"""
        result = cron_launcher.escape_for_osascript('echo "test\\path"')
        assert '\\"' in result
        assert "\\\\" in result
