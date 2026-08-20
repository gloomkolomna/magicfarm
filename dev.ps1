param(
    [switch]$NoFrontend,
    [switch]$NoBackend,
    [switch]$NoInstall
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$procs = @()

function Write-Step { Write-Host ">>> $args" -ForegroundColor Cyan }
function Write-OK   { Write-Host " OK $args" -ForegroundColor Green }
function Write-Warn { Write-Host " WARN $args" -ForegroundColor Yellow }
function Write-Err  { Write-Host " ERR $args" -ForegroundColor Red }

Write-Host @"

   ___  __  ____  ____  __    ____  _  _  ___
  / __ \/ / / / / / / / / /   / __ \/ |/ // _ \
 / /_/ / /_/ / / / / / / /__/ / /_/ /    / , _/
/ .___/\____/_/ /_/ /_/_____\____/_/|_/_/|_|  (mini app)

    Farm — local dev

"@ -ForegroundColor Magenta

$apiDir = Join-Path $root "api"
$venvPython = Join-Path $apiDir "venv\Scripts\python.exe"
$frontendDir = Join-Path $root "frontend"

# ─── venv: создать, если нет ───
if (-not (Test-Path $venvPython)) {
    Write-Step "Creating venv (api\venv)"
    if (-not (Test-Path $apiDir)) {
        Write-Err "api/ not found at $apiDir"
        exit 1
    }
    $py = "python"
    & $py -m venv (Join-Path $apiDir "venv") 2>&1 | ForEach-Object { Write-Host "  $($_.ToString())" }
    if (-not (Test-Path $venvPython)) {
        Write-Err "venv creation failed"
        exit 1
    }

    Write-Step "Installing Python deps (requirements.txt)"
    Push-Location $apiDir
    & $venvPython -m pip install --upgrade pip 2>&1 | ForEach-Object { Write-Host "  $($_.ToString())" }
    & $venvPython -m pip install -r requirements.txt 2>&1 | ForEach-Object { Write-Host "  $($_.ToString())" }
    $pipExit = $LASTEXITCODE
    Pop-Location
    if ($pipExit -ne 0) {
        Write-Err "pip install failed"
        exit 1
    }
    Write-OK "venv + deps ready"
}

# ─── Миграции ───
Write-Step "Initializing database"
Push-Location $apiDir
$initScript = @"
from models import Base; from db import engine; Base.metadata.create_all(bind=engine)
"@
& $venvPython -c $initScript 2>&1 | ForEach-Object { Write-Host "  $($_.ToString())" }
$initExit = $LASTEXITCODE
if ($initExit -ne 0) {
    Pop-Location
    Write-Err "DB init failed"
    exit 1
}
& $venvPython -m alembic stamp head 2>&1 | ForEach-Object { Write-Host "  $($_.ToString())" }
$alembicExit = $LASTEXITCODE
Pop-Location
if ($alembicExit -ne 0) {
    Write-Err "Alembic stamp failed"
    exit 1
}
Write-OK "Database ready"

function cleanup {
    if ($procs.Count -gt 0) {
        Write-Host "`nStopping..." -ForegroundColor Yellow
        foreach ($p in $procs) {
            if (-not $p.HasExited) {
                & taskkill /PID $p.Id /T /F 2>$null
            }
            $p.Dispose()
        }
        $procs = @()
        Write-Host "All processes stopped." -ForegroundColor Green
    }
}

# ─── Backend ───
if (-not $NoBackend) {
    Write-Step "Starting backend (FastAPI :8003, APP_ENV=dev)"

    $env:PYTHONPATH = $apiDir
    # dev-режим: сервер доверяет vk_user_id без проверки подписи VK.
    $env:APP_ENV = "dev"
    $env:DEV_LOGIN_ENABLED = "true"

    $apiProc = Start-Process -FilePath $venvPython `
        -ArgumentList "-m uvicorn main:app --host 127.0.0.1 --port 8003 --reload --log-level warning" `
        -WorkingDirectory $apiDir -NoNewWindow -PassThru
    $procs += $apiProc
    Write-OK "Backend (pid $($apiProc.Id))"
}

# ─── Frontend ───
if (-not $NoFrontend) {
    Write-Step "Starting frontend (Vite :5175)"

    if (-not (Test-Path (Join-Path $frontendDir "node_modules\.package-lock.json"))) {
        if ($NoInstall) {
            Write-Err "node_modules not found in frontend/ and -NoInstall set"
            exit 1
        }
        Write-Warn "node_modules not found, installing..."
        Push-Location $frontendDir
        npm install
        Pop-Location
    }

    $feProc = Start-Process -FilePath "cmd" -ArgumentList "/c npm run dev" `
        -WorkingDirectory $frontendDir -NoNewWindow -PassThru
    $procs += $feProc
    Write-OK "Frontend (pid $($feProc.Id))"
}

# ─── Подсказка: кто ты в дев-режиме ───
$demoId = ""
if (Test-Path (Join-Path $frontendDir ".env")) {
    $feEnv = Get-Content (Join-Path $frontendDir ".env")
    $demoLine = $feEnv | Where-Object { $_ -match '^VITE_DEMO_VK_ID=' }
    if ($demoLine) { $demoId = ($demoLine -replace '^VITE_DEMO_VK_ID=', '').Trim() }
}

Write-Host ""
Write-Host "──────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  API:       http://127.0.0.1:8003/api/" -ForegroundColor Green
Write-Host "  Mini App:  http://127.0.0.1:5175/magicfarm/" -ForegroundColor Green
if ($demoId) {
    Write-Host "  Дев-режим: ты = vk_id $demoId (админ, без VK-авторизации)" -ForegroundColor Yellow
} else {
    Write-Host "  Дев-режим: VITE_DEMO_VK_ID не задан — фронт не откроется без VK" -ForegroundColor Yellow
}
Write-Host "  APP_ENV=dev — подпись VK не проверяется" -ForegroundColor DarkGray
Write-Host "  Press Ctrl+C to stop all" -ForegroundColor DarkGray
Write-Host "──────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

try {
    while ($true) {
        $exited = $procs | Where-Object { $_.HasExited }
        foreach ($p in $exited) {
            Write-Warn "Process $($p.Id) stopped (exit: $($p.ExitCode))"
            $p.Dispose()
            $procs = @($procs | Where-Object { $_.Id -ne $p.Id })
        }
        if ($procs.Count -eq 0) { break }
        Start-Sleep -Seconds 2
    }
} finally {
    cleanup
}
