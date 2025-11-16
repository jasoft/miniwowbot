#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
副本通关进度查看工具
用于查看和管理副本通关记录
"""

import sys
import os
import json
from datetime import datetime
import argparse
from database import DungeonProgressDB
from wow_class_colors import get_class_ansi_color


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

    # 背景色
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


def colored(text, color="", bold=False):
    """给文本添加颜色

    Args:
        text: 要着色的文本
        color: 颜色代码
        bold: 是否加粗

    Returns:
        着色后的文本
    """
    result = ""
    if bold:
        result += Colors.BOLD
    if color:
        result += color
    result += str(text) + Colors.RESET
    return result


class ProgressViewer:
    """进度查看器"""

    def __init__(self, db_path="database/dungeon_progress.db", config_name="default"):
        """
        初始化进度查看器

        Args:
            db_path: 数据库文件路径
            config_name: 配置名称
        """
        self.db = DungeonProgressDB(db_path, config_name)

    def show_today_progress(self):
        """显示今天的通关进度"""
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
        """显示最近几天的统计

        Args:
            days: 显示最近几天
            all_configs: 是否显示所有配置的统计（默认只显示当前配置）
        """
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
            # 获取所有配置的统计
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

    def clear_today(self):
        """清除今天的记录"""
        deleted_count = self.db.clear_today()
        msg = colored(
            f"✅ 已清除今天的 {deleted_count} 条记录", Colors.GREEN, bold=True
        )
        print(f"\n{msg}\n")

    def clear_all(self):
        """清除所有记录"""
        deleted_count = self.db.clear_all()
        msg = colored(f"✅ 已清除所有 {deleted_count} 条记录", Colors.GREEN, bold=True)
        print(f"\n{msg}\n")

    def show_all_configs_progress(self):
        """显示所有职业的进度情况"""
        today = self.db.get_today_date()

        print(f"\n{colored('=' * 80, Colors.CYAN)}")
        print(colored(f"📊 所有职业今天的通关进度 ({today})", Colors.CYAN, bold=True))
        print(f"{colored('=' * 80, Colors.CYAN)}\n")

        # 获取所有配置的统计信息
        all_stats = self.db.get_all_configs_stats()

        if not all_stats:
            print(colored("❌ 今天还没有任何通关记录\n", Colors.YELLOW))
            return

        # 加载配置文件获取职业信息
        config_classes = self._load_config_classes()

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
            class_name = config_classes.get(config_name, "未知")
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

    def show_summary(self):
        """显示总体统计摘要"""
        today = self.db.get_today_date()

        print(f"\n{colored('=' * 80, Colors.CYAN)}")
        print(colored(f"📊 总体统计摘要 ({today})", Colors.CYAN, bold=True))
        print(f"{colored('=' * 80, Colors.CYAN)}\n")

        # 获取所有配置的统计信息
        all_stats = self.db.get_all_configs_stats()

        if not all_stats:
            print(colored("❌ 今天还没有任何通关记录\n", Colors.YELLOW))
            return

        # 加载配置文件获取职业信息
        config_classes = self._load_config_classes()

        # 统计数据
        total_dungeons = 0
        config_counts = []

        for stat in all_stats:
            config_name = stat["config_name"]
            total_count = stat["total_count"]

            if total_count > 0:
                class_name = config_classes.get(config_name, "未知")
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

    def _load_config_classes(self):
        """
        加载所有配置文件的职业信息

        Returns:
            dict: 配置名称到职业名称的映射
        """
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
                # 忽略读取错误
                pass

        return config_classes

    def close(self):
        """关闭数据库连接"""
        self.db.close()


def main():
    """主函数"""
    import logging

    # 初始化日志
    try:
        from logger_config import setup_logger_from_config

        logger = setup_logger_from_config(use_color=True)
    except Exception:
        # 如果无法导入日志配置，使用基础日志
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

    try:
        parser = argparse.ArgumentParser(description="副本通关进度查看工具")
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
        parser.add_argument("--clear-today", action="store_true", help="清除今天的记录")
        parser.add_argument("--clear-all", action="store_true", help="清除所有记录")

        args = parser.parse_args()

        viewer = ProgressViewer(args.db, args.config)

        try:
            # 如果没有指定任何参数，显示默认信息（新版本：显示所有职业和总体统计）
            if len(sys.argv) == 1:
                viewer.show_all_configs_progress()
                viewer.show_summary()
                viewer.show_recent_days(7, all_configs=True)
            else:
                if args.all:
                    viewer.show_all_configs_progress()

                if args.summary:
                    viewer.show_summary()

                if args.today:
                    viewer.show_today_progress()

                if args.zones:
                    viewer.show_zone_stats()

                if args.recent:
                    viewer.show_recent_days(args.recent)

                if args.clear_today:
                    confirm = input("⚠️  确定要清除今天的记录吗？(yes/no): ")
                    if confirm.lower() == "yes":
                        viewer.clear_today()
                    else:
                        print("\n❌ 已取消\n")

                if args.clear_all:
                    confirm = input("⚠️  确定要清除所有记录吗？(yes/no): ")
                    if confirm.lower() == "yes":
                        viewer.clear_all()
                    else:
                        print("\n❌ 已取消\n")

        finally:
            viewer.close()

    except Exception as e:
        import traceback

        error_traceback = traceback.format_exc()
        logger.critical(
            f"进度查看工具异常退出: {type(e).__name__}: {str(e)}\n{error_traceback}"
        )
        raise


if __name__ == "__main__":
    main()
