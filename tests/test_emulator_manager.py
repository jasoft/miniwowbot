import pytest

import emulator_manager


def test_initialize_uses_default_ocr_limits(monkeypatch):
    called = {}

    def fake_ocr_helper(*args, **kwargs):
        called["kwargs"] = kwargs
        class DummyOCR:
            pass
        return DummyOCR()

    monkeypatch.setattr(emulator_manager, "OCRHelper", fake_ocr_helper)
    monkeypatch.setattr(emulator_manager, "auto_setup", lambda *_: None)
    monkeypatch.setattr(emulator_manager, "snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(emulator_manager, "GameActions", lambda *args, **kwargs: object())

    manager = emulator_manager.EmulatorManager()
    manager.initialize(emulator_name=None, correction_map={"a": "b"})

    assert called["kwargs"]["max_cache_size"] == 200
    assert called["kwargs"]["max_width"] == 960
    assert called["kwargs"]["correction_map"] == {"a": "b"}
