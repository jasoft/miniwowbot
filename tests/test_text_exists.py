"""测试 text_exists 辅助函数"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auto_dungeon
from auto_dungeon import text_exists


class TestTextExistsBasic:
    """基础行为测试"""

    def test_text_exists_returns_none_when_ocr_not_initialized(self, monkeypatch):
        """ocr_helper 未初始化时应直接返回 None，而不是抛异常"""

        # 确保 ocr_helper 为 None
        monkeypatch.setattr(auto_dungeon, "ocr_helper", None, raising=False)

        result = text_exists(["测试"])
        assert result is None

    def test_text_exists_checks_texts_in_order_and_returns_first_match(self, monkeypatch):
        """应按传入数组顺序检查文本，找到第一个匹配后立即返回"""

        calls = []

        class FakeOCRHelper:
            def capture_and_find_text(
                self,
                target_text,
                confidence_threshold=0.5,
                screenshot_path=None,
                occurrence=1,
                use_cache=True,
                regions=None,
            ):
                calls.append(
                    {
                        "text": target_text,
                        "threshold": confidence_threshold,
                        "occurrence": occurrence,
                        "use_cache": use_cache,
                        "regions": regions,
                    }
                )

                # 只有当目标文本为 "存在" 时返回 found=True，其余都当作未找到
                if target_text == "存在":
                    return {
                        "found": True,
                        "center": (100, 200),
                        "text": target_text,
                        "confidence": 0.99,
                    }

                return {"found": False}

        fake_helper = FakeOCRHelper()
        monkeypatch.setattr(auto_dungeon, "ocr_helper", fake_helper, raising=False)

        texts = ["不存在1", "存在", "不存在2"]

        result = text_exists(texts, similarity_threshold=0.8, use_cache=False, regions=[7, 8, 9])

        # 返回结果应为第一个匹配到的文本
        assert result is not None
        assert result["found"] is True
        assert result["text"] == "存在"
        assert result["center"] == (100, 200)

        # 应严格按顺序调用，并在命中后停止，不再检测后续文本
        assert [c["text"] for c in calls] == ["不存在1", "存在"]
        for call in calls:
            assert call["threshold"] == 0.8
            assert call["occurrence"] == 1
            assert call["use_cache"] is False
            assert call["regions"] == [7, 8, 9]

