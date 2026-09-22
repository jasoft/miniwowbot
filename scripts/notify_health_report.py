#!/usr/bin/env python3
# -*- encoding=utf-8 -*-
"""把「每日体检」结果推送到 Bark 的独立通道。

通道地址取 ``BARK_HEALTH_SERVER``（未配置时回落 ``BARK_SERVER``），
与副本运行通知互不干扰 —— 体检报告推到指定设备，副本告警仍走原通道。

正文过长会自动截断：Bark 把正文放在 URL 路径里，中文经编码后一字占 9 个字符，
长正文会让整条推送失败，所以宁可截断并标注。

用法::

    # 通道自检
    python scripts/notify_health_report.py --test

    # 直接给正文
    python scripts/notify_health_report.py --title "体检 ✅ 一切正常" --body "warrior 11/11"

    # 正文从文件读（多行报告），``-`` 表示 stdin
    python scripts/notify_health_report.py --title "体检 ⚠️ 有异常" --body-file log/health.md

退出码：0 发送成功，1 发送失败（便于编排器/自动化脚本判断）。
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from auto_dungeon_notification import send_health_report  # noqa: E402
from logger_config import setup_simple_logger, update_log_context  # noqa: E402

logger = setup_simple_logger()

#: 审计里显示的运行上下文。体检不在某个模拟器会话里跑，但要显式声明，
#: 免得审计记录退化成 ``[unknown | unknown]``（那意味着「没设置上下文」）。
HEALTH_CONTEXT = {"config": "health_check", "emulator": "local"}

#: ``--test`` 用的固定文案
TEST_TITLE = "体检通道自检"
TEST_BODY = (
    "这是一条通道自检推送，不是真实体检结果。\n"
    "看到这条说明：BARK_HEALTH_SERVER 可用、urlencode 正确。"
)


def _read_body(args: argparse.Namespace) -> str:
    """按 CLI 参数取出正文。

    Args:
        args: 解析后的命令行参数。

    Returns:
        正文文本。

    Raises:
        SystemExit: 参数缺失或指定的文件读不到。
    """
    if args.body is not None:
        return args.body
    if args.body_file is not None:
        if args.body_file == "-":
            return sys.stdin.read()
        path = Path(args.body_file)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.is_file():
            logger.error(f"❌ 正文文件不存在: {path}")
            raise SystemExit(2)
        return path.read_text(encoding="utf-8")
    logger.error("❌ 必须提供 --body / --body-file，或使用 --test")
    raise SystemExit(2)


def main() -> int:
    """入口。

    Returns:
        进程退出码：0 成功，1 发送失败，2 参数错误。
    """
    parser = argparse.ArgumentParser(description="发送每日体检报告到 Bark 独立通道")
    parser.add_argument("--title", default="异世界勇者 · 每日体检", help="通知标题")
    parser.add_argument("--body", default=None, help="通知正文")
    parser.add_argument("--body-file", default=None, help="从文件读正文（- 表示 stdin）")
    parser.add_argument(
        "--level",
        default="active",
        choices=["active", "timeSensitive", "passive"],
        help="Bark 通知级别；有异常时用 timeSensitive 更容易被看到",
    )
    parser.add_argument("--test", action="store_true", help="只做通道自检，发送固定测试文案")
    args = parser.parse_args()

    update_log_context(HEALTH_CONTEXT)

    if args.test:
        args.title = TEST_TITLE
        message = TEST_BODY
        args.level = "active"
    else:
        message = _read_body(args)

    ok = send_health_report(args.title, message, level=args.level)
    if ok:
        logger.info("✅ 体检报告已推送")
    else:
        logger.error("❌ 体检报告推送失败（详见 log/notifications/ 审计）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
