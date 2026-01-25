# Emulator Manager Logger Decoupling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `emulator_manager.py` 与 `logger_config` 解耦，仅依赖标准 logger 接口，并提供默认日志格式（时间/级别/模块名/文件名/行号）。

**Architecture:** 在模块内构建默认 logger（标准库 logging），仅在无外部配置时启用；`EmulatorConnectionManager` 支持注入 logger，使外部可覆盖输出格式。将所有日志调用改为实例级 `self.logger` 并避免使用非约定接口（如 `critical`）。

**Tech Stack:** Python 3.10, 标准库 logging, pytest

### Task 1: 注入 logger 并提供默认格式

**Files:**
- Create: `tests/test_emulator_logger.py`
- Modify: `emulator_manager.py`

**Step 1: Write the failing test**

```python
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
    monkeypatch.setattr("emulator_manager.which", lambda *_: None)
    manager = emulator_manager.EmulatorConnectionManager(logger=dummy)

    assert manager.adb_path == "adb"
    assert any(level == "warning" for level, _ in dummy.records)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_emulator_logger.py -v`  
Expected: FAIL（构造函数不接受 logger 注入 / 默认日志不生效）

**Step 3: Write minimal implementation**

```python
def _create_default_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(module)s %(filename)s:%(lineno)d - %(message)s"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger

class EmulatorConnectionManager:
    def __init__(..., logger: Optional[LoggerLike] = None):
        self.logger = logger or _DEFAULT_LOGGER
        self.adb_path = self._resolve_adb_path()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_emulator_logger.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_emulator_logger.py emulator_manager.py
git commit -m "refactor: decouple emulator manager logger"
```
