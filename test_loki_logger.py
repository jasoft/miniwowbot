# -*- encoding=utf8 -*-
"""
测试 Loki 日志模块
"""

import time
from logstash_logger import create_loki_logger

print("=" * 70)
print("测试 Loki 日志模块")
print("=" * 70)

# 创建日志记录器
print("\n1. 创建日志记录器...")
logger = create_loki_logger(
    name="miniwow",
    level="INFO",
    loki_url="http://localhost:3100",
    enable_loki=True,
)
print("✅ 日志记录器创建成功")

# 记录日志
print("\n2. 记录日志...")
logger.info("这是一条信息日志")
logger.warning("这是一条警告日志")
logger.error("这是一条错误日志")
print("✅ 日志已记录")

# 等待上传
print("\n3. 等待日志上传（5 秒）...")
for i in range(5):
    print(f"   等待中... {i + 1}/5")
    time.sleep(1)
print("✅ 等待完成")

# 记录更多日志
print("\n4. 记录更多日志...")
for i in range(10):
    logger.info(f"测试日志 {i + 1}")
print("✅ 更多日志已记录")

# 等待上传
print("\n5. 等待日志上传（5 秒）...")
for i in range(5):
    print(f"   等待中... {i + 1}/5")
    time.sleep(1)
print("✅ 等待完成")

print("\n" + "=" * 70)
print("✅ 测试完成")
print("=" * 70)
print("\n💡 提示:")
print("1. 日志已输出到控制台")
print("2. 日志已上传到 Loki")
print("3. 可以在 Grafana 中查看日志:")
print("   - 访问 http://localhost:3000")
print("   - 用户名: admin")
print("   - 密码: admin")
print("   - 在 Explore 中选择 Loki 数据源")
print('   - 使用标签过滤: {app="miniwow"}')
print("=" * 70)

# 关闭日志处理器
print("\n正在关闭日志处理器...")
for handler in logger.handlers:
    handler.close()
logger.handlers.clear()
print("✅ 日志处理器已关闭")
