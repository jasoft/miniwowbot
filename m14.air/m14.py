# -*- encoding=utf8 -*-
__author__ = "weiwang"

from airtest.core.api import auto_setup, exists, touch, sleep, Template
from wrapt_timeout_decorator import timeout as timeout_decorator
from airtest.core.settings import Settings as ST
auto_setup(__file__)

ST.FIND_TIMEOUT = 20
ST.FIND_TIMEOUT_TMP = 1
ST.THRESHOLD = 0.8

@timeout_decorator(5, timeout_exception=TimeoutError, exception_message="[TIMEOUT]is_combat 超时")
def is_combat():
    return exists(Template(r"tpl1761909698093.png", record_pos=(-0.422, -0.408), resolution=(720, 1280)))


@timeout_decorator(5, timeout_exception=TimeoutError, exception_message="[TIMEOUT]is_main_world 超时")
def is_main_world():
    return exists(Template(r"tpl1761909776042.png", rgb=True, record_pos=(0.429, -0.478), resolution=(720, 1280)))


@timeout_decorator(120, timeout_exception=TimeoutError, exception_message="[TIMEOUT]complete_tasks 超时")
def complete_tasks():
    while True:
        res=exists(Template("tpl1761359506125.png")) #quest complete icon
        if(res):
            touch(res)
            sleep(2)
            touch(Template(r"tpl1761909189197.png", threshold=0.7, record_pos=(0.001, 0.315), resolution=(720, 1280)))
            sleep(1)
            touch(Template(r"tpl1761909210064.png", record_pos=(0.003, 0.325), resolution=(720, 1280)))
            sleep(1)
        else:
            break
    
while True:
            
    if is_main_world():
        complete_tasks()
        try:
            touch((158,111))
            sleep(0.5)
            touch(Template(r"tpl1761909274176.png", record_pos=(0.0, 0.319), resolution=(720, 1280)))
            touch(Template(r"tpl1761909291415.png", record_pos=(-0.001, 0.394), resolution=(720, 1280)))
        except Exception:
            pass

    if is_combat():
        print("战斗中...")
