# Kill BlueStacks instance by port
param(
    [int]$Port
)

$processIds = @(Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique)

if ($processIds.Count -eq 0) {
    Write-Output "No process listening on port $Port"
    exit 1
}

$killed = $false
foreach ($processId in $processIds) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process -and $process.ProcessName -eq "HD-Player") {
        Write-Output "Killing PID: $processId (Port: $Port)"
        Stop-Process -Id $processId -Force
        $killed = $true
    }
}

if (-not $killed) {
    Write-Output "No HD-Player process matched port $Port"
    exit 1
}

exit 0
