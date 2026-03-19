# DailyCollect 奖券兑换实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `dailycollect` 在火焰塔奖券兑换中按期次稳定兑换第一件紫色物品和第二件蓝色物品，并通过数据库防止重复购买。

**Architecture:** 在 `auto_dungeon_daily.py` 中把主题奖励兑换拆成“读取兑换行状态”和“按顺序尝试兑换”两层逻辑，基于 OCR 解析 `x/40`、`x/30`，并用价格颜色作为辅助校验。数据库在 `database/dungeon_db.py` 中新增按 `GMT+8 周五 06:00` 切分的期次记录，保存每期每件目标物品的兑换状态。

**Tech Stack:** Python 3.10、Peewee、pytest、ruff、pyright、Airtest、现有 OCR/GameActions 封装

---

## Chunk 1: 数据库期次与防重

### Task 1: 为主题兑换状态写数据库失败测试

**Files:**
- Modify: `tests/test_database.py`
- Modify: `database/dungeon_db.py`

- [ ] **Step 1: 写失败测试，覆盖周五 06:00 GMT+8 期次计算**

```python
def test_event_cycle_id_rolls_over_at_friday_6am_gmt8(temp_db, monkeypatch):
    ...
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `uv run pytest tests/test_database.py -m "not integration" -k event_cycle -v`
Expected: FAIL，提示缺少期次接口或断言不成立

- [ ] **Step 3: 写失败测试，覆盖同一期同物品幂等写入**

```python
def test_mark_event_item_completed_is_idempotent(temp_db):
    ...
```

- [ ] **Step 4: 运行测试并确认失败**

Run: `uv run pytest tests/test_database.py -m "not integration" -k event_item -v`
Expected: FAIL，提示缺少兑换状态接口

- [ ] **Step 5: 提交测试骨架**

```bash
git add tests/test_database.py
git commit -m "test: add event exchange db coverage"
```

### Task 2: 实现数据库期次与兑换状态接口

**Files:**
- Modify: `database/dungeon_db.py`
- Modify: `database/__init__.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: 最小实现活动兑换状态模型与表**

```python
class EventItemProgress(BaseModel):
    config_name = CharField(index=True, default="default")
    cycle_id = CharField(index=True)
    event_name = CharField(index=True)
    item_key = CharField()
    completed_at = DateTimeField()
```

- [ ] **Step 2: 实现 `get_event_cycle_id()` 与期次边界计算**

```python
def get_event_cycle_id(self, now: datetime | None = None) -> str:
    ...
```

- [ ] **Step 3: 实现查询与写入接口**

```python
def is_event_item_completed(self, event_name: str, item_key: str, cycle_id: str | None = None) -> bool:
    ...

def mark_event_item_completed(self, event_name: str, item_key: str, cycle_id: str | None = None) -> None:
    ...
```

- [ ] **Step 4: 运行数据库测试并确认通过**

Run: `uv run pytest tests/test_database.py -m "not integration" -v`
Expected: PASS

- [ ] **Step 5: 提交数据库实现**

```bash
git add database/dungeon_db.py database/__init__.py tests/test_database.py
git commit -m "feat: persist event exchange cycle progress"
```

## Chunk 2: 兑换状态识别与顺序逻辑

### Task 3: 为主题兑换顺序写失败测试

**Files:**
- Modify: `tests/test_auto_dungeon_daily_regression.py`
- Modify: `auto_dungeon_daily.py`

- [ ] **Step 1: 写失败测试，覆盖第一件可买时优先兑换第一件**

```python
def test_claim_event_rewards_buys_purple_item_first(monkeypatch):
    ...
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `uv run pytest tests/test_auto_dungeon_daily_regression.py -m "not integration" -k purple_item_first -v`
Expected: FAIL，提示缺少目标兑换顺序逻辑

- [ ] **Step 3: 写失败测试，覆盖第一件已买后再买第二件**

```python
def test_claim_event_rewards_buys_blue_item_after_purple_in_same_cycle(monkeypatch):
    ...
```

- [ ] **Step 4: 运行测试并确认失败**

Run: `uv run pytest tests/test_auto_dungeon_daily_regression.py -m "not integration" -k blue_item_after -v`
Expected: FAIL

- [ ] **Step 5: 写失败测试，覆盖第一件不可买时不越过购买第二件**

```python
def test_claim_event_rewards_does_not_skip_unbought_purple_item(monkeypatch):
    ...
```

- [ ] **Step 6: 运行测试并确认失败**

Run: `uv run pytest tests/test_auto_dungeon_daily_regression.py -m "not integration" -k does_not_skip -v`
Expected: FAIL

- [ ] **Step 7: 提交测试骨架**

```bash
git add tests/test_auto_dungeon_daily_regression.py
git commit -m "test: cover event exchange ordering"
```

### Task 4: 实现兑换页状态解析与顺序执行

**Files:**
- Modify: `auto_dungeon_daily.py`
- Test: `tests/test_auto_dungeon_daily_regression.py`

- [ ] **Step 1: 新增兑换项状态数据结构与解析辅助函数**

```python
@dataclass
class EventExchangeItemState:
    row_index: int
    item_key: str
    required_tickets: int
    current_tickets: int | None
    button_center: tuple[int, int] | None
    is_affordable_by_color: bool | None
```

- [ ] **Step 2: 最小实现前两行 OCR 读取和 `x/y` 文本解析**

```python
def _parse_exchange_progress(self, text: str) -> tuple[int | None, int | None]:
    ...
```

- [ ] **Step 3: 实现“先紫后蓝”的兑换状态机**

```python
def _redeem_fire_tower_ticket_items(self) -> bool:
    ...
```

- [ ] **Step 4: 在 `_claim_event_rewards()` 中接入新兑换逻辑**

```python
exchange_success = self._redeem_fire_tower_ticket_items()
```

- [ ] **Step 5: 运行回归测试并确认通过**

Run: `uv run pytest tests/test_auto_dungeon_daily_regression.py -m "not integration" -v`
Expected: PASS

- [ ] **Step 6: 提交兑换逻辑实现**

```bash
git add auto_dungeon_daily.py tests/test_auto_dungeon_daily_regression.py
git commit -m "feat: redeem fire tower tickets safely"
```

## Chunk 3: 验证、类型检查与真机干跑

### Task 5: 运行项目级校验

**Files:**
- Modify: `auto_dungeon_daily.py`
- Modify: `database/dungeon_db.py`
- Modify: `tests/test_auto_dungeon_daily_regression.py`
- Modify: `tests/test_database.py`

- [ ] **Step 1: 运行 Ruff**

Run: `uv run ruff check .`
Expected: PASS

- [ ] **Step 2: 运行 Pyright**

Run: `uv run pyright`
Expected: PASS

- [ ] **Step 3: 运行相关 pytest（跳过集成测试）**

Run: `uv run pytest tests/test_database.py tests/test_auto_dungeon_daily_regression.py -m "not integration" -v`
Expected: PASS

- [ ] **Step 4: 运行用户要求的 dry-run 命令**

Run: `uv run E:\\Projects\\miniwowbot\\run_dungeons.py --emulator 192.168.1.150:5555 --logfile log\\autodungeon_main.log --session main --config mage --config warrior --dryrun`
Expected: 正常退出，不报错

- [ ] **Step 5: 提交最终实现**

```bash
git add auto_dungeon_daily.py database/dungeon_db.py tests/test_auto_dungeon_daily_regression.py tests/test_database.py docs/superpowers/specs/2026-03-19-dailycollect-ticket-exchange-design.md docs/superpowers/plans/2026-03-19-dailycollect-ticket-exchange.md
git commit -m "feat: add fire tower ticket exchange tracking"
```
