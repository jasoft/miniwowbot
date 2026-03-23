#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
副本通关进度数据库模块
使用 Peewee ORM 管理数据库
"""

from datetime import datetime, timedelta, timezone

from peewee import (
    CharField,
    DateTimeField,
    IntegerField,
    Model,
    SqliteDatabase,
    fn,
)

import logging
logger = logging.getLogger(__name__)

# 数据库实例
db = SqliteDatabase(None)

# 特殊副本：每日收集
DAILY_COLLECT_ZONE_NAME = "__daily_collect__"
DAILY_COLLECT_DUNGEON_NAME = "daily_collect"
SPECIAL_ZONE_NAMES = (DAILY_COLLECT_ZONE_NAME,)
EVENT_RESET_TIMEZONE = timezone(timedelta(hours=8))
EVENT_RESET_WEEKDAY = 4
EVENT_RESET_HOUR = 6


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

    class Meta:  # type: ignore
        database = db
        table_name = "dungeon_progress"
        indexes = ((("config_name", "date", "zone_name", "dungeon_name"), True),)  # 唯一索引


class EventItemProgress(BaseModel):
    """主题活动兑换进度模型。"""

    config_name = CharField(index=True, default="default")
    cycle_id = CharField(index=True)
    event_name = CharField(index=True)
    item_key = CharField()
    completed_at = DateTimeField()

    class Meta:  # type: ignore
        database = db
        table_name = "event_item_progress"
        indexes = ((("config_name", "cycle_id", "event_name", "item_key"), True),)


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
        """初始化数据库。

        Returns:
            None.
        """
        db.init(self.db_path)
        db.connect()
        db.create_tables([DungeonProgress, EventItemProgress], safe=True)
        logger.info(f"📊 数据库初始化完成: {self.db_path}")
        logger.info(f"🎮 当前配置: {self.config_name}")

    def _get_logic_date(self):
        """获取按日常逻辑切分的日期对象。

        Returns:
            date: 以每天 06:00 为界限换日后的逻辑日期。
        """
        now = datetime.now()
        if now.hour < 6:
            return now.date() - timedelta(days=1)
        return now.date()

    def get_today_date(self):
        """获取今天的逻辑日期字符串。

        Returns:
            str: `YYYY-MM-DD` 格式的逻辑日期。
        """
        return self._get_logic_date().isoformat()

    def _normalize_event_time(self, now=None):
        """把输入时间规范为 GMT+8 时区时间。

        Args:
            now: 可选的当前时间；若为空则使用系统当前时间。

        Returns:
            datetime: 规范化后的 GMT+8 时间。
        """
        if now is None:
            return datetime.now(EVENT_RESET_TIMEZONE)
        if now.tzinfo is None:
            return now.replace(tzinfo=EVENT_RESET_TIMEZONE)
        return now.astimezone(EVENT_RESET_TIMEZONE)

    def get_event_cycle_id(self, now=None):
        """获取主题兑换期次标识。

        Args:
            now: 可选的当前时间；若为空则使用系统当前时间。

        Returns:
            str: 以 GMT+8 周五 06:00 为边界的期次起始时间字符串。
        """
        current = self._normalize_event_time(now)
        days_since_reset = (current.weekday() - EVENT_RESET_WEEKDAY) % 7
        cycle_start = (current - timedelta(days=days_since_reset)).replace(
            hour=EVENT_RESET_HOUR,
            minute=0,
            second=0,
            microsecond=0,
        )
        if current < cycle_start:
            cycle_start -= timedelta(days=7)
        return cycle_start.isoformat(timespec="seconds")

    def is_event_item_completed(self, event_name, item_key, cycle_id=None):
        """查询某个主题兑换物品在当前期次是否已完成。

        Args:
            event_name: 主题活动标识。
            item_key: 兑换物品标识。
            cycle_id: 可选期次标识；为空时自动按当前时间计算。

        Returns:
            bool: 若当前配置在该期次已记录兑换成功则返回 `True`。
        """
        target_cycle_id = cycle_id or self.get_event_cycle_id()
        try:
            EventItemProgress.get(
                (EventItemProgress.config_name == self.config_name)
                & (EventItemProgress.cycle_id == target_cycle_id)
                & (EventItemProgress.event_name == event_name)
                & (EventItemProgress.item_key == item_key)
            )
            return True
        except EventItemProgress.DoesNotExist:  # type: ignore
            return False

    def mark_event_item_completed(self, event_name, item_key, cycle_id=None):
        """记录某个主题兑换物品在当前期次已完成。

        Args:
            event_name: 主题活动标识。
            item_key: 兑换物品标识。
            cycle_id: 可选期次标识；为空时自动按当前时间计算。

        Returns:
            None.
        """
        target_cycle_id = cycle_id or self.get_event_cycle_id()
        completed_at = self._normalize_event_time()
        EventItemProgress.insert(
            config_name=self.config_name,
            cycle_id=target_cycle_id,
            event_name=event_name,
            item_key=item_key,
            completed_at=completed_at,
        ).on_conflict(
            conflict_target=[
                EventItemProgress.config_name,
                EventItemProgress.cycle_id,
                EventItemProgress.event_name,
                EventItemProgress.item_key,
            ],
            update={
                EventItemProgress.completed_at: completed_at,
            },
        ).execute()
        logger.info(
            "💾 记录主题兑换完成: %s - %s (%s)",
            event_name,
            item_key,
            target_cycle_id,
        )

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
        except DungeonProgress.DoesNotExist:  # type: ignore
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

    def mark_daily_collect_completed(self):
        """标记每日收集任务为已完成"""
        self.mark_dungeon_completed(DAILY_COLLECT_ZONE_NAME, DAILY_COLLECT_DUNGEON_NAME)

    def is_daily_collect_completed(self):
        """判断每日收集任务今天是否已完成"""
        return self.is_dungeon_completed(DAILY_COLLECT_ZONE_NAME, DAILY_COLLECT_DUNGEON_NAME)

    def mark_daily_step_completed(self, step_name):
        """标记每日收集的某个步骤为已完成"""
        self.mark_dungeon_completed(DAILY_COLLECT_ZONE_NAME, step_name)

    def is_daily_step_completed(self, step_name):
        """判断每日收集的某个步骤是否已完成"""
        return self.is_dungeon_completed(DAILY_COLLECT_ZONE_NAME, step_name)

    def _build_completed_query(self, target_date=None, include_special=False):
        """构建已通关记录查询条件"""
        if target_date is None:
            target_date = self.get_today_date()

        query = (
            (DungeonProgress.config_name == self.config_name)
            & (DungeonProgress.date == target_date)
            & (DungeonProgress.completed == 1)
        )

        if not include_special and SPECIAL_ZONE_NAMES:
            query &= ~(DungeonProgress.zone_name.in_(SPECIAL_ZONE_NAMES))

        return query

    def get_today_completed_count(self, include_special=False):
        """获取今天已通关的副本数量"""
        today = self.get_today_date()
        return (
            DungeonProgress.select()
            .where(self._build_completed_query(today, include_special))
            .count()
        )

    def get_today_completed_dungeons(self, include_special=False):
        """获取今天已通关的副本列表"""
        today = self.get_today_date()
        records = (
            DungeonProgress.select()
            .where(self._build_completed_query(today, include_special))
            .order_by(DungeonProgress.completed_at)
        )
        return [(r.zone_name, r.dungeon_name) for r in records]

    def cleanup_old_records(self, days_to_keep=7):
        """清理旧记录，只保留最近N天的数据"""
        cutoff_date = (self._get_logic_date() - timedelta(days=days_to_keep)).isoformat()

        deleted_count = DungeonProgress.delete().where(DungeonProgress.date < cutoff_date).execute()

        if deleted_count > 0:
            logger.info(f"🗑️ 清理了 {deleted_count} 条旧记录")

    def get_zone_stats(self, include_special=False):
        """获取各区域的通关统计"""
        today = self.get_today_date()
        query = (
            DungeonProgress.select(
                DungeonProgress.zone_name,
                fn.COUNT(DungeonProgress.id).alias("count"),  # type: ignore
            )
            .where(self._build_completed_query(today, include_special))
            .group_by(DungeonProgress.zone_name)
            .order_by(fn.COUNT(DungeonProgress.id).desc())  # type: ignore
        )
        return [(r.zone_name, r.count) for r in query]

    def get_recent_stats(self, days=7, include_special=False):
        """获取最近N天的统计"""
        stats = []
        for i in range(days):
            target_date = (self._get_logic_date() - timedelta(days=i)).isoformat()
            count = (
                DungeonProgress.select()
                .where(self._build_completed_query(target_date, include_special))
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
                (DungeonProgress.config_name == self.config_name) & (DungeonProgress.date == today)
            )
            .execute()
        )
        logger.debug(f"🗑️ 已清除今天的 {deleted_count} 条记录（配置: {self.config_name}）")
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
            logger.debug("📊 数据库连接已关闭")

    def __enter__(self):
        """支持 with 语句"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 语句"""
        self.close()

    def get_all_configs(self):
        """获取所有配置名称"""
        query = (
            DungeonProgress.select(DungeonProgress.config_name)
            .distinct()
            .order_by(DungeonProgress.config_name)
        )
        return [r.config_name for r in query]

    def get_config_stats(self, config_name, target_date=None, include_special=False):
        """
        获取指定配置的统计信息

        Args:
            config_name: 配置名称
            target_date: 目标日期，默认为今天
            include_special: 是否包含特殊副本（每日收集），默认为 False

        Returns:
            dict: 包含统计信息的字典
        """
        if target_date is None:
            target_date = self.get_today_date()

        # 构建查询条件（排除特殊区域）
        query = (
            (DungeonProgress.config_name == config_name)
            & (DungeonProgress.date == target_date)
            & (DungeonProgress.completed == 1)
        )
        if not include_special and SPECIAL_ZONE_NAMES:
            query &= ~(DungeonProgress.zone_name.in_(SPECIAL_ZONE_NAMES))

        # 总通关数
        total_count = (
            DungeonProgress.select()
            .where(query)
            .count()
        )

        # 各区域统计
        zone_stats_query = (
            DungeonProgress.select(
                DungeonProgress.zone_name,
                fn.COUNT(DungeonProgress.id).alias("count"),  # type: ignore
            )
            .where(query)
            .group_by(DungeonProgress.zone_name)
            .order_by(fn.COUNT(DungeonProgress.id).desc())  # type: ignore
        )

        return {
            "config_name": config_name,
            "total_count": total_count,
            "zone_stats": [(r.zone_name, r.count) for r in zone_stats_query],
        }

    def get_all_configs_stats(self, target_date=None, include_special=False):
        """
        获取所有配置的统计信息

        Args:
            target_date: 目标日期，默认为今天
            include_special: 是否包含特殊副本（每日收集），默认为 False

        Returns:
            list: 包含所有配置统计信息的列表
        """
        if target_date is None:
            target_date = self.get_today_date()

        configs = self.get_all_configs()
        stats = []
        for config in configs:
            config_stat = self.get_config_stats(config, target_date, include_special)
            stats.append(config_stat)

        return stats
