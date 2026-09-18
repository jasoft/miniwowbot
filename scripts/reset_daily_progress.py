#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""清理指定职业在副本进度库中的当日记录。

当某个职业因为任务失败、被 panic-stop 中断、或免费次数被别的流程抢先消耗，
导致当日进度被污染（或希望从头完整跑一遍）时，用这个脚本把它的当日记录删掉。

用法::

    # 先看会删掉什么（不写库）
    uv run python -m scripts.reset_daily_progress warrior --dry-run

    # 真删 warrior 今天的记录
    uv run python -m scripts.reset_daily_progress warrior --yes

    # 一次清理多个职业 / 全部职业
    uv run python -m scripts.reset_daily_progress warrior mage --yes
    uv run python -m scripts.reset_daily_progress --all --yes

    # 只清副本记录，保留日常任务与领取记录
    uv run python -m scripts.reset_daily_progress warrior --keep-daily --yes

    # 指定日期
    uv run python -m scripts.reset_daily_progress warrior --date 2026-09-17 --yes

poe 快捷方式::

    poe reset-daily warrior --dry-run
    poe reset-daily warrior --yes

说明：
    * 日期按游戏逻辑日计算（每日 06:00 换日），口径与
      :meth:`database.dungeon_db.DungeonProgressDB.get_today_date` 保持一致。
    * ``--keep-daily`` 会保留 ``日常任务`` 与 ``__daily_collect__`` 两类记录，
      适合「奖励已经领完，只想重跑副本」的场景。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence

import typer

from database.dungeon_db import DungeonProgress, db as progress_db
from logger_config import resolve_project_path, setup_logger

# 日常任务相关的 zone_name（见 auto_dungeon_daily.py）
DAILY_TASK_ZONE_NAME = "日常任务"
DAILY_COLLECT_ZONE_NAME = "__daily_collect__"
DAILY_ZONE_NAMES = (DAILY_TASK_ZONE_NAME, DAILY_COLLECT_ZONE_NAME)

# 游戏逻辑日换日时间：每天 06:00
LOGIC_DATE_SWITCH_HOUR = 6

DEFAULT_DB_PATH = resolve_project_path("database", "dungeon_progress.db")
CONFIGS_DIR = resolve_project_path("configs")

app = typer.Typer(add_completion=False)


def resolve_logic_date(now: Optional[datetime] = None) -> str:
    """按游戏逻辑日解析日期字符串。

    Args:
        now: 参考时间；为空时使用系统当前时间。

    Returns:
        ``YYYY-MM-DD`` 格式的逻辑日期；06:00 之前算作前一天。
    """
    current = now or datetime.now()
    if current.hour < LOGIC_DATE_SWITCH_HOUR:
        current = current - timedelta(days=1)
    return current.date().isoformat()


def validate_date(date_text: str) -> str:
    """校验日期字符串格式。

    Args:
        date_text: 待校验的日期文本，应为 ``YYYY-MM-DD``。

    Returns:
        校验通过的日期文本。

    Raises:
        typer.BadParameter: 日期格式不合法时抛出。
    """
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError as exc:
        raise typer.BadParameter(f"日期格式应为 YYYY-MM-DD，收到: {date_text}") from exc
    return date_text


def list_available_configs(configs_dir: Path = CONFIGS_DIR) -> list[str]:
    """列出 configs 目录下可选的职业配置名。

    Args:
        configs_dir: 配置目录路径。

    Returns:
        去掉 ``.json`` 后缀并按字母序排列的配置名列表。
    """
    if not configs_dir.is_dir():
        return []
    names = {path.stem for path in configs_dir.glob("*.json")}
    return sorted(names)


def connect_progress_db(db_path: Path) -> None:
    """初始化并连接副本进度库。

    Args:
        db_path: sqlite 数据库文件路径。

    Raises:
        typer.Exit: 数据库文件或数据表不存在时以退出码 1 结束。
    """
    if not db_path.exists():
        typer.secho(f"❌ 数据库文件不存在: {db_path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if not progress_db.is_closed():
        progress_db.close()
    progress_db.init(str(db_path))
    progress_db.connect()

    if not DungeonProgress.table_exists():
        typer.secho(f"❌ 数据表 dungeon_progress 不存在: {db_path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


def fetch_pending_records(
    configs: Sequence[str],
    target_date: str,
    keep_daily: bool = False,
) -> list[DungeonProgress]:
    """查询符合条件的待清理记录。

    Args:
        configs: 目标配置名列表，不能为空。
        target_date: 目标逻辑日期（``YYYY-MM-DD``）。
        keep_daily: 为 ``True`` 时保留日常任务相关记录。

    Returns:
        待清理的记录列表。
    """
    if not configs:
        return []

    query = DungeonProgress.select().where(
        (DungeonProgress.config_name.in_(list(configs))) & (DungeonProgress.date == target_date)
    )
    if keep_daily:
        query = query.where(~(DungeonProgress.zone_name.in_(DAILY_ZONE_NAMES)))

    return list(
        query.order_by(
            DungeonProgress.config_name,
            DungeonProgress.zone_name,
            DungeonProgress.dungeon_name,
        )
    )


def delete_records(
    configs: Sequence[str],
    target_date: str,
    keep_daily: bool = False,
) -> int:
    """删除符合条件的记录。

    Args:
        configs: 目标配置名列表，不能为空。
        target_date: 目标逻辑日期（``YYYY-MM-DD``）。
        keep_daily: 为 ``True`` 时保留日常任务相关记录。

    Returns:
        实际删除的记录条数。
    """
    if not configs:
        return 0

    query = DungeonProgress.delete().where(
        (DungeonProgress.config_name.in_(list(configs))) & (DungeonProgress.date == target_date)
    )
    if keep_daily:
        query = query.where(~(DungeonProgress.zone_name.in_(DAILY_ZONE_NAMES)))

    return query.execute()


def summarize_records(records: Sequence[DungeonProgress]) -> dict[str, dict[str, int]]:
    """按「配置 → 区域」汇总记录条数。

    Args:
        records: 待汇总的记录列表。

    Returns:
        形如 ``{"warrior": {"日常任务": 10, "__daily_collect__": 10}}`` 的汇总结果。
    """
    summary: dict[str, dict[str, int]] = {}
    for record in records:
        zone_stats = summary.setdefault(record.config_name, {})
        zone_stats[record.zone_name] = zone_stats.get(record.zone_name, 0) + 1
    return summary


def print_summary(summary: dict[str, dict[str, int]]) -> None:
    """打印「配置 → 区域」汇总表。

    Args:
        summary: :func:`summarize_records` 的返回值。

    Returns:
        None.
    """
    for config_name, zone_stats in summary.items():
        total = sum(zone_stats.values())
        typer.echo(f"  {config_name}  合计 {total} 条")
        for zone_name, count in sorted(zone_stats.items(), key=lambda item: -item[1]):
            display_zone = zone_name if zone_name != DAILY_COLLECT_ZONE_NAME else "每日领取"
            typer.echo(f"      {display_zone:<16} {count} 条")


@app.command(help="清理指定职业的当日副本完成记录。")
def main(
    configs: Optional[list[str]] = typer.Argument(
        None, help="要清理的职业配置名，可传多个；如 warrior 或 warrior mage"
    ),
    all_configs: bool = typer.Option(False, "--all", "-a", help="清理数据库中所有出现过的配置"),
    date: Optional[str] = typer.Option(
        None, "--date", "-d", help="目标日期 YYYY-MM-DD，默认为当前逻辑日（06:00 换日）"
    ),
    keep_daily: bool = typer.Option(
        False, "--keep-daily", help="保留日常任务与每日领取记录，只清副本记录"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="只列出将要删除的记录，不写库"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过删除确认"),
    db_path: Path = typer.Option(DEFAULT_DB_PATH, "--db", help="数据库文件路径"),
) -> None:
    """清理指定职业的当日完成记录。

    Args:
        configs: 目标职业配置名列表。
        all_configs: 是否清理全部配置。
        date: 目标日期；为空时使用逻辑日。
        keep_daily: 是否保留日常任务相关记录。
        dry_run: 是否只演练不写库。
        yes: 是否跳过确认。
        db_path: 数据库文件路径。

    Returns:
        None.

    Raises:
        typer.Exit: 参数缺失、配置名无效或用户取消时以非零退出码结束。
    """
    logger = setup_logger(name="reset_daily", level="INFO", use_color=True)
    target_date = validate_date(date) if date else resolve_logic_date()
    available_configs = list_available_configs()

    if not configs and not all_configs:
        typer.secho("❌ 请指定要清理的职业，或使用 --all", fg=typer.colors.RED, err=True)
        if available_configs:
            typer.secho(f"   可选职业: {', '.join(available_configs)}", err=True)
        raise typer.Exit(code=1)

    connect_progress_db(db_path)

    if all_configs:
        target_configs = sorted(
            row.config_name
            for row in DungeonProgress.select(DungeonProgress.config_name).distinct()
        )
    else:
        target_configs = [name[:-5] if name.endswith(".json") else name for name in configs or []]

    unknown = [name for name in target_configs if name not in available_configs]
    for name in unknown:
        logger.warning(f"⚠️ 配置名不在 configs 目录中，仍会尝试清理: {name}")

    logger.info(f"📅 目标逻辑日: {target_date}")
    logger.info(f"🎯 目标配置: {', '.join(target_configs) if target_configs else '（无）'}")

    records = fetch_pending_records(target_configs, target_date, keep_daily)
    if not records:
        logger.info("ℹ️ 没有符合条件的记录，无需清理")
        return

    summary = summarize_records(records)
    for name in target_configs:
        summary.setdefault(name, {})
    typer.echo("")
    typer.secho(f"待删除 {len(records)} 条记录:", fg=typer.colors.YELLOW)
    print_summary(summary)
    if keep_daily:
        typer.echo("  （--keep-daily 已保留日常任务与每日领取记录）")
    typer.echo("")

    if dry_run:
        logger.info("🧪 --dry-run 模式，未写入数据库")
        return

    if not yes and not typer.confirm(f"确认删除这 {len(records)} 条记录？", default=False):
        logger.info("🙅 已取消，未做任何修改")
        raise typer.Exit(code=1)

    deleted = delete_records(target_configs, target_date, keep_daily)
    logger.info(f"🗑️ 已删除 {deleted} 条记录")

    remaining = fetch_pending_records(target_configs, target_date, keep_daily)
    logger.info(f"✅ 清理完成，剩余匹配记录 {len(remaining)} 条")


if __name__ == "__main__":
    app()
