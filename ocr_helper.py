"""
OCR Helper Class - 项目侧的 vibe_ocr 封装。

**历史问题说明（2026-09 修复）**

本文件曾用“override ``_find_similar_cached_image`` 并先调用 ``_clean_expired_cache``”
的方式实现 24 小时缓存过期，但该机制**从未真正生效**，原因有两条：

1. 本模块从未被任何代码导入（全项目零引用），清理逻辑自然一次都没执行过；
   实际运行时代码一律直接使用 ``from vibe_ocr import OCRHelper``。
2. 即便被导入也不生效：``regions`` 查找路径走的是库内的
   ``_find_similar_in_cache``，会直接绕过这个 override。

后果是缓存条目可以永久存活 —— 实测有 2026-06-24 创建的条目在 86 天后
仍被复用，其中一条把「一键领取」识别成「键领取」（漏字）的错误结果
被反复命中上千次，导致「领取邮件」任务连续 70 次执行全部失败。

缓存过期能力现已下沉到 ``vibe_ocr.OCRHelper``：
``cache_ttl_seconds`` 参数（默认 24 小时）会在每次查找缓存前淘汰过期条目，
可用环境变量 ``OCR_CACHE_TTL_SECONDS`` 覆盖，传 0 表示永不过期。

本模块仅作为轻量封装保留，用于统一注入项目日志与输出目录解析，
不再承担任何缓存清理职责。
"""

from typing import Any, Dict, Optional

from dotenv import load_dotenv
from airtest.core.api import snapshot

from project_paths import ensure_project_path
from logger_config import setup_logger_from_config

# 缓存 TTL 由库统一负责，这里只做常量透出以兼容旧引用
from vibe_ocr.ocr_helper import DEFAULT_CACHE_TTL_SECONDS
from vibe_ocr.ocr_helper import OCRHelper as BaseOCRHelper

load_dotenv()

# 缓存过期时间：24小时（秒）—— 由 vibe_ocr 库统一维护
CACHE_TTL_SECONDS = DEFAULT_CACHE_TTL_SECONDS


class OCRHelper(BaseOCRHelper):
    """项目侧 OCRHelper：复用库能力，仅覆盖日志与输出目录解析。"""

    def __init__(
        self,
        output_dir="output",
        resize_image=True,
        max_width=960,
        delete_temp_screenshots=True,
        max_cache_size=200,
        hash_type="dhash",
        hash_threshold=10,
        correction_map: Optional[Dict[str, str]] = None,
        snapshot_func: Optional[Any] = None,
        cache_ttl_seconds: Optional[int] = None,
    ):
        """初始化项目侧 OCRHelper。

        Args:
            output_dir: 输出目录，会被解析为项目内的绝对路径。
            resize_image: 是否自动缩小图片以提升识别速度。
            max_width: 图片最大宽度。
            delete_temp_screenshots: 是否删除临时截图文件。
            max_cache_size: 最大缓存条目数。
            hash_type: 感知哈希算法类型（phash/dhash/ahash/whash）。
            hash_threshold: 哈希汉明距离阈值。
            correction_map: OCR 纠正映射，例如 ``{"装各": "装备"}``。
            snapshot_func: 自定义截图函数，默认使用 airtest 的 ``snapshot``。
            cache_ttl_seconds: 缓存条目有效期（秒）。为 None 时由库读取环境变量
                ``OCR_CACHE_TTL_SECONDS``，未设置则使用默认 24 小时。
        """
        resolved_output_dir = ensure_project_path(output_dir)

        super().__init__(
            output_dir=str(resolved_output_dir),
            resize_image=resize_image,
            max_width=max_width,
            delete_temp_screenshots=delete_temp_screenshots,
            max_cache_size=max_cache_size,
            hash_type=hash_type,
            hash_threshold=hash_threshold,
            correction_map=correction_map,
            snapshot_func=snapshot_func or snapshot,
            cache_ttl_seconds=cache_ttl_seconds,
        )

        # 覆盖 logger，使其符合项目日志配置
        self.logger = setup_logger_from_config(use_color=True)
