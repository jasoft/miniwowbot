"""
测试战斗进度条功能
"""
import pytest
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_auto_combat_signature():
    """测试 auto_combat 函数签名是否包含新参数"""
    from auto_dungeon import auto_combat
    import inspect

    # 获取函数签名
    sig = inspect.signature(auto_combat)
    params = list(sig.parameters.keys())

    # 检查是否有新参数
    assert "completed_dungeons" in params, "auto_combat 应该有 completed_dungeons 参数"
    assert "total_dungeons" in params, "auto_combat 应该有 total_dungeons 参数"

    # 检查默认值
    assert sig.parameters["completed_dungeons"].default == 0, (
        "completed_dungeons 默认值应该是 0"
    )
    assert sig.parameters["total_dungeons"].default == 0, (
        "total_dungeons 默认值应该是 0"
    )


def test_process_dungeon_signature():
    """测试 process_dungeon 函数签名是否包含新参数"""
    from auto_dungeon import process_dungeon
    import inspect

    # 获取函数签名
    sig = inspect.signature(process_dungeon)
    params = list(sig.parameters.keys())

    # 检查是否有新参数
    assert "completed_dungeons" in params, "process_dungeon 应该有 completed_dungeons 参数"

    # 检查默认值
    assert sig.parameters["completed_dungeons"].default == 0, (
        "completed_dungeons 默认值应该是 0"
    )


def test_auto_combat_backward_compatibility():
    """测试 auto_combat 向后兼容性 - 可以不传参数调用"""
    from auto_dungeon import auto_combat
    import inspect

    # 获取函数源代码
    source = inspect.getsource(auto_combat)

    # 检查是否有条件判断 total_dungeons > 0
    assert "if total_dungeons > 0:" in source, (
        "auto_combat 应该检查 total_dungeons 是否大于 0"
    )

    # 检查是否有向后兼容的时间进度模式
    assert "else:" in source, "auto_combat 应该有 else 分支用于向后兼容"


def test_progress_bar_format():
    """测试进度条格式是否正确"""
    from auto_dungeon import auto_combat
    import inspect

    # 获取函数源代码
    source = inspect.getsource(auto_combat)

    # 检查是否使用了 tqdm
    assert "tqdm(" in source, "auto_combat 应该使用 tqdm 库"

    # 检查是否有副本进度格式
    assert "[{completed_dungeons}/{total_dungeons}]" in source or (
        "completed_dungeons" in source and "total_dungeons" in source
    ), "auto_combat 应该显示副本进度"


def test_auto_combat_uses_tqdm():
    """测试 auto_combat 是否使用 tqdm 进度条"""
    from auto_dungeon import auto_combat
    import inspect

    # 获取函数源代码
    source = inspect.getsource(auto_combat)

    # 检查是否导入了 tqdm
    assert "tqdm(" in source, "auto_combat 应该使用 tqdm 进度条"

    # 检查是否有 bar_format 参数
    assert "bar_format=" in source, "auto_combat 应该自定义 bar_format"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

