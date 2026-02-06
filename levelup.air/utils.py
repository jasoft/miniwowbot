"""Utility functions for levelup.air."""

from __future__ import annotations

import logging
from typing import Any, Callable

from airtest.core.api import sleep, touch

logger = logging.getLogger(__name__)


def verified_touch(
    pos: Any,
    verify_func: Callable[[], bool],
    retry_interval: float = 1.0,
    max_retries: int = 3,
    wait_time_after_click: float = 0.5,
) -> bool:
    """
    点击指定位置，并通过 verify_func 验证是否成功。
    如果验证失败，会重试点击。

    Args:
        pos: 点击位置 (x, y) 或 Template
        verify_func: 验证函数，返回 True 表示点击生效（例如界面已跳转）
        retry_interval: 重试间隔（验证失败后等待多久再次点击）
        max_retries: 最大重试次数
        wait_time_after_click: 点击后等待 verify_func 执行的时间

    Returns:
        bool: 最终是否成功
    """
    for i in range(max_retries):
        try:
            logger.info("👆 尝试点击: %s (第 %d/%d 次)", pos, i + 1, max_retries)
            touch(pos)

            # 点击后等待界面响应
            sleep(wait_time_after_click)

            # 验证结果
            if verify_func():
                logger.info("✅ 点击验证成功")
                return True

            logger.warning("⚠️ 点击验证失败，等待 %.1fs 后重试...", retry_interval)
            sleep(retry_interval)

        except Exception as e:
            logger.error("❌ 点击操作异常: %s", e)
            sleep(retry_interval)

    logger.error("❌ 点击失败，已达到最大重试次数: %d", max_retries)
    return False
