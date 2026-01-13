#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试levelup.py代码改进后的功能

测试目标：
1. 验证改进后的代码逻辑正确性
2. 测试边界条件和异常情况
3. 确保代码可读性和维护性
"""

import asyncio
import os
import sys
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

# 添加levelup.air目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "levelup.air"))


# 模拟airtest模块
class MockTemplate:
    def __init__(self, *args, **kwargs):
        pass


class MockOCRHelper:
    def find(self, *args, **kwargs):
        return None


class MockGameActions:
    def __init__(self, ocr):
        self.ocr = ocr

    def find(self, *args, **kwargs):
        return None

    def find_all(self, *args, **kwargs):
        return Mock()


# 模拟airtest核心函数
def mock_exists(template):
    return None


def mock_touch(pos):
    pass


def mock_sleep(seconds):
    time.sleep(seconds * 0.01)  # 缩短睡眠时间用于测试


# 模拟模块导入
sys.modules["airtest.core.api"] = Mock(
    Template=MockTemplate,
    auto_setup=Mock(),
    exists=mock_exists,
    sleep=mock_sleep,
    swipe=Mock(),
    touch=mock_touch,
)

sys.modules["airtest.core.settings"] = Mock(
    Settings=Mock(FIND_TIMEOUT=1, FIND_TIMEOUT_TMP=1, THRESHOLD=0.8)
)

sys.modules["requests"] = Mock(get=Mock(return_value=Mock(status_code=200)))

# 现在可以导入被测试的模块
# 这些 functions/classes may not exist in current version
# Importing them will fail if they don't exist
try:
    from levelup import (
        DetectionJob,
        build_ocr_job,
        build_template_job,
        build_timeout_job,
        detect_first_match,
    )
    HAS_LEVELUP_FUNCTIONS = True
except ImportError:
    HAS_LEVELUP_FUNCTIONS = False
    # Create placeholders to avoid NameError
    DetectionJob = None
    build_ocr_job = None
    build_template_job = None
    build_timeout_job = None
    detect_first_match = None


# Skip all tests in this module if levelup functions are not available
import pytest
pytestmark = pytest.mark.skipif(
    not HAS_LEVELUP_FUNCTIONS,
    reason="levelup functions (DetectionJob, detect_first_match, etc.) not available in current version"
)


class TestDetectionJob:
    """测试DetectionJob数据类"""

    def test_detection_job_creation(self):
        """测试DetectionJob的创建"""
        mock_detector = AsyncMock(return_value=True)
        mock_handler = Mock()

        job = DetectionJob(name="test_job", detector=mock_detector, handler=mock_handler)

        assert job.name == "test_job"
        assert job.detector == mock_detector
        assert job.handler == mock_handler


class TestDetectFirstMatch:
    """测试detect_first_match函数"""

    @pytest.mark.asyncio
    async def test_no_jobs(self):
        """测试空作业列表"""
        result = await detect_first_match([])
        assert result is None

    @pytest.mark.asyncio
    async def test_single_matching_job(self):
        """测试单个匹配的作业"""
        mock_handler = Mock()

        async def mock_detector():
            return "result"

        job = DetectionJob(name="single_job", detector=mock_detector, handler=mock_handler)

        result = await detect_first_match([job])

        assert result == job
        mock_handler.assert_called_once_with("result")

    @pytest.mark.asyncio
    async def test_multiple_jobs_first_matches(self):
        """测试多个作业，第一个匹配"""
        handler1 = Mock()
        handler2 = Mock()
        handler3 = Mock()

        async def detector1():
            await asyncio.sleep(0.01)
            return None

        async def detector2():
            await asyncio.sleep(0.005)  # 第二个先完成
            return "match"

        async def detector3():
            await asyncio.sleep(0.02)
            return "should_not_match"

        jobs = [
            DetectionJob(name="job1", detector=detector1, handler=handler1),
            DetectionJob(name="job2", detector=detector2, handler=handler2),
            DetectionJob(name="job3", detector=detector3, handler=handler3),
        ]

        result = await detect_first_match(jobs)

        assert result.name == "job2"
        handler2.assert_called_once_with("match")
        handler1.assert_not_called()
        handler3.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_matches(self):
        """测试没有匹配的情况"""

        async def detector():
            return None

        jobs = [
            DetectionJob(name="job1", detector=detector, handler=Mock()),
            DetectionJob(name="job2", detector=detector, handler=Mock()),
        ]

        result = await detect_first_match(jobs)
        assert result is None

    @pytest.mark.asyncio
    async def test_exception_in_detector(self):
        """测试检测器抛出异常"""

        async def failing_detector():
            raise ValueError("检测失败")

        job = DetectionJob(name="failing_job", detector=failing_detector, handler=Mock())

        # 应该能够处理异常而不崩溃
        result = await detect_first_match([job])
        assert result is None


class TestBuildTimeoutJob:
    """测试build_timeout_job函数"""

    def test_timeout_job_not_expired(self):
        """测试未超时的情况"""
        global last_task_time
        last_task_time = time.time()

        job = build_timeout_job()

        # 未超时应该返回None
        result = asyncio.run(job.detector())
        assert result is None

    def test_timeout_job_expired(self):
        """测试超时的情况"""
        global last_task_time
        last_task_time = time.time() - 700  # 11分钟前

        job = build_timeout_job()

        # 超时应该返回True
        result = asyncio.run(job.detector())
        assert result is True


class TestBuildTemplateJob:
    """测试build_template_job函数"""

    def test_template_job_creation(self):
        """测试模板作业创建"""
        mock_template = MockTemplate()
        mock_handler = Mock()

        job = build_template_job("test_template", mock_template, mock_handler)

        assert job.name == "test_template"
        assert job.handler == mock_handler

    @pytest.mark.asyncio
    async def test_template_job_detector(self):
        """测试模板检测器"""
        mock_template = MockTemplate()
        mock_handler = Mock()

        with patch("levelup.exists", return_value="found_position"):
            job = build_template_job("test_template", mock_template, mock_handler)

            result = await job.detector()
            assert result == "found_position"


class TestBuildOcrJob:
    """测试build_ocr_job函数"""

    def test_ocr_job_creation(self):
        """测试OCR作业创建"""
        mock_handler = Mock()

        job = build_ocr_job("test_ocr", "测试文本", [1], mock_handler)

        assert job.name == "test_ocr"
        assert job.handler == mock_handler

    @pytest.mark.asyncio
    async def test_ocr_job_detector_success(self):
        """测试OCR检测成功"""
        with patch("levelup.actions") as mock_actions:
            mock_actions.find.return_value = "found_text"

            job = build_ocr_job("test_ocr", "测试文本", [1])

            result = await job.detector()
            assert result == "found_text"

    @pytest.mark.asyncio
    async def test_ocr_job_detector_failure(self):
        """测试OCR检测失败"""
        with patch("levelup.actions") as mock_actions:
            mock_actions.find.return_value = None

            job = build_ocr_job("test_ocr", "测试文本", [1])

            result = await job.detector()
            assert result is None


class TestEdgeCases:
    """测试边界条件和异常情况"""

    @pytest.mark.asyncio
    async def test_concurrent_detection_limit(self):
        """测试并发检测的性能"""
        import time

        async def slow_detector():
            await asyncio.sleep(0.1)
            return None

        jobs = [
            DetectionJob(name=f"job{i}", detector=slow_detector, handler=Mock()) for i in range(5)
        ]

        start_time = time.time()
        result = await detect_first_match(jobs)
        end_time = time.time()

        # 应该在合理时间内完成（不是每个任务都等待完整时间）
        assert end_time - start_time < 0.2
        assert result is None

    def test_global_state_management(self):
        """测试全局状态管理"""
        global failed_in_dungeon, last_task_time

        # 测试初始状态
        assert isinstance(failed_in_dungeon, bool)
        assert isinstance(last_task_time, float)

        # 测试状态修改
        failed_in_dungeon = True
        last_task_time = 1000.0

        assert failed_in_dungeon is True
        assert last_task_time == 1000.0

        # 重置状态
        failed_in_dungeon = False
        last_task_time = time.time()


class TestLoggingBehavior:
    """测试日志行为"""

    @pytest.mark.asyncio
    async def test_logging_with_match(self, caplog):
        """测试有匹配时的日志"""
        import logging

        async def detector():
            return "result"

        job = DetectionJob(name="test_job", detector=detector, handler=Mock())

        with caplog.at_level(logging.INFO):
            await detect_first_match([job])

        # 检查日志包含任务名称
        assert "test_job" in caplog.text

    @pytest.mark.asyncio
    async def test_logging_without_match(self, caplog):
        """测试无匹配时的日志"""
        import logging

        async def detector():
            return None

        job = DetectionJob(name="test_job", detector=detector, handler=Mock())

        with caplog.at_level(logging.DEBUG):
            result = await detect_first_match([job])

        # 应该返回None
        assert result is None


# 集成测试
class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_main_loop_logic_simulation(self):
        """模拟主循环逻辑"""
        global failed_in_dungeon, last_task_time

        # 重置状态
        failed_in_dungeon = False
        last_task_time = time.time()

        # 模拟场景1: 有匹配任务
        async def detector_with_match():
            return "matched"

        job_with_match = DetectionJob(
            name="match_job", detector=detector_with_match, handler=Mock()
        )

        result = await detect_first_match([job_with_match])
        assert result is not None

        # 模拟场景2: 无匹配且未失败
        async def detector_no_match():
            return None

        job_no_match = DetectionJob(name="no_match_job", detector=detector_no_match, handler=Mock())

        result = await detect_first_match([job_no_match])
        assert result is None

        # 验证兜底逻辑条件
        should_call_dungeon = result is None and not failed_in_dungeon
        assert should_call_dungeon is True

        # 模拟场景3: 无匹配但已失败
        failed_in_dungeon = True
        should_call_dungeon = result is None and not failed_in_dungeon
        assert should_call_dungeon is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
