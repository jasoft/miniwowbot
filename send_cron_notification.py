#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
发送 cron 任务完成通知的脚本
从 shell 脚本调用，发送 Bark 通知
"""

import sys
import json
import logging
import requests
import urllib.parse
from system_config_loader import load_system_config

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def send_bark_notification(title: str, message: str, level: str = "active") -> bool:
    """
    发送 Bark 通知

    Args:
        title: 通知标题
        message: 通知内容
        level: 通知级别 (active/timeSensitive/passive)

    Returns:
        是否发送成功
    """
    system_config = load_system_config()

    if not system_config.is_bark_enabled():
        logger.info("🔕 Bark 通知未启用，跳过发送")
        return False

    bark_config = system_config.get_bark_config()
    server = bark_config.get("server")

    if not server:
        logger.warning("⚠️ Bark 服务器地址未配置")
        return False

    try:
        # 构造 Bark URL
        encoded_title = urllib.parse.quote(title)
        encoded_message = urllib.parse.quote(message)

        if "?" in server or server.endswith("/"):
            url = f"{server.rstrip('/')}/{encoded_title}/{encoded_message}"
        else:
            url = f"{server}/{encoded_title}/{encoded_message}"

        # 添加可选参数
        params = {}
        if bark_config.get("group"):
            params["group"] = bark_config["group"]
        if level:
            params["level"] = level

        # 发送请求
        logger.info(f"📱 发送 Bark 通知: {title}")
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            logger.info("✅ Bark 通知发送成功")
            return True
        else:
            logger.warning(f"⚠️ Bark 通知发送失败，状态码: {response.status_code}")
            return False

    except requests.exceptions.Timeout:
        logger.warning("⚠️ Bark 通知发送超时")
        return False
    except Exception as e:
        logger.error(f"❌ 发送 Bark 通知失败: {e}")
        return False


def main():
    """
    主函数
    使用方式: python send_cron_notification.py <success_count> <failed_count> <total_count>
    """
    if len(sys.argv) < 4:
        logger.error("❌ 参数不足")
        logger.info("使用方式: python send_cron_notification.py <success_count> <failed_count> <total_count>")
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
        message = f"副本运行完成\n总计: {total_count} 个账号\n✅ 全部成功: {success_count} 个"
        level = "active"

    # 发送通知
    success = send_bark_notification(title, message, level)

    # 返回状态码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

