# Kill BlueStacks instance by name
param(
    [string]$InstanceName
)

# 通过 WMI 查找包含实例名的 HD-Player 进程
Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq 'HD-Player.exe' -and
        $_.CommandLine -like "*--instance $InstanceName*"
    } |
    ForEach-Object {
        Write-Output "Killing PID: $($_.ProcessId) (Instance: $InstanceName)"
        Stop-Process -Id $_.ProcessId -Force
    }
