#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""测试 run_all_dungeons.sh 是否在结束时发送 Bark 通知"""

from pathlib import Path


def test_run_all_dungeons_calls_send_cron_notification():
    """脚本应在结束时调用 send_cron_notification.py 发送 Bark 通知"""

    content = Path("run_all_dungeons.sh").read_text(encoding="utf-8")

    assert "send_cron_notification.py" in content
    assert "uv run send_cron_notification.py" in content

