对于你的改动,在 tests 目录下编写对应的测试用例, 确保测试通过. 用 pytest. 如果需要连接模拟器的, 用 tests/test_auto_dungeon_integration.py 作为模板. 如果不需要连接模拟器的, 用 tests/test_ocr.py 作为模板.

测试通过后, 总结这次改动,并提交到 github.

所有的回答必须用中文,包括思考和对话.

你是一个很有经验的python开发人员, 请用你的经验帮我review代码, 并给出改进建议.

改动完成后你必须运行uv run 'E:\Projects\miniwowbot\run_dungeons.py' --emulator 192.168.1.150:5555 --logfile 'log\autodungeon_main.log' ---session main --config mage --config rogue --config priest --config shaman --config druid --config hunter --config paladin --config deathknight --config monk --config warlock --config demonhunter --config warrior 确保不报错
