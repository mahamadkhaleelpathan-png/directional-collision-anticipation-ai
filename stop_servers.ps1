$ErrorActionPreference = "Continue"
$root = "C:\Users\maham\Downloads\ai-collision-anticipation-system"
$backendPid = "$root\.server_pid_backend"
$frontendPid = "$root\.server_pid_frontend"

foreach ($pidFile in @($backendPid, $frontendPid)) {
    $existing = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($existing) {
        Stop-Process -Id $existing -Force -ErrorAction SilentlyContinue
        Write-Output "Stopped pid $existing (from $(Split-Path $pidFile -Leaf))"
        Remove-Item $pidFile -ErrorAction SilentlyContinue
    }
}

Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*opencode-tools*" -or $_.MainWindowTitle -like "*vite*" } | ForEach-Object {
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    Write-Output "Stopped node pid $($_.Id)"
}

Start-Sleep -Seconds 2
"backend 8000 free: " + -not [bool](Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
"frontend 5173 free: " + -not [bool](Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)