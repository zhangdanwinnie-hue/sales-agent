$projectRoot = Split-Path -Parent $PSScriptRoot
$py = "C:\Users\wangj\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$env:PYTHONPATH = Join-Path $projectRoot "src"
Set-Location $projectRoot
& $py -m bp_ba_agent.workflow_web --host 127.0.0.1 --port 8083
