# 角色职业选择功能 - 完成总结

## ✅ 完成状态

所有功能已实现并测试通过！

## 📋 完成的工作

### 1. **完善 `select_character` 函数** (`auto_dungeon_simple.py`)

```python
def select_character(char_class):
    """
    选择角色
    
    Args:
        char_class: 角色职业名称（如：战士、法师、刺客等）
    """
    logger.info(f"⚔️ 选择角色: {char_class}")
    
    # 打开设置
    find_text_and_click("设置")
    sleep(1)
    
    # 返回角色选择界面
    find_text_and_click("返回角色选择界面")
    sleep(3)
    
    # 查找职业文字位置
    logger.info(f"🔍 查找职业: {char_class}")
    pos = find_text_with_paddleocr(char_class, similarity_threshold=0.6)
    
    if pos:
        # 点击文字上方 30 像素的位置
        click_x = pos[0]
        click_y = pos[1] - 30
        logger.info(f"👆 点击角色位置: ({click_x}, {click_y})")
        touch((click_x, click_y))
        sleep(2)
        
        # 等待加载完成（大约10秒）
        logger.info("⏳ 等待角色加载...")
        sleep(10)
        
        # 等待回到主界面
        wait_for_main()
        logger.info(f"✅ 成功选择角色: {char_class}")
    else:
        logger.error(f"❌ 未找到职业: {char_class}")
        raise Exception(f"无法找到职业: {char_class}")
```

**实现要点：**
- ✅ 使用 `find_text_with_paddleocr()` 查找职业文字位置
- ✅ 点击文字上方 30 像素（角色头像位置）
- ✅ 等待 10 秒让角色加载
- ✅ 调用 `wait_for_main()` 等待回到主界面
- ✅ 完整的错误处理和日志输出

### 2. **更新配置加载器** (`config_loader.py`)

**添加的代码：**

```python
class ConfigLoader:
    def __init__(self, config_file: str):
        # ...
        self.char_class = None  # 新增
        self._load_config()
    
    def _load_config(self):
        # ...
        # 加载角色职业
        self.char_class = config.get("class", None)  # 新增
        
        # 日志输出
        if self.char_class:
            logger.info(f"⚔️ 角色职业: {self.char_class}")
    
    def get_char_class(self) -> Optional[str]:  # 新增方法
        """
        获取角色职业

        Returns:
            角色职业，如果未配置则返回 None
        """
        return self.char_class
```

**改进：**
- ✅ 添加 `char_class` 属性
- ✅ 从 JSON 配置读取 `class` 字段
- ✅ 新增 `get_char_class()` 方法
- ✅ 在日志中显示角色职业信息

### 3. **主程序集成** (`auto_dungeon_simple.py`)

**添加的代码：**

```python
def main():
    # ...
    # 初始化OCR工具类
    ocr_helper = OCRHelper(output_dir="output")

    # 选择角色（如果配置了职业）
    char_class = config_loader.get_char_class()
    if char_class:
        select_character(char_class)
    else:
        logger.info("⚠️ 未配置角色职业，跳过角色选择")

    # 初始化数据库
    with DungeonProgressDB(config_name=config_loader.get_config_name()) as db:
        # ...
```

**流程：**
1. 加载配置文件
2. 初始化设备和 OCR
3. **选择角色**（如果配置了 `class` 字段）
4. 初始化数据库
5. 开始副本遍历

### 4. **测试更新** (`tests/test_config_loader.py`)

**新增测试：**

```python
def test_get_char_class(self):
    """测试获取角色职业"""
    # 测试有职业配置的
    config = load_config("configs/default.json")
    assert config.get_char_class() == "战士"

    config = load_config("configs/warrior.json")
    assert config.get_char_class() == "战士"

    config = load_config("configs/mage.json")
    assert config.get_char_class() == "法师"
```

**更新的测试：**
- ✅ 将 `main_character.json` 改为 `warrior.json`
- ✅ 将 `alt_character.json` 改为 `mage.json`
- ✅ 所有 20 个测试通过

### 5. **文档更新**

**新增文档：**
- ✅ `docs/CHARACTER_SELECTION_GUIDE.md` - 详细使用指南
  - 配置方法
  - 工作原理
  - 使用示例
  - 常见问题
  - 技术细节

**更新文档：**
- ✅ `CHANGELOG.md` - 添加 v4.1.0 更新日志

## 🎯 使用方法

### 1. 配置文件示例

**战士配置** (`configs/warrior.json`):
```json
{
  "description": "战士配置",
  "class": "战士",
  "ocr_correction_map": {
    "梦魔丛林": "梦魇丛林"
  },
  "zone_dungeons": {
    "风暴群岛": [
      { "name": "真理之地", "selected": true },
      { "name": "预言神殿", "selected": true }
    ]
  }
}
```

**法师配置** (`configs/mage.json`):
```json
{
  "description": "法师配置",
  "class": "法师",
  "zone_dungeons": {
    "风暴群岛": [
      { "name": "真理之地", "selected": false },
      { "name": "预言神殿", "selected": true }
    ]
  }
}
```

**不选择角色** (`configs/default.json`):
```json
{
  "description": "默认配置 - 不选择角色",
  "zone_dungeons": {
    "风暴群岛": [
      { "name": "真理之地", "selected": true }
    ]
  }
}
```

### 2. 运行脚本

```bash
# 使用战士配置（会自动选择战士角色）
python auto_dungeon_simple.py -c configs/warrior.json

# 使用法师配置（会自动选择法师角色）
python auto_dungeon_simple.py -c configs/mage.json

# 使用默认配置（不选择角色）
python auto_dungeon_simple.py
```

## 📊 测试结果

```
tests/test_config_loader.py - 20 passed ✅
tests/test_database.py - 16 passed ✅

总计: 36 passed
```

## 🔧 技术细节

### 选择流程

1. **打开设置** - `find_text_and_click("设置")`
2. **返回角色选择** - `find_text_and_click("返回角色选择界面")`
3. **查找职业** - `find_text_with_paddleocr(char_class)`
4. **点击角色** - `touch((click_x, click_y - 30))`
5. **等待加载** - `sleep(10)`
6. **等待主界面** - `wait_for_main()`
7. **开始挂机** - 继续执行副本遍历

### 配置字段

- `class` (可选): 角色职业名称
  - 类型: `string` 或 `null`
  - 示例: `"战士"`, `"法师"`, `"刺客"`, `"猎人"`, `"圣骑士"`
  - 如果未配置或为 `null`，跳过角色选择

### 关键参数

- **OCR 相似度阈值**: `0.6` - 用于查找职业文字
- **点击偏移**: `-30` 像素 - 文字上方的角色头像位置
- **加载等待时间**: `10` 秒 - 角色加载时间

## 📁 修改的文件

```
auto_dungeon_simple.py          # 完善 select_character 函数，主程序集成
config_loader.py                # 添加 char_class 支持
tests/test_config_loader.py     # 更新测试
CHANGELOG.md                    # 添加 v4.1.0 更新日志
docs/CHARACTER_SELECTION_GUIDE.md  # 新增使用指南
CHARACTER_SELECTION_SUMMARY.md  # 本文件
```

## ⚠️ 注意事项

1. **职业名称必须准确**
   - 必须与游戏中角色选择界面显示的文字完全一致
   - 区分大小写和标点符号

2. **点击位置可能需要调整**
   - 默认偏移 -30 像素
   - 如果点击位置不准确，可以修改偏移值

3. **加载时间可能需要调整**
   - 默认等待 10 秒
   - 如果角色加载较慢，可以增加等待时间

4. **可选功能**
   - 如果不需要自动选择角色，不添加 `class` 字段即可
   - 脚本会自动跳过角色选择步骤

## 🎉 功能亮点

1. **自动化** - 无需手动选择角色
2. **灵活配置** - 支持多个职业配置
3. **智能识别** - 使用 OCR 自动查找职业位置
4. **错误处理** - 完整的错误处理和日志输出
5. **可选功能** - 可以选择是否启用

---

**版本**: 4.1.0  
**日期**: 2025-01-07  
**状态**: ✅ 完成并测试通过

