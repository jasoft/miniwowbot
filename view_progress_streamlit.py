#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""使用 Streamlit 展示副本进度的可视化页面。"""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from database import DungeonProgressDB
from view_progress_dashboard import (
    build_config_progress,
    compute_recent_totals,
    compute_zone_stats,
    fetch_today_records,
    load_configurations,
    summarize_progress,
)


PAGE_TITLE = "副本进度监控面板"
AUTO_REFRESH_MS = 5000


@st.cache_data(ttl=30)
def _load_configs_cached(config_dir: str):
    return load_configurations(config_dir)


def _render_auto_refresh(interval_ms: int = AUTO_REFRESH_MS) -> int:
    """使用 streamlit-autorefresh 保持 5 秒刷新节奏。"""
    return st_autorefresh(interval=interval_ms, limit=None, key="progress_autorefresh")


def _render_summary(summary: dict) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("今日完成副本", summary.get("total_completed", 0))
    col2.metric("今日计划副本", summary.get("total_planned", 0))
    completion_rate = summary.get("completion_rate", 0.0) * 100
    col3.metric("计划完成率", f"{completion_rate:.1f}%")
    col4.metric("活跃职业", summary.get("active_configs", 0))

    ranking = summary.get("ranking", [])
    if ranking:
        st.caption("👉 职业完成度排名")
        ranking_df = pd.DataFrame(
            [
                {
                    "职业": f"{item['config_name']} ({item['class_name']})",
                    "计划内完成": item["completed"],
                    "总记录": item["actual_completed"],
                }
                for item in ranking
            ]
        )
        st.dataframe(ranking_df, hide_index=True, use_container_width=True)


def _render_recent_stats(recent_stats):
    if not recent_stats:
        st.info("最近没有通关记录")
        return

    recent_df = pd.DataFrame(recent_stats, columns=["日期", "完成数量"])
    recent_df = recent_df.iloc[::-1]
    st.line_chart(recent_df.set_index("日期"))


def _render_zone_stats(zone_stats):
    if not zone_stats:
        st.info("今天暂无区域统计数据")
        return

    zone_df = pd.DataFrame(zone_stats, columns=["区域", "完成数量"])
    st.bar_chart(zone_df.set_index("区域"))


def _render_today_records(records, selected_configs):
    if selected_configs is None:
        filtered = records
    elif len(selected_configs) == 0:
        st.info("未选择任何职业, 无法展示记录")
        return
    else:
        selected_set = set(selected_configs)
        filtered = [r for r in records if r["config_name"] in selected_set]
    if not filtered:
        st.info("所选职业今天还没有完成任何副本")
        return

    table = [
        {
            "时间": record["completed_at"].strftime("%H:%M:%S")
            if record["completed_at"]
            else "-",
            "职业": record["config_name"],
            "区域": record["zone_name"],
            "副本": record["dungeon_name"],
        }
        for record in filtered
    ]
    st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)


def _render_config_details(config_progress, selected_configs):
    if not config_progress:
        st.info("没有可展示的职业配置")
        return

    if selected_configs is not None and len(selected_configs) == 0:
        st.info("未选择任何职业, 请在侧边栏勾选至少一个配置")
        return

    for config in config_progress:
        if selected_configs is not None:
            if config["config_name"] not in selected_configs:
                continue

        header = (
            f"{config['config_name']} ({config['class_name']})"
            f" - {config['completed_planned']}/{config['total_planned']} 计划完成"
        )
        with st.expander(header, expanded=True):
            if config.get("description"):
                st.write(config["description"])

            zone_cols = st.columns(2)
            for idx, zone in enumerate(config.get("zones", [])):
                container = zone_cols[idx % 2]
                planned = zone["planned_count"]
                denominator = planned if planned else 1
                ratio = zone["completed_count"] / denominator if planned else 0
                container.metric(
                    f"{zone['zone_name']}",
                    f"{zone['completed_count']}/{planned}",
                    delta=f"{ratio*100:.0f}%",
                )
                check_cols = container.columns(2)
                for dungeon_idx, dungeon in enumerate(zone.get("dungeons", [])):
                    label = dungeon["name"]
                    if not dungeon["selected"]:
                        label += "（未勾选）"
                    if dungeon.get("completed_at"):
                        label += f" · {dungeon['completed_at'].strftime('%H:%M')}"
                    check_cols[dungeon_idx % 2].checkbox(
                        label,
                        value=dungeon["completed"],
                        key=f"chk-{config['config_name']}-{zone['zone_name']}-{dungeon['name']}",
                        disabled=True,
                    )

            if config.get("extra_completions"):
                st.warning("⚠️ 发现配置文件中未列出的额外副本记录:")
                st.write(
                    pd.DataFrame(
                        [
                            {
                                "区域": extra["zone_name"],
                                "副本": extra["dungeon_name"],
                                "完成时间": extra["completed_at"],
                            }
                            for extra in config["extra_completions"]
                        ]
                    )
                )


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon="📊", layout="wide")
    st.title(PAGE_TITLE)
    refresh_count = _render_auto_refresh(AUTO_REFRESH_MS)
    st.caption(
        f"数据每 5 秒自动刷新 (第 {refresh_count} 次), 随时掌握当前进度"
    )

    with st.sidebar:
        st.header("面板设置")
        db_path = st.text_input("数据库路径", "database/dungeon_progress.db")
        config_dir = st.text_input("配置目录", "configs")
        recent_days = st.slider("最近天数", 3, 30, 7)
        include_special = st.checkbox("包含特殊副本 (每日收集)")
        if st.button("刷新配置缓存"):
            _load_configs_cached.clear()

    if not os.path.exists(db_path):
        st.error(f"未找到数据库文件: {db_path}")
        return

    configs = _load_configs_cached(config_dir)

    db = DungeonProgressDB(db_path)
    try:
        today_records = fetch_today_records(db, include_special=include_special)
        config_progress = build_config_progress(configs, today_records)
        recent_stats = compute_recent_totals(
            db, days=recent_days, include_special=include_special
        )
    finally:
        db.close()

    available_configs = [entry["config_name"] for entry in config_progress]
    selected_configs = st.sidebar.multiselect(
        "筛选职业", options=available_configs, default=available_configs
    )

    st.subheader("今日概览")
    filtered_progress = [
        entry for entry in config_progress if entry["config_name"] in selected_configs
    ]
    summary = summarize_progress(filtered_progress)
    _render_summary(summary)

    st.subheader("最近几天的完成趋势")
    _render_recent_stats(recent_stats)

    st.subheader("今天的区域分布")
    zone_stats = compute_zone_stats(today_records)
    _render_zone_stats(zone_stats)

    st.subheader("今日详细记录")
    _render_today_records(today_records, selected_configs)

    st.subheader("职业详情")
    _render_config_details(config_progress, selected_configs)


if __name__ == "__main__":
    main()
