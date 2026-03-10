# BlueStacks Tool Start Stop Tests Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 `scripts/bluestack-tool.py` 的真实启动缺陷，补齐 `start` / `stop` 关键路径单元测试，并新增真实 BlueStacks 启停集成测试。

**Architecture:** 保持 `scripts/bluestack-tool.py` 单文件结构，但把“发送启动/停止命令”和“等待状态变化”明确拆开。单元测试覆盖命令分支与回退逻辑，集成测试只验证真实环境下从 stopped 到 running 再回到 stopped 的主流程。

**Tech Stack:** Python 3.10, pytest, unittest.mock, BlueStacks, adb, PowerShell

---

### Task 1: 固化当前回归根因

**Files:**
- Modify: `scripts/bluestack-tool.py`
- Test: `tests/test_bluestack_tool.py`

**Step 1: 写失败单元测试**

补充以下测试：
- `start_bluestacks_instance(..., no_wait=False)` 不应直接因为 `HD-Player.exe` 长时间存活而失败。
- `cmd_start` 在等待模式下应先成功发送启动命令，再调用 `wait_for_instance_status(...)`。
- `cmd_stop` 优先尝试实例级强制停止；失败后回退到 `adb emu kill`。

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_bluestack_tool.py -m "not integration" -k "start or stop" -v`

Expected: 至少 1 个新测试失败，且失败原因与当前启动/停止实现不符有关。

**Step 3: 写最小实现**

实现约束：
- 等待模式下的启动命令必须使用非阻塞方式发送。
- `wait_for_instance_status(...)` 负责等待，不由 `subprocess.run(..., timeout=5)` 代替。
- 停止命令的实例级 PowerShell 逻辑需要可测试，且移除不可达分支。

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_bluestack_tool.py -m "not integration" -k "start or stop" -v`

Expected: 新增 `start/stop` 相关测试全部通过。

### Task 2: 补齐停止路径的单元覆盖

**Files:**
- Modify: `tests/test_bluestack_tool.py`
- Modify: `scripts/bluestack-tool.py`

**Step 1: 写失败单元测试**

补充以下用例：
- `resolve_adb_serial_from_map(...)` 能匹配 `127.0.0.1:{expected_port + 1}`。
- `find_and_kill_bluestacks_instance(...)` 成功、失败、超时三种结果。
- `disconnect_instance(...)` / `stop_instance_via_adb(...)` 在传入匹配 serial 时使用实际 serial。

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_bluestack_tool.py -m "not integration" -k "resolve_adb_serial or kill or disconnect" -v`

Expected: 新测试先红灯，再进入实现。

**Step 3: 写最小实现**

实现约束：
- 保留 PowerShell 脚本调用，但命令、返回值和错误信息要可预测。
- 删除不可达代码和未使用分支，避免单文件内部重复策略。

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_bluestack_tool.py -m "not integration" -v`

Expected: `test_bluestack_tool.py` 全绿。

### Task 3: 新增真实 BlueStacks 启停集成测试

**Files:**
- Create: `tests/test_bluestack_tool_integration.py`
- Modify: `scripts/bluestack-tool.py`

**Step 1: 写失败集成测试**

新增 `pytest.mark.integration` 测试类，覆盖：
- 查询环境依赖（BlueStacks player、adb、默认实例）；
- 启动目标实例并等待 `running`；
- 调用 `stop` 后等待 `stopped`；
- 测试结束时保证清理，避免残留运行中的模拟器。

**Step 2: 运行集成测试确认失败或暴露真实问题**

Run: `uv run pytest tests/test_bluestack_tool_integration.py -m integration -v -s`

Expected: 如果实现未完成，测试应在启动或停止阶段失败，并给出真实环境错误。

**Step 3: 写最小实现**

实现约束：
- 默认选择一个配置实例执行真实启停。
- 若环境缺少 BlueStacks/adb/实例映射，测试应 `skip` 而不是误报失败。
- `finally` 中必须确保调用停止逻辑清理环境。

**Step 4: 运行集成测试确认通过**

Run: `uv run pytest tests/test_bluestack_tool_integration.py -m integration -v -s`

Expected: 真实启停流程通过。

### Task 4: 全量验证与交付

**Files:**
- Modify: `scripts/bluestack-tool.py`
- Modify: `tests/test_bluestack_tool.py`
- Create: `tests/test_bluestack_tool_integration.py`

**Step 1: 运行测试**

Run: `uv run pytest tests/test_bluestack_tool.py tests/test_bluestack_tool_integration.py -m "not integration" -v`

Expected: 非集成测试通过。

**Step 2: 运行静态检查**

Run: `uv run ruff check .`

Expected: 0 errors.

**Step 3: 运行类型检查**

Run: `uv run pyright`

Expected: 0 errors.

**Step 4: 运行项目 dryrun 验证**

Run: `uv run E:\Projects\miniwowbot\.worktrees\bluestack-stop-tests\run_dungeons.py --emulator 192.168.1.150:5555 --logfile log\autodungeon_main.log --session main --config mage --config warrior --dryrun`

Expected: 命令正常退出，无报错。

**Step 5: 查看变更并提交**

Run:
- `git status --short`
- `git add scripts/bluestack-tool.py tests/test_bluestack_tool.py tests/test_bluestack_tool_integration.py docs/plans/2026-03-10-bluestack-tool-start-stop-tests.md`
- `git commit -m "fix: cover bluestacks start stop flows"`
