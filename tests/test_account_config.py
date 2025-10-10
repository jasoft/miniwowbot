#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试账号配置加载功能
"""

import sys
import os
import pytest
import json

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_auto_dungeon_integration import load_test_accounts  # noqa: E402


class TestAccountConfig:
    """测试账号配置功能"""

    def test_load_test_accounts_function_exists(self):
        """测试 load_test_accounts 函数是否存在"""
        assert callable(load_test_accounts), "load_test_accounts 函数应该存在且可调用"

    def test_load_test_accounts_returns_list(self):
        """测试 load_test_accounts 返回列表"""
        try:
            accounts = load_test_accounts()
            assert isinstance(accounts, list), "load_test_accounts 应该返回列表"
        except pytest.skip.Exception:
            # 如果配置文件不存在，测试会被跳过
            pytest.skip("配置文件不存在，跳过测试")

    def test_load_test_accounts_not_empty(self):
        """测试 load_test_accounts 返回非空列表"""
        try:
            accounts = load_test_accounts()
            assert len(accounts) > 0, "至少应该有一个测试账号"
        except pytest.skip.Exception:
            pytest.skip("配置文件不存在，跳过测试")

    def test_config_file_format(self):
        """测试配置文件格式是否正确"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "test_accounts.json",
        )

        if not os.path.exists(config_path):
            pytest.skip("配置文件不存在，跳过测试")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 验证配置文件结构
            assert "accounts" in config, "配置文件应该包含 'accounts' 字段"
            assert isinstance(
                config["accounts"], list
            ), "'accounts' 字段应该是列表"
            assert len(config["accounts"]) > 0, "'accounts' 列表不应该为空"

            # 验证账号格式
            for account in config["accounts"]:
                assert isinstance(account, str), "账号应该是字符串"
                assert len(account) > 0, "账号不应该为空字符串"

        except json.JSONDecodeError as e:
            pytest.fail(f"配置文件 JSON 格式错误: {e}")

    def test_example_config_file_exists(self):
        """测试示例配置文件是否存在"""
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "test_accounts.json.example",
        )

        assert os.path.exists(example_path), "示例配置文件应该存在"

    def test_example_config_file_format(self):
        """测试示例配置文件格式是否正确"""
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "test_accounts.json.example",
        )

        try:
            with open(example_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 验证示例文件结构
            assert "accounts" in config, "示例文件应该包含 'accounts' 字段"
            assert isinstance(
                config["accounts"], list
            ), "'accounts' 字段应该是列表"

        except json.JSONDecodeError as e:
            pytest.fail(f"示例文件 JSON 格式错误: {e}")

    def test_gitignore_includes_config_file(self):
        """测试 .gitignore 是否包含配置文件"""
        gitignore_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".gitignore",
        )

        assert os.path.exists(gitignore_path), ".gitignore 文件应该存在"

        with open(gitignore_path, "r", encoding="utf-8") as f:
            gitignore_content = f.read()

        assert (
            "test_accounts.json" in gitignore_content
        ), ".gitignore 应该包含 test_accounts.json"


if __name__ == "__main__":
    # 直接运行此文件时执行测试
    pytest.main([__file__, "-v", "-s"])

