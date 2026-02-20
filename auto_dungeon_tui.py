#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
MiniWow 副本助手 TUI 控制台
使用方式: uv run --with textual --with psutil python auto_dungeon_tui.py
"""

import asyncio
import json
import subprocess
from datetime import datetime
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
    Select,
    Static,
    TabbedContent,
    TabPane,
)
from textual.worker import Worker

# 导入项目模块
DB_IMPORT_ERROR: Optional[Exception] = None
DASHBOARD_IMPORT_ERROR: Optional[Exception] = None
try:
    from database import DungeonProgressDB
except ImportError as exc:
    DungeonProgressDB = None  # type: ignore[assignment]
    DB_IMPORT_ERROR = exc

try:
    from view_progress_dashboard import (
        build_config_progress,
        fetch_today_records,
        load_configurations,
    )
except ImportError as exc:
    build_config_progress = None  # type: ignore[assignment]
    fetch_today_records = None  # type: ignore[assignment]
    load_configurations = None  # type: ignore[assignment]
    DASHBOARD_IMPORT_ERROR = exc

SCRIPT_DIR = Path(__file__).parent
LOG_DIR = SCRIPT_DIR / "log"
CONFIG_DIR = SCRIPT_DIR / "configs"


class SessionInfo:
    """会话元数据。

    Attributes:
        name: 会话名称。
        emulator: 模拟器地址。
        configs: 该会话关联的配置名列表。
        log_path: 日志文件路径。
        is_running: 当前会话是否运行中。
        pid: 会话对应进程 ID。
    """

    def __init__(self, name: str, emulator: str, configs: List[str], log_path: str):
        """初始化会话信息。

        Args:
            name: 会话名称。
            emulator: 模拟器地址。
            configs: 配置名列表。
            log_path: 相对项目目录的日志路径。
        """
        self.name = name
        self.emulator = emulator
        self.configs = configs
        self.log_path = SCRIPT_DIR / log_path
        self.is_running = False
        self.pid: Optional[int] = None


class AutoDungeonTUI(App):
    """MiniWow 副本助手 TUI 控制台。"""

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
        """初始化 TUI 运行时状态。"""
        super().__init__()
        self.sessions: List[SessionInfo] = []
        self.selected_session: Optional[SessionInfo] = None
        self.selected_config_name: Optional[str] = None
        self.log_watch_task: Optional[asyncio.Task] = None
        self.process_monitor_task: Optional[Worker] = None
        self.db_warning_notified = False
        self.last_refresh_time = "-"

    def on_mount(self) -> None:
        """挂载后初始化会话与界面状态。"""
        self.load_sessions()
        self.refresh_ui()
        self.start_process_monitor()

    def on_unmount(self) -> None:
        """卸载时停止后台任务。"""
        if self.log_watch_task and not self.log_watch_task.done():
            self.log_watch_task.cancel()

        if self.process_monitor_task and self.process_monitor_task.is_running:
            self.process_monitor_task.cancel()

    def load_sessions(self):
        """从 emulators.json 加载会话信息。"""
        try:
            with open(SCRIPT_DIR / "emulators.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                self.sessions = [
                    SessionInfo(
                        s["name"],
                        s["emulator"],
                        s["configs"],
                        s.get("log", f"log/autodungeon_{s['name']}.log"),
                    )
                    for s in data.get("sessions", [])
                ]
        except Exception as e:
            self.notify(f"加载会话失败: {e}", severity="error")

    def compose(self) -> ComposeResult:
        """构建应用布局。"""
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
                        yield Select[str](
                            options=[],
                            prompt="选择配置",
                            allow_blank=True,
                            id="config_select",
                        )
                        yield Log(id="config_view")

        yield Footer()

    def update_session_list(self):
        """更新侧边栏会话列表。"""
        list_view = self.query_one("#session_list", ListView)
        list_view.clear()
        for session in self.sessions:
            status_char = "●" if session.is_running else "○"
            status_class = "session-running" if session.is_running else "session-idle"
            item = ListItem(
                Label(f" {status_char} {session.name}"),
                classes=status_class,
            )
            list_view.append(item)

        if not self.selected_session and self.sessions:
            list_view.index = 0
            self.selected_session = self.sessions[0]

    def update_status_bar(self) -> None:
        """刷新状态栏内容。"""
        status_bar = self.query_one("#status_bar", Static)
        if not self.selected_session:
            status_bar.update(f"会话: 未选择 | 状态: 空闲 | 最后刷新: {self.last_refresh_time}")
            return

        running_text = "运行中" if self.selected_session.is_running else "已停止"
        status_bar.update(
            f"会话: {self.selected_session.name} | 状态: {running_text} | 最后刷新: {self.last_refresh_time}"
        )

    def update_control_buttons(self) -> None:
        """根据会话运行态更新按钮可用性。"""
        start_btn = self.query_one("#btn_start", Button)
        stop_btn = self.query_one("#btn_stop", Button)

        if not self.selected_session:
            start_btn.disabled = True
            stop_btn.disabled = True
            return

        start_btn.disabled = self.selected_session.is_running
        stop_btn.disabled = not self.selected_session.is_running

    def update_config_selector(self) -> None:
        """刷新配置选择器选项。"""
        selector = self.query_one("#config_select", Select)
        if not self.selected_session or not self.selected_session.configs:
            selector.set_options([])
            selector.value = Select.BLANK
            self.selected_config_name = None
            return

        options = [(cfg, cfg) for cfg in self.selected_session.configs]
        selector.set_options(options)
        if self.selected_config_name not in self.selected_session.configs:
            self.selected_config_name = self.selected_session.configs[0]
        selector.value = self.selected_config_name

    def start_process_monitor(self):
        """启动后台进程监控。"""
        self.process_monitor_task = self.run_worker(
            self.monitor_processes(), thread=True, name="monitor"
        )

    async def monitor_processes(self):
        """周期性检查脚本进程状态。"""
        while True:
            # 获取所有 python 进程
            running_sessions: Dict[str, int] = {}
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = proc.info.get("cmdline") or []
                    if not cmdline:
                        continue
                    cmd_str = " ".join(cmdline)
                    # 匹配 run_dungeons.py 或 auto_dungeon.py 及其参数
                    if "run_dungeons.py" in cmd_str or "auto_dungeon.py" in cmd_str:
                        for s in self.sessions:
                            if (
                                f"--session {s.name}" in cmd_str
                                or f"log/autodungeon_{s.name}.log" in cmd_str
                            ):
                                running_sessions[s.name] = proc.info["pid"]
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
        """刷新核心界面状态。"""
        self.last_refresh_time = datetime.now().strftime("%H:%M:%S")
        self.update_session_list()
        self.update_control_buttons()
        self.update_status_bar()
        self.update_config_selector()
        self.update_config_view()
        self.update_dashboard()

    @on(ListView.Selected)
    def on_session_selected(self, event: ListView.Selected):
        """处理会话选择事件。"""
        index = self.query_one("#session_list", ListView).index
        if index is not None and index < len(self.sessions):
            self.selected_session = self.sessions[index]
            self.selected_config_name = None
            self.update_control_buttons()
            self.update_status_bar()
            self.update_dashboard()
            self.update_config_selector()
            self.update_config_view()
            self.start_log_tail()

    @on(Select.Changed, "#config_select")
    def on_config_changed(self, event: Select.Changed) -> None:
        """处理配置选择变更事件。"""
        if event.value == Select.BLANK:
            self.selected_config_name = None
        else:
            self.selected_config_name = str(event.value)
        self.update_config_view()

    def update_dashboard(self):
        """更新进度看板。"""
        if not self.selected_session:
            return

        table = self.query_one("#progress_table", DataTable)
        table.clear(columns=True)
        table.add_columns("配置名称", "今日完成进度", "活跃区域", "状态")

        if not self._is_dashboard_data_available():
            table.add_row("-", "-", "-", "[red]数据库功能不可用[/]")
            return

        try:
            db_path = SCRIPT_DIR / "database" / "dungeon_progress.db"
            with DungeonProgressDB(db_path=str(db_path)) as db:
                config_map = load_configurations(str(CONFIG_DIR))
                today_records = fetch_today_records(db)
                progress_data = build_config_progress(config_map, today_records)
        except Exception as exc:
            self.log(f"更新看板失败: {exc}")
            table.add_row("-", "-", "-", "[red]数据加载失败[/]")
            return

        progress_by_name = {item["config_name"]: item for item in progress_data}
        for cfg_name in self.selected_session.configs:
            item = progress_by_name.get(cfg_name, {})
            total_planned = item.get("total_planned", 0)
            completed_planned = item.get("completed_planned", 0)
            actual_completed = item.get("actual_completed", 0)
            zones = item.get("zones", [])

            done_zones = sum(1 for zone in zones if zone.get("completed_count", 0) > 0)
            progress_text = f"{completed_planned}/{total_planned} (实际:{actual_completed})"
            zones_summary = f"{done_zones}/{len(zones)} 区域"

            if total_planned > 0 and completed_planned >= total_planned:
                status = "[green]已完成[/]"
            elif actual_completed > 0:
                status = "[yellow]进行中[/]"
            else:
                status = "[red]未开始[/]"

            table.add_row(cfg_name, progress_text, zones_summary, status)

    def _is_dashboard_data_available(self) -> bool:
        """检查仪表盘依赖是否可用。"""
        helpers_available = all((load_configurations, fetch_today_records, build_config_progress))
        db_available = DungeonProgressDB is not None
        if helpers_available and db_available:
            return True

        if not self.db_warning_notified:
            detail = str(DB_IMPORT_ERROR or DASHBOARD_IMPORT_ERROR or "缺少看板依赖")
            self.notify(f"进度看板降级: {detail}", severity="warning")
            self.db_warning_notified = True
        return False

    def update_config_view(self):
        """根据当前选择的配置更新预览。"""
        if not self.selected_session:
            return
        view = self.query_one("#config_view", Log)
        view.clear()

        if not self.selected_config_name:
            view.write("[dim]当前会话没有可用配置。[/]")
            return

        cfg_path = CONFIG_DIR / f"{self.selected_config_name}.json"
        if not cfg_path.exists():
            view.write(f"[red]配置文件不存在: {cfg_path}[/]")
            return

        with open(cfg_path, "r", encoding="utf-8") as f:
            view.write(f.read())

    def start_log_tail(self):
        """开始监控日志文件。"""
        if self.log_watch_task:
            self.log_watch_task.cancel()

        log_view = self.query_one("#log_view", Log)
        log_view.clear()

        if self.selected_session:
            self.log_watch_task = asyncio.create_task(
                self.tail_log_file(self.selected_session.log_path)
            )

    async def tail_log_file(self, path: Path):
        """实时监控并输出日志文件内容。

        Args:
            path: 需要跟踪的日志文件路径。
        """
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
        """启动当前选中会话。"""
        if not self.selected_session:
            return
        if self.selected_session.is_running:
            self.notify("会话已在运行中", severity="warning")
            return

        configs_args = []
        for c in self.selected_session.configs:
            configs_args.extend(["--config", c])

        cmd = [
            "uv",
            "run",
            "python",
            "run_dungeons.py",
            "--emulator",
            self.selected_session.emulator,
            "--session",
            self.selected_session.name,
            *configs_args,
        ]

        self.notify(f"正在启动会话: {self.selected_session.name}")

        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                cwd=str(SCRIPT_DIR),
            )
            self.selected_session.is_running = True
            self.refresh_ui()
        except Exception as e:
            self.notify(f"启动失败: {e}", severity="error")

    @on(Button.Pressed, "#btn_stop")
    def action_stop_session(self):
        """停止当前选中会话。"""
        if (
            not self.selected_session
            or not self.selected_session.is_running
            or not self.selected_session.pid
        ):
            self.notify("没有正在运行的进程", severity="warning")
            return

        self.notify(
            f"正在停止会话: {self.selected_session.name} (PID: {self.selected_session.pid})"
        )

        try:
            parent = psutil.Process(self.selected_session.pid)
            children = parent.children(recursive=True)

            for child in children:
                try:
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            _, alive_children = psutil.wait_procs(children, timeout=3)
            for child in alive_children:
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if parent.is_running():
                parent.terminate()
                try:
                    parent.wait(timeout=3)
                except psutil.TimeoutExpired:
                    parent.kill()
                    parent.wait(timeout=3)

            self.notify(f"会话已停止: {self.selected_session.name}")
            self.selected_session.is_running = False
            self.selected_session.pid = None
            self.refresh_ui()
        except psutil.NoSuchProcess:
            self.notify("目标进程不存在，可能已退出", severity="warning")
        except Exception as e:
            self.notify(f"停止进程失败: {e}", severity="error")

    @on(Button.Pressed, "#btn_refresh")
    def action_refresh(self):
        """手动刷新看板与状态栏。"""
        self.refresh_ui()
        self.notify("进度已更新")

    @on(Button.Pressed, "#btn_cleanup")
    def action_cleanup(self):
        """执行缓存清理脚本。"""
        try:
            subprocess.run(
                ["uv", "run", "python", "cleanup_cache.py"],
                check=False,
                cwd=str(SCRIPT_DIR),
            )
            self.notify("缓存已清理")
        except Exception as e:
            self.notify(f"清理失败: {e}", severity="error")

    def action_clear_log(self):
        """清空实时日志面板。"""
        self.query_one("#log_view", Log).clear()


if __name__ == "__main__":
    app = AutoDungeonTUI()
    app.run()
