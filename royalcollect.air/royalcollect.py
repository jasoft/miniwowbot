# -*- encoding=utf8 -*-
__author__ = "weiwang"

from airtest.core.api import *

auto_setup(__file__)

def restart_app():
    stop_app("com.tencent.tmgp.supercell.clashroyale")
    sleep(3)
    start_app("com.tencent.tmgp.supercell.clashroyale")
    sleep(60)
    for _ in range(10): #close popups
        touch((18,1139))
    touch((64,1218))
    sleep(3)

def swipe_to_daily_rewards():
    for _ in range(15):
        swipe((374,1080),(374,420),steps=20, duration=0.2)
    
    sleep(3)

    for _ in range(6):
        swipe((374,420),(374,600), steps=20, duration=1)

def collect_rewards():
    def _collect():
        close_button=exists(Template(r"tpl1762507184981.png", record_pos=(0.39, -0.285), resolution=(720, 1280)))

        if(close_button):
            touch(365,900) #点购买
            sleep(2)

            touch(close_button)
            sleep(1)
            touch(close_button)
    
    touch((124,520)) #点免费卡牌
    sleep(1)
    _collect()

    while True:
        try:
            touch(Template(r"tpl1762507052418.png", record_pos=(0.069, -0.078), resolution=(720, 1280)))
            sleep(1)
            _collect()
        except:
            print("no more cards")
            break

def main():
    #restart_app()
    swipe_to_daily_rewards()
    collect_rewards()

main()
            
