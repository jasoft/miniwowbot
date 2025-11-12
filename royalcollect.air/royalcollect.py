# -*- encoding=utf8 -*-
__author__ = "weiwang"

from airtest.core.api import *
from airtest.core.settings import Settings as ST

ST.LOG_FILE = "log123.txt"
set_logdir(r'/tmp/logs')

auto_setup(__file__)


log("first try", snapshot=True)
            
