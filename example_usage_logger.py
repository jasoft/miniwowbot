import sys
import time
from pathlib import Path

# --- 模拟环境配置 (实际安装后不需要这一步) ---
# 将本地库路径加入系统路径，以便直接导入
sys.path.append(str(Path(__file__).parent / "libraries" / "colored_context_logger" / "src"))
# ----------------------------------------

from colored_context_logger import setup_logger, GlobalLogContext, attach_file_handler, log_calls

def main():
    # 1. 初始化 Logger
    # 会自动配置 coloredlogs (如果有安装)
    logger = setup_logger(name="PaymentService", level="DEBUG")

    logger.info("服务启动中...")

    # 2. 设置全局上下文
    # 场景：假设这是一个 Web 请求或任务处理流程
    # 设置后，所有日志（包括文件日志）都会自动带上这些字段
    GlobalLogContext.update({
        "env": "prod",
        "version": "v1.2.0",
        "request_id": "req_8848",
        "user": "Alice"
    })

    logger.info("上下文已注入，接下来的日志将携带用户信息")

    # 3. 挂载文件日志
    # 不指定 filename 时，会自动根据上下文中的 session 或时间生成文件名
    # 这里我们明确指定一个目录
    log_path = attach_file_handler(
        logger_name="PaymentService",
        log_dir="logs_demo",
        level="DEBUG"
    )
    logger.info(f"文件日志已开始记录: {log_path}")

    # 4. 业务逻辑演示
    process_payment(100, "USD")

    # 5. 模拟上下文切换 (例如处理下一个请求)
    logger.info("--- 切换用户上下文 ---")
    GlobalLogContext.update({
        "request_id": "req_9527",
        "user": "Bob"
    })
    
    try:
        process_payment(0, "EUR") # 触发错误
    except Exception:
        pass # 错误已在装饰器中被记录

# 使用装饰器自动记录函数 入参、返回值、耗时
@log_calls(level="DEBUG")
def process_payment(amount, currency):
    # 模拟业务耗时
    time.sleep(0.3)
    
    if amount <= 0:
        raise ValueError("支付金额必须大于0")
    
    return f"Success: {amount} {currency}"

if __name__ == "__main__":
    main()
