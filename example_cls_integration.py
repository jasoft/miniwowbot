# -*- encoding=utf8 -*-
"""
腾讯云 CLS 日志集成示例

演示如何在项目中集成腾讯云 CLS 日志功能
"""

import logging
from logger_config import setup_logger
from cls_logger import add_cls_to_logger, close_cls_logger


def example_1_basic_usage():
    """示例 1: 基础用法 - 使用 setup_logger 启用 CLS"""
    print("\n" + "=" * 70)
    print("示例 1: 基础用法 - 使用 setup_logger 启用 CLS")
    print("=" * 70)

    # 创建日志记录器，启用 CLS
    logger = setup_logger(
        name="example1",
        level="INFO",
        enable_cls=True,  # 启用 CLS
    )

    # 记录日志
    logger.info("这是一条信息日志")
    logger.warning("这是一条警告日志")
    logger.error("这是一条错误日志")

    print("✅ 日志已记录，将在后台上传到 CLS")


def example_2_add_cls_to_existing_logger():
    """示例 2: 将 CLS 添加到现有日志记录器"""
    print("\n" + "=" * 70)
    print("示例 2: 将 CLS 添加到现有日志记录器")
    print("=" * 70)

    # 创建日志记录器（不启用 CLS）
    logger = logging.getLogger("example2")
    logger.setLevel(logging.INFO)

    # 添加控制台处理器
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # 添加 CLS 处理器
    add_cls_to_logger(logger)

    # 记录日志
    logger.info("这条日志会同时输出到控制台和 CLS")
    logger.warning("这条日志也会同时输出到控制台和 CLS")

    print("✅ 日志已记录，将同时输出到控制台和 CLS")


def example_3_multiple_loggers():
    """示例 3: 多个日志记录器"""
    print("\n" + "=" * 70)
    print("示例 3: 多个日志记录器")
    print("=" * 70)

    # 创建多个日志记录器
    logger1 = setup_logger(name="module1", enable_cls=True)
    logger2 = setup_logger(name="module2", enable_cls=True)
    logger3 = setup_logger(name="module3", enable_cls=True)

    # 记录日志
    logger1.info("模块 1 的日志")
    logger2.info("模块 2 的日志")
    logger3.info("模块 3 的日志")

    print("✅ 多个模块的日志已记录")


def example_4_different_log_levels():
    """示例 4: 不同的日志级别"""
    print("\n" + "=" * 70)
    print("示例 4: 不同的日志级别")
    print("=" * 70)

    logger = setup_logger(name="example4", level="DEBUG", enable_cls=True)

    logger.debug("调试信息")
    logger.info("信息")
    logger.warning("警告")
    logger.error("错误")
    logger.critical("严重错误")

    print("✅ 不同级别的日志已记录")


def example_5_custom_format():
    """示例 5: 自定义日志格式"""
    print("\n" + "=" * 70)
    print("示例 5: 自定义日志格式")
    print("=" * 70)

    custom_format = "%(asctime)s [%(levelname)s] %(name)s - %(funcName)s:%(lineno)d - %(message)s"
    custom_date_format = "%Y-%m-%d %H:%M:%S"

    logger = setup_logger(
        name="example5",
        log_format=custom_format,
        date_format=custom_date_format,
        enable_cls=True,
    )

    logger.info("使用自定义格式的日志")
    logger.error("错误信息")

    print("✅ 自定义格式的日志已记录")


def main():
    """主函数"""
    print("=" * 70)
    print("腾讯云 CLS 日志集成示例")
    print("=" * 70)

    try:
        # 运行示例
        example_1_basic_usage()
        example_2_add_cls_to_existing_logger()
        example_3_multiple_loggers()
        example_4_different_log_levels()
        example_5_custom_format()

        print("\n" + "=" * 70)
        print("✅ 所有示例已完成")
        print("=" * 70)
        print("\n💡 提示:")
        print("1. 确保在 .env 文件中配置了腾讯云凭证")
        print("2. 日志会在后台异步上传到 CLS")
        print("3. 可以在腾讯云 CLS 控制台查看日志")
        print("=" * 70)

    finally:
        # 关闭 CLS 日志处理器，确保所有日志都被上传
        close_cls_logger()
        print("\n✅ CLS 日志处理器已关闭")


if __name__ == "__main__":
    main()

