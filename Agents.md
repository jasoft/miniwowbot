## 编码规范

所有的回答必须用中文,包括思考和对话.

你是一个很有经验的python开发人员, 请用你的经验帮我review代码, 并给出改进建议.

## 测试说明

- 在测试的时候需要需要使用 `-m "not integration"` 参数跳过集成测试，不要写到pytest.ini中
- 如需手动运行集成测试：`pytest -m integration -v -s`（或在命令行覆盖 `-m "not integration"`）
- 改动完成后你必须运行uv run 'E:\Projects\miniwowbot\run_dungeons.py' --emulator 192.168.1.150:5555 --logfile 'log\autodungeon_main.log' --session main --config mage --config rogue --config priest --config shaman --config druid --config hunter --config paladin --config deathknight --config monk --config warlock --config demonhunter --config warrior --dryrun 确保不报错
- 测试通过后, 总结这次改动,并提交到 github.
