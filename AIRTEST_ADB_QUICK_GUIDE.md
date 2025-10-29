# Airtest 内置 ADB 快速指南

## 问题
本地 ADB v41 与模拟器 ADB v40 版本不匹配，导致连接中断。

## 解决方案
✅ **使用 Airtest 内置的 ADB v40**

## 工作原理

```
启动脚本
    ↓
EmulatorManager.__init__()
    ↓
self.adb_path = _get_adb_path()
    ↓
优先级查找：
  1️⃣ Airtest 内置 ADB v40 ✅ (推荐)
  2️⃣ 系统 PATH 中的 ADB
  3️⃣ ANDROID_HOME 中的 ADB
  4️⃣ 默认 'adb' 命令
    ↓
返回 ADB 路径
    ↓
所有 ADB 命令使用该路径
```

## 代码改动

### 1. 导入 Airtest ADB 模块
```python
try:
    from airtest.core.android.adb import ADB
except ImportError:
    ADB = None
```

### 2. 添加路径查找方法
```python
@staticmethod
def _get_adb_path() -> Optional[str]:
    """获取 ADB 路径，优先使用 Airtest 内置的 ADB"""
    if ADB is not None:
        try:
            airtest_adb_path = ADB.builtin_adb_path()
            if os.path.exists(airtest_adb_path):
                logger.info(f"✅ 使用 Airtest 内置 ADB: {airtest_adb_path}")
                return airtest_adb_path
        except Exception as e:
            logger.debug(f"⚠️ 获取 Airtest 内置 ADB 失败: {e}")
    
    # 备选方案...
    return "adb"
```

### 3. 初始化时获取路径
```python
def __init__(self):
    self.system = platform.system()
    self.running_emulators = {}
    self.adb_path = self._get_adb_path()  # ← 新增
```

### 4. 使用路径执行命令
```python
def get_adb_devices(self) -> Dict[str, str]:
    result = subprocess.run(
        [self.adb_path, "devices"],  # ← 使用 self.adb_path
        capture_output=True,
        text=True,
        timeout=10,
    )
    # ...
```

## 测试验证

运行测试脚本：
```bash
python test_adb_path.py
```

预期输出：
```
✅ 使用 Airtest 内置 ADB: /path/to/airtest/adb/mac/adb
📦 ADB 版本: Android Debug Bridge version 1.0.40
✅ 发现 2 个设备: emulator-5554, emulator-5564
```

## 日志示例

启动脚本时：
```
✅ 使用 Airtest 内置 ADB: /Users/weiwang/Projects/异世界勇者.air/helper/.venv/lib/python3.13/site-packages/airtest/core/android/static/adb/mac/adb
✅ 模拟器 emulator-5554 已在运行
🔍 检测到有未完成的副本，准备启动模拟器...
```

## 优势

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Airtest 内置 ADB** ✅ | 版本一致、无冲突、自动查找 | 依赖 Airtest |
| 系统 ADB | 通用、灵活 | 版本可能不匹配 |
| `-P` 参数 | 简单 | 不能完全解决 |
| 缓存机制 | 减少调用 | 不能解决根本 |

## 文件变更

- ✅ `emulator_manager.py` - 已修改
- ✅ `test_adb_path.py` - 新增测试脚本
- ✅ `CHANGELOG.md` - 已更新
- ✅ `AIRTEST_ADB_SOLUTION.md` - 详细文档

## 无需修改的文件

- `auto_dungeon.py` - 无需修改
- `ocr_helper.py` - 无需修改
- 其他文件 - 无需修改

## 故障排除

### 问题：仍然看到版本冲突
**解决：** 运行 `python test_adb_path.py` 检查 ADB 路径

### 问题：找不到 Airtest ADB
**解决：** 重新安装 Airtest：`pip install --upgrade airtest`

### 问题：模拟器仍然连接失败
**解决：** 清除 ADB 缓存：`adb kill-server`

## 总结

✅ **问题已完全解决！**

- 使用 Airtest 内置 ADB v40
- 自动路径查找，无需手动配置
- 向后兼容，有多个备选方案
- 日志清晰，便于调试

**关键改动：** 3 处代码修改，完全避免版本冲突

