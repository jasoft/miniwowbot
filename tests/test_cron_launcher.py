#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""测试 cron_launcher 中的统计解析与通知构建逻辑"""

import pytest

import cron_launcher


class TestParseRunStatistics:
    """测试从日志中解析统计信息"""

    def test_parse_statistics_with_color_codes(self):
        """日志包含 ANSI 颜色时也应正确解析"""

        sample_output = (
            "\x1b[0;34m[INFO]\x1b[0m 总共运行: 5 个角色\n"
            "\x1b[0;32m[SUCCESS]\x1b[0m 成功: 5 个\n"
        )
        stats = cron_launcher.parse_run_statistics(sample_output)
        assert stats["total"] == 5
        assert stats["success"] == 5
        # 未出现失败行时应该推导为 0
        assert stats["failed"] == 0


class TestNotificationContent:
    """测试 Bark 通知内容构建"""

    def test_build_notification_content_success(self):
        """成功运行时的通知应包含统计信息"""

        stats = {"total": 5, "success": 5, "failed": 0}
        title, message, level = cron_launcher.build_notification_content(
            config_name="default",
            emulator_addr="127.0.0.1:5555",
            stats=stats,
            success=True,
            duration=None,
        )

        assert "运行成功" in title
        assert "总计: 5 个角色" in message
        assert "✅ 成功: 5 个" in message
        assert level == "active"

    def test_build_notification_content_failure_without_stats(self):
        """无法解析统计时也要给出提示"""

        stats = {"total": None, "success": None, "failed": None}
        title, message, level = cron_launcher.build_notification_content(
            config_name="mage_alt",
            emulator_addr="127.0.0.1:5565",
            stats=stats,
            success=False,
            duration=None,
        )

        assert "运行失败" in title
        assert "统计数据: 无法解析" in message
        assert level == "timeSensitive"
