"""测试 text_exists 辅助函数"""

import sys
import os
from pathlib import Path

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

    def test_text_exists_checks_texts_in_order_and_returns_first_match(
        self, monkeypatch
    ):
        """应按传入数组顺序检查文本，找到第一个匹配后立即返回"""

        calls = []

        class FakeOCRHelper:
            def __init__(
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

        fake_helper = Fakevibe_ocr.OCRHelper()

        texts = ["不存在1", "存在", "不存在2"]

        result = text_exists(
            texts, similarity_threshold=0.8, use_cache=False, regions=[7, 8, 9]
        )

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


class TestTextExistsBulkOCR:
    """测试在 vibe_ocr.OCRHelper 支持批量 OCR 能力时的行为（单次截图，多次匹配）。"""

    def test_text_exists_uses_bulk_ocr_when_available(self, monkeypatch, tmp_path):
        """当 ocr_helper 提供 _get_or_create_ocr_result / _get_all_texts_from_json 时，应只截图一次并复用结果。"""

        calls = {"snapshot": 0, "get_or_create": 0, "get_all": 0}
        captured_paths = []

        class FakeOCRHelper:
            def __init__(self):
                # 模拟 auto_dungeon.OCRHelper 里的 temp_dir 属性
                self.temp_dir = str(tmp_path)

            def _get_or_create_ocr_result(
                self, image_path, use_cache=True, regions=None
            ):
                calls["get_or_create"] += 1
                captured_paths.append(image_path)
                # 返回一个假的 JSON 路径，供 _get_all_texts_from_json 使用
                return str(tmp_path / "ocr_result.json")

            def _get_all_texts_from_json(self, json_file_path):
                calls["get_all"] += 1
                # 模拟 OCR 返回的多条文本信息
                return [
                    {"text": "其他", "confidence": 0.9, "center": (10, 10)},
                    {
                        "text": "这里有一个存在的按钮",
                        "confidence": 0.95,
                        "center": (100, 200),
                    },
                    {"text": "无关文本", "confidence": 0.6, "center": (50, 50)},
                ]

        fake_helper = FakeOCRHelper()

        def fake_snapshot(filename=None):  # 与 auto_dungeon.snapshot 签名保持兼容
            calls["snapshot"] += 1
            if filename:
                # 创建一个空文件，方便后续 os.remove 不报错
                Path(filename).write_bytes(b"")

        # 注入 fake ocr_helper 和 snapshot，触发批量 OCR 分支
        monkeypatch.setattr(auto_dungeon, "ocr_helper", fake_helper, raising=False)
        monkeypatch.setattr(auto_dungeon, "snapshot", fake_snapshot, raising=False)

        # regions=None，可以避免在测试环境中依赖 cv2
        result = text_exists(
            ["不存在", "存在"], similarity_threshold=0.8, use_cache=True, regions=None
        )

        # 行为断言：使用了单次截图 + 单次 OCR JSON 生成 + 单次 JSON 解析
        assert calls["snapshot"] == 1
        assert calls["get_or_create"] == 1
        assert calls["get_all"] == 1
        assert len(captured_paths) == 1

        # 结果断言：命中了包含 "存在" 的那条 OCR 文本
        assert result is not None
        assert result["found"] is True
        assert "存在" in result["text"]
        assert result["center"] == (100, 200)
