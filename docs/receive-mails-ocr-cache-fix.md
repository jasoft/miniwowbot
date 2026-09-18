# 「领取邮件」永远找不到「一键领取」——OCR 缓存毒化排查

日期：2026-09-18
影响：`warrior` 及全部职业的每日任务「领取邮件」
状态：**已修复并实测通过**

## 症状

运行日志里反复出现这段（用户于 17:13 发现）：

```
17:13:32.892 INFO game_actions.py:250 Found: '邮箱' at (439, 645)
--- Logging error ---
TypeError: not all arguments converted during string formatting
Message: '🔎 找到一键领取按钮'
Arguments: (NullGameElement(),)
```

两处异常：`find_text` 返回了 `NullGameElement`，且日志自身抛 `TypeError`。

## 结论：70 天、70 次执行，一次都没成功过

统计 `log/autodungeon_main.log`（2026-06-25 ~ 09-18）：

| 指标 | 数值 |
| --- | --- |
| `开始领取邮件`（执行次数） | **70** |
| `Found: '一键领取'`（成功找到按钮） | **0** |
| `Found: '邮箱'`（对照，证明搜索方法可靠） | 69 |

今天三次全部失败：

```
16:34:22.226 DEBUG game_actions.py:258 Not found: '一键领取'
17:10:02.330 DEBUG game_actions.py:258 Not found: '一键领取'
17:13:39.427 DEBUG game_actions.py:258 Not found: '一键领取'
```

**每次都是：点开邮箱 → 找不到按钮 → 打「✅ 领取邮件成功」→ 写库记完成。**

## 根因：`vibe_ocr` 感知哈希缓存把一次 OCR 误差固化

### 机制

`vibe_ocr/ocr_helper.py` 的 `_find_text_in_regions()` 在 `use_cache=True` 时，先查
`_find_similar_in_cache(image=region_img, regions=regions)`：

```python
if use_cache:
    cached_result = self._find_similar_in_cache(image=region_img, regions=regions)
    if cached_result:
        result = [cached_result]      # ← 直接返回旧结果，本次不 OCR
        cache_used = True
```

而 `_find_similar_in_cache()` 的匹配是**感知哈希**（`hash_type=dhash`，
`hash_threshold=10`）—— 只要当前区域图的 dhash 与缓存里某条汉明距离 ≤ 10 就判为「同一界面」，
**完全不管内容差异**，直接返回那条缓存的 `json_data`。

### 毒条目

`output/cache/cache.db` 中 `regions='[8, 9]'` 的条目：

| image_hash | dhash | 命中次数 | 缓存文本 |
| --- | --- | --- | --- |
| `bd973bb67c` | `cccc1448010cbcad` | **1324** | `建删除 \| 键领取 \| 奖励会在发放7天后消失，请尽快领取 \| 战斗 \| 专业` |

关键：**「一键领取」被记成了「键领取」（漏了「一」字）**，且该条目**被命中 1324 次**
—— 因为每次命中都会刷新 `last_access_time`，`_evict_cache()` 的 LRU 反而把它一直保住。

`GameElementCollection.contains()` 的实现是**子串匹配**：

```python
def contains(self, text: str) -> "GameElementCollection":
    return self.filter(lambda e: text in (e.text or ""))
```

→ `"一键领取" in "键领取"` = **False** → 永远找不到。

### 现场对照（决定性证据）

同一界面、同一时刻，只差一个参数：

| 场景 | regions | use_cache | 结果 |
| --- | --- | --- | --- |
| **代码原写法** | `[8,9]` | **True（默认）** | ❌ found=False，耗时 6.33s |
| 对照 | `[8,9]` | **False** | ✅ `Found: '一键领取' at (475, 901)` |
| 对照 | 不加 | False | ❌ 全屏识别不到 |
| 对照 | `[8]` | False | ❌ 裁剪切掉了「一」字 |

区域过滤**不是**原因：`regions=[8,9]` 合并为 `x:[240,720), y:[852,1280)`，
覆盖 (475,901)；「一键领取」确实落在 region 8。用 `scripts/probe_mail.py` 可复核。

## 为什么故障全程静默

| 层 | 问题 | 位置 |
| --- | --- | --- |
| 库返回值 | `find_text` 找不到时返回 **`NullGameElement`（falsy）而不抛异常** | `vibe_ocr/game_actions.py:261` |
| 调用方 | 原有 `except Exception` 兜底是**按「找不到会抛异常」写的**，因此**永远不触发** | `auto_dungeon_daily.py:1033` |
| 日志 | `logger.info("🔎 找到一键领取按钮", res)` 无 `%s` 占位符却传参 → `TypeError` | `auto_dungeon_daily.py:1026` |
| 判定 | `if res:` 为假时不 return、不警告，函数正常结束 → `_run_step` 判成功 | `auto_dungeon_daily.py:177` |

## 修复

`auto_dungeon_daily.py` 的 `_receive_mails()`：

```python
find_text_and_click("主城", regions=[9], use_cache=False)
find_text_and_click("邮箱", regions=[5], use_cache=False)
res = find_text("一键领取", regions=[8, 9], use_cache=False, timeout=5)
self.logger.info(f"🔎 找到一键领取按钮: {res}")
if res:
    for _ in range(3):
        touch(res["center"])
        sleep(1, "点击邮箱一键领取")
    self.logger.info("✅ 领取邮件成功")
else:
    self.logger.warning("⚠️ 未找到「一键领取」按钮，本次未领取到邮件")
```

1. **三处查找补 `use_cache=False`** —— 同文件另有 10 处同类调用早已如此
   （含几乎同款的 `_open_chest` 的「开启10次」），这处是漏网
2. **日志改 f-string**，消除 `TypeError`
3. **补 `else` 分支 warning**，让失败在日志里可见
4. docstring 说明为何必须关缓存
5. 清掉 `output/cache/cache.db` 里 3 条 `regions='[8, 9]'` 条目（含那条 1324 次命中的）

**刻意未改**：找不到时仍不阻断流程（未 `return False`）。
改成「判失败」会触发 `FLOW_MAX_RETRIES=5` 整轮重试放大，影响面大，需另行拍板。

## 验证

| 项 | 结果 |
| --- | --- |
| 实跑 `_receive_mails`（17:28） | `Found: '一键领取' at (475,901)` → 点击 ×3 → `✅ 领取邮件成功`，20.8s |
| 日志 | **全程无 `--- Logging error ---`** |
| 邮件面板复查 | 4 封邮件的信封上**全带绿色 ✓ 已领取角标** |
| `ruff check` / `ruff format` | 通过 |
| `run_dungeons ... --dryrun` | EXIT=0 |
| 相关测试 8 个文件 | 20 passed |

**两处既有问题（已用 `git stash` 对照确认与本次改动无关）**：

- `pytest -m "not integration"` 全量收集时进程崩溃（`Error in sys.excepthook`，
  单个文件跑均正常）
- `tests/test_core_logic_refactor.py::test_main_proceeds_when_daily_collect_needed` 失败 ——
  它等真实设备的「角色选择界面」，游戏当前停在主城所以超时；该用例未标 `integration`

## 残留风险

`auto_dungeon_daily.py` 里**仍有 35 处查找未关缓存**（已关 10 处），同类问题会在别处复发。

| 方案 | 做法 | 代价 |
| --- | --- | --- |
| ① 逐处打补丁（现状） | 每个调用点手动传 `use_cache=False` | 容易漏，已漏一次 |
| ② 封装层统一 | 在 `auto_dungeon_ui.find_text` / `find_text_and_click` 里 `kwargs.setdefault("use_cache", False)` | 每次查找走真 OCR（~2.5s），整体变慢 |

同一类问题的通用判定手法：**同一界面连测两次，只差 `use_cache` 一个参数**，
若结果不同即为缓存命中导致的假阴性。

## 由本次新增的可复用工具

| 脚本 | 用途 |
| --- | --- |
| `scripts/probe_mail.py`（技能目录） | 进主城 → 点邮箱 → 打印面板全部元素及其 region 归属 |
| `scripts/scan_logging_calls.py`（技能目录） | 全项目扫 `logger.xxx("字面量", 参数)` 无占位符的写法（本次全项目仅此 1 处） |
| `sqlite3 output/cache/cache.db` 查询 | 直接看缓存里存了什么、被命中多少次 |
