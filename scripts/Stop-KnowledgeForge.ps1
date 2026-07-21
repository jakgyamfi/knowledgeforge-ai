# Stops only the process recorded by the companion start script.
$ErrorActionPreference = "Stop"
$ProjectRoot = "B:\iCloud\KnowledgeForge"
$PidFile = Join-Path $ProjectRoot "logs\knowledgeforge.pid"

if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host "KnowledgeForge does not appear to be running." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
    exit 0
}

$KnowledgeForgePid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue
if ($KnowledgeForgePid -and (Get-Process -Id $KnowledgeForgePid -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $KnowledgeForgePid -Force
    Write-Host "KnowledgeForge stopped." -ForegroundColor Green
} else {
    Write-Host "Removed a stale KnowledgeForge process record." -ForegroundColor Yellow
}

Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
