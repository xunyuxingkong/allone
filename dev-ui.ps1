$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:XGTEST_WEB_API_TARGET = 'http://127.0.0.1:8001'
Set-Location -LiteralPath (Join-Path $projectRoot 'webui')
$nodePath = (Get-Command node -ErrorAction Stop).Source
$vitePath = Join-Path $projectRoot 'webui/node_modules/vite/bin/vite.js'
& $nodePath $vitePath '--host' '127.0.0.1' '--port' '5173' '--strictPort'
