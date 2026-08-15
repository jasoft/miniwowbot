"""升级行为树引擎的配置助手。"""

from __future__ import annotations

import os
from pathlib import Path

from airtest.core.settings import Settings as ST


# 无论从哪个工作目录启动，都加载项目根目录的本地环境文件。
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(_ENV_PATH)
elif _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _value = _line.split("=", 1)
            os.environ.setdefault(_key.strip(), _value.strip())

BARK_URL = os.environ.get("BARK_SERVER", "").rstrip("/")
TASK_TIMEOUT = 120
FAST_SCAN_INTERVAL = 0.2
WORKFLOW_SCAN_INTERVAL = 1.0
DECISION_INTERVAL = 0.1


def configure_airtest() -> None:
    """配置 Airtest CV 策略和超时时间。"""
    ST.CVSTRATEGY = ["mstpl", "tpl"]
    ST.FIND_TIMEOUT = 10  # type: ignore[assignment]
    ST.FIND_TIMEOUT_TMP = 0.1  # type: ignore[assignment]
