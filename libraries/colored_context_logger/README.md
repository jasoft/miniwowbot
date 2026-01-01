# Colored Context Logger

A generic, easy-to-use logging library supporting:
- **Colored console output** (via `coloredlogs`).
- **Context injection**: Add global context (e.g., `session_id`, `config_name`) to all log records automatically.
- **File logging**: Easy attachment of file handlers with rotation support.
- **Function tracing**: `@log_calls` decorator to log function entry, exit, arguments, and execution time.

## Installation

```bash
pip install colored-context-logger
```

## Usage

```python
from colored_context_logger import setup_logger, GlobalLogContext, log_calls

# 1. Setup Logger
logger = setup_logger(name="my_app", level="DEBUG")

# 2. Set Global Context (will appear in all logs)
GlobalLogContext.update({"user": "alice", "request_id": "12345"})

logger.info("Processing request") 
# Output: 2025-01-01 12:00:00 INFO my_app ... user=alice request_id=12345 Processing request

# 3. Decorator
@log_calls()
def calculate(x, y):
    return x + y

calculate(1, 2)
# Output:
# ➡️ calculate 开始 (1, 2)
# ⬅️ calculate 结束 用时 0.0001s 返回 int
```
