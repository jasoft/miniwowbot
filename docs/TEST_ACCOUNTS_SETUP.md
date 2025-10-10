# 测试账号配置指南

## 概述

为了保护隐私，测试账号信息存储在独立的配置文件中，该文件已添加到 `.gitignore`，不会被提交到 Git 仓库。

## 配置步骤

### 1. 复制示例配置文件

```bash
cp test_accounts.json.example test_accounts.json
```

### 2. 编辑配置文件

打开 `test_accounts.json` 文件，填入真实的测试账号：

```json
{
  "accounts": [
    "your_account_1",
    "your_account_2"
  ]
}
```

**注意**：
- 至少需要配置 1 个账号
- 建议配置 2 个账号以测试账号切换功能
- 账号信息会被用于集成测试

### 3. 验证配置

运行测试验证配置是否正确：

```bash
pytest tests/test_auto_dungeon_integration.py::TestSwitchAccountIntegration -v
```

## 文件说明

### test_accounts.json（私有文件）

- **位置**：项目根目录
- **用途**：存储真实的测试账号
- **Git 状态**：已添加到 `.gitignore`，不会被提交
- **格式**：JSON 格式

```json
{
  "accounts": [
    "account1",
    "account2"
  ]
}
```

### test_accounts.json.example（示例文件）

- **位置**：项目根目录
- **用途**：配置文件模板
- **Git 状态**：会被提交到仓库
- **格式**：JSON 格式，包含占位符

## 安全注意事项

### ✅ 安全做法

1. **不要提交真实账号**：
   - `test_accounts.json` 已添加到 `.gitignore`
   - 只提交 `test_accounts.json.example` 模板文件

2. **本地保管**：
   - 真实账号信息只存在于本地
   - 不要通过任何方式分享配置文件

3. **定期检查**：
   ```bash
   git status
   ```
   确保 `test_accounts.json` 不在待提交列表中

### ❌ 避免的做法

1. **不要硬编码账号**：
   ```python
   # ❌ 错误做法
   accounts = ["15371008673", "18502542158"]
   
   # ✅ 正确做法
   accounts = load_test_accounts()
   ```

2. **不要在代码中直接写账号**：
   - 所有账号信息都应该从配置文件读取
   - 不要在测试代码中硬编码账号

3. **不要提交包含真实账号的文件**：
   - 提交前检查 `git diff`
   - 确保没有意外提交敏感信息

## 使用示例

### 在测试中使用

```python
from tests.test_auto_dungeon_integration import load_test_accounts

# 加载测试账号
accounts = load_test_accounts()

# 使用第一个账号
if accounts:
    test_account = accounts[0]
    switch_account(test_account)
```

### 在代码中使用

```python
import json

def load_accounts():
    """加载账号配置"""
    with open('test_accounts.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
        return config.get('accounts', [])

accounts = load_accounts()
```

## 故障排除

### 问题1：找不到配置文件

**错误信息**：
```
⚠️ 未找到配置文件: /path/to/test_accounts.json
💡 请复制 test_accounts.json.example 为 test_accounts.json 并填入真实账号
```

**解决方案**：
```bash
cp test_accounts.json.example test_accounts.json
# 然后编辑 test_accounts.json 填入真实账号
```

### 问题2：配置文件格式错误

**错误信息**：
```
❌ 配置文件格式错误: Expecting value: line 1 column 1 (char 0)
```

**解决方案**：
1. 检查 JSON 格式是否正确
2. 确保使用 UTF-8 编码
3. 验证 JSON 语法：
   ```bash
   python -m json.tool test_accounts.json
   ```

### 问题3：没有可用的测试账号

**错误信息**：
```
没有可用的测试账号
```

**解决方案**：
1. 确保 `test_accounts.json` 中至少有一个账号
2. 检查 `accounts` 数组不为空：
   ```json
   {
     "accounts": [
       "account1"
     ]
   }
   ```

## 测试覆盖

使用配置文件的测试：

1. **test_switch_account_real_device**
   - 使用第一个账号测试切换功能

2. **test_switch_account_execution_time**
   - 使用第一个账号测试执行时间

3. **test_switch_account_multiple_calls**
   - 使用所有账号（最多2个）测试多次切换

## 最佳实践

1. **团队协作**：
   - 每个开发者维护自己的 `test_accounts.json`
   - 不要共享真实账号信息

2. **CI/CD 环境**：
   - 在 CI 环境中使用环境变量或密钥管理
   - 不要在 CI 配置中硬编码账号

3. **定期更新**：
   - 定期检查账号是否有效
   - 及时更新失效的账号

4. **备份**：
   - 本地备份配置文件
   - 不要依赖单一副本

## 相关文件

- `.gitignore` - 包含 `test_accounts.json` 的忽略规则
- `test_accounts.json.example` - 配置文件模板
- `tests/test_auto_dungeon_integration.py` - 使用配置的测试文件

## 更新日志

- 2025-01-09: 初始版本，添加测试账号配置功能

