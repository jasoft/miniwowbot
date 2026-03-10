# Kill BlueStacks instance by name
param(
    [string]$InstanceName
)

$matchedProcesses = @(Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq 'HD-Player.exe' -and
        $_.CommandLine -like "*--instance $InstanceName*"
    })

if ($matchedProcesses.Count -eq 0) {
    Write-Output "No process matched instance $InstanceName"
    exit 1
}

foreach ($process in $matchedProcesses) {
    Write-Output "Killing PID: $($process.ProcessId) (Instance: $InstanceName)"
    Stop-Process -Id $process.ProcessId -Force
}

exit 0
