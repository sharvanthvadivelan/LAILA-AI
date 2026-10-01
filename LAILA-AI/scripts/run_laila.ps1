$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$pythonPath = @('.venv\Scripts\python.exe', '..\.venv\Scripts\python.exe') | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $pythonPath) { throw 'Run .\scripts\setup.ps1 first.' }
$pythonPath = (Resolve-Path $pythonPath).Path
$env:OLLAMA_NO_CLOUD = '1'
$env:HF_HUB_OFFLINE = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
Write-Host 'Starting Laila at http://127.0.0.1:8000'
Write-Host 'Open that address in your browser after the server is ready. Press Ctrl+C to stop.'
& $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
