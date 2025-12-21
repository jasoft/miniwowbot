# MiniWoW OCR 服务 (PaddleX Docker) API 使用文档

本项目使用 **PaddleX Serving** 部署独立的 OCR 服务。通过 HTTP 接口提供文字识别能力，从而将主程序的环境依赖与深度学习框架（PaddlePaddle）彻底解耦。

## 1. 服务部署

使用以下命令启动 Docker 容器。该命令会自动安装 serving 组件并启动 OCR 产线服务。

```bash
docker run -d --name paddlex \
  -v "$PWD:/paddle" \
  --shm-size=8g \
  --network=host \
  ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlex/paddlex:paddlex3.3.11-paddlepaddle3.2.0-cpu \
  sh -lc "paddlex --install serving && paddlex --serve --pipeline OCR"
```

**参数说明：**
- `--network=host`: 使用宿主机网络，服务默认监听在 `8080` 端口。
- `--shm-size=8g`: 共享内存大小，建议设置较大以支持高分辨率图片处理。
- `-v "$PWD:/paddle"`: 将当前目录映射到容器内，方便模型持久化或日志查看。

---

## 2. 接口说明

- **服务地址**: `http://localhost:8080/ocr`
- **请求方法**: `POST`
- **Content-Type**: `application/json`

### 请求参数 (Request Body)

| 参数名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `file` | string | 是 | 图片文件的 **Base64 编码字符串** (不带 `data:image/png;base64,` 前缀) |
| `fileType` | int | 否 | 文件类型，`1` 表示图片，`0` 表示 PDF。默认为 `1`。 |

### 响应参数 (Response)

响应结果遵循 PaddleX 3.0 的标准嵌套结构：

```json
{
  "errorCode": 0,       // 0 表示成功，非 0 表示失败
  "errorMsg": "Success",
  "result": {
    "ocrResults": [     // 结果数组
      {
        "prunedResult": {
          "rec_texts": ["进入游戏", "设置"],    // 识别到的文字列表
          "rec_scores": [0.99, 0.98],          // 对应的置信度
          "dt_polys": [                        // 文字区域坐标框
            [[63, 24], [157, 24], [157, 49], [63, 49]], 
            ...
          ]
        }
      }
    ]
  }
}
```

---

## 3. 代码示例 (Python)

主程序中已在 `ocr_helper.py` 实现了以下逻辑：

```python
import requests
import base64
import json

def ocr_request(image_path, url="http://localhost:8080/ocr"):
    # 1. 图片转 Base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')

    # 2. 构建 JSON Payload
    payload = {
        "file": image_data,
        "fileType": 1
    }
    
    # 3. 发送 POST 请求
    response = requests.post(url, json=payload, timeout=10)
    result = response.json()

    if result.get("errorCode") == 0:
        ocr_data = result["result"]["ocrResults"][0]["prunedResult"]
        return ocr_data
    return None
```

---

## 4. 常见问题排查

*   **Connection Refused**: 请检查容器是否成功启动 (`docker ps`)，以及 8080 端口是否被占用。
*   **422 Error**: 检查请求体格式。必须是 JSON 且字段名为 `file`。不支持 `multipart/form-data` 格式的文件上传。
*   **500 Internal Error**: 检查图片是否过大。如果首次运行报错，通常是因为容器正在后台下载模型权重文件，请等待 1-2 分钟后再试。
*   **日志查看**: 使用 `docker logs -f paddlex` 查看服务端详细推理日志。
