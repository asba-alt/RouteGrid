<#
  start-local.ps1 — start the full RouteGrid local stack.

  Layout note: the virtualenv lives at the REPO ROOT (RouteGrid\.venv), not in backend\.
  PostgreSQL + PostGIS and Redis are the portable install under C:\Users\Asba\.routegrid-pg
  (Docker cannot run on this machine: no WSL2/Hyper-V).

  Usage:  powershell -ExecutionPolicy Bypass -File scripts\start-local.ps1
#>

$root = "C:\Users\Asba\Desktop\Projects\RouteGrid"
$stack = "C:\Users\Asba\.routegrid-pg"
$logs = Join-Path $env:TEMP "routegrid-logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Test-Port([int]$Port) {
  $client = New-Object System.Net.Sockets.TcpClient
  try { $client.Connect('127.0.0.1', $Port); return $true }
  catch { return $false }
  finally { $client.Dispose() }
}

Write-Host "Starting RouteGrid local stack..." -ForegroundColor Cyan

# NOTE: every child process redirects stdout/stderr to a file. Without this the
# spawned servers inherit this script's console pipe and the script appears to hang.

# 1. PostgreSQL ---------------------------------------------------------------
if (Test-Port 5432) {
  Write-Host "  [skip] PostgreSQL already listening on 5432"
} else {
  Start-Process "$stack\pgsql\bin\postgres.exe" `
    -ArgumentList '-D', "$stack\data", '-p', '5432' `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$logs\postgres.out.log" `
    -RedirectStandardError "$logs\postgres.err.log"
  Write-Host "  [ok]   PostgreSQL starting on 5432"
}

# 2. Redis --------------------------------------------------------------------
if (Test-Port 6379) {
  Write-Host "  [skip] Redis already listening on 6379"
} else {
  Start-Process "$stack\redis\redis-server.exe" `
    -ArgumentList '--port', '6379', '--appendonly', 'no' `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$logs\redis.out.log" `
    -RedirectStandardError "$logs\redis.err.log"
  Write-Host "  [ok]   Redis starting on 6379"
}

# 3. FastAPI ------------------------------------------------------------------
if (Test-Port 8000) {
  Write-Host "  [skip] API already listening on 8000"
} else {
  Start-Process "$root\.venv\Scripts\python.exe" `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000' `
    -WorkingDirectory "$root\backend" -WindowStyle Hidden `
    -RedirectStandardOutput "$logs\api.out.log" `
    -RedirectStandardError "$logs\api.err.log"
  Write-Host "  [ok]   API starting on 8000"
}

# 4. Vite dashboard -----------------------------------------------------------
if (Test-Port 5173) {
  Write-Host "  [skip] Dashboard already listening on 5173"
} else {
  Start-Process "node" `
    -ArgumentList 'node_modules/vite/bin/vite.js', '--port', '5173', '--host', '127.0.0.1', '--strictPort' `
    -WorkingDirectory "$root\frontend" -WindowStyle Hidden `
    -RedirectStandardOutput "$logs\web.out.log" `
    -RedirectStandardError "$logs\web.err.log"
  Write-Host "  [ok]   Dashboard starting on 5173"
}

# 5. Wait for readiness then verify -------------------------------------------
$services = @(
  @{ Name = 'PostgreSQL'; Port = 5432 },
  @{ Name = 'Redis';      Port = 6379 },
  @{ Name = 'API';        Port = 8000 },
  @{ Name = 'Dashboard';  Port = 5173 }
)

$deadline = (Get-Date).AddSeconds(60)
foreach ($service in $services) {
  while (-not (Test-Port $service.Port) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
  }
}

Write-Host ""
Write-Host "Status:" -ForegroundColor Cyan
foreach ($service in $services) {
  $up = Test-Port $service.Port
  $colour = if ($up) { "Green" } else { "Red" }
  $state = if ($up) { "LISTENING" } else { "DOWN" }
  Write-Host ("  {0,-11} :{1}  {2}" -f $service.Name, $service.Port, $state) -ForegroundColor $colour
}

Write-Host ""
try {
  $health = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 10
  Write-Host ("  /health -> status={0} database={1} redis={2}" -f $health.status, $health.database, $health.redis)
} catch {
  Write-Host "  /health could not be reached" -ForegroundColor Red
}

Write-Host ""
Write-Host "  Dashboard : http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "  API docs  : http://127.0.0.1:8000/docs" -ForegroundColor Green
