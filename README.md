# 副本自动遍历脚本

自动遍历游戏副本，支持进度保存和 OCR 识别纠正。

## 功能特性

- ✅ 自动遍历所有副本
- ✅ 记录每天的通关进度
- ✅ 智能跳过已通关副本
- ✅ OCR 识别纠正
- ✅ 缓存持久化

## 快速开始

### 安装依赖

```bash
uv pip install peewee pytest
```

### 运行脚本

```bash
python auto_dungeon_simple.py
```

### 查看进度

```bash
python view_progress.py
```

## 配置

### 修改副本列表

编辑 `dungeon_config.py` 中的 `ZONE_DUNGEONS`。

### 添加 OCR 纠正

编辑 `dungeon_config.py` 中的 `OCR_CORRECTION_MAP`：

```python
OCR_CORRECTION_MAP = {
    "梦魔丛林": "梦魇丛林",  # OCR 把"魇"识别成"魔"
    # 添加更多纠正规则...
}
```

## 测试

### 运行所有测试

```bash
pytest
```

### 运行特定测试

```bash
pytest tests/test_config.py
pytest tests/test_database.py
```

### 查看详细输出

```bash
pytest -v
```

## 文件结构

```
helper/
├── auto_dungeon_simple.py    # 主程序
├── dungeon_config.py          # 配置文件
├── ocr_helper.py              # OCR 辅助类
├── view_progress.py           # 进度查看
├── database/                  # 数据库模块
│   ├── __init__.py
│   ├── dungeon_db.py          # 数据库类
│   └── dungeon_progress.db    # 数据库文件
├── tests/                     # 测试目录
│   ├── __init__.py
│   ├── test_config.py         # 配置测试（22个）
│   ├── test_database.py       # 数据库测试（12个）
│   └── test_ocr.py            # OCR 测试（15个）
├── pytest.ini                 # pytest 配置
├── README.md                  # 项目说明
└── CHANGELOG.md               # 更新日志
```

## 更新日志

查看 [CHANGELOG.md](CHANGELOG.md)
