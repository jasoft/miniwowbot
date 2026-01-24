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
