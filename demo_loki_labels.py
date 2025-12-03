#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""
Loki 标签详细 Demo
演示如何使用标签和日志内容，以及它们在 Loki 中的存储方式
"""

import json
from typing import Dict, List


class LokiSimulator:
    """Loki 模拟器 - 演示 Loki 的数据结构"""

    def __init__(self):
        self.streams: Dict[str, List] = {}

    def push(self, stream_labels: Dict, timestamp: str, log_content: str):
        """模拟 Loki 的 push 操作"""
        # 将标签转换为字符串作为 key
        stream_key = json.dumps(stream_labels, sort_keys=True)

        if stream_key not in self.streams:
            self.streams[stream_key] = []

        self.streams[stream_key].append({
            "timestamp": timestamp,
            "content": log_content
        })

    def query(self, label_filter: str) -> List:
        """模拟 Loki 的查询操作"""
        results = []
        for stream_key, logs in self.streams.items():
            # 简单的标签匹配
            if label_filter in stream_key:
                results.extend(logs)
        return results

    def print_storage(self):
        """打印 Loki 的存储结构"""
        print("\n" + "=" * 80)
        print("📊 Loki 存储结构")
        print("=" * 80)
        for stream_key, logs in self.streams.items():
            stream_labels = json.loads(stream_key)
            print(f"\n📌 Stream 标签: {stream_labels}")
            print(f"   日志数量: {len(logs)}")
            for i, log in enumerate(logs, 1):
                print(f"   [{i}] {log['timestamp']} → {log['content']}")


def demo_basic_labels():
    """Demo 1: 基础标签概念"""
    print("\n" + "=" * 80)
    print("Demo 1: 基础标签概念")
    print("=" * 80)

    # 标签（第一层）- 用于索引
    labels = {
        "app": "miniwow",
        "host": "docker-host",
        "config": "account1"
    }
    print("\n✅ 标签（用于索引和快速查询）:")
    print(f"   {labels}")

    # 日志内容（第二层）- 详细信息
    log_content = {
        "level": "INFO",
        "logger": "miniwow",
        "message": "应用启动",
        "module": "auto_dungeon",
        "function": "main",
        "line": 1725
    }
    print("\n✅ 日志内容（详细信息）:")
    print(f"   {json.dumps(log_content, ensure_ascii=False, indent=2)}")

    print("\n💡 关键区别:")
    print("   • 标签用于快速查询（数据库索引）")
    print("   • 日志内容用于存储详细信息")
    print("   • 标签应该有限（5-10 个）")
    print("   • 日志内容可以无限大")


def demo_loki_request_format():
    """Demo 2: Loki 请求格式"""
    print("\n" + "=" * 80)
    print("Demo 2: Loki 请求格式")
    print("=" * 80)

    # 模拟 Loki 请求
    loki_request = {
        "streams": [
            {
                "stream": {
                    "app": "miniwow",
                    "host": "docker-host",
                    "config": "account1"
                },
                "values": [
                    [
                        "1730534445000000000",
                        json.dumps({
                            "level": "INFO",
                            "logger": "miniwow",
                            "message": "应用启动",
                            "module": "auto_dungeon",
                            "function": "main",
                            "line": 1725
                        }, ensure_ascii=False)
                    ]
                ]
            }
        ]
    }

    print("\n✅ 发送到 Loki 的 JSON 格式:")
    print(json.dumps(loki_request, ensure_ascii=False, indent=2))


def demo_multiple_logs_same_stream():
    """Demo 3: 同一个 Stream 中的多条日志"""
    print("\n" + "=" * 80)
    print("Demo 3: 同一个 Stream 中的多条日志")
    print("=" * 80)

    simulator = LokiSimulator()

    # 相同标签的多条日志会进入同一个 Stream
    labels = {
        "app": "miniwow",
        "config": "account1"
    }

    logs = [
        ("1730534445000000000", '{"level":"INFO","message":"应用启动"}'),
        ("1730534446000000000", '{"level":"INFO","message":"加载配置"}'),
        ("1730534447000000000", '{"level":"ERROR","message":"连接失败"}'),
    ]

    print(f"\n✅ 标签: {labels}")
    print("\n✅ 三条日志（相同标签）:")
    for i, (ts, content) in enumerate(logs, 1):
        print(f"   [{i}] {ts} → {content}")

    for ts, content in logs:
        simulator.push(labels, ts, content)

    simulator.print_storage()


def demo_different_streams():
    """Demo 4: 不同标签创建不同的 Stream"""
    print("\n" + "=" * 80)
    print("Demo 4: 不同标签创建不同的 Stream")
    print("=" * 80)

    simulator = LokiSimulator()

    # 不同的标签会创建不同的 Stream
    configs = ["account1", "account2", "warrior"]

    print("\n✅ 三个不同的配置:")
    for config in configs:
        labels = {
            "app": "miniwow",
            "config": config
        }
        log_content = f'{{"level":"INFO","message":"配置 {config} 启动"}}'
        simulator.push(labels, "1730534445000000000", log_content)
        print(f"   • {config}")

    simulator.print_storage()


def demo_query_performance():
    """Demo 5: 查询性能对比"""
    print("\n" + "=" * 80)
    print("Demo 5: 查询性能对比")
    print("=" * 80)

    print("\n✅ 查询方式 1: 使用标签（⚡ 快速）")
    print("   查询语句: {config=\"account1\"}")
    print("   性能: ⚡⚡⚡ 毫秒级")
    print("   原因: 使用数据库索引，直接定位 Stream")

    print("\n✅ 查询方式 2: 标签 + JSON 过滤（⚡ 较快）")
    print("   查询语句: {config=\"account1\"} | json | level=\"ERROR\"")
    print("   性能: ⚡⚡ 秒级")
    print("   原因: 先用索引定位 Stream，再过滤内容")

    print("\n✅ 查询方式 3: 全文搜索（🐢 较慢）")
    print("   查询语句: {app=\"miniwow\"} | \"副本\"")
    print("   性能: ⚡ 秒-分钟级")
    print("   原因: 需要扫描所有日志内容")


def demo_label_design():
    """Demo 6: 标签设计最佳实践"""
    print("\n" + "=" * 80)
    print("Demo 6: 标签设计最佳实践")
    print("=" * 80)

    print("\n✅ 好的标签设计:")
    good_labels = {
        "app": "miniwow",
        "config": "account1",
        "env": "production",
        "version": "1.0.0",
        "region": "asia"
    }
    print(f"   {good_labels}")
    print("   • 标签数量适中（5 个）")
    print("   • 标签值有限且离散")
    print("   • 易于索引和查询")

    print("\n❌ 不好的标签设计:")
    bad_labels = {
        "app": "miniwow",
        "message": "应用启动",  # ❌ 不应该作为标签
        "user_id": "12345",     # ❌ 高基数
        "timestamp": "2025-11-02"  # ❌ 不应该作为标签
    }
    print(f"   {bad_labels}")
    print("   • 包含日志消息（应该在内容中）")
    print("   • 包含高基数字段（user_id）")
    print("   • 包含时间戳（Loki 已有）")


def demo_grafana_queries():
    """Demo 7: Grafana 查询示例"""
    print("\n" + "=" * 80)
    print("Demo 7: Grafana 查询示例")
    print("=" * 80)

    queries = [
        ("查询 account1 的所有日志", '{config="account1"}'),
        ("查询 account1 的 ERROR 日志", '{config="account1"} | json | level="ERROR"'),
        ("查询 account1 中 auto_dungeon.py 的日志", '{config="account1"} | json | filename="auto_dungeon.py"'),
        ("查询 account1 或 account2 的日志", '{config=~"account1|account2"}'),
        ("查询所有配置的 ERROR 日志", '{app="miniwow"} | json | level="ERROR"'),
        ("查询包含 '副本' 的日志", '{app="miniwow"} | "副本"'),
    ]

    for description, query in queries:
        print(f"\n✅ {description}")
        print(f"   {query}")


def main():
    """运行所有 Demo"""
    print("\n" + "=" * 80)
    print("🎓 Loki 标签详细 Demo")
    print("=" * 80)

    demo_basic_labels()
    demo_loki_request_format()
    demo_multiple_logs_same_stream()
    demo_different_streams()
    demo_query_performance()
    demo_label_design()
    demo_grafana_queries()

    print("\n" + "=" * 80)
    print("✅ Demo 完成！")
    print("=" * 80)
    print("\n💡 关键要点:")
    print("   1. 标签用于索引，日志内容用于存储详情")
    print("   2. 相同标签的日志进入同一个 Stream")
    print("   3. 不同标签创建不同的 Stream")
    print("   4. 标签应该有限（5-10 个），值应该离散")
    print("   5. 日志内容可以无限大，包含任意详细信息")
    print("   6. 先用标签过滤，再用内容过滤，性能最优")


if __name__ == "__main__":
    main()
