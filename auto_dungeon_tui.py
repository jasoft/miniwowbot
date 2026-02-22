#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MiniWow 副本助手高密度可观测 TUI 面板。"""

from __future__ import annotations

import asyncio
import json
import hashlib
import os
from dotenv import load_dotenv
import httpx
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Log, RichLog, Static, Tree
from textual.worker import Worker

from dashboard_runtime_status import load_emulator_sessions

try:
    from database import DungeonProgressDB
except Exception:
    DungeonProgressDB = None



load_dotenv()
API_BASE_URL = os.getenv("MINIWOW_API_URL", "http://127.0.0.1:8000").rstrip("/")

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
        grid-rows: 4 1fr 12 10;
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
        width: 2fr;
        border: tall #2f3d5c;
        background: #1b2131;
    }
    
    #interaction-panel {
        margin-top: 1;
        border: tall #2f3d5c;
        background: #1b2131;
        height: 100%;
    }
    
    #interaction-log {
        height: 1fr;
        border-top: solid #2f3d5c;
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
            with Vertical(id="interaction-panel"):
                yield Static("系统交互日志", classes="panel-title")
                yield RichLog(id="interaction-log", highlight=True, markup=True, auto_scroll=True)
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


    def log_interaction(self, message: str, level: str = "INFO") -> None:
        """将交互日志写入交互面板"""
        from datetime import datetime
        now = datetime.now().strftime("%H:%M:%S")
        log_widget = self.query_one("#interaction-log", RichLog)
        
        # Use Vibe Logger style emojis
        emoji = "ℹ️"
        color = "cyan"
        if level == "ERROR":
            color = "red"
            emoji = "❌"
        elif level == "WARNING":
            color = "yellow"
            emoji = "⚠️"
        elif level == "SUCCESS":
            color = "green"
            emoji = "✅"
            
        log_widget.write(f"[dim]{now}[/dim] [{color}]{emoji} {level}[/{color}] {message}")
        
    def notify(self, message: str, *, title: str = "", severity: str = "information", timeout: float = 3.0) -> None:
        super().notify(message, title=title, severity=severity, timeout=timeout)
        self.log_interaction(message, severity.upper())

    async def _refresh_loop(self) -> None:
        """每 2 秒刷新一次运行态与全局汇总。"""
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    response = await client.get(f"{API_BASE_URL}/api/v1/status", timeout=5.0)
                    response.raise_for_status()
                    data = response.json()
                    
                    rows = data.get("rows", [])
                    errors = data.get("errors", [])
                    summary = data.get("summary", {})
                    config_progress = data.get("config_progress", [])
                    
                    self.current_summary = summary
                    self.current_config_progress = config_progress
                    
                    self._sync_runtime_table(rows)
                    self._sync_summary_bar(rows)
                    self._sync_selected_views()
                    
                    for error in errors:
                        self.notify(error, severity="warning")
                        
                except httpx.RequestError as exc:
                    self.notify(f"API请求失败: {exc}", severity="error")
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    self.notify(f"刷新运行态失败: {exc}", severity="error")
                await asyncio.sleep(2)


    def _compute_hash(self, data: Any) -> str:
        return hashlib.md5(json.dumps(data, sort_keys=True, default=str, ensure_ascii=False).encode('utf-8')).hexdigest()

    def _sync_runtime_table(self, rows: list[dict[str, Any]]) -> None:
        """刷新 Runtime Monitor 表格（非破坏性更新）。"""
        table = self.query_one("#runtime-monitor", DataTable)
        
        # Check if row structure changed
        new_sessions = [str(r.get("会话", "")).strip() for r in rows if str(r.get("会话", "")).strip()]
        current_sessions = [table.get_row(key)[0] for key in self.row_keys] if self.row_keys else []
        
        self.rows_by_session = {str(r.get("会话", "")).strip(): r for r in rows if str(r.get("会话", "")).strip()}
        
        if current_sessions != new_sessions:
            table.clear()
            self.row_keys.clear()
            for row in rows:
                session_name = str(row.get("会话", "")).strip()
                if not session_name:
                    continue
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
        else:
            # Inline update to avoid jumping
            cols = table.columns
            col_keys = list(cols.keys())
            for i, row in enumerate(rows):
                key = self.row_keys[i]
                table.update_cell(key, col_keys[1], row.get("模拟器", "-"))
                table.update_cell(key, col_keys[2], row.get("状态", "-"))
                table.update_cell(key, col_keys[3], row.get("运行职业", "-"))
                table.update_cell(key, col_keys[4], row.get("运行配置", "-"))
                table.update_cell(key, col_keys[5], row.get("当前副本", "-"))
                table.update_cell(key, col_keys[6], row.get("进度", "-"))
                table.update_cell(key, col_keys[7], row.get("错误", ""))


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
        """基于API返回的数据构建全局统计。"""
        empty_summary = {
            "total_completed": 0,
            "total_planned": 0,
            "completion_rate": 0.0,
            "active_configs": 0,
        }
        return getattr(self, "current_summary", empty_summary)

    def _sync_selected_views(self) -> None:
        """更新选中会话的树形进度和日志视图。"""
        self._refresh_details_tree()
        self._refresh_log_view()

    def _refresh_details_tree(self) -> None:
        """渲染当前选中会话的配置-区域-副本分层树。"""
        tree = self.query_one("#details-tree", Tree)
        
        # Determine if data actually changed to avoid thrashing Tree
        config_progress = getattr(self, "current_config_progress", [])
        current_data_hash = self._compute_hash(config_progress) + str(self.selected_session_name)
        if getattr(self, "last_tree_hash", "") == current_data_hash:
            return
        self.last_tree_hash = current_data_hash
        
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

        config_progress = getattr(self, "current_config_progress", [])
        if not config_progress:
            tree.root.add("等待API数据...")
            tree.root.expand()
            return
            
        progress_index = {item.get("config_name", ""): item for item in config_progress}

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
            if getattr(self, "last_log_text", "") != "":
                log_widget.clear()
                self.last_log_text = ""
            return

        row = self.rows_by_session.get(self.selected_session_name, {})
        log_text = str(row.get("_log_text", ""))

        if log_text == getattr(self, "last_log_text", ""):
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
    async def on_start_pressed(self) -> None:
        """启动选中会话。"""
        await self.action_start_selected()

    @on(Button.Pressed, "#btn-stop")
    async def on_stop_pressed(self) -> None:
        """停止选中会话。"""
        await self.action_stop_selected()

    @on(Button.Pressed, "#btn-refresh")
    def on_refresh_pressed(self) -> None:
        """手动触发一次刷新。"""
        self.action_refresh_now()

    @on(Button.Pressed, "#btn-cleanup")
    async def on_cleanup_pressed(self) -> None:
        """执行缓存清理命令。"""
        await self.action_cleanup_cache()

    def action_refresh_now(self) -> None:
        """立即刷新会话定义并等待下一轮后台更新。"""
        self._load_sessions()
        self.notify("已刷新会话定义")

    async def action_start_selected(self) -> None:
        """启动当前选中的会话进程 (通过远端 API)。"""
        session = self._find_selected_session()
        if session is None:
            self.notify("请先在 Runtime Monitor 选择会话", severity="warning")
            return

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{API_BASE_URL}/api/v1/start",
                    json={"session_name": session.name},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    self.notify(f"已请求启动会话: {session.name}")
                else:
                    self.notify(f"启动失败: {resp.json().get('error', resp.text)}", severity="error")
        except Exception as exc:
            self.notify(f"请求API失败: {exc}", severity="error")

    async def action_stop_selected(self) -> None:
        """停止当前选中会话的进程树 (通过远端 API)。"""
        session = self._find_selected_session()
        if session is None:
            self.notify("请先在 Runtime Monitor 选择会话", severity="warning")
            return

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{API_BASE_URL}/api/v1/stop",
                    json={"session_name": session.name},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    self.notify(f"已请求停止会话: {session.name}")
                else:
                    self.notify(f"停止失败: {resp.json().get('error', resp.text)}", severity="warning")
        except Exception as exc:
            self.notify(f"请求API失败: {exc}", severity="error")

    async def action_cleanup_cache(self) -> None:
        """执行缓存清理命令 (通过远端 API)。"""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{API_BASE_URL}/api/v1/cleanup", timeout=10.0)
                if resp.status_code == 200:
                    self.notify("已发送命令: Cleanup (清理缓存)", severity="success")
                else:
                    self.notify(f"清理失败: {resp.json().get('error', resp.text)}", severity="error")
        except Exception as exc:
            self.notify(f"请求API失败: {exc}", severity="error")


if __name__ == "__main__":
    AutoDungeonTUI().run()
