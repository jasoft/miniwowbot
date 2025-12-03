#!/bin/zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ -z "${LOKI_URL:-}" ]; then
  echo "[ERROR] 未检测到 LOKI_URL 环境变量，请在项目根目录 .env 中设置"
  echo "示例: LOKI_URL=http://localhost:3100/loki/api/v1/push"
  exit 1
fi

# 允许填写基础地址，自动补齐 push 路径
if [[ "$LOKI_URL" != *"/loki/api/v1/push" ]]; then
  LOKI_URL="${LOKI_URL%/}/loki/api/v1/push"
fi

mkdir -p log

echo "[INFO] 使用配置: promtail-config.yml"
echo "[INFO] 发送到 Loki: $LOKI_URL"

promtail --config.file=promtail-config.yml --config.expand-env=true
