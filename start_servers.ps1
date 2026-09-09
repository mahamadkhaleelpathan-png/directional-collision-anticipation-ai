$ErrorActionPreference = "Continue"
$root = "C:\Users\maham\Downloads\ai-collision-anticipation-system"
$nodeBin = "C:\Users\maham\AppData\Local\opencode-tools\node-v20.20.2-win-x64"

$env:Path = "$nodeBin;" + $env:Path

function Start-Neighbor {
    param([string]$Name, [string]$PidFile, [scriptblock]$Cmd)
    $existing = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($existing) {
        try {
            $p = Get-Process -Id $existing -ErrorAction Stop
            if ($p -and -not $p.HasExited) {
                Write-Output "$Name already running (pid $existing)"
                return $true
            }
        } catch { }
    }
    Write-Output "Starting $Name ..."
    $proc = & $Cmd
    if ($proc -and $proc.Id) {
        Set-Content $PidFile $proc.Id
        Write-Output "$Name started pid=$($proc.Id)"
        return $true
    }
    Write-Output "$Name FAILED to start"
    return $false
}

$backendPid = "$root\.server_pid_backend"
$frontendPid = "$root\.server_pid_frontend"

$StartBackend = {
    $p = Start-Process -FilePath "$root\venv\Scripts\python.exe" -ArgumentList "-m","uvicorn","api.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory $root -WindowStyle Hidden -PassThru
    $p
}
$StartFrontend = {
    $p = Start-Process -FilePath "$nodeBin\npm.cmd" -ArgumentList "run","dev" -WorkingDirectory "$root\frontend" -WindowStyle Hidden -PassThru
    $p
}

Start-Neighbor "backend" $backendPid $StartBackend
Start-Neighbor "frontend" $frontendPid $StartFrontend

Start-Sleep -Seconds 12
"backend health: " + (curl.exe -s -o NUL -w "%{http_code}" --max-time 10 "http://127.0.0.1:8000/api/health")
"frontend:      " + (curl.exe -s -o NUL -w "%{http_code}" --max-time 10 "http://127.0.0.1:5173/")