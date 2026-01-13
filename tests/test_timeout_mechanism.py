"""
测试 timeout 机制是否正确工作

这个测试验证：
1. wait_for_main() 函数是否被正确装饰
2. timeout 装饰器是否能正确中断长时间运行的函数
3. wait() 调用是否有正确的超时时间
"""

import pytest
import time
from unittest.mock import Mock

# Try to import wrapt_timeout_decorator, but handle if not available
try:
    from wrapt_timeout_decorator import timeout as timeout_decorator
    HAS_TIMEOUT_DECORATOR = True
except ImportError:
    HAS_TIMEOUT_DECORATOR = False
    # Create a mock timeout decorator for testing purposes
    def timeout_decorator(timeout, timeout_exception=Exception, exception_message=""):
        def decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator


def test_timeout_decorator_exists():
    """测试 timeout 装饰器是否存在"""
    from auto_dungeon import wait_for_main

    # 检查 wait_for_main 是否被装饰
    assert hasattr(wait_for_main, "__wrapped__"), (
        "wait_for_main 应该被 timeout 装饰器装饰"
    )


def test_timeout_decorator_interrupts_long_running_function():
    """测试 timeout 装饰器是否能中断长时间运行的函数"""
    if not HAS_TIMEOUT_DECORATOR:
        pytest.skip("wrapt_timeout_decorator not installed")

    @timeout_decorator(1, timeout_exception=TimeoutError, exception_message="[TIMEOUT]long_running_function 超时")
    def long_running_function():
        time.sleep(5)
        return "completed"

    with pytest.raises(TimeoutError):
        long_running_function()


def test_timeout_decorator_allows_quick_function():
    """测试 timeout 装饰器是否允许快速完成的函数"""
    if not HAS_TIMEOUT_DECORATOR:
        pytest.skip("wrapt_timeout_decorator not installed")

    @timeout_decorator(5, timeout_exception=TimeoutError, exception_message="[TIMEOUT]quick_function 超时")
    def quick_function():
        time.sleep(0.1)
        return "completed"

    result = quick_function()
    assert result == "completed"


def test_wait_for_main_uses_wait_not_exists():
    """测试 wait_for_main 是否使用 wait() 而不是 exists()"""
    from auto_dungeon import wait_for_main
    import inspect

    # 获取函数源代码
    source = inspect.getsource(wait_for_main)

    # 检查是否使用了 wait()
    assert "wait(" in source, "wait_for_main 应该使用 wait() 函数"

    # 检查是否没有使用 exists() 函数调用（排除注释）
    # 移除注释后检查
    lines = source.split("\n")
    code_lines = [line.split("#")[0] for line in lines]  # 移除注释
    code_without_comments = "\n".join(code_lines)

    # 检查是否没有 exists( 调用
    assert "exists(" not in code_without_comments, (
        "wait_for_main 不应该使用 exists() 函数"
    )


def test_auto_combat_uses_wait_not_exists():
    """测试 auto_combat 是否使用 wait() 而不是 exists()"""
    from auto_dungeon import auto_combat
    import inspect

    # 获取函数源代码
    source = inspect.getsource(auto_combat)

    # 检查是否使用了 wait()
    assert "wait(" in source, "auto_combat 应该使用 wait() 函数"

    # 移除注释后检查
    lines = source.split("\n")
    code_lines = [line.split("#")[0] for line in lines]
    code_without_comments = "\n".join(code_lines)

    # 检查是否没有 exists( 调用
    assert "exists(" not in code_without_comments, (
        "auto_combat 不应该使用 exists() 函数"
    )


def test_select_character_uses_wait_not_exists():
    """测试 select_character 是否使用 wait() 而不是 exists()"""
    from auto_dungeon import select_character
    import inspect

    # 获取函数源代码
    source = inspect.getsource(select_character)

    # 检查是否使用了 wait()
    assert "wait(" in source, "select_character 应该使用 wait() 函数"

    # 移除注释后检查
    lines = source.split("\n")
    code_lines = [line.split("#")[0] for line in lines]
    code_without_comments = "\n".join(code_lines)

    # 检查是否没有 exists( 调用
    assert "exists(" not in code_without_comments, (
        "select_character 不应该使用 exists() 函数"
    )


def test_exists_not_imported():
    """测试 exists 是否不再被导入"""
    import auto_dungeon

    # 检查 exists 是否在 auto_dungeon 的命名空间中
    # 如果 exists 被导入，它应该在模块的属性中
    assert not hasattr(auto_dungeon, "exists"), (
        "exists 不应该被导入到 auto_dungeon 模块中"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
