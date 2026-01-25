import base64
import os
import time
from statistics import mean, median, stdev

import requests


def ocr_request_once(image_path, url="http://localhost:8080/ocr", verbose=True):
    """执行一次OCR请求并返回耗时（秒）"""
    if not os.path.exists(image_path):
        if verbose:
            print(f"❌ 找不到图片: {image_path}")
        return None

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    payload = {"file": image_data, "fileType": 1}

    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=30)
        elapsed_time = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            if result.get("errorCode") == 0:
                texts = result["result"]["ocrResults"][0]["prunedResult"]["rec_texts"]
                if verbose:
                    print(f"✅ OCR 识别成功！耗时: {elapsed_time:.3f}秒, 识别内容: {texts}")
                return elapsed_time
            else:
                if verbose:
                    print(f"❌ OCR识别失败: {result.get('errorMsg')}")
                return None
        else:
            if verbose:
                print(f"❌ 服务返回状态码 {response.status_code}")
            return None
    except Exception as e:
        if verbose:
            print(f"❌ 请求异常: {e}")
        return None


def test_ocr(image_path, url="http://localhost:8080/ocr"):
    """原有的测试函数，用于等待服务启动"""
    if not os.path.exists(image_path):
        print(f"❌ 找不到图片: {image_path}")
        return

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    payload = {"file": image_data, "fileType": 1}

    print(f"🚀 发送请求到 {url} (图片: {image_path})...")

    # 因为 OCR 服务启动较慢（下载模型），我们尝试重试
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("errorCode") == 0:
                    texts = result["result"]["ocrResults"][0]["prunedResult"]["rec_texts"]
                    print(f"✅ OCR 识别成功！识别内容: {texts}")
                    return True
                else:
                    print(
                        f"⏳ 服务已响应但尚未就绪 (Error: {result.get('errorMsg')}), 重试 {i+1}/{max_retries}..."
                    )
            else:
                print(f"⏳ 服务返回状态码 {response.status_code}, 重试 {i+1}/{max_retries}...")
        except Exception as e:
            print(f"⏳ 等待服务启动 (Error: {e}), 重试 {i+1}/{max_retries}...")

        time.sleep(10)

    print("❌ 测试失败：服务超时未就绪。")
    return False


def benchmark_ocr(image_path, url="http://localhost:8080/ocr", num_requests=10, interval=0.1):
    """
    执行多次OCR请求并统计性能数据

    Args:
        image_path: 测试图片路径
        url: OCR服务URL
        num_requests: 请求次数
        interval: 请求间隔（秒）
    """
    print(f"\n{'='*60}")
    print("📊 OCR性能基准测试")
    print(f"{'='*60}")
    print(f"图片路径: {image_path}")
    print(f"服务地址: {url}")
    print(f"请求次数: {num_requests}")
    print(f"请求间隔: {interval}秒")
    print(f"{'='*60}\n")

    if not os.path.exists(image_path):
        print(f"❌ 找不到图片: {image_path}")
        return

    response_times = []
    success_count = 0
    fail_count = 0

    for i in range(num_requests):
        print(f"[{i+1}/{num_requests}] ", end="", flush=True)
        elapsed = ocr_request_once(image_path, url, verbose=True)

        if elapsed is not None:
            response_times.append(elapsed)
            success_count += 1
        else:
            fail_count += 1

        # 最后一次请求后不需要等待
        if i < num_requests - 1:
            time.sleep(interval)

    # 打印统计结果
    print(f"\n{'='*60}")
    print("📈 统计结果")
    print(f"{'='*60}")
    print(f"总请求数: {num_requests}")
    print(f"成功: {success_count} ({success_count/num_requests*100:.1f}%)")
    print(f"失败: {fail_count} ({fail_count/num_requests*100:.1f}%)")

    if response_times:
        print("\n⏱️  响应时间统计 (秒):")
        print(f"  最小值: {min(response_times):.3f}")
        print(f"  最大值: {max(response_times):.3f}")
        print(f"  平均值: {mean(response_times):.3f}")
        print(f"  中位数: {median(response_times):.3f}")
        if len(response_times) > 1:
            print(f"  标准差: {stdev(response_times):.3f}")

        # 按响应时间排序显示每次请求
        print("\n📋 详细数据:")
        sorted_times = sorted(enumerate(response_times, 1), key=lambda x: x[1])
        for rank, (req_num, resp_time) in enumerate(sorted_times, 1):
            print(f"  #{rank:2d} - 请求{req_num:2d}: {resp_time:.3f}秒")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    import sys

    # 使用项目现有的图片进行测试
    test_image = "images/screenshots/example.png"

    # 如果指定了参数，则进行性能测试
    if len(sys.argv) > 1:
        num_requests = int(sys.argv[1]) if len(sys.argv) > 1 else 10
        interval = float(sys.argv[2]) if len(sys.argv) > 2 else 0.1
        benchmark_ocr(test_image, num_requests=num_requests, interval=interval)
    else:
        # 默认进行单次测试
        test_ocr(test_image)
