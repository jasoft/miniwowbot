# Clef Typesafe 游戏升级实验

实验入口为 `run_clef_levelup.py`。调用 Cloudflare Workers AI 的
`@cf/cloudflare/clef-flash`，从项目根目录 `.env` 加载
`CLOUDFLARE_ACCOUNT_ID`、`CLOUDFLARE_AUTH_TOKEN`，不输出凭据。

## 实现范围

模型接收截图、OCR 和当前检测状态，从 Typesafe `choice` 问题中选择下一动作。
候选项动态限制为当前可执行动作，并保留 `wait`；只有等待可选时不调用 API。
响应中的动作名称、概率键、概率范围、概率总和、最高概率选项及置信度均需校验。
实际点击前再次检测状态，置信度不足或动作条件变化时跳过。

模型选择的是以下工具。工具内的坐标、页面扫描和结果验证复用原升级脚本，
因此这个实验检验的是“模型编排固定工具”，并不让模型直接生成坐标或完整脚本。

| 动作 | 执行行为 |
| --- | --- |
| complete | 交任务，并接受可见的后续任务 |
| request | 扫描并领取支线、地下城及主线；确认本区任务清空后切下一大陆并继续领取 |
| advance | 满经验时推进副本或地点 |
| equip | 点击可用的新装备按钮 |
| combat | 战斗中点击技能 |
| recover | 超时后恢复导航 |
| wait | 等待界面或任务进展 |

区域边界、完整清单扫描、前景弹窗识别、切区标题验证由现有 `task_workflow.py`
负责。当前末区不会继续向菜单下方点击。
旧战斗模板漏检时，以 OCR 中血量条和至少三个技能数字共同识别可用技能，
出现任务操作弹窗时不补充。背景技能可见不会阻止接任务；原模板的副本战斗信号
仍用于阻止战斗时的导航动作。执行模式启动时先关闭遗留弹窗，观察模式不点击。

## 运行

先停止同设备的其他控制脚本。现有工具坐标要求设备画面为 720×1280。

```powershell
# 只观察和记录，不点击
uv run python run_clef_levelup.py --steps 10

# 实际执行；本次实测使用0.60，默认置信度门槛为0.65
uv run python run_clef_levelup.py --execute --emulator 127.0.0.1:5565 `
  --steps 30 --max-seconds 180 --min-confidence 0.60

# 仅用OCR及检测状态，不发送图片
uv run python run_clef_levelup.py --text-only --steps 10

# 合成状态调用真实API；不连接游戏
uv run python scripts/evaluate_clef_levelup.py

# 无网络、无真实点击的回归测试
uv run pytest levelup.air/tests/test_clef.py levelup.air/tests/test_task_workflow.py `
  -m "not integration"
```

`--max-seconds` 限制启动新一轮及新动作的时间；正在执行的固定工作流会完成后退出，
不是强制中断动作的硬超时。连续三轮异常终止实验；任意异常使最终退出码为1。
脚本不会自动启动或停止其他控制器，实验操作时应由调用方负责暂停及恢复。

默认输出在 `output/clef-levelup/`：原始 PNG、执行前复核截图、
`decisions.jsonl`（观察、概率、置信度、跳过原因和操作后 OCR）、`summary.json`。
`handler_called` 只表示调用了工具，不能直接当作任务成功。
成功需要结合工作流日志和 `after_ocr` 判断。这些运行记录及截图不纳入 Git。

## 2026-10-06 实验发现

- 真实 API 配置有效；两次截图观察请求平均约0.81秒。
- 原始 PNG 为约1.35 MiB，虽然未超过文档图片大小限制，Cloudflare 网关仍以
  估算输入451102令牌超过65536上下文为由返回413。保留完整PNG用于复查，
  上传360×640、质量70的JPEG后成功。OCR仍读取原始720×1280截图。
- 首轮固定七选项的实机实验：30次成功API请求，平均1.14秒，
  调用一次交任务工具并确认交接任务成功；模型多次选择不可用动作，被执行器拦截。
  因此最终实现改用动态候选项。
- 8个合成状态案例，中文提示命中4/8；英文提示命中7/8。
  英文版在“满经验推进和装备同时可用”时选择装备，未遵守预期优先级。
  单独推进和超时恢复虽然选对，置信度也不足以通过默认执行门槛。
  这是一次小样本评估，不能视为长期准确率或实机成功率。
- 最终版本复测12次API请求，平均0.97秒，无异常；确认1次交任务及接受后续任务。
  其余背景技能/等待选择置信度较低，被默认0.65门槛拦截，未执行技能点击。
  这说明最终版本的背景战斗选择仍存在不确定性，不能将第二轮的技能工具调用次数
  当作最终版本的稳定战斗表现。
- 收窄候选项的第二轮实机：18次成功API请求，平均1.11秒；调用3次交任务
  及11次战斗技能工具，日志确认连续交任务，其中2次接受了后续任务。
  当前账号位于末区，不能据此声称本次模型实验完成了跨大陆迁移。
  切区工具的行为由14项原有回归测试覆盖，包括切区后继续接任务。

结论：Clef 可以参与受约束工具的游戏自动化编排。当前证据支持继续实验，
尚不足以替代长期挂机的确定性行为树。模型耗时不适合作为高频技能循环的唯一驱动；
后续可保持本地战斗循环，把模型用于低频交接任务及异常恢复决策。

模块保持单一职责：`clef_decision.py` 保存响应，`clef_client.py` 调用及校验接口，
`clef_policy.py` 管理前置条件及动作分派，入口负责有界运行和审计记录。
31项目标回归测试、`ruff check .`、Pyright零错误及指定副本dryrun通过。
Pyright保留仓库既有的`tests/test_error_screenshot.py`生成器返回类型警告。

参考：[Cloudflare 模型文档](https://developers.cloudflare.com/workers-ai/models/clef-flash/)、
[请求协议](https://developers.cloudflare.com/workers-ai/models/clef-flash/schema-input.json)、
[响应协议](https://developers.cloudflare.com/workers-ai/models/clef-flash/schema-output.json)。
