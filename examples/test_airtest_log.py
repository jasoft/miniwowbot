__author__ = "weiwang"

from airtest.core.api import (
    auto_setup,
    connect_device,
    log,
)
from airtest.core.settings import Settings as ST
from airtest.core.helper import set_logdir
from airtest.report.report import simple_report

auto_setup(__file__, logdir=True)
connect_device("Android:///")

print(ST.LOG_FILE)
print(ST.LOG_DIR)

log("test log", snapshot=True)
simple_report(__file__, output="./log/report.html")
