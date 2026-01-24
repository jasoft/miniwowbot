# 批量修改 configs 目录下所有配置文件的副本 selected 状态
#
# 用法:
#   .\set-dungeon-selected.ps1 "青龙寺" "黑暗堡垒"              # 指定副本设为 true
#   .\set-dungeon-selected.ps1 -Deselect "青龙寺" "黑暗堡垒"     # 指定副本设为 false
#   .\set-dungeon-selected.ps1 -All                              # 所有副本设为 true
#   .\set-dungeon-selected.ps1 -All -Deselect                     # 所有副本设为 false
#   .\set-dungeon-selected.ps1 -Exclude "*_alt.json" "青龙寺"    # 排除 *_alt.json 后修改
#
# 示例:
#   # 把青龙寺和黑暗堡垒设为选中
#   .\set-dungeon-selected.ps1 "青龙寺" "黑暗堡垒"
#
#   # 取消选中青龙寺和黑暗堡垒
#   .\set-dungeon-selected.ps1 -Deselect "青龙寺" "黑暗堡垒"
#
#   # 全选（排除 *_alt.json）
#   .\set-dungeon-selected.ps1 -All -Exclude "*_alt.json"
#
#   # 全部取消选中
#   .\set-dungeon-selected.ps1 -All -Deselect
param(
    [Parameter(Mandatory=$false)]
    [switch]$All,
    [Parameter(Mandatory=$false)]
    [switch]$Deselect,
    [Parameter(Mandatory=$false)]
    [string[]]$Exclude,
    [Parameter(Mandatory=$false, ValueFromRemainingArguments=$true)]
    [string[]]$DungeonNames
)

if (-not $All -and $DungeonNames.Count -eq 0) {
    Write-Host ""
    Write-Host "  set-dungeon-selected.ps1  -  批量修改副本选择状态" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  用法:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    .\set-dungeon-selected.ps1 <副本1> <副本2> ..." -ForegroundColor White
    Write-Host "        将指定副本设为 true (选中)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    .\set-dungeon-selected.ps1 -Deselect <副本1> <副本2> ..." -ForegroundColor White
    Write-Host "        将指定副本设为 false (取消选中)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    .\set-dungeon-selected.ps1 -All" -ForegroundColor White
    Write-Host "        将所有副本设为 true (全选)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    .\set-dungeon-selected.ps1 -All -Deselect" -ForegroundColor White
    Write-Host "        将所有副本设为 false (全不选)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    .\set-dungeon-selected.ps1 -Exclude <模式> <副本1> ..." -ForegroundColor White
    Write-Host "        排除匹配模式的文件后再修改" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  示例:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    .\set-dungeon-selected.ps1 ""青龙寺"" ""黑暗堡垒""" -ForegroundColor White
    Write-Host "    .\set-dungeon-selected.ps1 -Deselect ""青龙寺"" ""黑暗堡垒""" -ForegroundColor White
    Write-Host "    .\set-dungeon-selected.ps1 -All" -ForegroundColor White
    Write-Host "    .\set-dungeon-selected.ps1 -All -Deselect" -ForegroundColor White
    Write-Host "    .\set-dungeon-selected.ps1 -All -Exclude ""*_alt.json""" -ForegroundColor White
    Write-Host "    .\set-dungeon-selected.ps1 -Exclude ""*_alt.json"" ""青龙寺""" -ForegroundColor White
    Write-Host ""
    exit 1
}

$targetValue = if ($Deselect) { $false } else { $true }
$configsPath = "e:\Projects\miniwowbot\configs\"

Get-ChildItem $configsPath -Filter *.json | Where-Object {
    $keep = $true
    if ($Exclude) {
        foreach ($pattern in $Exclude) {
            if ($_.Name -like $pattern) {
                $keep = $false
                break
            }
        }
    }
    $keep
} | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $original = $content

    if ($All) {
        # 批量处理所有副本
        $pattern = '"selected": ' + $(if ($Deselect) { 'true' } else { 'false' })
        $replace = '"selected": ' + $(if ($Deselect) { 'false' } else { 'true' })
        $content = $content -replace $pattern, $replace
    }

    # 处理指定的副本
    foreach ($name in $DungeonNames) {
        $content = $content -replace """name"": ""$name"", ""selected"": [^}]*?", """name"": ""$name"", ""selected"": $targetValue"
    }

    if ($content -ne $original) {
        $content | Set-Content $_.FullName
        Write-Host "已修改: $($_.Name)" -ForegroundColor Green
    }
}

Write-Host "`n完成!" -ForegroundColor Cyan
