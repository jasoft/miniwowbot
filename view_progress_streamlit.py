#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""使用 Streamlit 展示副本进度的可视化页面。"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from dashboard_runtime_status import render_runtime_monitor
from database import DungeonProgressDB
from view_progress_dashboard import (
    build_config_progress,
    compute_recent_totals,
    compute_zone_stats,
    compute_snapshot_hash,
    fetch_today_records,
    load_configurations,
    summarize_progress,
)
from wow_class_colors import get_class_hex_color


PAGE_TITLE = "副本进度监控面板"
AUTO_REFRESH_MS = 5000


@st.cache_data(ttl=30)
def _load_configs_cached(config_dir: str):
    return load_configurations(config_dir)


@st.cache_resource(show_spinner=False)
def _get_db(db_path: str) -> DungeonProgressDB:
    return DungeonProgressDB(db_path)


def _render_auto_refresh(interval_ms: int = AUTO_REFRESH_MS) -> int:
    """使用 streamlit-autorefresh 保持 5 秒刷新节奏。"""
    return st_autorefresh(interval=interval_ms, limit=None, key="progress_autorefresh")


def _class_label(config_name: str, class_name: str | None) -> str:
    color = get_class_hex_color(class_name)
    class_display = class_name or "未知"
    return f"<span style='color:{color}; font-weight:600'>{config_name} ({class_display})</span>"


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
        ranking_lines = []
        for idx, item in enumerate(ranking, 1):
            colored_label = _class_label(item["config_name"], item.get("class_name"))
            line_html = (
                f"<div style='margin-bottom: 4px;'>"
                f"{idx}. {colored_label} — 已完成 {item['completed']} / 需完成 {item.get('total_planned', 0)}"
                f"</div>"
            )
            ranking_lines.append(line_html)
        st.markdown("".join(ranking_lines), unsafe_allow_html=True)


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
    st.dataframe(pd.DataFrame(table), hide_index=True, width='stretch')


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
            st.markdown(
                _class_label(config["config_name"], config.get("class_name")),
                unsafe_allow_html=True,
            )
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
                    delta=f"{ratio * 100:.0f}%",
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


def _render_dashboard(context: dict) -> None:
    st.subheader("今日概览")
    _render_summary(context["summary"])

    st.subheader("最近几天的完成趋势")
    _render_recent_stats(context["recent_stats"])

    st.subheader("今天的区域分布")
    _render_zone_stats(context["zone_stats"])

    st.subheader("今日详细记录")
    _render_today_records(context["today_records"], context["selected_configs"])

    st.subheader("职业详情")
    _render_config_details(context["config_progress"], context["selected_configs"])


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon="📊", layout="wide")
    st.title(PAGE_TITLE)

    with st.sidebar:
        st.header("面板设置")
        auto_refresh = st.checkbox("自动刷新", value=True)
        refresh_ms = st.number_input(
            "刷新间隔 (ms)",
            min_value=1000,
            max_value=60000,
            value=AUTO_REFRESH_MS,
            step=1000,
        )
        emulators_path = st.text_input("模拟器配置路径", "emulators.json")
        log_tail_lines = st.slider("日志预览行数", 50, 1000, 200, step=50)

        db_path = st.text_input("数据库路径", "database/dungeon_progress.db")
        config_dir = st.text_input("配置目录", "configs")
        recent_days = st.slider("最近天数", 3, 30, 7)
        include_special = st.checkbox("包含特殊副本 (每日收集)")
        if st.button("刷新配置缓存"):
            _load_configs_cached.clear()

    refresh_count = 0
    if auto_refresh:
        refresh_count = _render_auto_refresh(int(refresh_ms))
        st.caption(f"数据每 {int(refresh_ms) // 1000} 秒自动刷新 (第 {refresh_count} 次)")
    else:
        st.caption("自动刷新已关闭")

    render_runtime_monitor(
        emulators_path=emulators_path,
        config_dir=config_dir,
        db_path=db_path,
        refresh_interval_ms=int(refresh_ms),
        log_tail_lines=int(log_tail_lines),
    )
    st.divider()

    if not os.path.exists(db_path):
        st.error(f"未找到数据库文件: {db_path}")
        return

    configs = _load_configs_cached(config_dir)

    db = _get_db(db_path)
    today_records = fetch_today_records(db, include_special=include_special)
    config_progress = build_config_progress(configs, today_records)
    recent_stats = compute_recent_totals(
        db, days=recent_days, include_special=include_special
    )

    available_configs = [entry["config_name"] for entry in config_progress]
    selected_configs = st.sidebar.multiselect(
        "筛选职业", options=available_configs, default=available_configs
    )

    filtered_progress = [
        entry for entry in config_progress if entry["config_name"] in selected_configs
    ]
    summary = summarize_progress(filtered_progress)
    zone_stats = compute_zone_stats(today_records)

    selected_configs_sorted = sorted(selected_configs)
    snapshot_payload = {
        "records": today_records,
        "progress": config_progress,
        "recent_stats": recent_stats,
        "zone_stats": zone_stats,
        "filters": {
            "selected_configs": selected_configs_sorted,
            "include_special": include_special,
            "recent_days": recent_days,
            "db_path": db_path,
            "config_dir": config_dir,
        },
    }
    current_hash = compute_snapshot_hash(snapshot_payload)
    previous_hash = st.session_state.get("progress_snapshot_hash")

    render_context = {
        "summary": summary,
        "recent_stats": recent_stats,
        "zone_stats": zone_stats,
        "today_records": today_records,
        "config_progress": config_progress,
        "selected_configs": selected_configs_sorted,
    }

    if previous_hash != current_hash or "progress_render_data" not in st.session_state:
        st.session_state["progress_snapshot_hash"] = current_hash
        st.session_state["progress_render_data"] = render_context
    else:
        render_context = st.session_state["progress_render_data"]

    _render_dashboard(render_context)


if __name__ == "__main__":
    main()
