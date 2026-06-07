param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8092
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$venv = Join-Path $root ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"
$bundledPython = "C:\Users\wangj\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
  Write-Error "Port $Port is already in use. V2 startup will not stop existing services."
  exit 1
}

if (-not (Test-Path $venvPython)) {
  if (Test-Path $bundledPython) {
    & $bundledPython -m venv $venv
  } else {
    & python -m venv $venv
  }
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $backend "requirements.txt")

Push-Location $frontend
try {
  if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    npm install
  }
  npm run build
} finally {
  Pop-Location
}

$env:PYTHONPATH = $backend
Write-Host "BP BA Agent V2 is starting at http://$HostName`:$Port/"
& $venvPython -m uvicorn app.main:app --host $HostName --port $Port --app-dir $backend
