"""`scripts/create_worktree.py` 的关键逻辑测试。"""

from __future__ import annotations

from pathlib import Path

from scripts import create_worktree


def test_parse_worktree_porcelain_returns_branch_mapping() -> None:
    """验证 porcelain 输出可以正确解析为路径与分支映射。"""
    output = (
        "worktree E:/Projects/miniwowbot\n"
        "HEAD 1111111111111111111111111111111111111111\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree E:/Projects/miniwowbot/.worktrees/dev\n"
        "HEAD 2222222222222222222222222222222222222222\n"
        "branch refs/heads/dev\n"
        "\n"
    )

    branches = create_worktree.parse_worktree_porcelain(output)

    assert branches == {
        "E:/Projects/miniwowbot": "main",
        "E:/Projects/miniwowbot/.worktrees/dev": "dev",
    }


def test_resolve_target_branch_for_create_branch_uses_worktree_name() -> None:
    """验证 create 模式未传 --branch 时使用 worktree 名称作为新分支名。"""
    branch = create_worktree.resolve_target_branch(
        project_root=Path("."),
        worktree_name="feature_x",
        branch_arg=None,
        create_branch=True,
    )

    assert branch == "feature_x"


def test_resolve_target_branch_for_create_branch_prefers_branch_arg() -> None:
    """验证 create 模式优先使用 --branch 指定的新分支名。"""
    branch = create_worktree.resolve_target_branch(
        project_root=Path("."),
        worktree_name="feature_x",
        branch_arg="feature/custom",
        create_branch=True,
    )

    assert branch == "feature/custom"


def test_resolve_target_branch_uses_current_branch_when_not_create(monkeypatch) -> None:
    """验证非 create 模式未传 --branch 时使用当前分支。"""
    monkeypatch.setattr(create_worktree, "get_current_branch", lambda _root: "main")

    branch = create_worktree.resolve_target_branch(
        project_root=Path("."),
        worktree_name="feature_x",
        branch_arg=None,
        create_branch=False,
    )

    assert branch == "main"


def test_normalize_branch_ref() -> None:
    """验证 `refs/heads/*` 能被正确归一化。"""
    assert create_worktree.normalize_branch_ref("refs/heads/main") == "main"
    assert create_worktree.normalize_branch_ref("feature/custom") == "feature/custom"
