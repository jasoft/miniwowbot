import logging
import threading
import time

from loki_logger import LokiHandler


def _make_record(message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_loki_handler_uploads_on_background_thread():
    handler = LokiHandler(
        loki_url="http://localhost:3100",
        app_name="test_app",
        buffer_size=1,
        upload_interval=0.2,
    )
    uploads = []
    event = threading.Event()

    def fake_upload(batch):
        uploads.append((threading.current_thread().name, list(batch)))
        event.set()

    handler._do_upload = fake_upload  # type: ignore

    try:
        handler.emit(_make_record("async-log"))
        assert event.wait(1), "后台线程未在预期时间内上传日志"

        worker_thread, batch = uploads[0]
        assert worker_thread != threading.current_thread().name
        assert batch[0]["message"] == "async-log"
    finally:
        handler.close()


def test_loki_handler_flushes_remaining_logs_on_close():
    handler = LokiHandler(
        loki_url="http://localhost:3100",
        app_name="test_app",
        buffer_size=10,
        upload_interval=5,
    )
    uploads = []
    event = threading.Event()

    def fake_upload(batch):
        uploads.append(list(batch))
        event.set()

    handler._do_upload = fake_upload  # type: ignore

    try:
        handler.emit(_make_record("pending-log"))
    finally:
        handler.close()

    assert event.wait(1), "关闭时未刷新剩余日志"
    assert uploads and uploads[0][0]["message"] == "pending-log"


def test_loki_handler_batches_by_buffer_size():
    handler = LokiHandler(
        loki_url="http://localhost:3100",
        app_name="test_app",
        buffer_size=3,
        upload_interval=10,
    )
    uploads = []
    event = threading.Event()

    def fake_upload(batch):
        uploads.append(list(batch))
        event.set()

    handler._do_upload = fake_upload  # type: ignore

    try:
        handler.emit(_make_record("log-1"))
        handler.emit(_make_record("log-2"))
        handler.emit(_make_record("log-3"))
        assert event.wait(1), "未按批量大小触发上传"
        assert len(uploads[0]) == 3
    finally:
        handler.close()
