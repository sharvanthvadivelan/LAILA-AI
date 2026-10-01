$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install 64-bit Python 3.11 or 3.12 from python.org, including the Python launcher, then reopen PowerShell.' }
& py -3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ is required"; assert sys.maxsize > 2**32, "64-bit Python is required"'
if ($LASTEXITCODE -ne 0) { throw 'Python version/architecture check failed.' }
& py -3 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check internet connectivity and Python wheel availability; Python 3.11 or 3.12 is preferred.' }
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Write-Host ''
Write-Host 'Laila dependencies are installed.'
Write-Host 'Next install Ollama, then run:'
Write-Host '  ollama pull llama3.2'
Write-Host '  ollama pull nomic-embed-text'
Write-Host 'Then run: .\scripts\run_laila.ps1'
