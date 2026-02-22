import asyncio
import psutil
import sys
import os
import subprocess
import logging
from vibe_colored_logger import setup_logger
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from prometheus_client import CollectorRegistry, Gauge, generate_latest
from starlette.responses import Response

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

logger = setup_logger(__name__)

# Suppress verbose DB connection logs during background scraping
logging.getLogger("database.dungeon_db").setLevel(logging.WARNING)
logging.getLogger("database").setLevel(logging.WARNING)

# Prometheus Metrics
REGISTRY = CollectorRegistry()

# System Metrics
system_online_devices = Gauge("miniwow_online_devices", "Number of online emulators", registry=REGISTRY)
system_active_configs = Gauge("miniwow_active_configs", "Number of active configurations", registry=REGISTRY)

# Progress Metrics
progress_total_completed = Gauge("miniwow_progress_total_completed", "Total completed planned dungeons", registry=REGISTRY)
progress_total_planned = Gauge("miniwow_progress_total_planned", "Total planned dungeons", registry=REGISTRY)
progress_completion_rate = Gauge("miniwow_progress_completion_rate", "Overall completion rate", registry=REGISTRY)

# Session Metrics
session_status = Gauge("miniwow_session_status", "Session status (1=online, 0=offline)", ["session_name", "emulator"], registry=REGISTRY)
session_has_error = Gauge("miniwow_session_has_error", "Session error state (1=error, 0=ok)", ["session_name", "emulator"], registry=REGISTRY)


async def update_metrics_task():
    """Background task to update Prometheus metrics periodically."""
    while True:
        try:
            # Update Session/Runtime Metrics
            rows, errors = await asyncio.to_thread(
                build_runtime_rows,
                repo_root=str(SCRIPT_DIR),
                emulators_path=str(EMULATORS_PATH),
                config_dir=str(CONFIG_DIR),
                db_path=str(DB_PATH),
                log_tail_lines=20, # Minimal lines for metrics
            )
            
            online_count = 0
            for row in rows:
                session_name = str(row.get("会话", "")).strip()
                if not session_name:
                    continue
                
                emulator = str(row.get("模拟器", "-"))
                is_online = 1 if str(row.get("状态", "")).startswith("🟢") else 0
                has_error = 1 if "⚠️" in str(row.get("错误", "")) else 0
                
                if is_online:
                    online_count += 1
                    
                session_status.labels(session_name=session_name, emulator=emulator).set(is_online)
                session_has_error.labels(session_name=session_name, emulator=emulator).set(has_error)
                
            system_online_devices.set(online_count)

            # Update Progress Metrics
            if DungeonProgressDB is not None and DB_PATH.exists():
                configs = load_configurations(str(CONFIG_DIR))
                with DungeonProgressDB(db_path=str(DB_PATH)) as db:
                    today_records = fetch_today_records(db, include_special=True)
                config_progress = build_config_progress(configs, today_records)
                summary = summarize_progress(config_progress)
                
                system_active_configs.set(summary.get("active_configs", 0))
                progress_total_completed.set(summary.get("total_completed", 0))
                progress_total_planned.set(summary.get("total_planned", 0))
                progress_completion_rate.set(summary.get("completion_rate", 0.0))
                
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
            
        await asyncio.sleep(15) # Update metrics every 15 seconds

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    task = asyncio.create_task(update_metrics_task())
    yield
    # Shutdown
    task.cancel()

app = FastAPI(title="MiniWow API Server", lifespan=lifespan)

@app.get("/metrics")
async def metrics():
    """Endpoint for Prometheus scraping."""
    return Response(generate_latest(REGISTRY), media_type="text/plain")

@app.get("/api/v1/status")
async def get_status():
    """Endpoint for TUI to get complete status data."""
    try:
        # Get Runtime Rows
        rows, errors = await asyncio.to_thread(
            build_runtime_rows,
            repo_root=str(SCRIPT_DIR),
            emulators_path=str(EMULATORS_PATH),
            config_dir=str(CONFIG_DIR),
            db_path=str(DB_PATH),
            log_tail_lines=200,
        )
        
        # Get Progress Summary
        summary = {
            "total_completed": 0,
            "total_planned": 0,
            "completion_rate": 0.0,
            "active_configs": 0,
            "ranking": []
        }
        
        config_progress = []
        if DungeonProgressDB is not None and DB_PATH.exists():
            configs = load_configurations(str(CONFIG_DIR))
            with DungeonProgressDB(db_path=str(DB_PATH)) as db:
                today_records = fetch_today_records(db, include_special=True)
            config_progress = build_config_progress(configs, today_records)
            summary = summarize_progress(config_progress)
            
        return {
            "rows": rows,
            "errors": errors,
            "summary": summary,
            "config_progress": config_progress
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


class SessionRequest(BaseModel):
    session_name: str

def _lookup_session_pid(session_name: str) -> int | None:
    """按会话名扫描并返回运行中的主进程 PID。"""
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            cmd = " ".join(cmdline)
            if "run_dungeons.py" not in cmd:
                continue
            if f"--session {session_name}" in cmd or f"--session {session_name}" in " ".join(cmdline):
                return int(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return None

@app.post("/api/v1/start")
async def start_session(req: SessionRequest):
    """启动会话"""
    session_name = req.session_name
    sessions = load_emulator_sessions(str(EMULATORS_PATH))
    session = next((s for s in sessions if s.name == session_name), None)
    
    if not session:
        from fastapi.responses import JSONResponse
        return JSONResponse(content={"error": f"Session {session_name} not found"}, status_code=404)
        
    if _lookup_session_pid(session_name):
        return JSONResponse(content={"error": f"Session {session_name} is already running"}, status_code=400)
        
    cmd = [
        sys.executable,
        "run_dungeons.py",
        "--emulator",
        session.emulator,
        "--session",
        session.name,
    ]
    for config in session.configs:
        cmd.extend(["--config", config])
        
    log_path = session.log_path or f"log/autodungeon_{session.name}.log"
    cmd.extend(["--logfile", log_path])
    
    try:
        if os.name == 'nt':
            # Windows
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008, # DETACHED_PROCESS
                cwd=str(SCRIPT_DIR)
            )
        else:
            # POSIX
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                cwd=str(SCRIPT_DIR)
            )
        return {"message": f"Started session {session_name}"}
    except Exception as exc:
        return JSONResponse(content={"error": f"Failed to start: {exc}"}, status_code=500)

@app.post("/api/v1/stop")
async def stop_session(req: SessionRequest):
    """停止会话"""
    pid = _lookup_session_pid(req.session_name)
    if not pid:
        return JSONResponse(content={"error": f"Session {req.session_name} is not running"}, status_code=400)
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.terminate()
        parent.terminate()
        return {"message": f"Stopped session {req.session_name}"}
    except Exception as exc:
        return JSONResponse(content={"error": f"Failed to stop: {exc}"}, status_code=500)

@app.post("/api/v1/cleanup")
async def cleanup_cache():
    """清理缓存"""
    try:
        subprocess.run(
            ["uv", "run", "python", "cleanup_cache.py"],
            check=False,
            cwd=str(SCRIPT_DIR),
        )
        return {"message": "Cleanup executed successfully"}
    except Exception as exc:
        return JSONResponse(content={"error": f"Cleanup failed: {exc}"}, status_code=500)

if __name__ == "__main__":

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
