"""升级行为树引擎的配置助手。"""

from __future__ import annotations

from airtest.core.settings import Settings as ST

BARK_URL = "https://api.day.app/LkBmavbbbYqtmjDLVvsbMR"
TASK_TIMEOUT = 120
FAST_SCAN_INTERVAL = 0.2
WORKFLOW_SCAN_INTERVAL = 1.0
DECISION_INTERVAL = 0.1


def configure_airtest() -> None:
    """配置 Airtest CV 策略和超时时间。"""
    ST.CVSTRATEGY = ["mstpl", "tpl"]
    ST.FIND_TIMEOUT = 10  # type: ignore[assignment]
    ST.FIND_TIMEOUT_TMP = 0.1  # type: ignore[assignment]