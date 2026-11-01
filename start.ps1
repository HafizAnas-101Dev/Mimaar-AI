<#
.SYNOPSIS
  Start Mimaar AI: the Muse Glimmer model server (when set up), the backend and the frontend.

.EXAMPLE
  .\start.ps1          # full app; uses local models if backend/.env says MODEL_BACKEND=local
  .\start.ps1 -Mock    # demo data only: no GPU, no models, no API key needed
#>
param([switch]$Mock)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

function Wait-Port([int]$Port, [int]$Seconds) {
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    if ((Test-NetConnection 127.0.0.1 -Port $Port -WarningAction SilentlyContinue).TcpTestSucceeded) { return $true }
    Start-Sleep -Seconds 2
  }
  return $false
}

# 1. Dependencies, first run only.
if (-not (Test-Path $python)) {
  Write-Host "Setting up the Python environment..."
  python -m venv (Join-Path $backend ".venv")
  & $python -m pip install -r (Join-Path $backend "requirements.txt")
}
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
  Write-Host "Installing frontend packages..."
  npm --prefix $frontend install
}
$envFile = Join-Path $backend ".env"
if (-not (Test-Path $envFile)) { Copy-Item (Join-Path $backend ".env.example") $envFile }

# 2. Muse Glimmer, when this PC runs the models locally.
$local = (Select-String -Path $envFile -Pattern '^\s*MODEL_BACKEND\s*=\s*local' -Quiet)
$models = Join-Path $backend "models"
$glimmer = Join-Path $models "glimmer\Muse-Glimmer-30B-UD-Q4_K_XL.gguf"
if ($Mock) {
  $env:MIMAAR_MOCK = "true"   # read by the backend; overrides backend/.env
  Write-Host "Mock mode: demo geometry and template reports, no models."
} elseif ($local -and (Test-Path $glimmer)) {
  Write-Host "Starting Muse Glimmer (takes about a minute to load)..."
  $serverArgs = @(
    "-m", $glimmer,
    "--mmproj", (Join-Path $models "glimmer\mmproj-Muse-Glimmer-30B-Q8_0.gguf"),
    "--alias", "muse-glimmer-30b", "--host", "127.0.0.1", "--port", "8080",
    "-c", "16384", "--fit", "on", "--fit-target", "3600", "--parallel", "1",
    "-md", (Join-Path $models "glimmer\dflash-kquant.gguf"), "--spec-type", "draft-dflash", "--spec-draft-n-max", "8"
  )
  Start-Process -FilePath (Join-Path $models "llama.cpp\llama-server.exe") -ArgumentList $serverArgs -WindowStyle Minimized
} elseif ($local) {
  Write-Warning "MODEL_BACKEND=local but the models are missing. Run: cd backend; .venv\Scripts\python -m scripts.setup_local_models --sam"
}

# 3. Backend and frontend, each in its own window so their logs stay visible.
Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--app-dir", $backend, "--port", "8000" -WorkingDirectory $root
Start-Process -FilePath "npm.cmd" -ArgumentList "--prefix", $frontend, "run", "dev" -WorkingDirectory $root

if ((Wait-Port 8000 60) -and (Wait-Port 5173 60)) {
  Start-Process "http://localhost:5173"
  Write-Host "Mimaar AI is running at http://localhost:5173"
  if (-not $Mock -and $local -and (Test-Path $glimmer)) {
    Write-Host "Reports appear at once; Muse Glimmer's write-up works once its window says 'server is listening'."
  }
} else {
  Write-Warning "The servers did not start in time. Check their windows for errors."
}
