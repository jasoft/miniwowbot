"""回归：生产实际加载的 ``vibe_ocr`` 必须带 OCR 请求重试。

背景（2026-10-24 06:27:54 真机）：OCR 服务经 AutoStopProxy 按需拉起，代理在上游瞬时
不可用时返回 502。旧版 ``vibe_ocr`` 只发一次请求，失败即吞成 ``result=None``，调用方
于是看到「画面上没有这段文字」——当天「开启宝箱」因此读不到「亡灵宝箱」存量，
跳过了 1800 秒的挂机补充奖励。

**为什么这条测试要放在项目里**：修复落在 ``E:\\Projects\\pythonlib\\vibe-ocr``，而项目
的 venv 是以 editable 方式装它（``.venv/Lib/site-packages/_editable_impl_vibe_ocr.pth``）。
一旦有人跑 ``uv sync`` 把 editable 换回 PyPI 上的 ``vibe_ocr-0.1.6`` 轮子，修复会**静默
消失**，而库仓库自己的测试仍在 ``src/`` 上跑、永远绿。所以这里断言的是
「**生产 import 路径**上的那个 OCRHelper 会重试」，而不是库源码。
"""

from __future__ import annotations

import requests

from vibe_ocr import ocr_helper

#: 生产路径上的重试上限（不直接 import 常量，撤回修复时要能跑到行为断言上）
EXPECTED_MIN_ATTEMPTS = 2

_OK_PAYLOAD = {
    "errorCode": 0,
    "result": {
        "ocrResults": [
            {
                "prunedResult": {
                    "rec_texts": ["亡灵宝箱"],
                    "rec_scores": [0.99],
                    "dt_polys": [[[10, 10], [60, 10], [60, 30], [10, 30]]],
                }
            }
        ]
    },
}


class _FakeResponse:
    """最小化的 ``requests.Response`` 替身。"""

    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} Server Error", response=self)

    def json(self):
        return self._payload


def test_production_ocr_helper_retries_transient_502(tmp_path, monkeypatch):
    """生产路径上的 OCRHelper：一次 502 之后必须重试并拿到识别结果。"""
    import ocr_helper as project_ocr_helper

    # 重试间隔压到 0（旧版本没有这个常量，raising=False 保证能跑起来）
    monkeypatch.setattr(ocr_helper, "OCR_RETRY_DELAYS_SECONDS", (0.0, 0.0), raising=False)

    calls: list[int] = []

    def fake_post(url, json=None, timeout=None):
        calls.append(1)
        if len(calls) == 1:
            return _FakeResponse(502)
        return _FakeResponse(200, _OK_PAYLOAD)

    monkeypatch.setattr(ocr_helper.requests, "post", fake_post)

    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    helper = project_ocr_helper.OCRHelper(
        output_dir=str(tmp_path / "out"),
        resize_image=False,
        snapshot_func=lambda *args, **kwargs: None,
    )

    result = helper._predict_with_timing(str(image_path))

    assert len(calls) >= EXPECTED_MIN_ATTEMPTS, "生产路径上的 OCR 请求没有重试"
    assert result is not None, "重试成功后必须返回识别结果"
    assert result["rec_texts"] == ["亡灵宝箱"]
