# Starts KnowledgeForge in the foreground so operational logs remain visible.
# This script is used by the desktop shortcut and can also be run directly.
$ErrorActionPreference = "Stop"
$ProjectRoot = "B:\iCloud\KnowledgeForge"
$Executable = Join-Path $ProjectRoot ".venv\Scripts\knowledgeforge.exe"
$PidFile = Join-Path $ProjectRoot "logs\knowledgeforge.pid"

Set-Location -LiteralPath $ProjectRoot

if (Test-Path -LiteralPath $PidFile) {
    $ExistingPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue
    if ($ExistingPid -and (Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue)) {
        Write-Host "KnowledgeForge is already running as process $ExistingPid." -ForegroundColor Yellow
        Read-Host "Press Enter to close"
        exit 0
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $Executable)) {
    Write-Host "Virtual environment not found. Follow docs\SETUP.md first." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "Starting KnowledgeForge at http://127.0.0.1:8765" -ForegroundColor Green
Write-Host "Keep this window open for logs. Use the Stop shortcut when finished." -ForegroundColor Cyan

$KnowledgeForgeProcess = Start-Process -FilePath $Executable -ArgumentList "serve" -PassThru -NoNewWindow
$KnowledgeForgeProcess.Id | Set-Content -LiteralPath $PidFile -Encoding ascii
try {
    Wait-Process -Id $KnowledgeForgeProcess.Id
}
finally {
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}
