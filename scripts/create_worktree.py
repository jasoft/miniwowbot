#!/usr/bin/env python3
"""
创建 Git worktree 的脚本。

该脚本支持三种模式：
1. 使用当前分支创建 worktree（默认）
2. 使用指定分支创建 worktree（`--branch`）
3. 创建新分支并创建 worktree（`--create-branch`）
"""

import argparse
import locale
import shutil
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str], cwd: Path | None = None) -> str:
    """运行命令并返回标准输出。

    Args:
        cmd: 要执行的命令参数列表。
        cwd: 命令工作目录。

    Returns:
        标准输出文本（去除首尾空白）。

    Raises:
        RuntimeError: 命令执行失败时抛出。
    """
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=False)
    stdout_text = decode_output(result.stdout)
    stderr_text = decode_output(result.stderr)
    if result.returncode != 0:
        print(f"Error running command: {' '.join(cmd)}", file=sys.stderr)
        error_text = stderr_text.strip() or stdout_text.strip()
        if error_text:
            print(error_text, file=sys.stderr)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return stdout_text.strip()


def decode_output(raw_output: bytes | None) -> str:
    """安全解码子进程输出字节流。

    Args:
        raw_output: 子进程原始字节输出。

    Returns:
        解码后的字符串；无法精确解码时使用替换字符兜底。
    """
    if raw_output is None:
        return ""

    candidate_encodings = (
        "utf-8",
        locale.getpreferredencoding(False) or "utf-8",
        "gbk",
    )
    for encoding in candidate_encodings:
        try:
            return raw_output.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw_output.decode("utf-8", errors="replace")


def get_current_branch(project_root: Path) -> str:
    """获取当前 Git 分支名称。

    Args:
        project_root: 项目根目录。

    Returns:
        当前分支名。
    """
    return run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root)


def get_worktree_branches(project_root: Path) -> dict[str, str]:
    """获取所有 worktree 使用的分支映射。

    Args:
        project_root: 项目根目录。

    Returns:
        键为 worktree 路径，值为分支名称的字典。
    """
    output = run_cmd(["git", "worktree", "list", "--porcelain"], cwd=project_root)
    return parse_worktree_porcelain(output)


def parse_worktree_porcelain(output: str) -> dict[str, str]:
    """解析 `git worktree list --porcelain` 输出。

    Args:
        output: `git worktree list --porcelain` 输出文本。

    Returns:
        键为 worktree 路径，值为分支名称的字典。
    """
    branches: dict[str, str] = {}
    current_path: str | None = None
    current_branch: str | None = None

    def flush_current() -> None:
        """把当前解析块写入结果。"""
        nonlocal current_path, current_branch
        if current_path and current_branch:
            branches[current_path] = current_branch
        current_path = None
        current_branch = None

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            flush_current()
            continue
        if line.startswith("worktree "):
            flush_current()
            current_path = line.removeprefix("worktree ").strip()
            continue
        if line.startswith("branch "):
            branch_ref = line.removeprefix("branch ").strip()
            current_branch = normalize_branch_ref(branch_ref)

    flush_current()
    return branches


def normalize_branch_ref(branch_ref: str) -> str:
    """把 `refs/heads/*` 形式规范为分支名。

    Args:
        branch_ref: 原始分支引用文本。

    Returns:
        规范化后的分支名。
    """
    prefix = "refs/heads/"
    if branch_ref.startswith(prefix):
        return branch_ref[len(prefix) :]
    return branch_ref


def resolve_target_branch(
    project_root: Path,
    worktree_name: str,
    branch_arg: str | None,
    create_branch: bool,
) -> str:
    """解析本次操作的目标分支。

    Args:
        project_root: 项目根目录。
        worktree_name: worktree 名称。
        branch_arg: 命令行 `--branch` 参数。
        create_branch: 是否创建新分支。

    Returns:
        目标分支名。
    """
    if create_branch:
        if branch_arg:
            return branch_arg
        return worktree_name

    if branch_arg:
        return branch_arg

    current_branch = get_current_branch(project_root)
    print(f"使用当前分支: {current_branch}")
    return current_branch


def branch_exists(project_root: Path, branch: str) -> bool:
    """检查本地分支是否已存在。

    Args:
        project_root: 项目根目录。
        branch: 分支名称。

    Returns:
        分支存在返回 `True`，否则返回 `False`。
    """
    branch_name = normalize_branch_ref(branch)
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
        cwd=project_root,
        capture_output=True,
        text=False,
    )
    return result.returncode == 0


def find_branch_worktree(worktree_branches: dict[str, str], branch: str) -> str | None:
    """查找分支正在被哪个 worktree 使用。

    Args:
        worktree_branches: worktree 到分支的映射。
        branch: 要查询的分支名。

    Returns:
        若分支被使用，返回 worktree 路径；否则返回 `None`。
    """
    for wt_path, wt_branch in worktree_branches.items():
        if wt_branch == branch:
            return wt_path
    return None


def create_worktree(
    project_root: Path,
    name: str,
    branch: str,
    create_branch: bool,
) -> None:
    """创建 worktree 并复制必要文件。

    Args:
        project_root: 项目根目录。
        name: worktree 名称。
        branch: 目标分支名。
        create_branch: 是否创建新分支。
    """
    worktree_path = project_root / ".worktrees" / name

    # 检查 worktree 是否已存在
    if worktree_path.exists():
        print(f"Error: worktree '{name}' already exists at {worktree_path}")
        sys.exit(1)

    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"=== 创建 worktree: {name} ===")

    # 0. 如果需要创建新分支（仅显示信息，实际由 git worktree add -b 处理）
    if create_branch:
        print("\n[0/3] 创建新分支并 worktree...")

    # 1. 创建 worktree
    print("\n[1/3] 创建 worktree...")
    if create_branch:
        # 使用 -b 创建新分支
        run_cmd(
            ["git", "worktree", "add", "-b", branch, str(worktree_path)],
            cwd=project_root,
        )
    else:
        run_cmd(
            ["git", "worktree", "add", str(worktree_path), branch], cwd=project_root
        )
    print(f"  [OK] worktree 创建成功: {worktree_path}")

    # 2. 复制 .env 文件
    print("\n[2/3] 复制 .env 文件...")
    env_source = project_root / ".env"
    env_dest = worktree_path / ".env"

    if env_source.exists():
        shutil.copy2(env_source, env_dest)
        print("  [OK] .env 复制成功")
    else:
        print("  [WARN] 源 .env 文件不存在，跳过复制")

    # 3. 复制 database 目录
    print("\n[3/3] 复制 database 目录...")
    db_source = project_root / "database"
    db_dest = worktree_path / "database"

    if db_source.exists():
        if db_dest.exists():
            shutil.rmtree(db_dest)
        shutil.copytree(db_source, db_dest)
        print("  [OK] database 目录复制成功")
    else:
        print("  [WARN] 源 database 目录不存在，跳过复制")

    print("\n=== 完成! ===")
    print(f"Worktree 路径: {worktree_path}")
    print(f"分支: {branch}")
    print("\n进入 worktree:")
    print(f"  cd {worktree_path}")
    print("\n激活虚拟环境 (需要重新创建):")
    print("  python -m venv .venv")
    print("  .venv\\Scripts\\Activate  (Windows)")
    print("  source .venv/bin/activate  (Linux/Mac)")


def main() -> None:
    """脚本主入口。"""
    parser = argparse.ArgumentParser(description="创建新 worktree")
    parser.add_argument("name", help="worktree 名称")
    parser.add_argument("--branch", "-b", help="分支名称 (默认使用当前分支)")
    parser.add_argument(
        "--create-branch", "-c", action="store_true", help="创建新分支"
    )

    args = parser.parse_args()

    # 获取项目根目录 (脚本所在目录的父目录)
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent

    # 验证项目根目录
    if not (project_root / ".git").exists():
        print("Error: 找不到 .git 目录，请确保脚本在项目目录下运行")
        sys.exit(1)

    branch = resolve_target_branch(
        project_root=project_root,
        worktree_name=args.name,
        branch_arg=args.branch,
        create_branch=args.create_branch,
    )
    branch = normalize_branch_ref(branch)

    if args.create_branch:
        if branch_exists(project_root, branch):
            print(f"Error: 目标新分支 '{branch}' 已存在")
            print("请更换分支名，或去掉 --create-branch 直接使用该分支")
            sys.exit(1)
    else:
        worktree_branches = get_worktree_branches(project_root)
        in_use_path = find_branch_worktree(worktree_branches, branch)
        if in_use_path:
            print(f"Warning: 分支 '{branch}' 已被 worktree 使用: {in_use_path}")
            print(f"Error: 分支 '{branch}' 已被其他 worktree 使用")
            print("请使用 --create-branch 参数创建新分支")
            print(f"示例: python create_worktree.py {args.name} --create-branch")
            sys.exit(1)

    try:
        create_worktree(project_root, args.name, branch, args.create_branch)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
