# Daily Collect 真机测试文档

## 概述

本文档说明如何运行 `daily_collect` 函数的真机测试。

## 测试内容

已在 [`tests/test_auto_dungeon_integration.py`](test_auto_dungeon_integration.py:285) 中添加了 `TestDailyCollectIntegration` 测试类，包含以下测试用例：

### 1. `test_daily_collect_function_exists`
- **目的**: 验证 `daily_collect` 函数是否存在且可调用
- **类型**: 单元测试
- **无需设备**: 此测试不需要真机连接

### 2. `test_daily_collect_real_device`
- **目的**: 测试 `daily_collect` 函数在真机上的基本执行
- **前提条件**:
  - 设备已连接
  - 游戏已打开并在主界面或任意可访问主界面的界面
- **测试步骤**:
  1. 调用 [`daily_collect()`](../auto_dungeon.py:411) 函数
  2. 验证函数能够正常执行完成（不抛出异常）

### 3. `test_daily_collect_execution_time`
- **目的**: 验证函数执行时间在合理范围内
- **预期**: 执行时间应小于 60 秒
- **测试内容**: 测量函数从开始到结束的执行时间

### 4. `test_daily_collect_multiple_calls`
- **目的**: 测试函数的稳定性和幂等性
- **测试内容**: 连续调用 3 次 `daily_collect` 函数
- **预期**: 至少有一次成功执行
- **注意**: 多次调用应该能够正常处理"已领取"的情况

### 5. `test_daily_collect_with_different_states`
- **目的**: 测试在不同游戏状态下调用函数的表现
- **测试内容**:
  - 第一次调用（可能领取成功）
  - 等待 3 秒后第二次调用（可能显示已领取）
- **预期**: 函数在两种状态下都能正常执行

## 运行测试

### 方法 1: 使用便捷脚本（推荐）

```bash
# 运行 daily_collect 专项测试
./test_daily_collect.sh
```

这个脚本会：
1. 检查设备连接状态
2. 询问是否继续
3. 运行所有 `daily_collect` 相关测试
4. 显示详细的测试结果

### 方法 2: 直接使用 pytest

```bash
# 运行所有 daily_collect 测试
pytest tests/test_auto_dungeon_integration.py::TestDailyCollectIntegration -v -s

# 运行单个测试
pytest tests/test_auto_dungeon_integration.py::TestDailyCollectIntegration::test_daily_collect_real_device -v -s

# 运行所有集成测试
pytest tests/test_auto_dungeon_integration.py -v -s --tb=short
```

### 方法 3: 直接运行测试文件

```bash
python tests/test_auto_dungeon_integration.py
```

## 前置条件

### 1. 设备准备
```bash
# 检查设备连接
adb devices

# 应该看到类似输出：
# List of devices attached
# emulator-5554   device
```

### 2. 游戏状态
- 游戏应该已经打开
- 建议在主界面运行测试
- 角色已选择完成

### 3. 环境准备
```bash
# 安装依赖（如果还没安装）
pip install pytest airtest-selenium poco
```

## daily_collect 函数说明

[`daily_collect()`](../auto_dungeon.py:411) 函数的主要功能：

1. 返回主界面 (`back_to_main`)
2. 在区域 8 查找并点击"战斗"文本
3. 点击箱子位置（战斗按钮上方 50 像素）
4. 点击"收下"按钮
5. 点击"确定"按钮
6. 记录领取结果

**位置**: [`auto_dungeon.py:411-423`](../auto_dungeon.py:411)

## 测试结果解读

### 成功的测试输出示例
```
tests/test_auto_dungeon_integration.py::TestDailyCollectIntegration::test_daily_collect_real_device
🧪 开始测试每日领取功能
✅ 领取成功
✅ daily_collect 函数执行成功
PASSED

tests/test_auto_dungeon_integration.py::TestDailyCollectIntegration::test_daily_collect_execution_time
🧪 开始测试每日领取功能执行时间
✅ 领取成功
⏱️ daily_collect 执行时间: 12.34 秒
PASSED

tests/test_auto_dungeon_integration.py::TestDailyCollectIntegration::test_daily_collect_multiple_calls
🔄 第 1 次调用 daily_collect
✅ 领取成功
✅ 第 1 次调用成功
🔄 第 2 次调用 daily_collect
⚠️ 未找到领取按钮
✅ 第 2 次调用成功
🔄 第 3 次调用 daily_collect
⚠️ 未找到领取按钮
✅ 第 3 次调用成功
📊 daily_collect 成功率: 3/3
PASSED
```

### 常见问题

#### 1. "未找到领取按钮"
这是正常的，可能的原因：
- 奖励已经被领取过
- 当前不在正确的界面
- OCR 识别失败

**不影响测试**: 函数应该能够正常处理这种情况

#### 2. 设备连接失败
```
❌ 设备连接失败: ...
```

**解决方案**:
- 确保模拟器/设备已启动
- 运行 `adb devices` 检查连接
- 重启 ADB: `adb kill-server && adb start-server`

#### 3. 测试超时
```
pytest.fail(f"函数执行时间过长: XX.XX 秒")
```

**可能原因**:
- 网络延迟
- 游戏响应慢
- 界面卡住

**解决方案**:
- 检查游戏状态
- 手动返回主界面后重试
- 增加超时时间（修改测试代码中的 60 秒限制）

## 测试最佳实践

1. **测试前准备**
   - 确保游戏在主界面
   - 确保网络连接稳定
   - 关闭其他可能干扰的应用

2. **测试顺序**
   - 建议先运行 `test_daily_collect_function_exists`
   - 再运行 `test_daily_collect_real_device`
   - 最后运行其他测试

3. **测试频率**
   - 每次修改 `daily_collect` 函数后运行测试
   - 定期运行以确保功能稳定性
   - 在不同游戏状态下测试

4. **调试技巧**
   - 使用 `-v -s` 参数查看详细输出
   - 使用 `--tb=short` 查看简化的错误追踪
   - 单独运行失败的测试用例进行调试

## 相关文件

- 测试文件: [`tests/test_auto_dungeon_integration.py`](test_auto_dungeon_integration.py:1)
- 被测函数: [`auto_dungeon.py:411-423`](../auto_dungeon.py:411)
- 便捷脚本: [`test_daily_collect.sh`](../test_daily_collect.sh:1)
- 其他集成测试: 切换账号测试、选择角色测试

## 扩展测试

如果需要添加更多测试场景，可以在 `TestDailyCollectIntegration` 类中添加新的测试方法：

```python
def test_daily_collect_custom_scenario(self, setup_device):
    """自定义测试场景"""
    # 你的测试代码
    pass
```

## 反馈与改进

如果发现测试问题或需要添加新的测试场景，请：
1. 记录详细的错误信息
2. 说明游戏当前状态
3. 提供设备/模拟器信息
4. 建议改进方案
