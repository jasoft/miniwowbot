#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试 OCR API 性能基准测试功能
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.quick_test_ocr_api import benchmark_ocr, ocr_request_once


class TestOCRBenchmark:
    """测试 OCR 基准测试功能"""

    @patch("scripts.quick_test_ocr_api.time.time")
    @patch("scripts.quick_test_ocr_api.requests.post")
    @patch("builtins.open", create=True)
    @patch("os.path.exists")
    def test_ocr_once_success(self, mock_exists, mock_open, mock_post, mock_time):
        """测试单次 OCR 请求成功"""
        # 模拟文件存在
        mock_exists.return_value = True

        # 模拟文件读取
        mock_file = MagicMock()
        mock_file.read.return_value = b"fake_image_data"
        mock_open.return_value.__enter__.return_value = mock_file

        # 模拟时间流逝（1.5秒）
        mock_time.side_effect = [100.0, 101.5]

        # 模拟成功的响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errorCode": 0,
            "result": {"ocrResults": [{"prunedResult": {"rec_texts": ["测试文本1", "测试文本2"]}}]},
        }
        mock_post.return_value = mock_response

        # 执行测试
        elapsed = ocr_request_once("test.png", verbose=False)

        # 验证
        assert elapsed is not None
        assert elapsed > 0
        assert abs(elapsed - 1.5) < 0.01  # 允许小误差
        assert isinstance(elapsed, float)
        mock_post.assert_called_once()

    @patch("os.path.exists")
    def test_ocr_once_file_not_exists(self, mock_exists):
        """测试文件不存在的情况"""
        mock_exists.return_value = False

        elapsed = ocr_request_once("nonexistent.png", verbose=False)

        assert elapsed is None

    @patch("scripts.quick_test_ocr_api.requests.post")
    @patch("builtins.open", create=True)
    @patch("os.path.exists")
    def test_ocr_once_server_error(self, mock_exists, mock_open, mock_post):
        """测试服务器错误的情况"""
        mock_exists.return_value = True

        mock_file = MagicMock()
        mock_file.read.return_value = b"fake_image_data"
        mock_open.return_value.__enter__.return_value = mock_file

        # 模拟服务器错误
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        elapsed = ocr_request_once("test.png", verbose=False)

        assert elapsed is None

    @patch("scripts.quick_test_ocr_api.requests.post")
    @patch("builtins.open", create=True)
    @patch("os.path.exists")
    def test_ocr_once_ocr_error(self, mock_exists, mock_open, mock_post):
        """测试 OCR 识别错误的情况"""
        mock_exists.return_value = True

        mock_file = MagicMock()
        mock_file.read.return_value = b"fake_image_data"
        mock_open.return_value.__enter__.return_value = mock_file

        # 模拟 OCR 错误响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errorCode": 1, "errorMsg": "OCR failed"}
        mock_post.return_value = mock_response

        elapsed = ocr_request_once("test.png", verbose=False)

        assert elapsed is None

    @patch("scripts.quick_test_ocr_api.requests.post")
    @patch("builtins.open", create=True)
    @patch("os.path.exists")
    def test_ocr_once_network_exception(self, mock_exists, mock_open, mock_post):
        """测试网络异常的情况"""
        mock_exists.return_value = True

        mock_file = MagicMock()
        mock_file.read.return_value = b"fake_image_data"
        mock_open.return_value.__enter__.return_value = mock_file

        # 模拟网络异常
        mock_post.side_effect = Exception("Network error")

        elapsed = ocr_request_once("test.png", verbose=False)

        assert elapsed is None

    @patch("scripts.quick_test_ocr_api.ocr_request_once")
    @patch("os.path.exists")
    @patch("time.sleep")
    def test_benchmark_ocr_all_success(self, mock_sleep, mock_exists, mock_test_ocr):
        """测试基准测试全部成功的情况"""
        mock_exists.return_value = True

        # 模拟 5 次成功的请求，返回不同的耗时
        mock_test_ocr.side_effect = [1.1, 1.2, 1.3, 1.0, 1.4]

        # 捕获打印输出
        with patch("builtins.print"):
            benchmark_ocr("test.png", num_requests=5, interval=0.1)

        # 验证调用次数
        assert mock_test_ocr.call_count == 5
        # 验证 sleep 被调用了 4 次（最后一次不需要 sleep）
        assert mock_sleep.call_count == 4

    @patch("scripts.quick_test_ocr_api.ocr_request_once")
    @patch("os.path.exists")
    @patch("time.sleep")
    def test_benchmark_ocr_partial_failure(self, mock_sleep, mock_exists, mock_test_ocr):
        """测试基准测试部分失败的情况"""
        mock_exists.return_value = True

        # 模拟部分请求失败（返回 None）
        mock_test_ocr.side_effect = [1.1, None, 1.3, None, 1.4]

        with patch("builtins.print"):
            benchmark_ocr("test.png", num_requests=5, interval=0.1)

        # 验证调用次数
        assert mock_test_ocr.call_count == 5

    @patch("os.path.exists")
    def test_benchmark_ocr_file_not_exists(self, mock_exists):
        """测试文件不存在的情况"""
        mock_exists.return_value = False

        with patch("builtins.print") as mock_print:
            benchmark_ocr("nonexistent.png", num_requests=5)

        # 验证打印了错误信息
        error_printed = any("找不到图片" in str(call) for call in mock_print.call_args_list)
        assert error_printed

    @patch("scripts.quick_test_ocr_api.ocr_request_once")
    @patch("os.path.exists")
    @patch("time.sleep")
    def test_benchmark_ocr_statistics(self, mock_sleep, mock_exists, mock_test_ocr):
        """测试统计数据的计算"""
        mock_exists.return_value = True

        # 模拟一组响应时间
        response_times = [1.0, 1.1, 1.2, 1.3, 1.4]
        mock_test_ocr.side_effect = response_times

        with patch("builtins.print") as mock_print:
            benchmark_ocr("test.png", num_requests=5, interval=0.1)

        # 验证打印了统计信息
        print_output = " ".join(str(call) for call in mock_print.call_args_list)

        # 检查是否包含关键统计信息
        assert "最小值" in print_output
        assert "最大值" in print_output
        assert "平均值" in print_output
        assert "中位数" in print_output
        assert "标准差" in print_output
        assert "成功: 5" in print_output
        assert "失败: 0" in print_output

    @patch("scripts.quick_test_ocr_api.ocr_request_once")
    @patch("os.path.exists")
    @patch("time.sleep")
    def test_benchmark_ocr_custom_interval(self, mock_sleep, mock_exists, mock_test_ocr):
        """测试自定义请求间隔"""
        mock_exists.return_value = True
        mock_test_ocr.side_effect = [1.0, 1.1, 1.2]

        # 使用 0.5 秒的间隔
        with patch("builtins.print"):
            benchmark_ocr("test.png", num_requests=3, interval=0.5)

        # 验证 sleep 被调用时使用了正确的间隔
        assert mock_sleep.call_count == 2
        for call in mock_sleep.call_args_list:
            assert call[0][0] == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
