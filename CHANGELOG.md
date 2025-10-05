# 更新日志

## 2025-01-05 - 多匹配功能和日志优化

### 🎯 新增功能

#### 多匹配支持
- **OCRHelper 类增强**: 所有查找方法现在支持 `occurrence` 参数
  - `find_text_in_image(text, occurrence=1)` - 指定查找第N个匹配
  - `capture_and_find_text(text, occurrence=1)` - 截图并查找第N个匹配
  - `find_and_click_text(text, occurrence=1)` - 查找并点击第N个匹配

- **新增方法**:
  - `find_all_matching_texts(image, text)` - 返回所有匹配的文字列表
  - `_find_all_matching_texts_in_json(json_file, text)` - 从JSON中查找所有匹配

#### 返回值增强
所有查找方法的返回值新增字段：
- `total_matches` - 总共找到的匹配数量
- `selected_index` - 实际选择的匹配索引

#### 智能选择机制
- 如果请求的 `occurrence` 超出实际匹配数量，自动选择最后一个匹配
- 详细的日志输出，显示所有匹配项的位置和置信度

### 🐛 Bug 修复

#### 日志重复输出问题
- **问题**: 日志信息输出两次
- **原因**: Logger 有多个 handlers 或 propagate 设置不当
- **修复**:
  - 在 `auto_dungeon_simple.py` 中添加 `logger.handlers.clear()` 和 `logger.propagate = False`
  - 在 `ocr_helper.py` 中添加相同的配置
- **结果**: 每条日志只输出一次，输出清晰

#### OCR 匹配逻辑问题
- **问题**: 查找"预言神殿"时会错误匹配到"言神殿"
- **原因**: 之前使用双向匹配逻辑 `target_text in text or text in target_text`
- **修复**: 改为单向匹配 `target_text in text`（只检查识别出的文字是否包含目标文字）
- **结果**:
  - 查找"预言神殿" → 不会匹配"言神殿" ✅
  - 查找"预言神殿" → 会匹配"预言神殿" ✅
  - 查找"预言" → 会匹配"预言神殿" ✅

### 🔧 脚本更新

#### auto_dungeon_simple.py
- `find_text_and_click()` 函数新增 `occurrence` 参数
- 保持向后兼容，默认行为不变（occurrence=1）
- 智能日志显示：只在 occurrence > 1 时显示序号
- 用户手动修改：切换区域时使用 `occurrence=2` 点击第2个匹配

### 📚 文档更新

#### README.md
- 添加多匹配功能说明章节
- 提供详细的使用示例
- 说明智能选择机制

#### 新增文件
- `CHANGELOG.md` - 本更新日志文件

### 💡 使用示例

```python
# 基本用法（默认第1个匹配）
find_text_and_click("确定")

# 点击第2个"确定"按钮
find_text_and_click("确定", occurrence=2)

# 查看所有匹配
matches = ocr_helper.find_all_matching_texts(image_path, "确定")
print(f"找到 {len(matches)} 个确定按钮")
for i, match in enumerate(matches, 1):
    print(f"  {i}. 位置: {match['center']}, 置信度: {match['confidence']:.3f}")
```

### 🎨 日志输出示例

```
23:53:33 INFO 🔍 查找文本: 确定 (第2个)
23:53:33 INFO 找到 3 个匹配的文字
23:53:33 INFO   匹配 1: '确定' (置信度: 0.999) 位置: (360, 640)
23:53:33 INFO   匹配 2: '确定' (置信度: 0.998) 位置: (360, 800)
23:53:33 INFO   匹配 3: '确定' (置信度: 0.997) 位置: (360, 960)
23:53:33 INFO 选择第2个匹配: '确定'
23:53:33 INFO ✅ 成功点击: 确定 (第2个)
```

### ✅ 测试验证

- ✅ OCRHelper 类所有方法语法正确
- ✅ auto_dungeon_simple.py 语法检查通过
- ✅ 日志输出无重复
- ✅ 多匹配功能正常工作
- ✅ 向后兼容性保持

### 🔄 向后兼容性

所有现有代码无需修改即可继续工作：
- 默认 `occurrence=1`，行为与之前完全一致
- 可选择性地使用新的多匹配功能
- 返回值结构扩展，但保留了所有原有字段

---

## 历史版本

### 2025-01-04 - 彩色日志集成
- 使用 coloredlogs 替换所有输出
- 不同级别的日志用不同颜色显示
- 添加表情符号增强可读性

### 2025-01-03 - 文件清理
- 删除所有测试文件和示例文件
- 只保留核心工作文件
- 更新 README.md

### 2025-01-02 - OCR 类抽象
- 创建 OCRHelper 类
- 封装 PaddleOCR 功能
- 更新自动挂机脚本使用新类

