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
    
    def test_parse_gold_with_k_suffix(self):
        """测试带 k 后缀的金币数量"""
        # 一口价2000k金币 -> 2000000
        result = parse_gold_amount("一口价2000k金币")
        assert result == 2000000, f"期望 2000000，实际 {result}"
    
    def test_parse_gold_without_k_suffix(self):
        """测试不带 k 后缀的金币数量"""
        # 一口价100000金币 -> 100000
        result = parse_gold_amount("一口价100000金币")
        assert result == 100000, f"期望 100000，实际 {result}"
    
    def test_parse_gold_with_space(self):
        """测试带空格的金币数量"""
        # 一口价 2000 k 金币 -> 2000000
        result = parse_gold_amount("一口价 2000 k 金币")
        assert result == 2000000, f"期望 2000000，实际 {result}"
    
    def test_parse_gold_50k(self):
        """测试 50k 金币"""
        result = parse_gold_amount("一口价50k金币")
        assert result == 50000, f"期望 50000，实际 {result}"
    
    def test_parse_gold_100k(self):
        """测试 100k 金币"""
        result = parse_gold_amount("一口价100k金币")
        assert result == 100000, f"期望 100000，实际 {result}"
    
    def test_parse_gold_99k(self):
        """测试 99k 金币"""
        result = parse_gold_amount("一口价99k金币")
        assert result == 99000, f"期望 99000，实际 {result}"
    
    def test_parse_gold_with_decimal(self):
        """测试带小数的金币数量"""
        result = parse_gold_amount("一口价2.5k金币")
        assert result == 2500, f"期望 2500，实际 {result}"
    
    def test_parse_gold_invalid_text(self):
        """测试无效文本"""
        result = parse_gold_amount("这是一个无效的文本")
        assert result is None, f"期望 None，实际 {result}"
    
    def test_parse_gold_no_amount(self):
        """测试没有数字的文本"""
        result = parse_gold_amount("一口价金币")
        assert result is None, f"期望 None，实际 {result}"
    
    def test_parse_gold_with_extra_text(self):
        """测试带额外文本的金币数量"""
        result = parse_gold_amount("当前一口价1500k金币，快来购买")
        assert result == 1500000, f"期望 1500000，实际 {result}"
    
    def test_parse_gold_less_than_100k(self):
        """测试小于 100k 的金币"""
        result = parse_gold_amount("一口价50k金币")
        assert result < 100000, f"期望 < 100000，实际 {result}"
    
    def test_parse_gold_greater_than_100k(self):
        """测试大于 100k 的金币"""
        result = parse_gold_amount("一口价200k金币")
        assert result > 100000, f"期望 > 100000，实际 {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

