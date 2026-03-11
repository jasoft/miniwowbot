# Kill BlueStacks instance by port
param(
    [int]$Port
)

# 不限制 IP 地址，只匹配端口
Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object {
        $p = Get-Process -Id $_ -ErrorAction SilentlyContinue
        if ($p -and $p.ProcessName -eq "HD-Player") {
            Write-Output "Killing PID: $_ (Port: $Port)"
            Stop-Process -Id $_ -Force
        }
    }
