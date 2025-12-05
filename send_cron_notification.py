#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
发送 cron 任务完成通知的脚本。

统一通过 auto_dungeon.send_bark_notification 发送 Bark 通知，避免重复实现。
"""

import sys
from system_config_loader import load_system_config
from logger_config import setup_simple_logger
import auto_dungeon as ad
from auto_dungeon import send_bark_notification as bark_send

# 设置日志
logger = setup_simple_logger()



def main():
    """
    主函数
    使用方式: python send_cron_notification.py <success_count> <failed_count> <total_count>
    """
    if len(sys.argv) < 4:
        logger.error("❌ 参数不足")
        logger.info(
            "使用方式: python send_cron_notification.py <success_count> <failed_count> <total_count>"
        )
        sys.exit(1)

    try:
        success_count = int(sys.argv[1])
        failed_count = int(sys.argv[2])
        total_count = int(sys.argv[3])
    except ValueError:
        logger.error("❌ 参数必须是整数")
        sys.exit(1)

    # 构造通知内容
    if failed_count > 0:
        title = "异世界勇者 - 副本运行失败"
        message = f"副本运行完成\n总计: {total_count} 个账号\n✅ 成功: {success_count} 个\n❌ 失败: {failed_count} 个"
        level = "timeSensitive"  # 失败时使用时间敏感级别
    else:
        title = "异世界勇者 - 副本运行成功"
        message = (
            f"副本运行完成\n总计: {total_count} 个账号\n✅ 全部成功: {success_count} 个"
        )
        level = "active"

    # 发送通知
    # 确保 auto_dungeon 的全局系统配置可用
    try:
        ad.system_config = load_system_config()
    except Exception:
        ad.system_config = None
    success = bark_send(title, message, level)

    # 返回状态码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
