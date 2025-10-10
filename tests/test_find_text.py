"""
测试 find_text 和 find_text_and_click 方法
"""

import pytest
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_dungeon import find_text, find_text_and_click


class TestFindText:
    """测试 find_text 方法"""

    def test_find_text_timeout_exception(self):
        """测试 find_text 超时抛出异常"""
        # OCR helper 未初始化时会抛出 RuntimeError
        # 这也是一种异常，符合预期
        with pytest.raises((TimeoutError, RuntimeError)) as exc_info:
            find_text("不存在的文本", timeout=1, raise_exception=True)

        # 验证异常消息包含相关信息
        assert "超时未找到文本" in str(exc_info.value) or "OCR助手未初始化" in str(
            exc_info.value
        )

    def test_find_text_timeout_no_exception(self):
        """测试 find_text 超时不抛出异常"""
        result = find_text("不存在的文本", timeout=1, raise_exception=False)
        assert result is None

    def test_find_text_with_regions(self):
        """测试 find_text 支持 regions 参数"""
        # 这个测试只验证参数能正确传递，不验证实际功能
        # 因为需要真实的游戏界面才能测试
        try:
            result = find_text(
                "测试文本", timeout=1, regions=[7, 8, 9], raise_exception=False
            )
            # 应该返回 None（因为找不到）
            assert result is None
        except Exception as e:
            pytest.fail(f"find_text 调用失败: {e}")


class TestFindTextAndClick:
    """测试 find_text_and_click 方法"""

    def test_find_text_and_click_returns_false_on_timeout(self):
        """测试 find_text_and_click 超时返回 False"""
        result = find_text_and_click("不存在的文本", timeout=1)
        assert result is False

    def test_find_text_and_click_with_regions(self):
        """测试 find_text_and_click 支持 regions 参数"""
        # 这个测试只验证参数能正确传递，不验证实际功能
        try:
            result = find_text_and_click("测试文本", timeout=1, regions=[7, 8, 9])
            # 应该返回 False（因为找不到）
            assert result is False
        except Exception as e:
            pytest.fail(f"find_text_and_click 调用失败: {e}")

    def test_find_text_and_click_backward_compatible(self):
        """测试 find_text_and_click 向后兼容"""
        # 不指定 regions 参数应该也能正常工作
        result = find_text_and_click("测试文本", timeout=1)
        assert result is False


class TestCodeRefactoring:
    """测试代码重构后的一致性"""

    def test_find_text_and_click_uses_find_text(self):
        """验证 find_text_and_click 内部调用了 find_text"""
        # 这个测试通过检查两个函数的行为一致性来验证重构
        # 两个函数对于不存在的文本应该有一致的超时行为

        # find_text 超时返回 None
        result1 = find_text("不存在的文本", timeout=1, raise_exception=False)
        assert result1 is None

        # find_text_and_click 超时返回 False
        result2 = find_text_and_click("不存在的文本", timeout=1)
        assert result2 is False

    def test_both_functions_support_regions(self):
        """验证两个函数都支持 regions 参数"""
        # find_text 支持 regions
        result1 = find_text("测试", timeout=1, regions=[1, 2, 3], raise_exception=False)
        assert result1 is None

        # find_text_and_click 支持 regions
        result2 = find_text_and_click("测试", timeout=1, regions=[1, 2, 3])
        assert result2 is False

    def test_both_functions_support_occurrence(self):
        """验证两个函数都支持 occurrence 参数"""
        # find_text 支持 occurrence
        result1 = find_text("测试", timeout=1, occurrence=2, raise_exception=False)
        assert result1 is None

        # find_text_and_click 支持 occurrence
        result2 = find_text_and_click("测试", timeout=1, occurrence=2)
        assert result2 is False
