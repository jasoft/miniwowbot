#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试辅助函数（避免测试之间相互依赖导入）。
"""

from __future__ import annotations

import json
import os
import logging

import pytest


logger = logging.getLogger(__name__)


def load_test_accounts() -> list[str]:
    """
    从配置文件加载测试账号

    Returns:
        list: 账号列表
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "test_accounts.json",
    )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            accounts = config.get("accounts", [])
            logger.info("✅ 成功加载 %s 个测试账号", len(accounts))
            return accounts
    except FileNotFoundError:
        logger.warning("⚠️ 未找到配置文件: %s", config_path)
        logger.info("💡 请复制 test_accounts.json.example 为 test_accounts.json 并填入真实账号")
        pytest.skip("未找到测试账号配置文件")
    except json.JSONDecodeError as exc:
        logger.error("❌ 配置文件格式错误: %s", exc)
        pytest.skip(f"配置文件格式错误: {exc}")
    except Exception as exc:
        logger.error("❌ 加载配置文件失败: %s", exc)
        pytest.skip(f"加载配置文件失败: {exc}")

    return []
