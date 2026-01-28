"""Tests for detect_first_match behavior."""

# ruff: noqa: E402

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from levelup import DetectionJob, detect_first_match


def test_detect_first_match_runs_first_truthy_handler():
    events = []

    async def slow_false():
        await asyncio.sleep(0.05)
        return None

    async def fast_true():
        await asyncio.sleep(0.01)
        return "hit"

    job1 = DetectionJob("slow", slow_false, lambda res: events.append(("slow", res)))
    job2 = DetectionJob("fast", fast_true, lambda res: events.append(("fast", res)))

    matched = asyncio.run(detect_first_match([job1, job2]))

    assert matched is not None
    assert matched.name == "fast"
    assert events == [("fast", "hit")]


def test_detect_first_match_waits_until_true():
    called = []

    async def fast_false():
        await asyncio.sleep(0.01)
        return None

    async def slower_true():
        await asyncio.sleep(0.02)
        return "go"

    job_false = DetectionJob("false", fast_false, lambda res: called.append(("false", res)))
    job_true = DetectionJob("true", slower_true, lambda res: called.append(("true", res)))

    matched = asyncio.run(detect_first_match([job_false, job_true]))

    assert matched is not None
    assert matched.name == "true"
    assert called == [("true", "go")]


def test_detect_first_match_returns_none_when_no_match():
    async def always_none():
        await asyncio.sleep(0.01)
        return None

    job = DetectionJob("none", always_none, lambda res: None)
    matched = asyncio.run(detect_first_match([job]))

    assert matched is None
