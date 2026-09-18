# 每日任务排查报告 · warrior（主账号战士）

> 2026-09-18 · 已重置当日记录并实机复跑验证

## 结论

11 个每日任务里 **只有「领取广告奖励」真的做不成**（实测 10 ✅ / 1 ❌）。
但它一条卡死，把整个 warrior 配置拖成「永远未完成」，进而触发整轮重试。

## 实机复跑结果

重置 warrior 当日记录后逐项执行（`daily_probe.py`，用时 4 分 31 秒）：

| 任务 | 结果 | 耗时 | 任务 | 结果 | 耗时 |
|---|---|---|---|---|---|
| 领取挂机奖励 | ✅ | 32.1s | 领取邮件 | ✅ | 12.1s |
| 购买商店每日 | ✅ | 10.4s | 领取主题奖励 | ✅ | 27.1s |
| 随从派遣 | ✅ | 30.9s | 领取礼包 | ✅ | 9.6s |
| 每日免费地下城 | ✅ | 30.1s | **领取广告奖励** | **❌** | **0.0s** |
| 开启宝箱 | ✅ | 21.9s | 猎魔试炼 | ✅ | 4.3s |
| 世界BOSS | ✅ | 85.2s | | | |

失败项日志只有一行：`⚠️ 未知的每日任务: 领取广告奖励` —— 耗时 0 秒，根本没进游戏。

## 三条独立证据链

### 1. 代码：TASK_MAPPING 缺这一条

`auto_dungeon_daily.py` 第 100 行 ——

```python
# "领取广告奖励": (self._buy_ads_items, "buy_ads_items"),
```

`execute_task()` 查表查不到 → 第 114 行打 `未知的每日任务` → 返回 `False` → 不写完成记录。

顺带发现 `collect_daily_rewards()` 第 614 行仍在调 `_buy_ads_items`，但那条路径**是死的**：
唯一触发点 `DungeonStateMachine.claim_daily_rewards()` 全项目**无调用者**。
所以实际执行的只有走 TASK_MAPPING 的 10 个。

### 2. 历史日志：它一直被「跳过」

`log/autodungeon_main.log` 里该任务共 66 条记录，全部是：

```
⏭️ [10/109] 未选定，跳过: 领取广告奖励      （2026-06-24 ~ 2026-09-17）
```

即 git 里它的 `selected` 一直是 `false`。工作区版本（09:13 改的）把它改成了 `true` ——
但代码没放开，所以改 true 只是**从「静默跳过」变成「报未知任务」**，结果一样。

### 3. 实测口径：怎么努力都差 1 个（✅ 2026-09-18 18:15 已修复）

| 量 | 修复前 | 修复后 |
|---|---|---|
| `get_selected_dungeon_count()` | **22** = 「日常任务」11 项 + 亡灵之地 11 副本 | **11**（纯副本） |
| `get_today_completed_count()` 理论上限 | **21**（日常恒缺 1） | 随副本数，不再差 1 |
| `_is_config_completed('warrior')` | **False**（插桩实测：即使全部副本打完也返回 False） | 副本打完即 True |

`config_loader._load_config()` 把 `daily_tasks` 包成「日常任务」区域塞进 `zone_dungeons`，
`get_selected_dungeon_count()` 遍历时把它一起数了进去 —— 这是口径 bug。

**修法**：新增 `ConfigLoader.get_dungeon_zones()` 只返回真副本区域，副本计数系列方法改用它；
`get_zone_dungeons()` 保持含「日常任务」供执行流程遍历。DB 层把「日常任务」纳入
`SPECIAL_ZONE_NAMES`（与 `__daily_collect__` 同等对待），使两侧口径对齐。

## 为什么会放大（✅ 已随口径修复一起解决）

```
_is_config_completed → False
  → filter_pending_configs 每天保留 warrior
  → poe stats（check_progress.py）退出码恒 1
  → run_single_flow 失败
  → FLOW_MAX_RETRIES = 5 整轮重试，每次重跑全部 12 个职业
```

再叠加 `emulators.json` 里 warrior 排在 **main session 第 12 位（最末）**：
前置流程一断（今天 06:42 执行过 `poe panic-stop`）它当天就一条记录都没有。

## 另外两处「假完成」风险（✅ 2026-09-18 已修复）

| 位置 | 问题 | 现状 |
|---|---|---|
| `_run_step()` | 判成功用 `raw_output is not False`，而多数任务方法**不返回值**（None）→ 一律记 ✅ | 改为 `raw_result is True` + 失败 Pushover 告警（带截图） |
| `_demonhunter_exam()` | try/except 吞异常 → 活动下线时照样记 ✅ | 所有任务方法必须显式返回 bool |


## 待定选项（等大王拍板）

| # | 事项 | 选项 |
|---|---|---|
| 1 | 领取广告奖励 | (a) 放开代码 —— 需先解决 `_buy_ads_items` 里 `sleep(150)`×15 ≈ **37 分钟**的等待；(b) 把 `selected` 改回 `false` |
| 2 | `total_selected` 口径 | 把「日常任务」区域排除出副本计数（推荐，一处修复解决「永远未完成」） |
| 3 | warrior 排序 | 是否从 main session 末位前移 |

> 补充：`_buy_ads_items` 那个 37 分钟等待，大概才是它当初被禁掉的真实原因 —— 不是任务本身有问题。
