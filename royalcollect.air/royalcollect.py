# -*- encoding=utf8 -*-
__author__ = "weiwang"

from airtest.core.api import *
from airtest.core.settings import Settings as ST

ST.LOG_FILE = "log123.txt"
set_logdir(r'/tmp/logs')
wait(Template(r"map_dungeon.png", rgb=True, record_pos=(0.35, 0.422), resolution=(720, 1280)))

auto_setup(__file__)


log("first try", snapshot=True)
            
