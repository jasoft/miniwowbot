import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from game_actions import GameActions, GameElementCollection

def test_declarative_api_logic():
    """测试声明式 API 的过滤和链式调用逻辑（不依赖实际 OCR）"""
    mock_ocr = MagicMock()
    actions = GameActions(mock_ocr)
    
    # 模拟 OCR 返回的数据
    elements_data = [
        {"text": "开始游戏", "center": (100, 100), "confidence": 0.9},
        {"text": "设置", "center": (200, 200), "confidence": 0.8},
        {"text": "退出", "center": (300, 300), "confidence": 0.7},
        {"text": "等级达到 10 级", "center": (400, 400), "confidence": 0.95},
    ]
    
    collection = GameElementCollection(elements_data, actions)
    
    # 1. 测试 filter 和 contains
    filtered = collection.contains("等级达到")
    assert len(filtered) == 1
    assert filtered.first().text == "等级达到 10 级"
    
    # 2. 测试链式调用
    mock_touch = MagicMock()
    with patch.object(actions, 'touch', mock_touch):
        collection.contains("设置").first().click()
        mock_touch.assert_called_with((200, 200))
        
    # 3. 测试 map
    texts = collection.map(lambda e: e.text)
    assert texts == ["开始游戏", "设置", "退出", "等级达到 10 级"]
    
    # 4. 测试 click_all
    mock_touch.reset_mock()
    with patch.object(actions, 'touch', mock_touch):
        collection.filter(lambda e: e.confidence > 0.8).click_all()
        assert mock_touch.call_count == 2 # "开始游戏" and "等级达到 10 级"

def test_find_all_delegation():
    """测试 find_all 是否正确调用 vibe_ocr.OCRHelper"""
    mock_ocr = MagicMock()
    mock_ocr.capture_and_get_all_texts.return_value = [{"text": "A", "center": (1,1)}]
    
    actions = GameActions(mock_ocr)
    results = actions.find_all(regions=[1,2])
    
    mock_ocr.capture_and_get_all_texts.assert_called_with(use_cache=True, regions=[1,2])
    assert len(results) == 1
    assert results.first().text == "A"
