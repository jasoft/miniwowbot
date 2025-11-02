# Config 标签实现总结

## 功能概述

为所有 Loki 日志添加 `config` 标签，标签值为当前加载的配置文件名称。这样可以在 Grafana 中快速区分不同账号和职业的日志。

## 实现方式

### 1. 新增函数 - `logger_config.py`

```python
def update_all_loki_labels(loki_labels: Dict[str, str]) -> None:
    """
    更新所有日志记录器的 Loki 标签
    
    这个函数用于在运行时更新所有已创建的日志记录器的 Loki 标签。
    特别适用于在加载配置文件后，需要添加 config 标签的场景。
    """
```

**工作原理**：
- 遍历所有已创建的日志记录器
- 找到每个日志记录器中的 `LokiHandler`
- 更新 `LokiHandler` 的标签字典

### 2. 修改文件 - `auto_dungeon.py`

在 `initialize_configs()` 函数中：

```python
# 获取配置文件名称，用于 Loki 标签
config_name = config_loader.get_config_name()

# 重新初始化日志，添加配置文件名称标签
logger = setup_logger_from_config(
    use_color=True, loki_labels={"config": config_name}
)

# 更新所有已创建的日志记录器的 Loki 标签
# 这样 emulator_manager, ocr_helper 等模块的日志也会包含 config 标签
update_all_loki_labels({"config": config_name})
```

## 工作流程

```
1. 应用启动
   ↓
2. 模块导入，各模块初始化日志记录器
   - auto_dungeon.py: logger = setup_logger_from_config(use_color=True)
   - emulator_manager.py: logger = setup_logger_from_config(use_color=True)
   - ocr_helper.py: logger = setup_logger_from_config(use_color=True)
   - 等等...
   
   此时日志记录器没有 config 标签
   ↓
3. main() 函数调用 initialize_configs()
   ↓
4. 加载配置文件，获取配置名称（如 "account1", "warrior" 等）
   ↓
5. 重新初始化主日志记录器，添加 config 标签
   ↓
6. 调用 update_all_loki_labels({"config": config_name})
   ↓
7. 所有日志记录器的 Loki 标签都被更新
   ↓
8. 后续所有日志都会包含 config 标签
```

## Loki 标签结构

### 更新前

```json
{
  "app": "miniwow",
  "host": "docker-host"
}
```

### 更新后

```json
{
  "app": "miniwow",
  "host": "docker-host",
  "config": "account1"
}
```

## Grafana 查询示例

### 查询特定配置的所有日志

```
{config="account1"}
```

### 查询特定配置的 ERROR 日志

```
{config="account1"} | json | level="ERROR"
```

### 查询特定配置中特定文件的日志

```
{config="account1"} | json | filename="auto_dungeon.py"
```

### 查询多个配置的日志

```
{config=~"account1|account2"}
```

### 查询特定配置中特定函数的日志

```
{config="account1"} | json | function="main"
```

## 支持的配置名称

配置名称来自配置文件名称（不包括 `.json` 扩展名）：

- `account1` - 来自 `configs/account1.json`
- `warrior` - 来自 `configs/warrior.json`
- `mage` - 来自 `configs/mage.json`
- `hunter` - 来自 `configs/hunter.json`
- 等等...

## 实现细节

### 配置跟踪机制

`logger_config.py` 中的 `LoggerConfig` 类使用 `_configured_loggers` 集合来跟踪已配置的日志记录器，避免重复配置。

这意味着：
- 第一次调用 `setup_logger_from_config()` 会创建日志记录器
- 后续调用会返回同一个日志记录器
- 这样可以确保所有模块共享同一个日志记录器和 Loki 处理器

### 标签更新机制

`update_all_loki_labels()` 函数：
1. 遍历 `logging.Logger.manager.loggerDict` 中的所有日志记录器
2. 对每个日志记录器，遍历其所有处理器
3. 如果处理器是 `LokiHandler`，更新其标签字典
4. 也更新 root logger 的处理器

## 测试验证

已通过以下测试验证功能正确性：

1. **基础功能测试** - 验证 `update_all_loki_labels()` 能正确更新标签
2. **集成测试** - 验证在实际场景中，所有日志记录器都能获得 config 标签

## 相关文件

- `logger_config.py` - 新增 `update_all_loki_labels()` 函数
- `auto_dungeon.py` - 在 `initialize_configs()` 中调用 `update_all_loki_labels()`
- `CHANGELOG.md` - 记录此功能的添加

## 注意事项

1. **时序问题**：必须在加载配置文件后调用 `update_all_loki_labels()`，否则标签不会被应用
2. **模块初始化**：所有模块必须在 `initialize_configs()` 之前初始化日志记录器
3. **标签值**：config 标签值应该是配置文件名称（不包括路径和扩展名）
4. **性能**：`update_all_loki_labels()` 的性能开销很小，只是更新字典

## 后续改进建议

1. 可以考虑添加其他标签，如 `character_class`（职业）、`account_id` 等
2. 可以在 Grafana 中创建预定义的仪表板，按 config 标签分组显示日志
3. 可以添加告警规则，针对特定配置的错误日志进行告警

