# -*- encoding=utf8 -*-
"""
测试 logger_config 中的 Loki 集成功能
"""

import time
from logger_config import setup_logger

print("=" * 70)
print("测试 logger_config 中的 Loki 集成")
print("=" * 70)

# 测试 1: 仅使用 console 输出
print("\n1. 测试仅使用 console 输出...")
logger1 = setup_logger(
    name="test_console",
    level="INFO",
    use_color=True,
)
logger1.info("这是一条 console 日志")
logger1.warning("这是一条 console 警告")
print("✅ Console 输出测试完成")

# 测试 2: 同时使用 console 和 Loki
print("\n2. 测试同时使用 console 和 Loki...")
logger2 = setup_logger(
    name="test_with_loki",
    level="INFO",
    use_color=True,
    enable_loki=True,
    loki_url="http://localhost:3100",
    loki_labels={"env": "dev", "version": "1.0"},
)
logger2.info("这是一条 console + Loki 日志")
logger2.warning("这是一条 console + Loki 警告")
logger2.error("这是一条 console + Loki 错误")
print("✅ Console + Loki 输出测试完成")

# 等待日志上传
print("\n3. 等待日志上传到 Loki（5 秒）...")
for i in range(5):
    print(f"   等待中... {i + 1}/5")
    time.sleep(1)
print("✅ 等待完成")

# 测试 3: 记录更多日志
print("\n4. 记录更多日志...")
for i in range(5):
    logger2.info(f"测试日志 {i + 1}")
print("✅ 更多日志已记录")

# 等待上传
print("\n5. 等待日志上传（3 秒）...")
for i in range(3):
    print(f"   等待中... {i + 1}/3")
    time.sleep(1)
print("✅ 等待完成")

print("\n" + "=" * 70)
print("✅ 测试完成")
print("=" * 70)
print("\n💡 提示:")
print("1. Console 日志已输出到控制台")
print("2. Loki 日志已上传到 Loki 服务")
print("3. 可以在 Grafana 中查看日志:")
print("   - 访问 http://localhost:3000")
print("   - 用户名: admin")
print("   - 密码: admin")
print("   - 在 Explore 中选择 Loki 数据源")
print('   - 使用标签过滤: {app="test_with_loki"}')
print("=" * 70)

# 关闭日志处理器
print("\n正在关闭日志处理器...")
for handler in logger2.handlers:
    handler.close()
logger2.handlers.clear()
print("✅ 日志处理器已关闭")

