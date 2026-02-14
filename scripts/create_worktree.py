#!/usr/bin/env python3
"""
创建新 worktree 的脚本

用法:
    python create_worktree.py <worktree-name> [--branch <branch-name>] [--create-branch]

示例:
    python create_worktree.py feature_new_dungeon
    python create_worktree.py feature_new_dungeon --create-branch
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str], cwd: Path | None = None) -> str:
    """运行命令并返回输出"""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running command: {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result.stdout.strip()


def get_current_branch(project_root: Path) -> str:
    """获取当前分支"""
    return run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root)


def get_worktree_branches(project_root: Path) -> dict[str, str]:
    """获取所有 worktree 使用的分支映射 {path: branch}"""
    output = run_cmd(["git", "worktree", "list"], cwd=project_root)
    result = {}
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 3 and parts[1].startswith("e") and "[" in parts[-1]:
            wt_path = parts[0]
            branch = parts[-1].strip("[]")
            result[wt_path] = branch
    return result


def create_worktree(
    project_root: Path,
    name: str,
    branch: str,
    create_branch: bool,
):
    """创建 worktree"""
    worktree_path = project_root / ".worktrees" / name

    # 检查 worktree 是否已存在
    if worktree_path.exists():
        print(f"Error: worktree '{name}' already exists at {worktree_path}")
        sys.exit(1)

    print(f"=== 创建 worktree: {name} ===")

    # 0. 如果需要创建新分支（仅显示信息，实际由 git worktree add -b 处理）
    if create_branch:
        print("\n[0/3] 创建新分支并 worktree...")

    # 1. 创建 worktree
    step_num = 1 if not create_branch else 1
    print(f"\n[{step_num}/3] 创建 worktree...")
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


def main():
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

    # 获取分支
    branch = args.branch
    if not branch:
        branch = get_current_branch(project_root)
        print(f"使用当前分支: {branch}")

    # 获取所有 worktree 使用的分支
    worktree_branches = get_worktree_branches(project_root)

    # 检查分支是否已被使用（包括当前目录）
    branch_in_use = False
    for wt_path, wt_branch in worktree_branches.items():
        if wt_branch == branch:
            branch_in_use = True
            print(f"Warning: 分支 '{branch}' 已被 worktree 使用: {wt_path}")
            break

    if branch_in_use:
        if args.create_branch:
            print(f"分支 '{branch}' 已被使用，将使用新分支: {args.name}")
            branch = args.name
        else:
            print(f"Error: 分支 '{branch}' 已被其他 worktree 使用")
            print("请使用 --create-branch 参数创建新分支")
            print(f"示例: python create_worktree.py {args.name} --create-branch")
            sys.exit(1)

    create_worktree(project_root, args.name, branch, args.create_branch)


if __name__ == "__main__":
    main()
