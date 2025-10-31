# 自动启动 BlueStacks 实例功能实现总结

## 功能概述

当指定的模拟器不在设备列表中时，自动启动对应的 BlueStacks 实例，无需手动启动。

## 实现内容

### 1. 代码修改

#### 1.1 `emulator_manager.py` 修改

**新增映射表：**
```python
EMULATOR_TO_INSTANCE = {
    "emulator-5554": "Tiramisu64",      # 主实例
    "emulator-5564": "Tiramisu64_1",    # 第二个实例
    "emulator-5574": "Tiramisu64_2",    # 第三个实例
    "emulator-5584": "Tiramisu64_3",    # 第四个实例
}
```

**新增方法：`start_bluestacks_instance(emulator_name)`**
- 检查模拟器是否已运行
- 查找对应的 BlueStacks 实例名称
- 启动 BlueStacks 应用
- 等待模拟器启动完成（最多 60 秒）
- 支持 macOS、Windows、Linux 三个平台

#### 1.2 `auto_dungeon.py` 修改

在三个关键函数中修改设备检查逻辑：

**1. `check_and_start_emulator(emulator_name)`**
- 当模拟器不在设备列表中时，调用 `start_bluestacks_instance()`
- 自动启动对应的 BlueStacks 实例
- 启动失败时发送 Bark 通知

**2. `handle_load_account_mode(account_name, emulator_name)`**
- 同样的自动启动逻辑
- 启动失败时调用 `sys.exit(1)` 退出

**3. `initialize_device_and_ocr(emulator_name)`**
- 同样的自动启动逻辑
- 启动失败时抛出 `RuntimeError` 异常

### 2. 新增文件

#### 2.1 `tests/test_auto_start_emulator.py`
- 6 个单元测试，全部通过
- 测试覆盖：
  - ✅ 模拟器到实例的映射
  - ✅ 成功启动 BlueStacks 实例
  - ✅ 启动超时处理
  - ✅ 未知模拟器处理
  - ✅ 第二个实例启动
  - ✅ 已运行的实例检查

#### 2.2 `demo_auto_start_emulator.py`
- 演示脚本
- 展示映射关系、工作流程等

### 3. 更新文件

#### 3.1 `CHANGELOG.md`
- 添加了新功能的详细记录

## 工作流程

```
用户指定模拟器: --emulator emulator-5564
    ↓
获取设备列表: adb devices
    ↓
检查模拟器是否在列表中
    ├─ 存在 → 直接启动 ✅
    └─ 不存在 → 进入自动启动流程
        ↓
    查找模拟器对应的 BlueStacks 实例
        ├─ 找到 → 启动实例
        └─ 未找到 → 报错并发送 Bark 通知 ❌
            ↓
        启动 BlueStacks 实例
            ├─ macOS: open -a BlueStacksMIM
            ├─ Windows: HD-Player.exe --instance Tiramisu64_1
            └─ Linux: bluestacks
                ↓
            等待模拟器启动（最多 60 秒）
                ├─ 启动成功 → 继续执行脚本 ✅
                └─ 启动超时 → 报错并发送 Bark 通知 ❌
```

## 测试结果

### 单元测试
```bash
uv run python -m pytest tests/test_auto_start_emulator.py -v
```
结果：✅ 6 passed in 1.29s

### 演示脚本
```bash
uv run python demo_auto_start_emulator.py
```
结果：✅ 正常运行，显示映射关系和工作流程

### 语法检查
```bash
uv run python -m py_compile emulator_manager.py auto_dungeon.py
```
结果：✅ 所有文件语法检查通过

## 使用示例

### 正常使用（模拟器已在运行）
```bash
uv run auto_dungeon.py --emulator emulator-5554
# 输出：✅ 模拟器 emulator-5554 已在设备列表中
```

### 自动启动（模拟器未运行）
```bash
uv run auto_dungeon.py --emulator emulator-5564
# 输出：⚠️ 模拟器 emulator-5564 不在设备列表中
#      🚀 尝试启动对应的 BlueStacks 实例...
#      🚀 正在启动 BlueStacks 实例: Tiramisu64_1 (对应 emulator-5564)
#      ⏳ 等待 BlueStacks 实例 Tiramisu64_1 启动...
#      ✅ 模拟器 emulator-5564 已启动 (耗时 XX 秒)
```

### 错误处理（未知模拟器）
```bash
uv run auto_dungeon.py --emulator emulator-9999
# 输出：⚠️ 模拟器 emulator-9999 不在设备列表中
#      🚀 尝试启动对应的 BlueStacks 实例...
#      ❌ 未找到模拟器 emulator-9999 对应的 BlueStacks 实例
#      ❌ 无法启动模拟器 emulator-9999 对应的 BlueStacks 实例
#      📱 发送 Bark 通知: 副本助手 - 错误
```

## 技术细节

### 平台支持
- **macOS**: 使用 `open -a BlueStacksMIM` 启动
- **Windows**: 使用 `HD-Player.exe --instance <instance_name>` 启动
- **Linux**: 使用 `bluestacks` 命令启动

### 等待机制
- 每 5 秒检查一次模拟器是否启动
- 最多等待 60 秒
- 启动成功后额外等待 5 秒确保完全就绪

### 错误处理
- 模拟器已运行：直接返回成功
- 模拟器未找到映射：返回失败并发送 Bark 通知
- 启动超时：返回失败并发送 Bark 通知

## 优势

1. **自动化** - 无需手动启动 BlueStacks，脚本自动处理
2. **智能** - 检查模拟器是否已运行，避免重复启动
3. **可靠** - 支持多个 BlueStacks 实例，映射关系清晰
4. **跨平台** - 支持 macOS、Windows、Linux
5. **通知** - 启动失败时发送 Bark 通知告知用户
6. **完整测试** - 单元测试确保功能正确性

## 相关文件

- `emulator_manager.py` - 模拟器管理器，包含自动启动逻辑
- `auto_dungeon.py` - 主脚本，集成自动启动功能
- `tests/test_auto_start_emulator.py` - 单元测试
- `demo_auto_start_emulator.py` - 演示脚本
- `CHANGELOG.md` - 更新日志

## 后续改进

1. 可以添加更多 BlueStacks 实例的映射
2. 可以添加自定义启动参数
3. 可以添加启动失败的自动重试机制
4. 可以添加更详细的启动日志

