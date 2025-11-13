对于你的改动,在 tests 目录下编写对应的测试用例, 确保测试通过. 用 pytest. 如果需要连接模拟器的, 用 tests/test_auto_dungeon_integration.py 作为模板. 如果不需要连接模拟器的, 用 tests/test_ocr.py 作为模板.

测试通过后, 总结这次改动,并提交到 github.

所有的回答必须用中文,包括思考和对话.

系统用到了 streamlit, 请注意:025-11-12 21:02:14.456 Please replace `use_container_width` with `width`.

`use_container_width` will be removed after 2025-12-31.

For `use_container_width=True`, use `width='stretch'`. For `use_container_width=False`, use `width='content'`.
