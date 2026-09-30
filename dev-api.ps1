$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:XGTEST_RUNTIME_PROFILE = Join-Path $projectRoot 'artifacts/runtime-profile-v14.json'
Set-Location -LiteralPath $projectRoot
& (Join-Path $projectRoot '.venv/Scripts/uvicorn.exe') 'xgtest.web.app:app' --host 127.0.0.1 --port 8001
