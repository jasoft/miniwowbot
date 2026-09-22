#Requires -Version 7.0
<#
.SYNOPSIS
    注册 / 重建「每周挑战-聚魂之地」计划任务（每周一自动闯关）。

.DESCRIPTION
    让 Windows 计划任务直接驱动 weekly_soul_land.py，完全脱离 Agent 沙箱 ——
    这样不需要 dangerouslyDisableSandbox 授权，也不会因为会话结束被回收。

    权限模型对齐既有的 RunDungeons 任务：
      - Principal   : 当前用户 / InteractiveToken / RunLevel = HighestAvailable
      - Settings    : WakeToRun + StartWhenAvailable + MultipleInstances = IgnoreNew
      - 动作        : 直接调用项目 venv 的 python.exe（不经 cmd / uv 中间层，便于排查）

    需要管理员权限才注册得了（RunLevel=Highest 与 WakeToRun 都要求提权）。
    本脚本**不自动提权**，避免无人值守时卡在 UAC 弹窗上；请这样调用：

        sudo pwsh -NoProfile -File E:\Projects\miniwowbot\scripts\register_weekly_soul_land_task.ps1

.PARAMETER TaskName
    计划任务名称，默认 WeeklySoulLand。

.PARAMETER ProjectRoot
    项目根目录，默认 E:\Projects\miniwowbot。

.PARAMETER Time
    每周一触发时间（24 小时制 HH:mm），默认 10:00。

.PARAMETER MaxSeconds
    传给脚本的 --max-seconds 硬超时，默认 3600。

.PARAMETER TimeLimitHours
    计划任务自身的执行时长上限（小时），默认 2 —— 比脚本硬超时留足余量，
    用于兜住「脚本自己卡死」这种意外。

.EXAMPLE
    sudo pwsh -NoProfile -File scripts\register_weekly_soul_land_task.ps1
#>
param(
    [string]$TaskName = 'WeeklySoulLand',
    [string]$ProjectRoot = 'E:\Projects\miniwowbot',
    [string]$Time = '10:00',
    [int]$MaxSeconds = 3600,
    [int]$TimeLimitHours = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# PowerShell 工具不回传 stdout，所以结果实时落一份到临时文件便于事后核对
# （必须实时写：中途 throw 时末尾那次统一写盘不会执行）
$LogFile = Join-Path $env:TEMP 'weekly_soul_land_task_register.log'

function Say {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "[{0}] {1,-5} {2}" -f (Get-Date -Format 'HH:mm:ss'), $Level, $Message
    try {
        Add-Content -LiteralPath $LogFile -Value $line -Encoding utf8
    }
    catch {
        # 写日志失败不能影响主流程
    }
    Write-Host $line
}

# 兜住任何未处理异常，保证日志里有痕迹再退出
trap {
    Say "未捕获异常: $($_.Exception.Message)" 'ERROR'
    Say $_.ScriptStackTrace 'ERROR'
    exit 1
}

Set-Content -LiteralPath $LogFile -Value "=== 注册计划任务开始 $((Get-Date).ToString('u')) ===" -Encoding utf8

function Get-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$identity).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

Say "== 注册计划任务 [$TaskName] =="

# 1. 权限检查（不自动提权）
$isAdmin = Get-IsAdmin
Say "当前是否管理员: $isAdmin"
if (-not $isAdmin) {
    Say "需要管理员权限。请用：sudo pwsh -NoProfile -File `"$PSCommandPath`"" 'ERROR'
    exit 1
}

# 2. 前置检查：解释器与脚本都要在
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Script = Join-Path $ProjectRoot 'weekly_soul_land.py'
foreach ($path in @($Python, $Script)) {
    if (-not (Test-Path -LiteralPath $path)) {
        Say "路径不存在: $path" 'ERROR'
            exit 1
    }
    Say "已确认: $path"
}

# 3. 时间解析
try {
    $triggerTime = [datetime]::ParseExact($Time, 'HH:mm', $null)
}
catch {
    Say "时间格式错误: $Time，应为 HH:mm" 'ERROR'
    exit 1
}

# 4. 幂等：同名任务先删掉
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Say "发现同名任务，先删除…"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Say "旧任务已删除"
}

# 5. 构造 Action / Trigger / Settings / Principal
$arguments = "`"$Script`" --max-seconds $MaxSeconds"
$action = New-ScheduledTaskAction -Execute $Python -Argument $arguments -WorkingDirectory $ProjectRoot

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $triggerTime

$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours $TimeLimitHours) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

# InteractiveToken：只在用户已登录时运行。必须如此 —— 模拟器 GUI 与 adb 都在用户会话里，
# 换成 S4U / ServiceAccount 反而起不来。
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

# 6. 注册
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "每周挑战「聚魂之地」自动闯关（weekly_soul_land.py），每周一 $Time。含唤醒。" | Out-Null
Say "任务已注册"

# 7. 回读验证（不信任注册返回值，实际读一遍）
$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName
Say "状态     : $($task.State)"
Say "下次运行 : $($info.NextRunTime)"
Say "运行账户 : $($task.Principal.UserId) / $($task.Principal.LogonType) / RunLevel=$($task.Principal.RunLevel)"
Say "动作     : $($task.Actions[0].Execute) $($task.Actions[0].Arguments)"
Say "工作目录 : $($task.Actions[0].WorkingDirectory)"
Say "唤醒运行 : $($task.Settings.WakeToRun)  错过补跑: $($task.Settings.StartWhenAvailable)"

# 8. 唤醒计时器检查。
#    注意：powercfg /waketimers 只列出「最近的」计时器，周期性 CalendarTrigger 任务
#    通常不出现在里面 —— 本机每天 06:05 照常唤醒执行的 RunDungeons（WakeToRun=true）
#    同样不在列表中。所以这里只做参考打印，判 False 不代表配置有问题。
$wakeTimers = & powercfg /waketimers 2>&1 | Out-String
if ($wakeTimers -match [regex]::Escape($TaskName)) {
    Say "✓ 唤醒计时器已注册（powercfg 中可见）"
}
else {
    Say "powercfg /waketimers 未列出本任务 —— 属正常现象，WakeToRun 已为 True，无需处理"
}

Say "日志已写入: $LogFile"
exit 0
