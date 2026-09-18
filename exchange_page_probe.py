"""临时探针：截图 + 全量 OCR，用于观察活动兑换页布局。

用法：
    python _probe_exchange.py shot <tag>      截图并打印全部 OCR 文本
    python _probe_exchange.py tap <x> <y>     点击指定坐标
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from vibe_ocr import OCRHelper  # noqa: E402

DEVICE = os.getenv("PROBE_DEVICE", "192.168.1.150:5555")


def shot(tag):
    """截图并返回路径。"""
    os.makedirs("log", exist_ok=True)
    path = os.path.join("log", f"_probe_{tag}.png")
    with open(path, "wb") as fh:
        subprocess.run(
            ["adb", "-s", DEVICE, "exec-out", "screencap", "-p"],
            stdout=fh,
            check=True,
        )
    return path


def tap(x, y):
    """点击坐标。"""
    subprocess.run(
        ["adb", "-s", DEVICE, "shell", "input", "tap", str(x), str(y)],
        check=True,
    )


def dump(tag):
    """截图 + 全量 OCR + 打印。"""
    path = shot(tag)
    helper = OCRHelper(output_dir="log/_probe_out", delete_temp_screenshots=False)
    items = helper.find_all_matching_texts(path, "", confidence_threshold=0.0)
    print(f"--- {tag}: {path} ({len(items)} items) ---")
    ordered = sorted(
        items, key=lambda it: ((it.get("center") or [0, 0])[1], (it.get("center") or [0, 0])[0])
    )
    for item in ordered:
        center = item.get("center")
        conf = item.get("confidence") or 0.0
        print(f"  {item.get('text')!r:26} center={center} conf={conf:.2f}")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "shot"
    if action == "tap":
        tap(int(sys.argv[2]), int(sys.argv[3]))
    elif action == "shot":
        dump(sys.argv[2] if len(sys.argv) > 2 else "shot")
    else:
        dump(action)
