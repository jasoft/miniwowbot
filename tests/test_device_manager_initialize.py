import pytest

pytest.importorskip("airtest.core.api")
pytest.importorskip("vibe_ocr")

import auto_dungeon_device


def test_initialize_uses_default_ocr_limits(monkeypatch):
    called = {}

    def fake_ocr_helper(*args, **kwargs):
        called["kwargs"] = kwargs

        class DummyOCR:
            pass

        return DummyOCR()

    monkeypatch.setattr(auto_dungeon_device, "OCRHelper", fake_ocr_helper)
    monkeypatch.setattr(auto_dungeon_device, "auto_setup", lambda *_: None)
    monkeypatch.setattr(auto_dungeon_device, "snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(auto_dungeon_device, "GameActions", lambda *args, **kwargs: object())

    manager = auto_dungeon_device.DeviceManager()
    manager.initialize(emulator_name=None, correction_map={"a": "b"})

    assert called["kwargs"]["max_cache_size"] == 200
    assert called["kwargs"]["max_width"] == 960
    assert called["kwargs"]["correction_map"] == {"a": "b"}
