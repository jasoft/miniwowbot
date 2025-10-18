# VSCode 测试管理器日志输出配置指南

## 问题说明

在 VSCode 测试管理器中运行测试时，默认情况下看不到日志输出（`logger.info()` 等），但在命令行运行 `./test_daily_collect.sh` 或 `pytest` 时可以看到。

## 解决方案

已配置以下文件使 VSCode 测试管理器显示日志输出：

### 1. pytest.ini 配置

文件路径：[`pytest.ini`](../pytest.ini:1)

添加了以下选项：
```ini
addopts =
    -v                      # 详细输出
    -s                      # 不捕获标准输出（显示 print 和 logger 输出）
    --tb=short              # 简化错误追踪
    --strict-markers        # 严格标记模式
    --capture=no            # 禁用输出捕获
    --log-cli-level=INFO    # 显示 INFO 级别及以上的日志
```

### 2. VSCode 设置配置

文件路径：[`.vscode/settings.json`](../.vscode/settings.json:1)

配置了 pytest 参数：
```json
{
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "python.testing.pytestArgs": [
        "tests",
        "-v",
        "-s",
        "--tb=short",
        "--capture=no",
        "--log-cli-level=INFO"
    ]
}
```

## 关键配置项说明

### `-s` 或 `--capture=no`
- **作用**: 禁用输出捕获，允许 `print()` 和 `logger` 输出直接显示
- **效果**: 测试运行时可以看到所有的日志输出

### `--log-cli-level=INFO`
- **作用**: 设置命令行日志输出级别
- **可选值**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **效果**: 显示指定级别及以上的日志

### `-v`
- **作用**: 详细模式（verbose）
- **效果**: 显示每个测试的详细信息

## 使用方法

### 方法 1: VSCode 测试管理器（现在可以看到日志）

1. 打开 VSCode 的测试侧边栏（烧瓶图标）
2. 刷新测试列表
3. 运行任意测试
4. 在"测试结果"面板中查看输出

**现在应该能看到**：
```
🧪 开始测试每日领取功能
✅ 领取成功
✅ daily_collect 函数执行成功
```

### 方法 2: 命令行（一直可以看到日志）

```bash
# 使用便捷脚本
./test_daily_collect.sh

# 直接使用 pytest
pytest tests/test_auto_dungeon_integration.py::TestDailyCollectIntegration -v -s
```

### 方法 3: VSCode 集成终端

在 VSCode 终端中运行：
```bash
pytest tests/test_auto_dungeon_integration.py -v -s
```

## 日志级别调整

如果需要查看更详细的日志（包括 DEBUG 级别）：

### 临时调整（单次测试）
```bash
pytest tests/test_auto_dungeon_integration.py -v -s --log-cli-level=DEBUG
```

### 永久调整
修改 [`pytest.ini`](../pytest.ini:1)：
```ini
addopts =
    -v
    -s
    --tb=short
    --strict-markers
    --capture=no
    --log-cli-level=DEBUG  # 改为 DEBUG
```

或修改 [`.vscode/settings.json`](../.vscode/settings.json:1)：
```json
"python.testing.pytestArgs": [
    "tests",
    "-v",
    "-s",
    "--tb=short",
    "--capture=no",
    "--log-cli-level=DEBUG"  // 改为 DEBUG
]
```

## 日志输出格式

在测试代码中使用的日志格式（来自 [`auto_dungeon.py`](../auto_dungeon.py:38)）：
```python
coloredlogs.install(
    level="INFO",
    logger=logger,
    fmt="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
```

输出示例：
```
17:30:15 INFO 🧪 开始测试每日领取功能
17:30:18 INFO ✅ 领取成功
17:30:18 INFO ✅ daily_collect 函数执行成功
```

## 常见问题

### 1. VSCode 测试管理器仍然看不到日志

**解决方案**：
1. 重新加载 VSCode 窗口：按 `Cmd+Shift+P`（Mac）或 `Ctrl+Shift+P`（Windows/Linux），输入 "Reload Window"
2. 清除 pytest 缓存：
   ```bash
   rm -rf .pytest_cache
   ```
3. 检查 Python 解释器是否正确选择

### 2. 日志输出太多

**解决方案**：
- 调整日志级别为 `WARNING` 或 `ERROR`
- 在测试代码中使用条件日志：
  ```python
  if verbose:
      logger.info("详细信息")
  ```

### 3. 某些第三方库的日志看不到

**解决方案**：
在测试文件顶部添加：
```python
import logging
logging.basicConfig(level=logging.INFO)
```

或者在 [`pytest.ini`](../pytest.ini:1) 中配置：
```ini
log_cli = true
log_cli_level = INFO
log_cli_format = %(asctime)s [%(levelname)8s] %(message)s
log_cli_date_format = %H:%M:%S
```

## 验证配置

运行以下测试验证日志输出是否正常：

```bash
# 在 VSCode 测试管理器中运行，应该能看到日志
# 或者在终端运行：
pytest tests/test_auto_dungeon_integration.py::TestDailyCollectIntegration::test_daily_collect_real_device -v -s
```

期望输出：
```
tests/test_auto_dungeon_integration.py::TestDailyCollectIntegration::test_daily_collect_real_device
17:30:15 INFO 🧪 开始测试每日领取功能
17:30:18 INFO ✅ 领取成功
17:30:18 INFO ✅ daily_collect 函数执行成功
PASSED
```

## 参考资料

- [Pytest 输出捕获文档](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html)
- [Pytest 日志配置文档](https://docs.pytest.org/en/stable/how-to/logging.html)
- [VSCode Python 测试配置](https://code.visualstudio.com/docs/python/testing)

## 相关文件

- pytest 配置：[`pytest.ini`](../pytest.ini:1)
- VSCode 设置：[`.vscode/settings.json`](../.vscode/settings.json:1)
- 测试文件：[`tests/test_auto_dungeon_integration.py`](test_auto_dungeon_integration.py:1)
- 日志配置：[`auto_dungeon.py`](../auto_dungeon.py:38)
