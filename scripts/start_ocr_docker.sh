#!/bin/bash

# PaddleX Docker 启动脚本 (Linux/macOS)
# 用途: 启动 PaddleX OCR 服务 (GPU版)
# 端口: 8080 (使用 host 网络模式)

CONTAINER_NAME="paddlex"
# 使用已验证存在的 PaddleX 3.0 GPU 镜像标签
IMAGE_NAME="ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlex/paddlex:paddlex3.0.1-paddlepaddle3.0.0-gpu-cuda11.8-cudnn8.9-trt8.6"

echo "🚀 Starting OCR Service (GPU Docker)..."

# 清理旧容器
docker rm -f $CONTAINER_NAME 2>$null
  # 启动容器
  # 使用 --network=host
  # 添加 --gpus all 支持 GPU
  docker run -d --name ${CONTAINER_NAME} \
    --gpus all \
    -v "$PWD:/paddle" \
    -v "paddlex_data:/root" \
    --shm-size=8g \
    --network=host \
    ${IMAGE_NAME} \
    sh -lc "paddlex --install serving && rm -f OCR.yaml && paddlex --get_pipeline_config OCR --save_path . && sed -i 's/_server_/_mobile_/g' OCR.yaml && paddlex --serve --pipeline OCR.yaml"
fi

echo "✅ OCR GPU Service container started."
