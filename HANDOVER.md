# 交接文档 · miniwowbot

> 本文件是 **2026-09-18 会话**的交接记录，供下一个对话快速恢复上下文。
> 读法：先看 §0 快速上手 → §1 本次做了什么 → §2 技能沉淀 → §3 环境状态 → §4 待办。

---

## 0. 快速上手（新对话先读这段）

### 0.1 人的约定

- 称呼：用户 = **大王**，AI = **兔子**（已固化在 `~/.workbuddy/IDENTITY.md`、`USER.md`、`SOUL.md`、`MEMORY.md`）。
- 沟通：中文、祈使句下指令；说「继续」= 一路做完，不要中途请示；要**结论 + 证据**，不要过程流水账。
- 判断错了要主动说「我上次错了」，不要含糊过去。
- 本地改动可以直接做；**push / 发布这类对外动作，等大王拍板**。
- 大王在**南京**。

### 0.2 环境常量

| 项 | 值 |
|---|---|
| 项目根 | `E:\Projects\miniwowbot` |
| Python | 项目自带 `E:\Projects\miniwowbot\.venv\Scripts\python.exe`（不要用系统 Python） |
| 游戏包名 | `com.ms.ysjyzr`（《异世界勇者》） |
| 主账号设备 | `192.168.1.150:5555`（BlueStacks 实例 1 / Pie64），多开 `:5565` |
| 分辨率 | **720x1280 / 320dpi**，所有坐标常量基于此 |
| OCR | `http://192.168.1.150:8311/ocr`（PaddleX 3.0 协议，BASE64 传图） |
| 专用技能 | `~/.workbuddy/skills/miniwow-game-automation/` |

### 0.3 三个「不知道就会踩」的前提

1. **OCR 8311 是按需服务，不要改成 8310。**
   8311 是 `AutoStopProxy` 入口（`-container paddlex -target localhost:8310 -listen :8311 -timeout 30m`），
   空闲 30 分钟自动 `docker stop` 省内存。第一个请求会触发代理把容器拉起来（冷启动约 20s）。
   8310 是容器直连，绕过代理 → 容器永不回收，破坏省内存设计。这是上一轮已经修过一次的错。
   自检：`curl -s -o /dev/null -w "%{http_code}" -X POST http://192.168.1.150:8311/ocr` → **422 = 正常**（只缺参数），**502 = 后端没起来**。
2. **绝对不能按 `keyevent 4`（BACK）关面板** —— 会把游戏退到桌面。
   关面板点面板外空白，或点底部导航「战斗」`(362,1245)`；
   地图面板与技能书弹窗**关不掉**，直接 `am force-stop` + `monkey` 重启游戏（约 25s，进度不丢）。
3. **权限分层**：`RunDungeons` 计划任务是 RunLevel=Highest，子进程跑在 High IL；
   兔子的会话是 Medium IL，`taskkill` / `schtasks /RL HIGHEST` 全部 `Access is denied`。
   唯一可行路径是 `Start-Process -FilePath <bat> -Verb RunAs` 发起 UAC。
   而且**必须先杀脚本再关模拟器**，否则脚本会读 `emulator_start_cmd` 把模拟器重新拉起来（打地鼠）。

---

## 1. 本次会话（2026-09-18）做了什么

| # | 大王的要求 | 兔子做了什么 | 结果 |
|---|---|---|---|
| 1 | 解析地图截图上的副本名 → 在 configs 新增「亡灵之地」section → 全设 true | 判读截图 + 用仓库既有地图截图反推分类规则 | ✅ 落入 `configs/warrior.json`，录入 11 个副本全 true |
| 2 | 「用你掌握的技能把这几个副本全部用史诗难度打一遍」 | 摸索出史诗难度入口 → 写脚本 → 实跑 | ✅ 11 个里 **10 个史诗通关**，总评分 42290 → **49710** |
| 3 | 总结对话与技能，供新开对话使用 | 写本文件 | ✅ |

### 1.1 新区「亡灵之地」录入（configs/warrior.json）

- 文件是**单数** `warrior.json`，没有 `warriors.json`。
- `zone_dungeons` 从 8 个区域扩到 **9 个**，副本总数 98 → 109。新增 section 全部 `selected: true`，顺序按**地图从上到下**（沿用既有规律，不是等级序）：

  | 副本 | Lv | 副本 | Lv |
  |---|---|---|---|
  | 聚魂之地 | 440 | 深渊囚牢 | 430 |
  | 永恒王座 | 440 | 亡灵异界 | 415 |
  | 深渊圣所 | 445 | 迷雾林地 | 410 |
  | 猩红古堡 | 435 | 凋零废墟 | 405 |
  | 堕落教堂 | 425 | 战争剧院 | 400 |
  | 权利高塔 | 420 | | |

- **分类规则（本次沉淀的核心判据）**：地图带名节点分三类，只有一类是真副本。

  | 节点外观 | 含义 | 是否录入 |
  |---|---|---|
  | 深色椭圆 + 副本立绘 | 地下城 | ✅ 录入 |
  | 白/米黄气泡（带小尾巴） | 非地下城节点 | ❌ |
  | 红色描边异形（海盗巨人、统御者） | 区域首领 | ❌ |

  验证方式：拿 `images/1766307149539_d.png`（军团领域地图）对账 —— 20 个带名节点里配置只录 13 个，**恰好等于全部深色椭圆**；攻略站讨论军团副本时也只出现这 13 个名字。本次又用实机副本列表做了第 3 次验证（见 1.3）。

- 因此**未录入 6 个**：亡者战场 430 / 诅咒之渊 440 / 星光之森 410 / 永恒国度 420 / 荣耀堡垒 400（白气泡）、统御者 440（红框首领）。
  大王已明确回复「不用」补录。
- 被 `false` 浮层盖住半个名字的节点 = **权利高塔 Lv.420**（用 TapTap《9.0 各秘境攻略》按等级排序交叉验证：400 战争剧院 / 405 凋零废墟 / 410 迷雾林地 / 415 亡灵异界 / 420 权利高塔 / 425 堕落教堂 / 430 深渊囚牢，逐一对上）。
- 教堂那格是「**堕落**教堂」不是「坠落教堂」。
- 校验：`python -m json.tool configs/warrior.json` 通过。

### 1.2 史诗难度体系（以前没人碰过）

项目那条 `run_dungeons.py` 流水线**只打默认的「普通」**，史诗档要手工选。本次摸清：

- **难度活点在副本详情面板难度行右端的绿色 ⟳ 图标 `(470,533)`** —— 点「普通」那两个字**没有任何反应**，这是最大的坑。
- 弹出下拉三档：普通 `(360,377)` / 英雄 `(359,423)` / **史诗 `(360,468)`**。
- 选中后标题变「史诗-<副本名>」，下方多两行：「高难度地下城，440级可以进入」「装备和道具的掉落提高100%」。
- 史诗档的「需要总评分 95210/42290」「440级可以进入」**只是提示、不拦人** —— 战士 Lv.436 / 总评分 42290 实测能进能过，别被数字劝退。
- 进本成功判据：**顶部 y<80 区域出现 `史诗-<副本名>`**。战斗 4 波自动打，单本 **80~150 秒**。
- 难度**按副本记忆**（切过一次后，下次打开还是史诗）。
- 每天每副本 **1 次免费，普通与史诗共用**；用掉后按钮变「前往」，只剩付费入口。
- 通关弹金色「获得新战利品」弹窗 → 点右上空白 `(620,200)` 关掉（残留再点 `(120,300)`）。

### 1.3 史诗批量跑批结果

脚本：`~/.workbuddy/skills/miniwow-game-automation/scripts/epic_dungeons.py`（含状态自愈 `go_field()`）。
日志：`E:\Projects\miniwowbot\log\epic_run_20260918.log`。

| 结果 | 副本 |
|---|---|
| ✅ 史诗通关（10） | 战争剧院、凋零废墟、迷雾林地、亡灵异界、权力高塔、堕落教堂、深渊囚牢、猩红古堡、永恒王座、深渊圣所 |
| ⏭️ 未打（1） | **聚魂之地** —— 当天连**普通档**免费次数都已用掉（普通/史诗都只剩付费入口 📜-23，账上 9025 硬币），未擅自花费 |

- 战士**总评分 42290 → 49710**；掉落出现「通灵之书」这类史诗专属道具。
- 实机副本列表正好 **11 个**，与截图解析结果一致，**分类规则第 3 次验证通过**。
- 今早 06:05 计划任务跑的是 **mage**（8 个副本）；warrior 当天数据库 0 条记录 → 聚魂之地的次数疑似大王自己手动打过，不是流水线消耗的。
- 左侧任务栏「通关史诗2-战争剧院」打完史诗后从任务栏消失，应已判定完成。

---

## 2. 技能沉淀

技能目录：`C:\Users\11885\.workbuddy\skills\miniwow-game-automation\`

```
SKILL.md                     总入口（8 个步骤的工作流 + 前提 + 坑）
references/
  game-ui-map.md             全部已知坐标、面板结构、任务/技能/副本清单
  skill-recognition.md       技能冷却识别的原理、实测数据、调参方法
  pitfalls.md                踩过的坑与排查清单
scripts/
  game_tool.py               截图 / OCR / 点击 / 滑动 基础工具（其它脚本复用它）
  quest_claimer.py           黄色感叹号任务的自动识别与交付
  skill_reader.py            技能栏冷却状态的自学习识别与自动释放
  epic_dungeons.py           批量用「史诗」难度刷副本 ← 本次新增
```

本次对技能的修改：

| 文件 | 改动 |
|---|---|
| `scripts/epic_dungeons.py` | **新增**。默认覆盖亡灵之地 11 副本，支持指定副本名 / `--list` |
| `SKILL.md` | 新增「第 7 步：新区上线时把副本录入 configs」（含三类节点判据表）、「第 8 步：批量用史诗难度打副本」（含完整点击序列与实测事实）；frontmatter 的 `description` 补上这两个触发场景；参考文件清单补 `epic_dungeons.py` |
| `references/game-ui-map.md` | 补齐 11 个副本的列表坐标表与难度档位坐标 |

技能设计的边界（写进了 SKILL.md，别弄混）：

- **批量刷副本**用项目自己的 `run_dungeons.py`（成熟流水线，多账号、普通难度）。
- **史诗难度 / 交任务 / 看技能 / 界面勘察 / 新区录入配置**用本技能。

`epic_dungeons.py` 用法：

```bash
cd E:/Projects/miniwowbot
.venv/Scripts/python.exe "C:/Users/11885/.workbuddy/skills/miniwow-game-automation/scripts/epic_dungeons.py"          # 全部（自动跳过次数用完的）
.venv/Scripts/python.exe ".../epic_dungeons.py" 迷雾林地 权力高塔 深渊圣所   # 只跑指定副本
.venv/Scripts/python.exe ".../epic_dungeons.py" --list                      # 打印副本名→坐标表
```

---

## 3. 当前环境与仓库状态

### 3.1 游戏 / 设备

- 主账号**战士**：Lv.436，总评分 **49710**，人在**野外挂机界面**。
- 最后一个区域 = **东部大陆**，最后一个副本 = **沉没的神庙**（`warrior.json` 里 8/9 区顺序中的末位；新区亡灵之地是 9.0 新增）。
- BlueStacks 实例 1 运行时占用约 6GB；其余实例本次未启动。

### 3.2 OCR / Docker

- OCR 走 8311 → AutoStopProxy → 容器 `paddlex`。容器空闲会 `Exited`，**属正常**，不用管。
- Docker Desktop `AutoStart: true`（`settings-store.json` 已落盘），HKCU Run 键有 `Docker Desktop` 项，`AutoAdminLogon=1`。
- `.env` 里 `OCR_SERVER_URL` / `OCR_HEALTH_URL` 指向 **8311**（改回过的，别再改成 8310）。备份在 `.env.bak`。

### 3.3 Git

- `main` = **65be6fa**（`fix: OCR 容器生命周期交还 AutoStopProxy，不再绕过代理直接启动`），与远端同步。
- 相关提交：`8d70d25`（角色选择死循环修复 + 临时截图兜底清理）、`65be6fa`（OCR 生命周期）。
- **13 个 `configs/*.json` 有未提交改动**（早期批量改 `selected` 留下的，不是本次会话产生的）；另有未跟踪的 `.workbuddy/`。
- `system_config.json` 里的明文 Bark 密钥已迁到本地 `.env`（gitignore 保护）。**推代码时注意别再把它带上去。**

### 3.4 计划任务

- `RunDungeons` **未禁用**，下次运行 **2026/9/19 06:05**。要停需要大王点头。
- 该任务 RunLevel=Highest → 子进程 High IL，终止方式见 §0.3 第 3 条。

---

## 4. 待办与未决

| # | 事项 | 状态 |
|---|---|---|
| 1 | **聚魂之地**史诗还欠一次 —— 当天免费次数已耗尽 | 等 **9/19 06:00** 免费重置后可补：`epic_dungeons.py 聚魂之地`。是否要花 23 硬币立即打，等大王发话 |
| 2 | 13 个 `configs/*.json` 的未提交改动 | 是否提交等大王决定 |
| 3 | `RunDungeons` 是否禁用 | 未决 |
| 4 | 其余 12 个职业配置是否同步「亡灵之地」section | 大王说不用，已关闭 |

---

## 5. 常用命令速查

```bash
cd E:/Projects/miniwowbot

# 模拟器状态 / 启动（注意别把启动命令接进管道，HD-Player 会被回收）
.venv/Scripts/python.exe scripts/bluestack-tool.py status --format json
.venv/Scripts/python.exe scripts/bluestack-tool.py start --id 1 --timeout 180
# 更稳：PowerShell 分离启动
#   Start-Process -FilePath 'C:\Program Files\BlueStacks_nxt\HD-Player.exe' -ArgumentList '--instance','Pie64'

# 启动游戏
adb -s 192.168.1.150:5555 shell monkey -p com.ms.ysjyzr -c android.intent.category.LAUNCHER 1

# OCR 自检（422 = 正常）
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://192.168.1.150:8311/ocr

# 单步交互：截图 + OCR / 点击
.venv/Scripts/python.exe "C:/Users/11885/.workbuddy/skills/miniwow-game-automation/scripts/game_tool.py" shotocr 01_now
.venv/Scripts/python.exe ".../game_tool.py" tap 350 50

# 史诗批量刷副本
.venv/Scripts/python.exe ".../epic_dungeons.py"
```
