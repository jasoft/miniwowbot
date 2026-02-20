#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
MiniWow 副本助手 TUI 控制台
使用方式: uv run --with textual --with psutil python auto_dungeon_tui.py
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import psutil
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    Log,
    Static,
    TabbedContent,
    TabPane,
)
from textual.worker import Worker

# 导入项目模块
try:
    from database import DungeonProgressDB
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).parent
LOG_DIR = SCRIPT_DIR / "log"
CONFIG_DIR = SCRIPT_DIR / "configs"


class SessionInfo:
    def __init__(self, name: str, emulator: str, configs: List[str], log_path: str):
        self.name = name
        self.emulator = emulator
        self.configs = configs
        self.log_path = SCRIPT_DIR / log_path
        self.is_running = False
        self.pid: Optional[int] = None


class AutoDungeonTUI(App):
    """MiniWow 副本助手 TUI 控制台"""

    CSS = """
    Screen {
        background: #1a1b26;
    }

    #sidebar {
        width: 30;
        background: #24283b;
        border-right: solid #414868;
    }

    #main_content {
        padding: 1;
    }

    .session-item {
        padding: 1;
    }

    .session-running {
        color: #9ece6a;
        text-style: bold;
    }

    .session-idle {
        color: #565f89;
    }

    Log {
        background: #1a1b26;
        color: #c0caf5;
        border: solid #414868;
        height: 1fr;
    }

    DataTable {
        height: 1fr;
        border: solid #414868;
    }

    #controls {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        background: #24283b;
        border: solid #414868;
    }

    Button {
        margin-right: 1;
    }

    #status_bar {
        height: 1;
        background: #414868;
        color: #c0caf5;
        padding-left: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "退出"),
        ("r", "refresh", "刷新状态"),
        ("s", "start_session", "启动会话"),
        ("x", "stop_session", "停止会话"),
        ("l", "clear_log", "清空日志"),
    ]

    def __init__(self):
        super().__init__()
        self.sessions: List[SessionInfo] = []
        self.selected_session: Optional[SessionInfo] = None
        self.log_watch_task: Optional[asyncio.Task] = None
        self.process_monitor_task: Optional[Worker] = None

    def on_mount(self) -> None:
        self.load_sessions()
        self.update_session_list()
        self.start_process_monitor()

    def load_sessions(self):
        """从 emulators.json 加载会话信息"""
        try:
            with open(SCRIPT_DIR / "emulators.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                self.sessions = [
                    SessionInfo(
                        s["name"], s["emulator"], s["configs"], s.get("log", f"log/autodungeon_{s['name']}.log")
                    )
                    for s in data.get("sessions", [])
                ]
        except Exception as e:
            self.notify(f"加载会话失败: {e}", severity="error")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Label(" [bold]会话列表[/]", variant="info")
                yield ListView(id="session_list")
                yield Static(id="status_bar")

            with Container(id="main_content"):
                with Vertical(id="controls"):
                    with Horizontal():
                        yield Button("启动会话", variant="success", id="btn_start")
                        yield Button("停止会话", variant="error", id="btn_stop")
                        yield Button("刷新进度", variant="primary", id="btn_refresh")
                        yield Button("清理缓存", variant="warning", id="btn_cleanup")

                with TabbedContent():
                    with TabPane("进度看板", id="tab_dashboard"):
                        yield DataTable(id="progress_table")
                    with TabPane("实时日志", id="tab_logs"):
                        yield Log(id="log_view", highlight=True)
                    with TabPane("配置预览", id="tab_config"):
                        yield Log(id="config_view")

        yield Footer()

    def update_session_list(self):
        """更新侧边栏会话列表"""
        list_view = self.query_one("#session_list", ListView)
        list_view.clear()
        for session in self.sessions:
            status_char = "●" if session.is_running else "○"
            status_class = "session-running" if session.is_running else "session-idle"
            item = ListItem(
                Label(f" {status_char} {session.name}"),
                classes=status_class,
                id=f"session_{session.name}"
            )
            list_view.append(item)

        if not self.selected_session and self.sessions:
            list_view.index = 0
            self.selected_session = self.sessions[0]

    def start_process_monitor(self):
        """启动后台进程监控"""
        self.process_monitor_task = self.run_worker(self.monitor_processes(), thread=True, name="monitor")

    async def monitor_processes(self):
        """周期性检查脚本进程状态"""
        while True:
            # 获取所有 python 进程
            running_sessions: Dict[str, int] = {}
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline') or []
                    if not cmdline:
                        continue
                    cmd_str = " ".join(cmdline)
                    # 匹配 run_dungeons.py 或 auto_dungeon.py 及其参数
                    if "run_dungeons.py" in cmd_str or "auto_dungeon.py" in cmd_str:
                        for s in self.sessions:
                            if f"--session {s.name}" in cmd_str or f"log/autodungeon_{s.name}.log" in cmd_str:
                                running_sessions[s.name] = proc.info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # 更新 session 状态
            changed = False
            for s in self.sessions:
                was_running = s.is_running
                s.is_running = s.name in running_sessions
                s.pid = running_sessions.get(s.name)
                if was_running != s.is_running:
                    changed = True

            if changed:
                self.call_from_thread(self.refresh_ui)

            await asyncio.sleep(2)

    def refresh_ui(self):
        self.update_session_list()
        self.update_dashboard()

    @on(ListView.Selected)
    def on_session_selected(self, event: ListView.Selected):
        index = self.query_one("#session_list", ListView).index
        if index is not None and index < len(self.sessions):
            self.selected_session = self.sessions[index]
            self.update_dashboard()
            self.update_config_view()
            self.start_log_tail()

    def update_dashboard(self):
        """更新进度看板"""
        if not self.selected_session:
            return

        table = self.query_one("#progress_table", DataTable)
        table.clear(columns=True)
        table.add_columns("配置名称", "今日完成进度", "活跃区域", "状态")

        try:
            db_path = SCRIPT_DIR / "database" / "dungeon_progress.db"
            with DungeonProgressDB(db_path=str(db_path)) as db:
                for cfg_name in self.selected_session.configs:
                    stats = db.get_config_stats(cfg_name)
                    total = stats["total_count"]
                    
                    # 获取该配置预期的副本总数
                    expected_total = 0
                    try:
                        with open(CONFIG_DIR / f"{cfg_name}.json", "r", encoding="utf-8") as f:
                            cfg_data = json.load(f)
                            zones = cfg_data.get("zone_dungeons", {})
                            for dungeons in zones.values():
                                for d in dungeons:
                                    if isinstance(d, dict) and d.get("selected", True):
                                        expected_total += 1
                                    elif isinstance(d, str):
                                        expected_total += 1
                    except Exception:
                        pass

                    progress_text = f"{total}/{expected_total}" if expected_total > 0 else str(total)
                    
                    # 区域分布简述
                    zones_summary = ", ".join([f"{z}:{c}" for z, c in stats["zone_stats"][:3]])
                    
                    if expected_total > 0 and total >= expected_total:
                        status = "[green]已完成[/]"
                    elif total > 0:
                        status = "[yellow]进行中[/]"
                    else:
                        status = "[red]未开始[/]"

                    table.add_row(cfg_name, progress_text, zones_summary, status)
        except Exception as e:
            self.log(f"更新看板失败: {e}")

    def update_config_view(self):
        """更新配置预览"""
        if not self.selected_session:
            return
        view = self.query_one("#config_view", Log)
        view.clear()
        
        # 默认显示第一个配置
        if self.selected_session.configs:
            cfg_name = self.selected_session.configs[0]
            cfg_path = CONFIG_DIR / f"{cfg_name}.json"
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    view.write(content)

    def start_log_tail(self):
        """开始监控日志文件"""
        if self.log_watch_task:
            self.log_watch_task.cancel()
        
        log_view = self.query_one("#log_view", Log)
        log_view.clear()
        
        if self.selected_session:
            self.log_watch_task = asyncio.create_task(self.tail_log_file(self.selected_session.log_path))

    async def tail_log_file(self, path: Path):
        """监控文件内容"""
        log_view = self.query_one("#log_view", Log)
        
        if not path.exists():
            log_view.write(f"[dim]等待日志文件生成: {path}[/]")
        
        # 先读取最后 100 行
        if path.exists():
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                for line in lines[-100:]:
                    log_view.write(line.rstrip())

        # 持续监控
        last_size = path.stat().st_size if path.exists() else 0
        while True:
            try:
                if path.exists():
                    current_size = path.stat().st_size
                    if current_size > last_size:
                        with open(path, "r", encoding="utf-8", errors="replace") as f:
                            f.seek(last_size)
                            new_data = f.read()
                            if new_data:
                                log_view.write(new_data.rstrip())
                            last_size = current_size
                    elif current_size < last_size:
                        last_size = 0
                        log_view.clear()
                        log_view.write("[yellow]--- 日志文件已重置 ---[/]")
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log(f"读取日志错误: {e}")
                await asyncio.sleep(2)

    @on(Button.Pressed, "#btn_start")
    def action_start_session(self):
        if not self.selected_session:
            return
        if self.selected_session.is_running:
            self.notify("会话已在运行中", severity="warning")
            return

        configs_args = []
        for c in self.selected_session.configs:
            configs_args.extend(["--config", c])
        
        cmd = [
            "uv", "run", "python", "run_dungeons.py",
            "--emulator", self.selected_session.emulator,
            "--session", self.selected_session.name,
            *configs_args
        ]
        
        self.notify(f"正在启动会话: {self.selected_session.name}")
        
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        except Exception as e:
            self.notify(f"启动失败: {e}", severity="error")

    @on(Button.Pressed, "#btn_stop")
    def action_stop_session(self):
        if not self.selected_session or not self.selected_session.is_running or not self.selected_session.pid:
            self.notify("没有正在运行的进程", severity="warning")
            return

        self.notify(f"正在停止会话: {self.selected_session.name} (PID: {self.selected_session.pid})")
        
        try:
            parent = psutil.Process(self.selected_session.pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
        except Exception as e:
            self.notify(f"停止进程失败: {e}", severity="error")

    @on(Button.Pressed, "#btn_refresh")
    def action_refresh(self):
        self.update_dashboard()
        self.notify("进度已更新")

    @on(Button.Pressed, "#btn_cleanup")
    def action_cleanup(self):
        try:
            subprocess.run(["uv", "run", "python", "cleanup_cache.py"], check=False)
            self.notify("缓存已清理")
        except Exception as e:
            self.notify(f"清理失败: {e}", severity="error")

    def action_clear_log(self):
        self.query_one("#log_view", Log).clear()

if __name__ == "__main__":
    app = AutoDungeonTUI()
    app.run()
