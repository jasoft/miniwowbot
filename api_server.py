import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import CollectorRegistry, Gauge, generate_latest
from starlette.responses import Response

from dashboard_runtime_status import build_runtime_rows
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                    today_records = fetch_today_records(db, include_special=False)
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
                today_records = fetch_today_records(db, include_special=False)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
