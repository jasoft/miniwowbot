# -*- encoding=utf8 -*-
"""m14 自动任务脚本。"""

__author__ = "weiwang"

import logging
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from airtest.core.api import Template, exists, sleep, touch  # noqa: E402
from airtest.core.settings import Settings as ST  # noqa: E402

from logger_config import get_logger, log_calls  # noqa: E402

ST.FIND_TIMEOUT = 20
ST.FIND_TIMEOUT_TMP = 1
ST.THRESHOLD = 0.8

logger = get_logger(name="m14")
logging.getLogger("airtest").setLevel(logging.CRITICAL)


@log_calls(level="INFO")
def is_combat():
    return exists(
        Template(r"tpl1761909698093.png", record_pos=(-0.422, -0.408), resolution=(720, 1280))
    )


@log_calls(level="INFO")
def is_main_world():
    return exists(
        Template(
            r"gifts_button.png",
            record_pos=(0.429, -0.478),
            resolution=(720, 1280),
            threshold=0.7,
        )
    )


@log_calls(level="INFO")
def complete_tasks():
    logger.info("开始完成任务")
    while True:
        res = exists(Template("tpl1761359506125.png"))  # quest complete icon
        if res:
            logger.info("有任务完成图标")
            touch(res)
            sleep(2)
            touch(
                Template(
                    r"tpl1761909189197.png",
                    threshold=0.7,
                    record_pos=(0.001, 0.315),
                    resolution=(720, 1280),
                )
            )
            sleep(1)
            touch(
                Template(r"tpl1761909210064.png", record_pos=(0.003, 0.325), resolution=(720, 1280))
            )
            sleep(1)
        else:
            logger.info("没有找到任务完成图标")
            break


while True:
    if is_main_world():
        complete_tasks()
        try:
            touch((158, 111))
            sleep(1)
            touch(
                Template(r"tpl1761909274176.png", record_pos=(0.0, 0.319), resolution=(720, 1280))
            )
            touch(
                Template(
                    r"tpl1761909291415.png", record_pos=(-0.001, 0.394), resolution=(720, 1280)
                )
            )
        except Exception:
            pass

    if is_combat():
        logger.info("战斗中...")
