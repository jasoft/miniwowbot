#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
OCR 区域调试测试
测试 /tmp/s1.png 文件的区域识别功能
"""

import sys
import os
import pytest

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ocr_helper import OCRHelper  # noqa: E402


class TestOCRDebug:
    """OCR 区域调试测试"""

    @pytest.fixture(scope="class")
    def ocr_helper(self):
        """创建 OCR Helper 实例"""
        return OCRHelper(output_dir="output")

    def test_image_exists(self):
        """测试图像文件是否存在"""
        image_path = "/tmp/s1.png"
        assert os.path.exists(image_path), f"图像文件不存在: {image_path}"

    def test_region_789_extraction(self, ocr_helper):
        """测试区域 [7,8,9] 的提取和保存"""
        image_path = "/tmp/s1.png"

        if not os.path.exists(image_path):
            pytest.skip(f"图像文件不存在: {image_path}")

        # 测试提取区域并保存
        import cv2

        image = cv2.imread(image_path)
        assert image is not None, "无法读取图像"

        # 提取区域 [7,8,9]（底部）
        region_img, offset = ocr_helper._extract_region(
            image, regions=[7, 8, 9], debug_save_path="/tmp/region_789_debug.png"
        )

        assert region_img is not None, "区域提取失败"
        assert offset is not None, "偏移量为空"

        print(f"\n✅ 区域 [7,8,9] 提取成功")
        print(f"   偏移量: {offset}")
        print(f"   区域尺寸: {region_img.shape}")
        print(f"   调试截图已保存到: /tmp/region_789_debug.png")

    def test_find_text_in_region_789(self, ocr_helper):
        """测试在区域 [7,8,9] 中查找文字"""
        image_path = "/tmp/s1.png"

        if not os.path.exists(image_path):
            pytest.skip(f"图像文件不存在: {image_path}")

        # 要查找的文字列表
        target_texts = ["随从", "装备", "战斗", "专业", "主城"]

        print(f"\n🔍 开始在区域 [7,8,9] 中查找文字...")

        results = {}
        for text in target_texts:
            result = ocr_helper.find_text_in_image(
                image_path=image_path,
                target_text=text,
                confidence_threshold=0.5,
                occurrence=1,
                use_cache=False,
                regions=[7, 8, 9],
                debug_save_path=f"/tmp/region_789_{text}_debug.png",
            )

            results[text] = result

            if result["found"]:
                print(f"   ✅ 找到 '{text}':")
                print(f"      中心坐标: {result['center']}")
                print(f"      识别文本: {result['text']}")
                print(f"      置信度: {result['confidence']:.2f}")
                print(f"      边界框: {result['bbox']}")
            else:
                print(f"   ❌ 未找到 '{text}'")

        # 验证至少找到一些文字
        found_count = sum(1 for r in results.values() if r["found"])
        print(f"\n📊 总结: 找到 {found_count}/{len(target_texts)} 个文字")

        # 至少应该找到一个文字
        assert found_count > 0, f"在区域 [7,8,9] 中一个文字都没找到，请检查 OCR 配置"

    def test_find_all_texts_in_region_789(self, ocr_helper):
        """测试查找区域 [7,8,9] 中的所有文字"""
        image_path = "/tmp/s1.png"

        if not os.path.exists(image_path):
            pytest.skip(f"图像文件不存在: {image_path}")

        # 直接对区域进行 OCR
        import cv2

        image = cv2.imread(image_path)
        region_img, offset = ocr_helper._extract_region(
            image,
            regions=[7, 8, 9],
            debug_save_path="/tmp/region_789_all_text_debug.png",
        )

        print(f"\n🔍 对区域 [7,8,9] 进行完整 OCR 识别...")
        print(f"   区域偏移: {offset}")

        # 进行 OCR 识别
        result = ocr_helper.ocr.predict(region_img)

        if result and len(result) > 0:
            print(f"\n📝 识别到的所有文字:")
            for idx, res in enumerate(result, 1):
                # 支持字典访问（OCRResult 对象）
                try:
                    rec_texts = res["rec_texts"]
                    rec_scores = res["rec_scores"]
                    dt_polys = res["dt_polys"]
                except (KeyError, TypeError):
                    # 尝试属性访问
                    rec_texts = res.rec_texts if hasattr(res, "rec_texts") else []
                    rec_scores = res.rec_scores if hasattr(res, "rec_scores") else []
                    dt_polys = res.dt_polys if hasattr(res, "dt_polys") else []

                # 打印所有识别到的文字
                for i, (text, score) in enumerate(zip(rec_texts, rec_scores)):
                    if i < len(dt_polys):
                        bbox = dt_polys[i]

                        # 计算中心坐标（相对于区域）
                        center_x = int((bbox[0][0] + bbox[2][0]) / 2)
                        center_y = int((bbox[0][1] + bbox[2][1]) / 2)

                        # 转换为原图坐标
                        full_center_x = center_x + offset[0]
                        full_center_y = center_y + offset[1]

                        print(f"   {i + 1}. '{text}'")
                        print(f"      区域坐标: ({center_x}, {center_y})")
                        print(f"      原图坐标: ({full_center_x}, {full_center_y})")
                        print(f"      置信度: {score:.2f}")
        else:
            print("   ❌ 未识别到任何文字")
            pytest.fail("区域 [7,8,9] 中未识别到任何文字")

    def test_coordinate_conversion(self, ocr_helper):
        """测试坐标转换是否正确"""
        image_path = "/tmp/s1.png"

        if not os.path.exists(image_path):
            pytest.skip(f"图像文件不存在: {image_path}")

        # 查找一个文字
        result = ocr_helper.find_text_in_image(
            image_path=image_path,
            target_text="战斗",
            confidence_threshold=0.5,
            occurrence=1,
            use_cache=False,
            regions=[7, 8, 9],
            debug_save_path="/tmp/region_789_coordinate_test.png",
        )

        if result["found"]:
            print(f"\n✅ 找到 '战斗':")
            print(f"   中心坐标: {result['center']}")
            print(f"   边界框: {result['bbox']}")

            # 验证坐标在合理范围内
            import cv2

            image = cv2.imread(image_path)
            height, width = image.shape[:2]

            center_x, center_y = result["center"]

            # 坐标应该在图像范围内
            assert 0 <= center_x <= width, (
                f"X坐标超出范围: {center_x} (图像宽度: {width})"
            )
            assert 0 <= center_y <= height, (
                f"Y坐标超出范围: {center_y} (图像高度: {height})"
            )

            # 由于是底部区域 [7,8,9]，Y坐标应该在下半部分
            assert center_y > height * 0.6, (
                f"Y坐标不在底部区域: {center_y} (应该 > {height * 0.6})"
            )

            print(f"   ✅ 坐标验证通过")
            print(f"   图像尺寸: {width}x{height}")
            print(f"   Y坐标占比: {center_y / height * 100:.1f}%")
        else:
            pytest.skip("未找到 '战斗' 文字，跳过坐标验证")


if __name__ == "__main__":
    # 直接运行此文件时执行测试
    pytest.main([__file__, "-v", "-s"])
