# -*- encoding=utf8 -*-
__author__ = "soj"

from airtest.core.api import *
from airtest.core.settings import Settings as ST
import time
import requests

auto_setup(__file__)


ST.FIND_TIMEOUT = 1
ST.FIND_TIMEOUT_TMP = 1
ST.THRESHOLD = 0.8

# Bark通知配置
BARK_URL = "https://api.day.app/LkBmavbbbYqtmjDLVvsbMR"  # 请替换为你的Bark推送地址
TASK_TIMEOUT = 300  # 10分钟 = 600秒


def send_bark_notification(title, content):
    """发送Bark通知"""
    try:
        url = f"{BARK_URL}/{title}/{content}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"Bark通知发送成功: {title}")
        else:
            print(f"Bark通知发送失败: {response.status_code}")
    except Exception as e:
        print(f"Bark通知发送异常: {e}")


def check_task_timeout(last_task_time):
    """检查是否超过10分钟没有完成任务"""
    current_time = time.time()
    elapsed_time = current_time - last_task_time
    if elapsed_time > TASK_TIMEOUT:
        minutes = int(elapsed_time / 60)
        send_bark_notification(
            "魔兽世界挂机异常", f"已经{minutes}分钟没有完成任务，可能遇到问题，请检查！"
        )
        return True
    return False


def click_back(n=3):
    for _ in range(n):
        touch((719, 1))


def sell_trash():
    touch((226, 1213))
    sleep(0.5)
    touch((446, 1108))
    sleep(0.5)
    touch((469, 954))
    click_back()


sell_trash()

# 初始化最后一次完成任务的时间
last_task_time = time.time()

while True:
    # 检查是否超时
    if check_task_timeout(last_task_time):
        # 发送通知后重置时间，避免重复通知
        last_task_time = time.time()

    while True:  # 完成所有任务
        res = exists(
            Template(
                r"tpl1761359506125.png",
                record_pos=(-0.281, -0.411),
                resolution=(720, 1280),
            )
        )
        if not res:
            break
        try:
            touch(res)  # 点击完成任务那个感叹号
            # 更新最后一次完成任务的时间
            last_task_time = time.time()
            print(
                f"任务完成，更新时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_task_time))}"
            )

            sleep(0.5)
            touch((363, 867))
            sleep(0.5)
            touch(
                Template(
                    r"tpl1761359681084.png",
                    record_pos=(-0.004, 0.319),
                    resolution=(720, 1280),
                )
            )
        except Exception:
            pass

    if exists(
        Template(
            r"tpl1761362182198.png",
            record_pos=(-0.422, -0.406),
            resolution=(720, 1280),
            threshold=0.9,
        )
    ):
        # 前面四个技能是有cd的,第五个没cd
        for i in range(4):
            touch((105 + i * 130, 560))
        for _ in range(5):
            touch((615, 560))
            sleep(0.5)

    # 自动选择下一个副本
    if exists(
        Template(
            r"tpl1761376402373.png",
            record_pos=(-0.003, -0.306),
            resolution=(720, 1280),
            threshold=0.9,
        )
    ):
        touch((160, 112))
        try:
            touch(
                Template(
                    r"tpl1761376472172.png",
                    record_pos=(0.001, 0.318),
                    resolution=(720, 1280),
                )
            )
            sleep(0.5)

            while True:
                arrow_pos = exists(
                    Template(
                        r"tpl1761376974575.png",
                        record_pos=(-0.144, -0.56),
                        resolution=(720, 1280),
                        rgb=True,
                        threshold=0.4,
                    )
                )
                if arrow_pos:
                    print(arrow_pos)
                    touch((arrow_pos[0], arrow_pos[1] + 100))
                    sleep(0.5)
                    touch(
                        Template(
                            r"tpl1761443492446.png",
                            threshold=0.96,
                            rgb=True,
                            record_pos=(0.0, 0.394),
                            resolution=(720, 1280),
                        )
                    )

                    sleep(3)
                    sell_trash()
                    touch((357, 1209))
                    break
        except:
            pass

