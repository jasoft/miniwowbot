# 角色选择功能使用指南

## 概述

从 v4.1.0 开始，脚本支持自动选择角色功能。你可以在配置文件中指定角色职业，脚本会在开始挂机前自动选择对应的角色。

## 配置方法

### 1. 在配置文件中添加 `class` 字段

编辑你的配置文件（如 `configs/warrior.json`），添加 `class` 字段：

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

### 2. 支持的职业

- 战士
- 法师
- 刺客
- 猎人
- 圣骑士
- 其他游戏中显示的职业名称

**注意**：职业名称必须与游戏中角色选择界面显示的文字完全一致。

### 3. 可选配置

如果不需要自动选择角色，可以：
- 不添加 `class` 字段
- 或者设置为 `null`：`"class": null`

脚本会跳过角色选择步骤。

## 工作原理

### 选择流程

1. **打开设置** - 点击主界面的"设置"按钮
2. **返回角色选择** - 点击"返回角色选择界面"
3. **查找职业** - 使用 OCR 查找指定职业的文字位置
4. **点击角色** - 点击文字上方 30 像素的位置（角色头像）
5. **等待加载** - 等待约 10 秒让角色加载完成
6. **等待主界面** - 调用 `wait_for_main()` 等待回到主界面
7. **开始挂机** - 继续执行副本遍历

### 技术细节

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
    pos = find_text_with_paddleocr(char_class, similarity_threshold=0.6)
    
    if pos:
        # 点击文字上方 30 像素的位置
        click_x = pos[0]
        click_y = pos[1] - 30
        touch((click_x, click_y))
        sleep(2)
        
        # 等待加载完成（大约10秒）
        sleep(10)
        
        # 等待回到主界面
        wait_for_main()
    else:
        raise Exception(f"无法找到职业: {char_class}")
```

## 使用示例

### 示例 1：战士配置

```bash
# 使用战士配置
python auto_dungeon_simple.py -c configs/warrior.json
```

配置文件 `configs/warrior.json`：
```json
{
  "description": "战士配置 - 高防御副本",
  "class": "战士",
  "zone_dungeons": {
    "风暴群岛": [
      { "name": "真理之地", "selected": true },
      { "name": "预言神殿", "selected": true }
    ]
  }
}
```

### 示例 2：法师配置

```bash
# 使用法师配置
python auto_dungeon_simple.py -c configs/mage.json
```

配置文件 `configs/mage.json`：
```json
{
  "description": "法师配置 - 高输出副本",
  "class": "法师",
  "zone_dungeons": {
    "风暴群岛": [
      { "name": "真理之地", "selected": false },
      { "name": "预言神殿", "selected": true }
    ]
  }
}
```

### 示例 3：不选择角色

```bash
# 使用默认配置（不选择角色）
python auto_dungeon_simple.py -c configs/default.json
```

配置文件 `configs/default.json`：
```json
{
  "description": "默认配置 - 不选择角色",
  "zone_dungeons": {
    "风暴群岛": [
      { "name": "真理之地", "selected": true },
      { "name": "预言神殿", "selected": true }
    ]
  }
}
```

## 常见问题

### Q1: 找不到职业怎么办？

**A**: 检查以下几点：
1. 职业名称是否与游戏中显示的完全一致（包括空格、标点）
2. 游戏界面是否正常显示
3. OCR 识别是否正常工作
4. 尝试调整 `similarity_threshold` 参数

### Q2: 点击位置不准确怎么办？

**A**: 可能需要调整偏移量：
- 当前默认是文字上方 30 像素
- 如果点击位置不对，可以修改 `auto_dungeon_simple.py` 中的偏移值：
  ```python
  click_y = pos[1] - 30  # 修改这个数值
  ```

### Q3: 加载时间太长怎么办？

**A**: 可以调整等待时间：
- 当前默认等待 10 秒
- 如果角色加载较慢，可以增加等待时间：
  ```python
  sleep(10)  # 修改这个数值，如改为 15
  ```

### Q4: 可以跳过角色选择吗？

**A**: 可以，有两种方法：
1. 不在配置文件中添加 `class` 字段
2. 设置 `"class": null`

脚本会自动跳过角色选择步骤。

### Q5: 支持哪些职业？

**A**: 理论上支持所有游戏中的职业，只要：
1. 职业名称在角色选择界面可见
2. OCR 能够识别职业名称
3. 职业名称在配置文件中正确拼写

## 日志示例

成功选择角色的日志：

```
⚔️ 选择角色: 战士
🔍 查找文本: 设置
✅ 找到并点击: 设置
🔍 查找文本: 返回角色选择界面
✅ 找到并点击: 返回角色选择界面
🔍 查找职业: 战士
找到文本: '战士' (置信度: 0.95) 位置: (360, 500)
👆 点击角色位置: (360, 470)
⏳ 等待角色加载...
等待战斗结束...
✅ 成功选择角色: 战士
```

## 相关文档

- [CHANGELOG.md](../CHANGELOG.md) - 版本更新日志
- [README.md](../README.md) - 项目说明
- [MULTI_CONFIG_GUIDE.md](MULTI_CONFIG_GUIDE.md) - 多配置使用指南
- [configs/README.md](../configs/README.md) - 配置文件说明

## 技术支持

如果遇到问题：
1. 检查日志输出
2. 确认游戏界面正常
3. 验证配置文件格式
4. 查看相关文档

---

**版本**: 4.1.0  
**日期**: 2025-01-07  
**状态**: ✅ 已实现并测试

