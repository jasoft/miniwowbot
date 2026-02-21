#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MiniWow 副本助手高密度可观测 TUI 面板。"""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psutil
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Log, Static, Tree
from textual.worker import Worker

from dashboard_runtime_status import build_runtime_rows, load_emulator_sessions
from view_progress_dashboard import (
    build_config_progress,
    fetch_today_records,
    load_configurations,
    summarize_progress,
)

try:
    from database import DungeonProgressDB
except Exception:
    DungeonProgressDB = None


SCRIPT_DIR = Path(__file__).parent
EMULATORS_PATH = SCRIPT_DIR / "emulators.json"
CONFIG_DIR = SCRIPT_DIR / "configs"
DB_PATH = SCRIPT_DIR / "database" / "dungeon_progress.db"


@dataclass
class SessionState:
    """保存会话元信息与运行态。"""

    name: str
    emulator: str
    configs: list[str] = field(default_factory=list)
    log_path: str = ""
    pid: int | None = None


class AutoDungeonTUI(App):
    """MiniWow 副本助手 TUI 主应用。"""

    CSS = """
    Screen {
        background: #141926;
    }

    #dashboard-grid {
        layout: grid;
        grid-size: 1;
        grid-rows: 4 1fr 18 1;
        height: 1fr;
        padding: 0 1;
    }

    #summary-bar {
        layout: horizontal;
        height: 4;
        background: #1c2233;
        border: tall #2f3d5c;
        padding: 0 1;
    }

    .summary-card {
        width: 1fr;
        height: 100%;
        content-align: center middle;
        border-right: solid #2f3d5c;
    }

    .summary-card.last {
        border-right: none;
    }

    #runtime-wrapper {
        border: tall #2f3d5c;
        background: #1b2131;
    }

    #runtime-title {
        height: 1;
        padding: 0 1;
        color: #93c5fd;
    }

    #runtime-monitor {
        height: 1fr;
    }

    #bottom-panels {
        layout: horizontal;
        height: 100%;
    }

    #progress-panel {
        width: 1fr;
        border: tall #2f3d5c;
        background: #1b2131;
        margin-right: 1;
    }

    #log-panel {
        width: 1fr;
        border: tall #2f3d5c;
        background: #1b2131;
    }

    .panel-title {
        height: 1;
        padding: 0 1;
        color: #fcd34d;
    }

    #details-tree {
        height: 1fr;
        padding: 0 1 1 1;
    }

    #log-toolbar {
        height: 3;
        padding: 0 1;
    }

    #session-log {
        height: 1fr;
        border-top: solid #2f3d5c;
    }

    Button {
        margin-right: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "退出"),
        ("r", "refresh_now", "刷新"),
        ("s", "start_selected", "启动"),
        ("x", "stop_selected", "停止"),
    ]

    def __init__(self) -> None:
        """初始化应用状态。"""
        super().__init__()
        self.sessions: dict[str, SessionState] = {}
        self.rows_by_session: dict[str, dict[str, Any]] = {}
        self.row_keys: list[Any] = []
        self.selected_session_name: str | None = None
        self.last_log_text: str = ""
        self.refresh_worker: Worker | None = None

    def compose(self) -> ComposeResult:
        """构建应用布局。"""
        yield Header(show_clock=True)
        with Grid(id="dashboard-grid"):
            with Horizontal(id="summary-bar"):
                yield Static("总完成\n0", id="summary-completed", classes="summary-card")
                yield Static("总计划\n0", id="summary-planned", classes="summary-card")
                yield Static("完成率\n0.0%", id="summary-rate", classes="summary-card")
                yield Static("在线设备\n0", id="summary-online", classes="summary-card")
                yield Static(
                    "活跃配置\n0",
                    id="summary-active-configs",
                    classes="summary-card last",
                )
            with Vertical(id="runtime-wrapper"):
                yield Static("Runtime Monitor", id="runtime-title")
                yield DataTable(id="runtime-monitor", cursor_type="row")
            with Horizontal(id="bottom-panels"):
                with Vertical(id="progress-panel"):
                    yield Static("当前会话进度树", classes="panel-title")
                    yield Tree("未选择会话", id="details-tree")
                with Vertical(id="log-panel"):
                    yield Static("会话实时日志", classes="panel-title")
                    with Horizontal(id="log-toolbar"):
                        yield Button("Start", id="btn-start", variant="success")
                        yield Button("Stop", id="btn-stop", variant="error")
                        yield Button("Refresh", id="btn-refresh", variant="primary")
                        yield Button("Cleanup", id="btn-cleanup", variant="warning")
                    yield Log(id="session-log", highlight=True, auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        """初始化表头并启动后台刷新任务。"""
        table = self.query_one("#runtime-monitor", DataTable)
        table.add_columns(
            "会话",
            "模拟器",
            "状态",
            "运行职业",
            "当前配置",
            "当前副本",
            "进度",
            "错误",
        )
        self._load_sessions()
        self.refresh_worker = self.run_worker(
            self._refresh_loop(),
            name="runtime-refresh-loop",
            exclusive=True,
        )

    def on_unmount(self) -> None:
        """在退出时停止后台任务。"""
        if self.refresh_worker is not None:
            self.refresh_worker.cancel()

    def _load_sessions(self) -> None:
        """加载 emulators.json 并构建本地会话索引。"""
        if not EMULATORS_PATH.exists():
            self.notify(f"未找到会话配置文件: {EMULATORS_PATH}", severity="warning")
            return

        sessions = load_emulator_sessions(str(EMULATORS_PATH))
        self.sessions = {
            s.name: SessionState(
                name=s.name,
                emulator=s.emulator,
                configs=s.configs,
                log_path=s.log_path or f"log/autodungeon_{s.name}.log",
            )
            for s in sessions
        }

        if not self.selected_session_name and self.sessions:
            self.selected_session_name = next(iter(self.sessions))

    async def _refresh_loop(self) -> None:
        """每 2 秒刷新一次运行态与全局汇总。"""
        while True:
            try:
                rows, errors = await asyncio.to_thread(
                    build_runtime_rows,
                    repo_root=str(SCRIPT_DIR),
                    emulators_path=str(EMULATORS_PATH),
                    config_dir=str(CONFIG_DIR),
                    db_path=str(DB_PATH),
                    log_tail_lines=200,
                )
                self.call_from_thread(self._sync_runtime_table, rows)
                self.call_from_thread(self._sync_summary_bar, rows)
                self.call_from_thread(self._sync_selected_views)
                for error in errors:
                    self.call_from_thread(self.notify, error, severity="warning")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.call_from_thread(self.notify, f"刷新运行态失败: {exc}", severity="error")
            await asyncio.sleep(2)

    def _sync_runtime_table(self, rows: list[dict[str, Any]]) -> None:
        """刷新 Runtime Monitor 表格。"""
        table = self.query_one("#runtime-monitor", DataTable)
        table.clear()
        self.row_keys.clear()
        self.rows_by_session = {}

        for row in rows:
            session_name = str(row.get("会话", "")).strip()
            if not session_name:
                continue
            self.rows_by_session[session_name] = row
            row_key = table.add_row(
                session_name,
                row.get("模拟器", "-"),
                row.get("状态", "-"),
                row.get("运行职业", "-"),
                row.get("运行配置", "-"),
                row.get("当前副本", "-"),
                row.get("进度", "-"),
                row.get("错误", ""),
            )
            self.row_keys.append(row_key)

        if not self.selected_session_name and rows:
            self.selected_session_name = str(rows[0].get("会话", "")).strip() or None

        if self.selected_session_name:
            for index, key in enumerate(self.row_keys):
                row_data = table.get_row(key)
                if row_data and row_data[0] == self.selected_session_name:
                    table.cursor_coordinate = (index, 0)
                    break

    def _sync_summary_bar(self, rows: list[dict[str, Any]]) -> None:
        """计算并更新顶部 Summary Bar。"""
        summary = self._build_global_summary()
        online_devices = sum(1 for item in rows if str(item.get("状态", "")).startswith("🟢"))

        self.query_one("#summary-completed", Static).update(f"总完成\n{summary['total_completed']}")
        self.query_one("#summary-planned", Static).update(f"总计划\n{summary['total_planned']}")
        self.query_one("#summary-rate", Static).update(
            f"完成率\n{summary['completion_rate'] * 100:.1f}%"
        )
        self.query_one("#summary-online", Static).update(f"在线设备\n{online_devices}")
        self.query_one("#summary-active-configs", Static).update(
            f"活跃配置\n{summary['active_configs']}"
        )

    def _build_global_summary(self) -> dict[str, Any]:
        """基于数据库与配置构建全局统计。"""
        empty_summary = {
            "total_completed": 0,
            "total_planned": 0,
            "completion_rate": 0.0,
            "active_configs": 0,
        }

        if DungeonProgressDB is None:
            return empty_summary
        if not DB_PATH.exists():
            return empty_summary

        try:
            configs = load_configurations(str(CONFIG_DIR))
            with DungeonProgressDB(db_path=str(DB_PATH)) as db:
                today_records = fetch_today_records(db, include_special=False)
            config_progress = build_config_progress(configs, today_records)
            return summarize_progress(config_progress)
        except Exception as exc:
            self.notify(f"读取全局统计失败: {exc}", severity="warning")
            return empty_summary

    def _sync_selected_views(self) -> None:
        """更新选中会话的树形进度和日志视图。"""
        self._refresh_details_tree()
        self._refresh_log_view()

    def _refresh_details_tree(self) -> None:
        """渲染当前选中会话的配置-区域-副本分层树。"""
        tree = self.query_one("#details-tree", Tree)
        tree.clear()

        if not self.selected_session_name:
            tree.root.set_label("未选择会话")
            tree.root.expand()
            return

        session = self.sessions.get(self.selected_session_name)
        if not session:
            tree.root.set_label(f"会话未定义: {self.selected_session_name}")
            tree.root.expand()
            return

        tree.root.set_label(f"会话: {session.name}")

        if DungeonProgressDB is None or not DB_PATH.exists():
            tree.root.add("数据库不可用，无法加载详细进度")
            tree.root.expand()
            return

        try:
            configs = load_configurations(str(CONFIG_DIR))
            with DungeonProgressDB(db_path=str(DB_PATH)) as db:
                today_records = fetch_today_records(db, include_special=False)
            config_progress = build_config_progress(configs, today_records)
            progress_index = {item.get("config_name", ""): item for item in config_progress}
        except Exception as exc:
            tree.root.add(f"进度读取失败: {exc}")
            tree.root.expand()
            return

        for config_name in session.configs:
            payload = progress_index.get(config_name)
            if not payload:
                tree.root.add(f"{config_name} (无配置或无进度数据)")
                continue

            cfg_done = payload.get("completed_planned", 0)
            cfg_total = payload.get("total_planned", 0)
            config_node = tree.root.add(f"{config_name} [{cfg_done}/{cfg_total}]")

            for zone in payload.get("zones", []):
                zone_name = zone.get("zone_name", "未知区域")
                zone_done = zone.get("completed_count", 0)
                zone_total = zone.get("planned_count", 0)
                zone_node = config_node.add(f"{zone_name} [{zone_done}/{zone_total}]")

                for dungeon in zone.get("dungeons", []):
                    completed = bool(dungeon.get("completed", False))
                    icon = "✅" if completed else "⬜"
                    dungeon_name = dungeon.get("name", "未知副本")
                    zone_node.add(f"{icon} {dungeon_name}")

            config_node.expand()

        tree.root.expand()

    def _refresh_log_view(self) -> None:
        """刷新当前会话日志内容。"""
        log_widget = self.query_one("#session-log", Log)
        if not self.selected_session_name:
            if self.last_log_text != "":
                log_widget.clear()
                self.last_log_text = ""
            return

        row = self.rows_by_session.get(self.selected_session_name, {})
        log_text = str(row.get("_log_text", ""))

        if log_text == self.last_log_text:
            return

        log_widget.clear()
        if log_text:
            for line in log_text.splitlines():
                log_widget.write_line(line)
        else:
            log_widget.write_line("暂无日志，等待输出...")
        self.last_log_text = log_text

    def _find_selected_session(self) -> SessionState | None:
        """获取当前选中的会话对象。"""
        if not self.selected_session_name:
            return None
        return self.sessions.get(self.selected_session_name)

    def _lookup_session_pid(self, session_name: str) -> int | None:
        """按会话名扫描并返回运行中的主进程 PID。"""
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                cmd = " ".join(cmdline)
                if "run_dungeons.py" not in cmd:
                    continue
                if f"--session {session_name}" in cmd:
                    return int(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return None

    @on(DataTable.RowSelected, "#runtime-monitor")
    def on_runtime_row_selected(self, event: DataTable.RowSelected) -> None:
        """当用户选择 Runtime Monitor 行时同步底部详情。"""
        row_data = event.data_table.get_row(event.row_key)
        if not row_data:
            return
        session_name = str(row_data[0]).strip()
        if session_name:
            self.selected_session_name = session_name
            self.last_log_text = ""
            self._sync_selected_views()

    @on(Button.Pressed, "#btn-start")
    def on_start_pressed(self) -> None:
        """启动选中会话。"""
        self.action_start_selected()

    @on(Button.Pressed, "#btn-stop")
    def on_stop_pressed(self) -> None:
        """停止选中会话。"""
        self.action_stop_selected()

    @on(Button.Pressed, "#btn-refresh")
    def on_refresh_pressed(self) -> None:
        """手动触发一次刷新。"""
        self.action_refresh_now()

    @on(Button.Pressed, "#btn-cleanup")
    def on_cleanup_pressed(self) -> None:
        """执行缓存清理命令。"""
        self.action_cleanup_cache()

    def action_refresh_now(self) -> None:
        """立即刷新会话定义并等待下一轮后台更新。"""
        self._load_sessions()
        self.notify("已刷新会话定义")

    def action_start_selected(self) -> None:
        """启动当前选中的会话进程。"""
        session = self._find_selected_session()
        if session is None:
            self.notify("请先在 Runtime Monitor 选择会话", severity="warning")
            return

        if self._lookup_session_pid(session.name):
            self.notify(f"会话 {session.name} 已在运行", severity="warning")
            return

        cmd = [
            "uv",
            "run",
            "python",
            "run_dungeons.py",
            "--emulator",
            session.emulator,
            "--session",
            session.name,
        ]
        for config in session.configs:
            cmd.extend(["--config", config])

        if session.log_path:
            cmd.extend(["--logfile", session.log_path])

        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.notify(f"已启动会话: {session.name}")
        except Exception as exc:
            self.notify(f"启动失败: {exc}", severity="error")

    def action_stop_selected(self) -> None:
        """停止当前选中会话的进程树。"""
        session = self._find_selected_session()
        if session is None:
            self.notify("请先在 Runtime Monitor 选择会话", severity="warning")
            return

        pid = self._lookup_session_pid(session.name)
        if pid is None:
            self.notify(f"会话 {session.name} 当前未运行", severity="warning")
            return

        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
            self.notify(f"已发送停止信号: {session.name} (PID {pid})")
        except Exception as exc:
            self.notify(f"停止失败: {exc}", severity="error")

    def action_cleanup_cache(self) -> None:
        """执行缓存清理脚本。"""
        try:
            subprocess.run(
                ["uv", "run", "python", "cleanup_cache.py"],
                check=False,
                cwd=str(SCRIPT_DIR),
            )
            self.notify("清理命令已执行")
        except Exception as exc:
            self.notify(f"清理失败: {exc}", severity="error")


if __name__ == "__main__":
    AutoDungeonTUI().run()
