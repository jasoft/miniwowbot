import emulator_manager


def test_logger_injection_used_for_adb_warning(monkeypatch):
    class DummyLogger:
        def __init__(self):
            self.records = []

        def info(self, msg, *args, **kwargs):
            self.records.append(("info", msg))

        def warning(self, msg, *args, **kwargs):
            self.records.append(("warning", msg))

        def debug(self, msg, *args, **kwargs):
            self.records.append(("debug", msg))

        def error(self, msg, *args, **kwargs):
            self.records.append(("error", msg))

    dummy = DummyLogger()
    monkeypatch.setattr(emulator_manager, "which", lambda *_: None)

    manager = emulator_manager.EmulatorConnectionManager(logger=dummy)

    assert manager.adb_path == "adb"
    assert any(level == "warning" for level, _ in dummy.records)
