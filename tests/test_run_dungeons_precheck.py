"""Tests for run_dungeons precheck behavior."""

from __future__ import annotations

import json
from pathlib import Path

import run_dungeons


def _write_config(tmp_path: Path, name: str) -> Path:
    """Create a minimal config file for testing.

    Args:
        tmp_path: Temporary directory root.
        name: Config name without extension.

    Returns:
        Path to the created config file.
    """
    config_dir = tmp_path / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"{name}.json"
    payload = {
        "zone_dungeons": {
            "ZoneA": [
                {"name": "DungeonA", "selected": True},
            ]
        }
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path


def _make_db_class(completed_count: int):
    """Build a dummy DungeonProgressDB class with a fixed completion count.

    Args:
        completed_count: Completed dungeon count to report.

    Returns:
        Dummy database class.
    """

    class DummyDB:
        """Dummy DB for precheck tests."""

        def __init__(self, config_name: str, db_path: str = "database/dungeon_progress.db"):
            self.config_name = config_name
            self.db_path = db_path

        def cleanup_old_records(self, days_to_keep: int = 7) -> None:
            """No-op cleanup."""
            return None

        def get_today_completed_count(self, include_special: bool = False) -> int:
            """Return the fixed completion count."""
            return completed_count

        def __enter__(self) -> "DummyDB":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    return DummyDB


def test_run_configs_skips_emulator_when_completed(monkeypatch, tmp_path):
    """Skip emulator startup when tasks are already completed."""
    _write_config(tmp_path, "test")
    monkeypatch.setattr(run_dungeons, "SCRIPT_DIR", tmp_path)
    monkeypatch.setattr(run_dungeons, "_is_windows", lambda: False)
    monkeypatch.setattr(run_dungeons, "DungeonProgressDB", _make_db_class(1))

    calls = {"ensure": 0, "invoke": 0}

    def fake_ensure(_emulator: str, _logger) -> bool:
        calls["ensure"] += 1
        return True

    def fake_invoke(_config_name: str, _emulator: str, _session: str) -> int:
        calls["invoke"] += 1
        return 0

    monkeypatch.setattr(run_dungeons, "_ensure_emulator_ready", fake_ensure)
    monkeypatch.setattr(run_dungeons, "_invoke_auto_dungeon_once", fake_invoke)

    rc = run_dungeons.run_configs(
        configs=["test"],
        emulator="127.0.0.1:5555",
        session="session",
        retries=1,
        logfile=None,
        dryrun=False,
    )

    assert rc == 0
    assert calls["ensure"] == 0
    assert calls["invoke"] == 0


def test_run_configs_starts_emulator_when_pending(monkeypatch, tmp_path):
    """Start emulator when there are pending tasks."""
    _write_config(tmp_path, "test")
    monkeypatch.setattr(run_dungeons, "SCRIPT_DIR", tmp_path)
    monkeypatch.setattr(run_dungeons, "_is_windows", lambda: False)
    monkeypatch.setattr(run_dungeons, "DungeonProgressDB", _make_db_class(0))

    calls = {"ensure": 0, "invoke": 0}

    def fake_ensure(_emulator: str, _logger) -> bool:
        calls["ensure"] += 1
        return True

    def fake_invoke(_config_name: str, _emulator: str, _session: str) -> int:
        calls["invoke"] += 1
        return 0

    monkeypatch.setattr(run_dungeons, "_ensure_emulator_ready", fake_ensure)
    monkeypatch.setattr(run_dungeons, "_invoke_auto_dungeon_once", fake_invoke)

    rc = run_dungeons.run_configs(
        configs=["test"],
        emulator="127.0.0.1:5555",
        session="session",
        retries=1,
        logfile=None,
        dryrun=False,
    )

    assert rc == 0
    assert calls["ensure"] == 1
    assert calls["invoke"] == 1
