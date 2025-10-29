#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试 cron 通知脚本
"""

import sys
import os

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from send_cron_notification import send_bark_notification

def test_notification():
    """测试通知功能"""
    print("=" * 50)
    print("测试 Bark 通知功能")
    print("=" * 50)
    
    # 测试成功通知
    print("\n1️⃣ 测试成功通知...")
    result = send_bark_notification(
        "异世界勇者 - 副本运行成功",
        "副本运行完成\n总计: 5 个账号\n✅ 全部成功: 5 个",
        "active"
    )
    print(f"结果: {'✅ 成功' if result else '⚠️ 未启用或失败'}")
    
    # 测试失败通知
    print("\n2️⃣ 测试失败通知...")
    result = send_bark_notification(
        "异世界勇者 - 副本运行失败",
        "副本运行完成\n总计: 5 个账号\n✅ 成功: 3 个\n❌ 失败: 2 个",
        "timeSensitive"
    )
    print(f"结果: {'✅ 成功' if result else '⚠️ 未启用或失败'}")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

if __name__ == "__main__":
    test_notification()

