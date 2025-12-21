#!/bin/bash

# PaddleX Docker 启动脚本 (OCR Mobile 版)
# 用途: 启动 PaddleX OCR 服务，并自动配置为轻量级 Mobile 模型以提升速度。
# 端口: 8080 (使用 host 网络模式)

CONTAINER_NAME="paddlex"
IMAGE_NAME="ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlex/paddlex:paddlex3.3.11-paddlepaddle3.2.0-cpu"

# 检查容器是否存在
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "🔄 容器 ${CONTAINER_NAME} 已存在，正在重启..."
    docker rm -f ${CONTAINER_NAME}
fi

echo "🚀 正在启动 PaddleX OCR 服务 (Mobile Mode)..."

# 启动容器
# 核心逻辑:
# 1. paddlex --install serving: 安装服务化组件
# 2. paddlex --get_pipeline_config: 下载默认 OCR 配置
# 3. sed substitution: 将 server 模型替换为 mobile 模型
# 4. paddlex --serve: 启动服务
docker run -d \
  --name ${CONTAINER_NAME} \
  -v "$PWD:/paddle" \
  -v "paddlex_data:/root" \
  --shm-size=8g \
  --network=host \
  --restart=unless-stopped \
  ${IMAGE_NAME} \
  sh -lc "paddlex --install serving && \
          rm -f OCR.yaml && \
          paddlex --get_pipeline_config OCR --save_path . && \
          sed -i 's/_server_/_mobile_/g' OCR.yaml && \
          paddlex --serve --pipeline OCR.yaml"

echo "✅ 服务已启动，正在后台初始化 (首次运行需要下载模型)..."
echo "📜 使用 'docker logs -f ${CONTAINER_NAME}' 查看日志"
echo "⏳ API 地址: http://localhost:8080/ocr"
