$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Laila.lnk'
if (Test-Path $shortcutPath) { throw 'A Laila desktop shortcut already exists. Rename it first to keep a backup.' }
$shellObject = New-Object -ComObject WScript.Shell
$shortcut = $shellObject.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $projectRoot 'Start-Laila.cmd'
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = 'Start your local Laila assistant'
$shortcut.Save()
Write-Host 'Laila shortcut created on your desktop. Open http://127.0.0.1:8000 after starting it.'
