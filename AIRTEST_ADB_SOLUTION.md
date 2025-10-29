# 使用 Airtest 内置 ADB 解决版本冲突问题

## 问题回顾

本地 ADB 版本（41）与模拟器 ADB 版本（40）不匹配，导致执行 `adb devices` 命令时会杀掉旧版本的 ADB 服务并重启，中断模拟器连接。

## 解决方案

使用 **Airtest 内置的 ADB v40**，完全避免版本冲突问题。

### 为什么这个方案最优？

1. **版本一致性** - Airtest 内置的 ADB v40 与模拟器版本完全匹配
2. **无需额外安装** - Airtest 已经安装，ADB 已经包含
3. **自动路径查找** - 代码会自动定位 Airtest 内置 ADB
4. **向后兼容** - 如果 Airtest ADB 不可用，会自动降级到系统 ADB

## 实现细节

### 1. ADB 路径查找优先级

```python
# 优先级顺序：
1. Airtest 内置 ADB（推荐）
   └─ /Users/weiwang/Projects/异世界勇者.air/helper/.venv/lib/python3.13/site-packages/airtest/core/android/static/adb/mac/adb

2. 系统 PATH 中的 ADB
   └─ 通过 which/where 命令查找

3. ANDROID_HOME 中的 ADB
   └─ $ANDROID_HOME/platform-tools/adb

4. 默认 'adb' 命令
   └─ 依赖系统 PATH 配置
```

### 2. 代码实现

**emulator_manager.py 中的关键改动：**

```python
# 导入 Airtest 的 ADB 模块
try:
    from airtest.core.android.adb import ADB
except ImportError:
    ADB = None

class EmulatorManager:
    def __init__(self):
        self.system = platform.system()
        self.running_emulators = {}
        self.adb_path = self._get_adb_path()  # 初始化时获取 ADB 路径
    
    @staticmethod
    def _get_adb_path() -> Optional[str]:
        """获取 ADB 路径，优先使用 Airtest 内置的 ADB"""
        # 首先尝试使用 Airtest 内置的 ADB
        if ADB is not None:
            try:
                airtest_adb_path = ADB.builtin_adb_path()
                if os.path.exists(airtest_adb_path):
                    logger.info(f"✅ 使用 Airtest 内置 ADB: {airtest_adb_path}")
                    return airtest_adb_path
            except Exception as e:
                logger.debug(f"⚠️ 获取 Airtest 内置 ADB 失败: {e}")
        
        # 备选方案：尝试从系统 PATH 中找到 ADB
        # ... 其他备选方案 ...
        
        return "adb"  # 最后的默认值
    
    def get_adb_devices(self) -> Dict[str, str]:
        """获取所有已连接的 ADB 设备"""
        try:
            result = subprocess.run(
                [self.adb_path, "devices"],  # 使用 self.adb_path
                capture_output=True,
                text=True,
                timeout=10,
            )
            # ... 处理结果 ...
        except Exception as e:
            logger.error(f"❌ 获取 ADB 设备列表失败: {e}")
            return {}
```

## 测试结果

✅ **测试成功！**

```
✅ 使用 Airtest 内置 ADB: /Users/weiwang/Projects/异世界勇者.air/helper/.venv/lib/python3.13/site-packages/airtest/core/android/static/adb/mac/adb

📦 ADB 版本信息:
   Android Debug Bridge version 1.0.40
   Version 4986621

✅ 发现 2 个设备:
   - emulator-5554: device
   - emulator-5564: device
```

## 优势对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Airtest 内置 ADB** ✅ | 版本一致、无冲突、自动查找 | 依赖 Airtest 安装 |
| 系统 ADB | 通用、灵活 | 版本可能不匹配 |
| 指定 `-P` 参数 | 简单 | 不能完全解决版本冲突 |
| 缓存机制 | 减少调用 | 不能解决根本问题 |

## 使用方式

### 自动使用（推荐）

代码已经自动集成，无需任何修改：

```python
from emulator_manager import EmulatorManager

manager = EmulatorManager()
# manager.adb_path 会自动设置为 Airtest 内置 ADB
devices = manager.get_adb_devices()
```

### 手动获取 ADB 路径

```python
from emulator_manager import EmulatorManager

adb_path = EmulatorManager._get_adb_path()
print(f"ADB 路径: {adb_path}")
```

## 日志输出示例

启动脚本时会看到：

```
✅ 使用 Airtest 内置 ADB: /Users/weiwang/Projects/异世界勇者.air/helper/.venv/lib/python3.13/site-packages/airtest/core/android/static/adb/mac/adb
✅ 模拟器 emulator-5554 已在运行
🔍 检测到有未完成的副本，准备启动模拟器...
```

## 故障排除

### 问题：仍然看到版本冲突错误

**解决方案：**
1. 确保 Airtest 已正确安装：`pip list | grep airtest`
2. 检查 ADB 路径是否正确：运行 `python test_adb_path.py`
3. 清除 ADB 缓存：`adb kill-server`

### 问题：找不到 Airtest 内置 ADB

**解决方案：**
1. 重新安装 Airtest：`pip install --upgrade airtest`
2. 检查虚拟环境是否激活
3. 查看日志中的备选方案是否生效

## 相关文件

- `emulator_manager.py` - 模拟器管理器（已修改）
- `test_adb_path.py` - ADB 路径测试脚本
- `auto_dungeon.py` - 主程序（无需修改）

## 总结

✅ **问题已解决！** 通过使用 Airtest 内置的 ADB v40，完全避免了版本冲突问题。

**关键改动：**
- 添加 `_get_adb_path()` 方法自动查找 Airtest 内置 ADB
- 在 `__init__()` 中初始化 `self.adb_path`
- 在 `get_adb_devices()` 中使用 `self.adb_path` 替代硬编码的 "adb"

**效果：**
- ✅ 完全避免 ADB 版本冲突
- ✅ 自动路径查找，无需手动配置
- ✅ 向后兼容，有备选方案
- ✅ 日志清晰，便于调试

