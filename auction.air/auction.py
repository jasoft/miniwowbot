# -*- encoding=utf8 -*-
__author__ = "weiwang"

from airtest.core.api import auto_setup, touch, sleep, keyevent, text

auto_setup(__file__)
touch((210,293))
sleep(1)
for i in range(10):
    keyevent("67")
text("利爪")
