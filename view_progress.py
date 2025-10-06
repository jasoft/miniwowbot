#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
副本通关进度查看工具
用于查看和管理副本通关记录
"""

import sys
from datetime import datetime
import argparse
from database import DungeonProgressDB


class ProgressViewer:
    """进度查看器"""

    def __init__(self, db_path="dungeon_progress.db"):
        self.db = DungeonProgressDB(db_path)

    def show_today_progress(self):
        """显示今天的通关进度"""
        today = self.db.get_today_date()
        results = self.db.get_today_completed_dungeons()

        print(f"\n{'=' * 60}")
        print(f"📊 今天的通关记录 ({today})")
        print(f"{'=' * 60}\n")

        if not results:
            print("❌ 今天还没有通关任何副本\n")
            return

        print(f"✅ 共通关 {len(results)} 个副本:\n")
        for idx, (zone, dungeon) in enumerate(results, 1):
            print(f"{idx:3d}. {zone:12s} - {dungeon}")

        print()

    def show_recent_days(self, days=7):
        """显示最近几天的统计"""
        print(f"\n{'=' * 60}")
        print(f"📊 最近 {days} 天的通关统计")
        print(f"{'=' * 60}\n")

        stats = self.db.get_recent_stats(days)

        for target_date, count in stats:
            date_obj = datetime.fromisoformat(target_date)
            weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][
                date_obj.weekday()
            ]

            bar = "█" * (count // 2) if count > 0 else ""
            print(f"{target_date} ({weekday}): {count:3d} 个 {bar}")

        print()

    def show_zone_stats(self):
        """显示各区域的统计"""
        print(f"\n{'=' * 60}")
        print("📊 今天各区域通关统计")
        print(f"{'=' * 60}\n")

        results = self.db.get_zone_stats()

        if not results:
            print("❌ 今天还没有通关任何副本\n")
            return

        for zone, count in results:
            bar = "█" * count
            print(f"{zone:12s}: {count:3d} 个 {bar}")

        print()

    def clear_today(self):
        """清除今天的记录"""
        deleted_count = self.db.clear_today()
        print(f"\n✅ 已清除今天的 {deleted_count} 条记录\n")

    def clear_all(self):
        """清除所有记录"""
        deleted_count = self.db.clear_all()
        print(f"\n✅ 已清除所有 {deleted_count} 条记录\n")

    def close(self):
        """关闭数据库连接"""
        self.db.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="副本通关进度查看工具")
    parser.add_argument("--db", default="dungeon_progress.db", help="数据库文件路径")
    parser.add_argument("--today", action="store_true", help="显示今天的通关记录")
    parser.add_argument("--recent", type=int, metavar="DAYS", help="显示最近N天的统计")
    parser.add_argument("--zones", action="store_true", help="显示各区域统计")
    parser.add_argument("--clear-today", action="store_true", help="清除今天的记录")
    parser.add_argument("--clear-all", action="store_true", help="清除所有记录")

    args = parser.parse_args()

    viewer = ProgressViewer(args.db)

    try:
        # 如果没有指定任何参数，显示默认信息
        if len(sys.argv) == 1:
            viewer.show_today_progress()
            viewer.show_zone_stats()
            viewer.show_recent_days(7)
        else:
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


if __name__ == "__main__":
    main()
