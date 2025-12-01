# -*- coding: utf-8 -*-
"""
测试 Loki 日志模块基本功能（不需要 Loki 服务运行）
"""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loki_logger import create_loki_logger

print("=" * 70)
print("测试 Loki 日志模块基本功能")
print("=" * 70)

# 创建日志记录器（禁用 Loki，只测试控制台输出）
print("\n1. 创建日志记录器（禁用 Loki）...")
logger = create_loki_logger(
    name="miniwow",
    level="INFO",
    enable_loki=False,  # 禁用 Loki，只测试控制台输出
)
print("日志记录器创建成功")

# 记录日志
print("\n2. 记录日志...")
logger.info("这是一条信息日志")
logger.warning("这是一条警告日志")
logger.error("这是一条错误日志")
print("✅ 日志已记录")

# 记录更多日志
print("\n3. 记录更多日志...")
for i in range(5):
    logger.info(f"测试日志 {i + 1}")
print("✅ 更多日志已记录")

print("\n" + "=" * 70)
print("✅ 基本功能测试完成")
print("=" * 70)
print("\n💡 提示:")
print("1. 日志已输出到控制台")
print("2. 如果需要上传到 Loki，请：")
print("   - 启动 Loki 和 Grafana: docker-compose -f docker-compose.loki.yml up -d")
print("   - 修改 enable_loki=True")
print("   - 运行 examples/test_loki_logger.py")
print("=" * 70)
