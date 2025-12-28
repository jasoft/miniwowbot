import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Add project root and levelup.air to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'levelup.air'))

@pytest.mark.asyncio
async def test_build_ocr_job_success():
    """验证修复后的 build_ocr_job 在找到文字时能正确返回结果 (不再依赖 found 键) """
    
    with patch('airtest.core.api.auto_setup'), \
         patch('airtest.core.api.Template'), \
         patch('levelup.actions') as mock_actions:
        
        import levelup
        
        # 模拟 actions.find 返回一个 GameElement (dict子类)，但不包含 'found' 键
        mock_element = MagicMock()
        mock_element.__bool__.return_value = True
        mock_element.get.side_effect = lambda k, d=None: None if k == 'found' else mock_element.get(k, d)
        
        # 设置 mock_actions.find 的返回值
        mock_actions.find.return_value = mock_element
        
        # 创建 job
        job = levelup.build_ocr_job("test_job", "测试", [1])
        
        # 执行 detector
        result = await job.detector()
        
        # 验证结果
        assert result is not None
        assert result == mock_element
        # 验证 actions.find 被调用，且 timeout 为 2
        mock_actions.find.assert_called_with("测试", 2, 0.8, 1, True, [1], False)

@pytest.mark.asyncio
async def test_detect_first_match_with_fixed_job():
    """验证 detect_first_match 能正确捕捉到 job 成功的返回"""
    
    with patch('airtest.core.api.auto_setup'), \
         patch('airtest.core.api.Template'), \
         patch('levelup.actions') as mock_actions:
        
        import levelup
        
        # 模拟找到结果
        mock_element = {"text": "领取任务", "center": (100, 100)}
        mock_actions.find.return_value = mock_element
        
        # 创建 jobs
        handler_called = False
        def test_handler(res):
            nonlocal handler_called
            handler_called = True
            
        job = levelup.build_ocr_job("request_task", "领取任务", [1], handler=test_handler)
        
        # 执行 detect_first_match
        matched_job = await levelup.detect_first_match([job])
        
        # 验证
        assert matched_job is not None
        assert matched_job.name == "request_task"
        assert handler_called is True
