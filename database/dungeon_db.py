#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
副本通关进度数据库模块
使用 Peewee ORM 管理数据库
"""

import logging
from datetime import date, datetime, timedelta
from peewee import (
    SqliteDatabase,
    Model,
    CharField,
    IntegerField,
    DateTimeField,
    fn,
)

logger = logging.getLogger(__name__)

# 数据库实例
db = SqliteDatabase(None)


class BaseModel(Model):
    """基础模型"""

    class Meta:
        database = db


class DungeonProgress(BaseModel):
    """副本通关进度模型"""

    config_name = CharField(index=True, default="default")  # 配置名称
    date = CharField(index=True)  # 日期 (YYYY-MM-DD)
    zone_name = CharField(index=True)  # 区域名称
    dungeon_name = CharField()  # 副本名称
    completed = IntegerField(default=0)  # 是否完成 (0/1)
    completed_at = DateTimeField(null=True)  # 完成时间

    class Meta:
        table_name = "dungeon_progress"
        indexes = (
            (("config_name", "date", "zone_name", "dungeon_name"), True),
        )  # 唯一索引


class DungeonProgressDB:
    """副本通关进度数据库管理类"""

    def __init__(self, db_path="database/dungeon_progress.db", config_name="default"):
        """
        初始化数据库连接

        Args:
            db_path: 数据库文件路径
            config_name: 配置名称，用于区分不同角色
        """
        self.db_path = db_path
        self.config_name = config_name
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        db.init(self.db_path)
        db.connect()
        db.create_tables([DungeonProgress], safe=True)
        logger.info(f"📊 数据库初始化完成: {self.db_path}")
        logger.info(f"🎮 当前配置: {self.config_name}")

    def get_today_date(self):
        """获取今天的日期字符串"""
        return date.today().isoformat()

    def is_dungeon_completed(self, zone_name, dungeon_name):
        """检查副本今天是否已通关"""
        today = self.get_today_date()
        try:
            record = DungeonProgress.get(
                (DungeonProgress.config_name == self.config_name)
                & (DungeonProgress.date == today)
                & (DungeonProgress.zone_name == zone_name)
                & (DungeonProgress.dungeon_name == dungeon_name)
            )
            return record.completed == 1
        except DungeonProgress.DoesNotExist:
            return False

    def mark_dungeon_completed(self, zone_name, dungeon_name):
        """标记副本为已通关"""
        today = self.get_today_date()
        now = datetime.now()

        # 使用 insert 或 replace
        DungeonProgress.insert(
            config_name=self.config_name,
            date=today,
            zone_name=zone_name,
            dungeon_name=dungeon_name,
            completed=1,
            completed_at=now,
        ).on_conflict(
            conflict_target=[
                DungeonProgress.config_name,
                DungeonProgress.date,
                DungeonProgress.zone_name,
                DungeonProgress.dungeon_name,
            ],
            update={
                DungeonProgress.completed: 1,
                DungeonProgress.completed_at: now,
            },
        ).execute()

        logger.info(f"💾 记录通关: {zone_name} - {dungeon_name}")

    def get_today_completed_count(self):
        """获取今天已通关的副本数量"""
        today = self.get_today_date()
        return (
            DungeonProgress.select()
            .where(
                (DungeonProgress.config_name == self.config_name)
                & (DungeonProgress.date == today)
                & (DungeonProgress.completed == 1)
            )
            .count()
        )

    def get_today_completed_dungeons(self):
        """获取今天已通关的副本列表"""
        today = self.get_today_date()
        records = (
            DungeonProgress.select()
            .where(
                (DungeonProgress.config_name == self.config_name)
                & (DungeonProgress.date == today)
                & (DungeonProgress.completed == 1)
            )
            .order_by(DungeonProgress.completed_at)
        )
        return [(r.zone_name, r.dungeon_name) for r in records]

    def cleanup_old_records(self, days_to_keep=7):
        """清理旧记录，只保留最近N天的数据"""
        cutoff_date = (date.today() - timedelta(days=days_to_keep)).isoformat()

        deleted_count = (
            DungeonProgress.delete().where(DungeonProgress.date < cutoff_date).execute()
        )

        if deleted_count > 0:
            logger.info(f"🗑️ 清理了 {deleted_count} 条旧记录")

    def get_zone_stats(self):
        """获取各区域的通关统计"""
        today = self.get_today_date()
        query = (
            DungeonProgress.select(
                DungeonProgress.zone_name,
                fn.COUNT(DungeonProgress.id).alias("count"),
            )
            .where(
                (DungeonProgress.config_name == self.config_name)
                & (DungeonProgress.date == today)
                & (DungeonProgress.completed == 1)
            )
            .group_by(DungeonProgress.zone_name)
            .order_by(fn.COUNT(DungeonProgress.id).desc())
        )
        return [(r.zone_name, r.count) for r in query]

    def get_recent_stats(self, days=7):
        """获取最近N天的统计"""
        stats = []
        for i in range(days):
            target_date = (date.today() - timedelta(days=i)).isoformat()
            count = (
                DungeonProgress.select()
                .where(
                    (DungeonProgress.config_name == self.config_name)
                    & (DungeonProgress.date == target_date)
                    & (DungeonProgress.completed == 1)
                )
                .count()
            )
            stats.append((target_date, count))
        return stats

    def clear_today(self):
        """清除今天的记录（仅当前配置）"""
        today = self.get_today_date()
        deleted_count = (
            DungeonProgress.delete()
            .where(
                (DungeonProgress.config_name == self.config_name)
                & (DungeonProgress.date == today)
            )
            .execute()
        )
        logger.info(
            f"🗑️ 已清除今天的 {deleted_count} 条记录（配置: {self.config_name}）"
        )
        return deleted_count

    def clear_all(self):
        """清除所有记录（仅当前配置）"""
        deleted_count = (
            DungeonProgress.delete()
            .where(DungeonProgress.config_name == self.config_name)
            .execute()
        )
        logger.info(f"🗑️ 已清除所有 {deleted_count} 条记录（配置: {self.config_name}）")
        return deleted_count

    def close(self):
        """关闭数据库连接"""
        if not db.is_closed():
            db.close()
            logger.info("📊 数据库连接已关闭")

    def __enter__(self):
        """支持 with 语句"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 语句"""
        self.close()
