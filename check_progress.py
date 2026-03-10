#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
副本进度检查工具
用于检查当日副本完成情况并决定是否需要继续刷本

返回值:
  0 - 所有副本已完成，无需继续刷本
  1 - 存在未完成副本，需要继续刷本
  2 - 发生错误
"""

import sys
import os
import json
import logging

# 强制 UTF-8 输出，解决 Windows GBK 编码问题
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 先设置全局日志上下文，避免格式化错误
try:
    from vibe_logger import GlobalLogContext
    GlobalLogContext.update({"config": "check_progress", "emulator": "local"})
except Exception:
    pass

from datetime import datetime
import argparse

from config_loader import load_config
from database import DungeonProgressDB
from wow_class_colors import get_class_ansi_color, get_class_hex_color
from auto_dungeon_notification import send_pushover_html_notification


# ANSI 颜色代码
class Colors:
    """终端颜色"""

    RESET = "\033[0m"
    BOLD = "\033[1m"

    # 前景色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # 亮色
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


def colored(text, color="", bold=False):
    """给文本添加颜色"""
    result = ""
    if bold:
        result += Colors.BOLD
    if color:
        result += color
    result += str(text) + Colors.RESET
    return result


def escape_html(text):
    """转义 HTML 特殊字符"""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_html_for_pushover(text, color_mapping=None):
    """将带颜色的终端文本转换为 HTML 格式（Pushover 支持）

    Args:
        text: 原始文本（可能包含 ANSI 转义序列）
        color_mapping: 颜色代码到 HTML 颜色的映射

    Returns:
        HTML 格式的字符串
    """
    if color_mapping is None:
        color_mapping = {
            Colors.RESET: "</span>",
            Colors.BOLD: "<b>",
            Colors.BLUE: "#3498db",
            Colors.GREEN: "#2ecc71",
            Colors.YELLOW: "#f1c40f",
            Colors.RED: "#e74c3c",
            Colors.CYAN: "#1abc9c",
            Colors.MAGENTA: "#9b59b6",
            Colors.WHITE: "#ecf0f1",
            Colors.BRIGHT_BLACK: "#7f8c8d",
            Colors.BRIGHT_GREEN: "#27ae60",
            Colors.BRIGHT_YELLOW: "#f39c12",
            Colors.BRIGHT_CYAN: "#16a085",
            Colors.BRIGHT_WHITE: "#bdc3c7",
        }

    # 移除 ANSI 转义序列，保留纯文本用于初步处理
    import re

    # 先将 ANSI 序列转换为占位符
    ansi_pattern = re.compile(r"\033\[[0-9;]*m")
    text_without_ansi = ansi_pattern.sub("", text)

    # 将纯文本转换为 HTML，保留换行
    html = escape_html(text_without_ansi).replace("\n", "<br>")

    return html


class ProgressChecker:
    """进度检查器"""

    def __init__(self, db_path="database/dungeon_progress.db", config_name="default"):
        """
        初始化进度检查器

        Args:
            db_path: 数据库文件路径
            config_name: 配置名称
        """
        self.db_path = db_path
        self.config_name = config_name
        self.db = DungeonProgressDB(db_path, config_name)
        self.config_classes = self._load_config_classes()
        self.all_configs = self._get_all_config_names()
        # 为每个配置创建独立的 DB 实例
        self._db_instances = {}

    def _load_config_classes(self):
        """加载所有配置文件的职业信息"""
        config_classes = {}
        configs_dir = "configs"

        if not os.path.exists(configs_dir):
            return config_classes

        for filename in os.listdir(configs_dir):
            if not filename.endswith(".json"):
                continue

            config_name = filename[:-5]  # 去掉 .json 后缀
            config_path = os.path.join(configs_dir, filename)

            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    class_name = config.get("class", "未知")
                    config_classes[config_name] = class_name
            except Exception:
                pass

        return config_classes

    def _get_all_config_names(self):
        """获取所有配置的名称列表"""
        config_names = set()

        # 从配置文件目录获取
        configs_dir = "configs"
        if os.path.exists(configs_dir):
            for filename in os.listdir(configs_dir):
                if filename.endswith(".json"):
                    config_names.add(filename[:-5])

        # 从数据库获取（包含可能有记录但配置文件已删除的配置）
        db_configs = self.db.get_all_configs()
        config_names.update(db_configs)

        return sorted(list(config_names))

    def _get_db(self, config_name) -> DungeonProgressDB:
        """获取指定配置的数据库实例"""
        if config_name not in self._db_instances:
            self._db_instances[config_name] = DungeonProgressDB(
                self.db_path, config_name=config_name
            )
        return self._db_instances[config_name]

    def close(self):
        """关闭所有数据库连接"""
        self.db.close()
        for db in self._db_instances.values():
            db.close()

    def _load_config_dungeons(self, config_name):
        """加载指定配置的已选中副本列表。

        Args:
            config_name: 配置名称。

        Returns:
            tuple: 原始区域副本映射与扁平化后的已选中副本列表。
        """
        config_path = f"configs/{config_name}.json"
        if not os.path.exists(config_path):
            return {}, []

        try:
            config_loader = load_config(config_path)
            zone_dungeons = config_loader.get_zone_dungeons()
            all_dungeons = []

            for zone, dungeons in zone_dungeons.items():
                for d in dungeons:
                    if isinstance(d, dict) and d.get("selected", True):
                        all_dungeons.append((zone, d["name"]))
                    elif isinstance(d, str):
                        all_dungeons.append((zone, d))

            return zone_dungeons, all_dungeons
        except Exception:
            return {}, []

    def show_today_progress(self):
        """显示今天的通关记录"""
        today = self.db.get_today_date()
        results = self.db.get_today_completed_dungeons()

        print(f"\n{colored('=' * 60, Colors.CYAN)}")
        print(colored(f"📊 今天的通关记录 ({today})", Colors.CYAN, bold=True))
        print(f"{colored('=' * 60, Colors.CYAN)}\n")

        if not results:
            print(colored("❌ 今天还没有通关任何副本\n", Colors.YELLOW))
            return

        print(colored(f"✅ 共通关 {len(results)} 个副本:\n", Colors.GREEN, bold=True))
        for idx, (zone, dungeon) in enumerate(results, 1):
            zone_colored = colored(zone, Colors.BLUE)
            dungeon_colored = colored(dungeon, Colors.WHITE)
            print(f"{idx:3d}. {zone_colored:12s} - {dungeon_colored}")

        print()

    def show_recent_days(self, days=7, all_configs=False):
        """显示最近几天的统计"""
        print(f"\n{colored('=' * 80, Colors.CYAN)}")
        if all_configs:
            print(
                colored(
                    f"📊 最近 {days} 天的通关统计（所有职业）", Colors.CYAN, bold=True
                )
            )
        else:
            print(
                colored(
                    f"📊 最近 {days} 天的通关统计（{self.db.config_name}）",
                    Colors.CYAN,
                    bold=True,
                )
            )
        print(f"{colored('=' * 80, Colors.CYAN)}\n")

        if all_configs:
            from datetime import date, timedelta

            stats = []
            for i in range(days):
                target_date = (date.today() - timedelta(days=i)).isoformat()
                # 查询所有配置的总数
                from database.dungeon_db import DungeonProgress

                count = (
                    DungeonProgress.select()
                    .where(
                        (DungeonProgress.date == target_date)
                        & (DungeonProgress.completed == 1)
                    )
                    .count()
                )
                stats.append((target_date, count))
        else:
            stats = self.db.get_recent_stats(days)

        for target_date, count in stats:
            date_obj = datetime.fromisoformat(target_date)
            weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][
                date_obj.weekday()
            ]

            # 根据数量选择颜色
            if count == 0:
                color = Colors.BRIGHT_BLACK
            elif count < 20:
                color = Colors.YELLOW
            elif count < 50:
                color = Colors.GREEN
            else:
                color = Colors.BRIGHT_GREEN

            bar = colored("█" * min(count // 2, 40), color) if count > 0 else ""
            date_colored = colored(target_date, Colors.BLUE)
            weekday_colored = colored(weekday, Colors.MAGENTA)
            count_colored = colored(f"{count:3d}", color, bold=True)
            print(f"{date_colored} ({weekday_colored}): {count_colored} 个 {bar}")

        print()

    def show_zone_stats(self):
        """显示各区域的统计"""
        print(f"\n{colored('=' * 60, Colors.CYAN)}")
        print(colored("📊 今天各区域通关统计", Colors.CYAN, bold=True))
        print(f"{colored('=' * 60, Colors.CYAN)}\n")

        results = self.db.get_zone_stats()

        if not results:
            print(colored("❌ 今天还没有通关任何副本\n", Colors.YELLOW))
            return

        for zone, count in results:
            # 根据数量选择颜色
            if count < 5:
                color = Colors.YELLOW
            elif count < 10:
                color = Colors.GREEN
            else:
                color = Colors.BRIGHT_GREEN

            bar = colored("█" * min(count, 30), color)
            zone_colored = colored(zone, Colors.BLUE)
            count_colored = colored(f"{count:3d}", color, bold=True)
            print(f"{zone_colored:12s}: {count_colored} 个 {bar}")

        print()

    def show_all_configs_progress(self, include_special=False):
        """显示所有职业的进度情况"""
        today = self.db.get_today_date()

        print(f"\n{colored('=' * 80, Colors.CYAN)}")
        print(colored(f"📊 所有职业今天的通关进度 ({today})", Colors.CYAN, bold=True))
        print(f"{colored('=' * 80, Colors.CYAN)}\n")

        # 获取所有配置的统计信息
        all_stats = self.db.get_all_configs_stats(include_special=include_special)

        if not all_stats:
            print(colored("❌ 今天还没有任何通关记录\n", Colors.YELLOW))
            return

        # 显示每个配置的统计
        total_dungeons = 0
        for stat in all_stats:
            config_name = stat["config_name"]
            total_count = stat["total_count"]
            zone_stats = stat["zone_stats"]

            if total_count == 0:
                continue

            total_dungeons += total_count

            # 获取职业名称和颜色
            class_name = self.config_classes.get(config_name, "未知")
            class_color = get_class_ansi_color(class_name)

            config_colored = colored(config_name, class_color, bold=True)
            class_colored = colored(class_name, class_color)
            total_colored = colored(f"{total_count}", Colors.BRIGHT_GREEN, bold=True)

            print(f"⚔️  {config_colored} ({class_colored})")
            print(f"   总计: {total_colored} 个副本")

            if zone_stats:
                print(colored("   区域分布:", Colors.BRIGHT_BLACK))
                for zone_name, count in zone_stats:
                    # 根据数量选择颜色
                    if count < 5:
                        bar_color = Colors.YELLOW
                    elif count < 10:
                        bar_color = Colors.GREEN
                    else:
                        bar_color = Colors.BRIGHT_GREEN

                    bar = colored("█" * min(count, 30), bar_color)
                    zone_colored = colored(zone_name, Colors.BLUE)
                    count_colored = colored(f"{count:3d}", bar_color, bold=True)
                    print(f"      {zone_colored:12s}: {count_colored} 个 {bar}")

            print()

        # 显示总计
        print(f"{colored('=' * 80, Colors.BRIGHT_CYAN)}")
        total_colored = colored(f"{total_dungeons}", Colors.BRIGHT_GREEN, bold=True)
        print(
            colored("📈 总计: ", Colors.BRIGHT_CYAN, bold=True)
            + total_colored
            + colored(" 个副本", Colors.BRIGHT_CYAN, bold=True)
        )
        print(f"{colored('=' * 80, Colors.BRIGHT_CYAN)}\n")

    def show_summary(self, include_special=False):
        """显示总体统计摘要"""
        today = self.db.get_today_date()

        print(f"\n{colored('=' * 80, Colors.CYAN)}")
        print(colored(f"📊 总体统计摘要 ({today})", Colors.CYAN, bold=True))
        print(f"{colored('=' * 80, Colors.CYAN)}\n")

        # 获取所有配置的统计信息
        all_stats = self.db.get_all_configs_stats(include_special=include_special)

        if not all_stats:
            print(colored("❌ 今天还没有任何通关记录\n", Colors.YELLOW))
            return

        # 统计数据
        total_dungeons = 0
        config_counts = []

        for stat in all_stats:
            config_name = stat["config_name"]
            total_count = stat["total_count"]

            if total_count > 0:
                class_name = self.config_classes.get(config_name, "未知")
                config_counts.append((config_name, class_name, total_count))
                total_dungeons += total_count

        # 按通关数量排序
        config_counts.sort(key=lambda x: x[2], reverse=True)

        # 显示排行
        print(colored("🏆 职业排行榜:\n", Colors.BRIGHT_YELLOW, bold=True))

        # 排名颜色
        rank_colors = [Colors.BRIGHT_YELLOW, Colors.BRIGHT_WHITE, Colors.YELLOW]

        for idx, (config_name, class_name, count) in enumerate(config_counts, 1):
            # 根据数量选择颜色
            if count < 10:
                bar_color = Colors.YELLOW
            elif count < 30:
                bar_color = Colors.GREEN
            else:
                bar_color = Colors.BRIGHT_GREEN

            bar = colored("█" * min(count // 2, 40), bar_color)

            # 排名颜色（前三名特殊颜色）
            if idx <= 3:
                rank_color = rank_colors[idx - 1]
                rank_str = colored(f"{idx}.", rank_color, bold=True)
            else:
                rank_str = f"{idx}."

            # 职业颜色
            class_color = get_class_ansi_color(class_name)
            config_colored = colored(config_name, class_color, bold=True)
            class_colored = colored(class_name, class_color)
            count_colored = colored(f"{count:3d}", bar_color, bold=True)

            print(
                f"   {rank_str} {config_colored:15s} ({class_colored:6s}): {count_colored} 个 {bar}"
            )

        print(f"\n{colored('=' * 80, Colors.BRIGHT_CYAN)}")
        total_colored = colored(f"{total_dungeons}", Colors.BRIGHT_GREEN, bold=True)
        active_colored = colored(
            f"{len(config_counts)}", Colors.BRIGHT_MAGENTA, bold=True
        )
        print(
            colored("📈 今日总计: ", Colors.BRIGHT_CYAN, bold=True)
            + total_colored
            + colored(" 个副本", Colors.BRIGHT_CYAN, bold=True)
        )
        print(
            colored("🎮 活跃职业: ", Colors.BRIGHT_CYAN, bold=True)
            + active_colored
            + colored(" 个", Colors.BRIGHT_CYAN, bold=True)
        )
        print(f"{colored('=' * 80, Colors.BRIGHT_CYAN)}\n")

    def check_incomplete_dungeons(self):
        """
        检查各职业未完成的副本

        Returns:
            tuple: (all_completed: bool, incomplete_count: int)
        """
        total_incomplete = 0

        print(f"\n{colored('=' * 70, Colors.CYAN)}")
        print(colored("📊 各职业完成情况检查", Colors.CYAN, bold=True))
        print(f"{colored('=' * 70, Colors.CYAN)}\n")

        for config_name in self.all_configs:
            class_name = self.config_classes.get(config_name, "未知")
            class_color = get_class_ansi_color(class_name)

            # 加载该配置的副本列表
            _, all_dungeons = self._load_config_dungeons(config_name)

            if not all_dungeons:
                continue

            # 使用对应配置的数据库实例
            config_db = self._get_db(config_name)

            # 获取已完成的副本
            completed = set()
            for zone, dungeon in all_dungeons:
                if config_db.is_dungeon_completed(zone, dungeon):
                    completed.add((zone, dungeon))

            # 计算未完成
            all_dungeons_set = set(all_dungeons)
            incomplete = all_dungeons_set - completed

            completed_count = len(completed)
            incomplete_count = len(incomplete)
            total_count = len(all_dungeons)

            config_colored = colored(config_name, class_color, bold=True)
            class_colored = colored(class_name, class_color)

            if incomplete_count == 0:
                status = colored("✅ 全部完成", Colors.GREEN, bold=True)
                completed_colored = colored(f"{completed_count}", Colors.GREEN)
                print(f"⚔️  {config_colored} ({class_colored}): {status} ({completed_colored}/{total_count})")
            elif completed_count == 0:
                count_colored = colored(f"{incomplete_count}", Colors.RED, bold=True)
                print(f"⚔️  {config_colored} ({class_colored}): {count_colored} 个未打")
                print(colored("   未完成:", Colors.BRIGHT_BLACK))
                for zone, dungeon in sorted(incomplete):
                    zone_colored = colored(zone[:8], Colors.BLUE)
                    dungeon_colored = colored(dungeon, Colors.WHITE)
                    print(f"      - {zone_colored}: {dungeon_colored}")
                print()
            else:
                count_colored = colored(f"{incomplete_count}", Colors.YELLOW, bold=True)
                print(f"⚔️  {config_colored} ({class_colored}): {count_colored} 个未完成 ({completed_count}/{total_count})")

                # 显示未完成的副本
                if incomplete_count <= 10:
                    print(colored("   未完成:", Colors.BRIGHT_BLACK))
                    for zone, dungeon in sorted(incomplete):
                        zone_colored = colored(zone[:8], Colors.BLUE)
                        dungeon_colored = colored(dungeon, Colors.WHITE)
                        print(f"      - {zone_colored}: {dungeon_colored}")
                else:
                    print(colored("   未完成 (前5个):", Colors.BRIGHT_BLACK))
                    for zone, dungeon in sorted(incomplete)[:5]:
                        zone_colored = colored(zone[:8], Colors.BLUE)
                        dungeon_colored = colored(dungeon, Colors.WHITE)
                        print(f"      - {zone_colored}: {dungeon_colored}")
                    print(f"      ... 还有 {incomplete_count - 5} 个")
                print()

            total_incomplete += incomplete_count

        return total_incomplete == 0, total_incomplete


def _send_pushover_summary(checker, include_special, incomplete_count, all_completed, pushover_output):
    """发送摘要到 Pushover

    Args:
        checker: ProgressChecker 实例
        include_special: 是否包含特殊副本
        incomplete_count: 未完成数量
        all_completed: 是否全部完成
        pushover_output: 收集的输出内容
    """
    try:
        # 获取今日统计
        all_stats = checker.db.get_all_configs_stats(include_special=include_special)

        # 构建 HTML 消息
        html_lines = [
            "<b>副本进度检查报告</b>",
            f"<b>日期:</b> {checker.db.get_today_date()}",
            "<hr>",
        ]

        # 添加各职业统计（使用 WOW 职业颜色）
        for stat in all_stats:
            if stat["total_count"] > 0:
                config_name = stat["config_name"]
                class_name = checker.config_classes.get(config_name, "未知")
                # 获取职业对应的颜色
                class_color = get_class_hex_color(class_name)
                html_lines.append(
                    f"<b style='color: {class_color}'>{escape_html(config_name)}</b> "
                    f"(<span style='color: {class_color}'>{escape_html(class_name)}</span>): "
                    f"<b>{stat['total_count']}</b> 个副本"
                )

        # 添加总体结果
        html_lines.append("<hr>")
        if all_completed:
            html_lines.append("<b><span style='color: #2ecc71'>✅ 全部完成</span></b>")
        else:
            html_lines.append(
                f"<b><span style='color: #e74c3c'>{incomplete_count} 个未完成</span></b>"
            )

        # 添加详细输出（如果有）
        if pushover_output:
            html_lines.append("<hr>")
            html_lines.append("<details><summary>详细输出</summary>")
            html_lines.append(f"<pre>{escape_html(pushover_output)}</pre>")
            html_lines.append("</details>")

        html_message = "<br>".join(html_lines)

        # 发送通知
        title = f"副本进度 - {'全部完成' if all_completed else '未完成'}"
        send_pushover_html_notification(title, html_message)

    except Exception as e:
        print(colored(f"⚠️ Pushover 通知发送失败: {e}", Colors.YELLOW))


def main():
    """主函数"""
    # 简单的日志记录器，不使用会出问题的 coloredlogs
    logger = logging.getLogger("check_progress")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(handler)

    try:
        parser = argparse.ArgumentParser(
            description="副本进度检查工具",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
返回值说明:
  0 - 所有副本已完成，无需继续刷本
 1 - 存在未完成副本，需要继续刷本
 2 - 发生错误

使用示例:
  python check_progress.py              # 显示所有统计和未完成检查
  python check_progress.py --quiet      # 安静模式，只返回退出码
  python check_progress.py && echo "完成" || echo "继续刷本"
            """
        )
        parser.add_argument(
            "--db", default="database/dungeon_progress.db", help="数据库文件路径"
        )
        parser.add_argument(
            "-c",
            "--config",
            type=str,
            default="default",
            help="配置名称 (默认: default)",
        )
        parser.add_argument("--today", action="store_true", help="显示今天的通关记录")
        parser.add_argument(
            "--recent", type=int, metavar="DAYS", help="显示最近N天的统计"
        )
        parser.add_argument("--zones", action="store_true", help="显示各区域统计")
        parser.add_argument("--all", action="store_true", help="显示所有职业的进度")
        parser.add_argument("--summary", action="store_true", help="显示总体统计摘要")
        parser.add_argument(
            "--include-special",
            action="store_true",
            help="包含特殊副本（每日收集）的统计",
        )
        parser.add_argument(
            "--pushover",
            action="store_true",
            help="同时发送通知到 Pushover（HTML 格式）",
        )
        parser.add_argument(
            "--quiet", "-q", action="store_true", help="安静模式，只返回退出码"
        )

        args = parser.parse_args()

        checker = ProgressChecker(args.db, args.config)

        try:
            # 如果没有指定任何参数，显示完整统计和未完成检查
            if len(sys.argv) == 1:
                checker.show_all_configs_progress(include_special=args.include_special)
                checker.show_summary(include_special=args.include_special)
                checker.show_recent_days(7, all_configs=True)
                all_completed, incomplete_count = checker.check_incomplete_dungeons()
            else:
                if args.all:
                    checker.show_all_configs_progress(include_special=args.include_special)

                if args.summary:
                    checker.show_summary(include_special=args.include_special)

                if args.today:
                    checker.show_today_progress()

                if args.zones:
                    checker.show_zone_stats()

                if args.recent:
                    checker.show_recent_days(args.recent)

                # 默认也显示未完成检查
                all_completed, incomplete_count = checker.check_incomplete_dungeons()

            # 根据结果返回退出码
            if all_completed:
                if not args.quiet:
                    print(colored("退出码: 0 (全部完成)", Colors.GREEN))
                # 发送 Pushover 通知
                if args.pushover:
                    _send_pushover_summary(
                        checker, args.include_special, incomplete_count, all_completed, ""
                    )
                return 0
            else:
                if not args.quiet:
                    print(colored(f"退出码: 1 ({incomplete_count} 个未完成)", Colors.YELLOW))
                # 发送 Pushover 通知
                if args.pushover:
                    _send_pushover_summary(
                        checker, args.include_special, incomplete_count, all_completed, ""
                    )
                return 1

        finally:
            checker.close()

    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.critical(
            f"进度检查工具异常退出: {type(e).__name__}: {str(e)}\n{error_traceback}"
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
