# ============================================================
#  DealHawk Scraper - Windows Task Scheduler Setup
#  2시간마다 자동으로 스크래퍼를 실행하는 예약 작업 등록
# ============================================================
#
# Usage (관리자 권한 PowerShell에서 실행):
#   .\setup_scheduler.ps1
#
# 작업 삭제:
#   Unregister-ScheduledTask -TaskName "DealHawk-Scraper" -Confirm:$false
#

$ErrorActionPreference = "Stop"

$TaskName = "DealHawk-Scraper"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatFile = Join-Path $ScriptDir "run_scraper.bat"

# Validate bat file exists
if (-not (Test-Path $BatFile)) {
    Write-Error "run_scraper.bat not found at: $BatFile"
    exit 1
}

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "[INFO] Task '$TaskName' already exists. Removing old task..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create the action (run the batch file)
$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatFile`"" `
    -WorkingDirectory $ScriptDir

# Create the trigger (every 2 hours, indefinitely)
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date.AddHours(8) `
    -RepetitionInterval (New-TimeSpan -Hours 2) `
    -RepetitionDuration (New-TimeSpan -Days 365)

# Task settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# Register the task (runs as current user)
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "DealHawk deal scraper - runs every 2 hours to collect deals from 11 shopping sites" `
    -RunLevel Limited

Write-Host ""
Write-Host "============================================"
Write-Host "  Task '$TaskName' registered successfully!"
Write-Host "============================================"
Write-Host ""
Write-Host "  Schedule : Every 2 hours"
Write-Host "  Script   : $BatFile"
Write-Host "  Logs     : $ScriptDir\logs\"
Write-Host ""
Write-Host "  Manual run  : schtasks /run /tn `"$TaskName`""
Write-Host "  Check status: schtasks /query /tn `"$TaskName`""
Write-Host "  Remove      : Unregister-ScheduledTask -TaskName `"$TaskName`" -Confirm:`$false"
Write-Host ""
