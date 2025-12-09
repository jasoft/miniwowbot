import time
from logger_config import (
    setup_logger_from_config,
    update_log_context,
    attach_emulator_file_handler,
)


def write_sample_logs(emulator: str, cfg: str, n: int = 5):
    logger = setup_logger_from_config(use_color=False)
    update_log_context({"emulator": emulator, "config": cfg})
    path = attach_emulator_file_handler(emulator_name=emulator, config_name=cfg, log_dir="log", level="DEBUG")
    logger.info(f"启动 {cfg} on {emulator}")
    for i in range(n):
        logger.info(f"第 {i+1} 条测试日志 for {cfg} on {emulator}")
        time.sleep(0.05)
    logger.warning(f"测试告警 for {cfg} on {emulator}")
    print(path)


def main():
    write_sample_logs("192.168.1.150:5555", "mage", 5)
    write_sample_logs("192.168.1.150:5565", "paladin", 5)


if __name__ == "__main__":
    main()
