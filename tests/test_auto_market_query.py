"""
自动化市场查询脚本的单元测试
"""

import pytest
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_market_query import parse_gold_amount


class TestParseGoldAmount:
    """测试金币数量解析函数"""

    def test_parse_gold_standard_format(self):
        """测试标准格式 '一口价 2000k 金币'"""
        result = parse_gold_amount("一口价 2000k 金币")
        assert result == 2000000, f"期望 2000000，实际 {result}"

    def test_parse_gold_no_space(self):
        """测试无空格格式 '一口价2000k金币'"""
        result = parse_gold_amount("一口价2000k金币")
        assert result == 2000000, f"期望 2000000，实际 {result}"

    def test_parse_gold_extra_space(self):
        """测试多空格格式 '一口价  2000  k  金币'"""
        result = parse_gold_amount("一口价  2000  k  金币")
        assert result == 2000000, f"期望 2000000，实际 {result}"

    def test_parse_gold_50k(self):
        """测试 50k 金币"""
        result = parse_gold_amount("一口价 50k 金币")
        assert result == 50000, f"期望 50000，实际 {result}"

    def test_parse_gold_100k(self):
        """测试 100k 金币"""
        result = parse_gold_amount("一口价 100k 金币")
        assert result == 100000, f"期望 100000，实际 {result}"

    def test_parse_gold_99k(self):
        """测试 99k 金币"""
        result = parse_gold_amount("一口价 99k 金币")
        assert result == 99000, f"期望 99000，实际 {result}"

    def test_parse_gold_with_decimal(self):
        """测试带小数的金币数量"""
        result = parse_gold_amount("一口价 2.5k 金币")
        assert result == 2500, f"期望 2500，实际 {result}"

    def test_parse_gold_invalid_text(self):
        """测试无效文本"""
        result = parse_gold_amount("这是一个无效的文本")
        assert result is None, f"期望 None，实际 {result}"

    def test_parse_gold_missing_pattern(self):
        """测试缺少模式的文本"""
        result = parse_gold_amount("2000k")
        assert result is None, f"期望 None，实际 {result}"

    def test_parse_gold_missing_k(self):
        """测试缺少 k 的文本"""
        result = parse_gold_amount("一口价 2000 金币")
        assert result == 2000, f"期望 2000，实际 {result}"

    def test_parse_gold_uppercase_k(self):
        """测试大写 K 格式 '一口价2000K金币'"""
        result = parse_gold_amount("一口价2000K金币")
        assert result == 2000000, f"期望 2000000，实际 {result}"

    def test_parse_gold_uppercase_k_with_space(self):
        """测试大写 K 格式带空格 '一口价 2000 K 金币'"""
        result = parse_gold_amount("一口价 2000 K 金币")
        assert result == 2000000, f"期望 2000000，实际 {result}"

    def test_parse_gold_no_k_suffix(self):
        """测试不带 k/K 的格式 '一口价88888金币'"""
        result = parse_gold_amount("一口价88888金币")
        assert result == 88888, f"期望 88888，实际 {result}"

    def test_parse_gold_no_k_suffix_with_space(self):
        """测试不带 k/K 的格式带空格 '一口价 88888 金币'"""
        result = parse_gold_amount("一口价 88888 金币")
        assert result == 88888, f"期望 88888，实际 {result}"

    def test_parse_gold_less_than_100k(self):
        """测试小于 100k 的金币"""
        result = parse_gold_amount("一口价 50k 金币")
        assert result < 100000, f"期望 < 100000，实际 {result}"

    def test_parse_gold_greater_than_100k(self):
        """测试大于 100k 的金币"""
        result = parse_gold_amount("一口价 200k 金币")
        assert result > 100000, f"期望 > 100000，实际 {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
