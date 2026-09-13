## 编码规范

- 新增或修改的公开 Python 接口使用 Google 风格 docstring；不为局部修改清理无关现存代码。

## 测试说明

- 在测试的时候需要需要使用 `-m "not integration"` 参数跳过集成测试，不要写到pytest.ini中
- 如需手动运行集成测试：`uv run pytest -m integration -v -s`（或在命令行覆盖 `-m "not integration"`）
- 副本运行链路修改后，在具备目标环境的 Windows 主机运行 `uv run run_dungeons.py --emulator 192.168.1.150:5555 --logfile log/autodungeon_main.log --session main --config mage --config warrior --dryrun`。本机 macOS 不直接使用旧的 `E:\Projects\...` 路径。
- 纯文档修改检查文档即可，不连接模拟器。完成后仅提交本次改动并推送 GitHub；合并 main 仍需用户审核。

## Worktree 工具

项目提供了 `scripts/create_worktree.py` 脚本用于创建 Git Worktree, 在实现功能的时候, 首先要创建一个worktree, 测试完成通过后, 用户审核再决定是否合并到main.

### 基本用法

```bash
# 使用当前分支创建 worktree
python scripts/create_worktree.py <worktree-name>

# 创建新分支并创建 worktree
python scripts/create_worktree.py <worktree-name> --create-branch

# 使用指定分支创建 worktree
python scripts/create_worktree.py <worktree-name> --branch <branch-name>
```

### 说明

- Worktree 保存在 `.worktrees/<name>` 目录下
- 创建时会自动复制 `.env` 文件和 `database` 目录
- 虚拟环境在新 worktree 中用 `uv` 管理。
- 同一个分支只能被一个 worktree 使用
