import pytest

import run_dungeons


def test_prevent_system_sleep_calls_kernel32(monkeypatch):
    calls = []

    class DummyKernel32:
        def SetThreadExecutionState(self, flags):
            calls.append(flags)
            return 1

    monkeypatch.setattr(run_dungeons, "_is_windows", lambda: True)
    monkeypatch.setattr(run_dungeons, "_get_kernel32", lambda: DummyKernel32())

    with run_dungeons.prevent_system_sleep():
        pass

    assert len(calls) == 2
    assert calls[0] & run_dungeons.ES_CONTINUOUS
    assert calls[0] & run_dungeons.ES_SYSTEM_REQUIRED
    assert calls[1] == run_dungeons.ES_CONTINUOUS


def test_run_restores_sleep_on_error(monkeypatch):
    calls = []

    def fake_set_sleep_state(keep_awake: bool) -> bool:
        calls.append(keep_awake)
        return True

    def fake_run_configs(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(run_dungeons, "_set_windows_sleep_state", fake_set_sleep_state)
    monkeypatch.setattr(run_dungeons, "run_configs", fake_run_configs)

    with pytest.raises(RuntimeError):
        run_dungeons.run(
            emulator="127.0.0.1:5555",
            session="test",
            config=["mage"],
            retries=1,
            logfile=None,
        )

    assert calls and calls[-1] is False


def test_run_restores_sleep_on_keyboard_interrupt(monkeypatch):
    calls = []

    def fake_set_sleep_state(keep_awake: bool) -> bool:
        calls.append(keep_awake)
        return True

    def fake_run_configs(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(run_dungeons, "_set_windows_sleep_state", fake_set_sleep_state)
    monkeypatch.setattr(run_dungeons, "run_configs", fake_run_configs)

    with pytest.raises(KeyboardInterrupt):
        run_dungeons.run(
            emulator="127.0.0.1:5555",
            session="test",
            config=["mage"],
            retries=1,
            logfile=None,
        )

    assert calls and calls[-1] is False
