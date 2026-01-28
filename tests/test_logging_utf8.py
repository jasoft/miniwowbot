"""Tests for UTF-8 stream configuration."""

import logger_config


def test_ensure_utf8_output_reconfigures_streams(monkeypatch):
    calls = []

    class FakeStream:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

    fake_out = FakeStream()
    fake_err = FakeStream()

    monkeypatch.setattr(logger_config, "_is_windows", lambda: True)
    monkeypatch.setattr(logger_config.sys, "stdout", fake_out, raising=False)
    monkeypatch.setattr(logger_config.sys, "stderr", fake_err, raising=False)

    logger_config.ensure_utf8_output()

    assert calls
    assert all(call["encoding"] == "utf-8" for call in calls)
    assert all(call["errors"] == "replace" for call in calls)
