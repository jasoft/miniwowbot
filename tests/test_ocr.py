#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
测试 OCR 模块
"""

import sys
import os
import tempfile
import shutil
import json
import sqlite3
import pytest
from PIL import Image

from project_paths import resolve_project_path

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ocr_helper
from vibe_ocr import OCRHelper


@pytest.fixture
def temp_output_dir():
    """创建临时输出目录用于测试"""
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="test_ocr_")

    yield temp_dir

    # 清理
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


def create_dummy_image(path):
    """创建简单测试图片"""
    img = Image.new("RGB", (10, 10), color=(255, 255, 255))
    img.save(path)


class TestOCRHelperBasic:
    """测试 OCR 辅助类基本功能"""

    def test_ocr_helper_creation(self, temp_output_dir):
        """测试 OCRHelper 创建"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        assert ocr is not None
        assert ocr.output_dir == temp_output_dir

    def test_output_dir_exists_after_init(self, temp_output_dir):
        """测试初始化后输出目录存在"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        assert os.path.exists(ocr.output_dir)

    def test_cache_dir_created(self, temp_output_dir):
        """测试缓存目录创建"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        assert os.path.exists(ocr.cache_dir)
        assert ocr.cache_dir == os.path.join(temp_output_dir, "cache")

    def test_default_output_dir_relative_to_auto_dungeon(self):
        """默认输出目录应相对 auto_dungeon.py"""
        ocr = OCRHelper()
        expected_dir = str(resolve_project_path("output"))
        assert ocr.output_dir == expected_dir

    def test_ocr_cache_initialized(self, temp_output_dir):
        """测试 OCR 缓存初始化"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        assert isinstance(ocr.ocr_cache, list)
        assert len(ocr.ocr_cache) == 0  # 初始为空
        assert os.path.exists(ocr.cache_db_path)


class TestOCRCacheLoading:
    """测试 OCR 缓存加载功能"""

    def test_cache_db_created(self, temp_output_dir):
        """测试缓存数据库创建"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        with sqlite3.connect(ocr.cache_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ocr_cache")
            assert cursor.fetchone()[0] == 0

    def test_drop_legacy_cache_table(self, temp_output_dir):
        """旧的 cache_entries 表会被删除"""
        cache_dir = os.path.join(temp_output_dir, "cache")
        os.makedirs(cache_dir, exist_ok=True)
        db_path = os.path.join(cache_dir, "cache.db")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS cache_entries (image_path TEXT, json_path TEXT)"
            )
            conn.commit()

        OCRHelper(output_dir=temp_output_dir)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='cache_entries'"
            )
            assert cursor.fetchone() is None

    def test_cache_persistence(self, temp_output_dir, monkeypatch):
        """测试缓存持久化"""
        # 第一次初始化
        ocr1 = OCRHelper(output_dir=temp_output_dir)
        image_path = os.path.join(temp_output_dir, "dummy.png")
        create_dummy_image(image_path)

        dummy_result = {
            "rec_texts": ["测试"],
            "rec_scores": [0.99],
            "dt_polys": [[[0, 0], [1, 0], [1, 1], [0, 1]]],
        }

        def fake_predict(self, path):
            return dummy_result

        monkeypatch.setattr(OCRHelper, "_predict_with_timing", fake_predict)

        ocr1._get_or_create_ocr_result(image_path, use_cache=True)
        with sqlite3.connect(ocr1.cache_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ocr_cache")
            initial_cache_count = cursor.fetchone()[0]

        ocr2 = OCRHelper(output_dir=temp_output_dir)
        with sqlite3.connect(ocr2.cache_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ocr_cache")
            assert cursor.fetchone()[0] == initial_cache_count

    def test_cache_dir_structure(self, temp_output_dir):
        """测试缓存目录结构"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        cache_dir = ocr.cache_dir

        # 检查缓存目录存在
        assert os.path.exists(cache_dir)
        assert os.path.isdir(cache_dir)


class TestOCRConfiguration:
    """测试 OCR 配置"""

    def test_cache_similarity_threshold_exists(self, temp_output_dir):
        """测试缓存相似度阈值属性存在"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        assert hasattr(ocr, "cache_similarity_threshold")
        assert isinstance(ocr.cache_similarity_threshold, float)
        assert 0 < ocr.cache_similarity_threshold <= 1

    def test_default_cache_similarity_threshold(self, temp_output_dir):
        """测试默认缓存相似度阈值"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        # 默认应该是 0.95
        assert ocr.cache_similarity_threshold == 0.95

    def test_logger_initialized(self, temp_output_dir):
        """测试日志器初始化"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        assert hasattr(ocr, "logger")
        assert ocr.logger is not None


class TestOCRMethods:
    """测试 OCR 方法"""

    def test_find_and_click_text_exists(self, temp_output_dir):
        """测试 find_and_click_text 方法存在"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        assert hasattr(ocr, "find_and_click_text")
        assert callable(ocr.find_and_click_text)

    def test_ocr_url_configured(self, temp_output_dir):
        """测试 OCR URL 配置"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        assert hasattr(ocr, "ocr_url")
        assert ocr.ocr_url


class TestOCRCacheManagement:
    """测试 OCR 缓存管理"""

    def test_ocr_cache_is_list(self, temp_output_dir):
        """测试 OCR 缓存是列表"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        assert isinstance(ocr.ocr_cache, list)

    def test_ocr_cache_structure(self, temp_output_dir):
        """测试 OCR 缓存结构"""
        ocr = OCRHelper(output_dir=temp_output_dir)

        # 如果有缓存，检查结构
        for cache_item in ocr.ocr_cache:
            assert isinstance(cache_item, tuple)
            assert len(cache_item) == 2
            # 第一个元素是图片路径
            assert isinstance(cache_item[0], str)
            # 第二个元素是 JSON 路径
            assert isinstance(cache_item[1], str)

    def test_cache_files_management(self, temp_output_dir, monkeypatch):
        """测试缓存文件管理"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        image_path = os.path.join(temp_output_dir, "dummy.png")
        create_dummy_image(image_path)

        dummy_result = {
            "rec_texts": ["缓存测试"],
            "rec_scores": [0.99],
            "dt_polys": [[[0, 0], [1, 0], [1, 1], [0, 1]]],
        }

        monkeypatch.setattr(OCRHelper, "_predict_with_timing", lambda self, p: dummy_result)
        ocr._get_or_create_ocr_result(image_path, use_cache=True)

        cache_files = [
            name
            for name in os.listdir(ocr.cache_dir)
            if os.path.isfile(os.path.join(ocr.cache_dir, name))
        ]

        assert "cache.db" in cache_files
        assert not any(name.endswith(".png") for name in cache_files)
        assert not any(name.endswith("_res.json") for name in cache_files)

        with sqlite3.connect(ocr.cache_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT json_data FROM ocr_cache")
            row = cursor.fetchone()
            assert row is not None
            assert json.loads(row[0])["rec_texts"] == ["缓存测试"]


class TestOCRIntegration:
    """测试 OCR 集成功能"""

    def test_multiple_instances_share_cache_dir(self, temp_output_dir):
        """测试多个实例共享缓存目录"""
        ocr1 = OCRHelper(output_dir=temp_output_dir)
        ocr2 = OCRHelper(output_dir=temp_output_dir)

        assert ocr1.cache_dir == ocr2.cache_dir

    def test_cache_dir_path(self, temp_output_dir):
        """测试缓存目录路径"""
        ocr = OCRHelper(output_dir=temp_output_dir)
        expected_cache_dir = os.path.join(temp_output_dir, "cache")
        assert ocr.cache_dir == expected_cache_dir


class TestCaptureAndFindTextCacheFallback:
    """测试 capture_and_find_text 的缓存回退逻辑"""

    def test_capture_and_find_text_retries_without_cache_when_cache_result_missing(
        self, temp_output_dir, monkeypatch
    ):
        """缓存命中但找不到文字时应重新截图并刷新缓存"""

        snapshot_calls = []

        def fake_snapshot(filename):
            snapshot_calls.append(filename)
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "wb") as f:
                f.write(b"test")

        call_history = []

        def fake_find(
            self,
            image_path,
            target_text,
            confidence_threshold=0.5,
            occurrence=1,
            use_cache=True,
            regions=None,
            debug_save_path=None,
            return_all=False,
        ):
            call_history.append((use_cache, image_path))
            if use_cache:
                return self._empty_result()

            return {
                "found": True,
                "center": (10, 10),
                "text": target_text,
                "confidence": 0.99,
                "bbox": [[0, 0], [20, 0], [20, 20], [0, 20]],
                "total_matches": 1,
                "selected_index": 1,
                "ocr_data": {
                    "rec_texts": [target_text],
                    "rec_scores": [0.99],
                    "dt_polys": [[[0, 0], [20, 0], [20, 20], [0, 20]]],
                },
            }

        cache_updates = []

        def fake_save_to_cache(self, image_path, ocr_result, regions):
            cache_updates.append((image_path, ocr_result, regions))

        monkeypatch.setattr(ocr_helper, "snapshot", fake_snapshot)
        monkeypatch.setattr(OCRHelper, "find_text_in_image", fake_find)
        monkeypatch.setattr(OCRHelper, "_save_to_cache", fake_save_to_cache)

        def fake_predict(self, image_path):
            return {
                "rec_texts": ["测试文字"],
                "rec_scores": [0.99],
                "dt_polys": [[[0, 0], [20, 0], [20, 20], [0, 20]]],
            }
        monkeypatch.setattr(OCRHelper, "_predict_with_timing", fake_predict)

        helper = OCRHelper(output_dir=temp_output_dir)

        result = helper.capture_and_find_text("测试文字", use_cache=True)

        assert result["found"] is True
        assert [flag for flag, _ in call_history] == [True]
        assert len(snapshot_calls) == 2
        assert len(cache_updates) == 1
        # 第二次截图结果应该写入缓存
        assert cache_updates[0][0] == snapshot_calls[-1]
        assert cache_updates[0][1]["rec_texts"] == ["测试文字"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
