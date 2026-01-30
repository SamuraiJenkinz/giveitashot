# M365 Email Summarizer - Scheduled Task Setup Script
# Run as Administrator on Windows Server
# Created by Kevin "Overlord of AI Bespoke Apps" Taylor

param(
    [string]$AppPath = "C:\m365incidents",
    [string]$TaskName = "M365EmailSummarizer",
    [string]$StartTime = "00:00",
    [int]$IntervalHours = 1,
    [switch]$RunNow
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "M365 Email Summarizer - Deployment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check for admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Run this script as Administrator" -ForegroundColor Red
    exit 1
}

# Verify app path exists
if (-not (Test-Path "$AppPath\src\main.py")) {
    Write-Host "ERROR: src\main.py not found at $AppPath" -ForegroundColor Red
    Write-Host "Ensure the m365incidents project is at $AppPath" -ForegroundColor Yellow
    exit 1
}

# Verify venv exists
if (-not (Test-Path "$AppPath\venv\Scripts\python.exe")) {
    Write-Host "ERROR: Virtual environment not found at $AppPath\venv" -ForegroundColor Red
    Write-Host "Create venv first:" -ForegroundColor Yellow
    Write-Host "  cd $AppPath" -ForegroundColor White
    Write-Host "  python -m venv venv" -ForegroundColor White
    Write-Host "  venv\Scripts\pip install -r requirements.txt" -ForegroundColor White
    exit 1
}

# Verify .env exists
if (-not (Test-Path "$AppPath\.env")) {
    Write-Host "ERROR: .env file not found at $AppPath" -ForegroundColor Red
    Write-Host "Copy .env.example to .env and configure:" -ForegroundColor Yellow
    Write-Host "  - Azure AD credentials (TENANT_ID, CLIENT_ID, CLIENT_SECRET)" -ForegroundColor White
    Write-Host "  - Mailbox settings (SHARED_MAILBOX, USER_EMAIL)" -ForegroundColor White
    Write-Host "  - Azure OpenAI settings (if using LLM summaries)" -ForegroundColor White
    exit 1
}

Write-Host "Configuration:" -ForegroundColor Green
Write-Host "  App Path:  $AppPath"
Write-Host "  Task Name: $TaskName"
Write-Host "  Interval:  Every $IntervalHours hour(s)"
Write-Host "  Start:     $StartTime"
Write-Host ""

# Create logs directory
$logsPath = "$AppPath\logs"
if (-not (Test-Path $logsPath)) {
    New-Item -ItemType Directory -Path $logsPath | Out-Null
    Write-Host "Created logs directory: $logsPath" -ForegroundColor Green
}

# Create startup batch script
$timestamp = '$(Get-Date -Format "yyyy-MM-dd_HH-mm-ss")'
$batchScript = @"
@echo off
cd /d $AppPath
echo ========================================
echo M365 Email Summarizer - Starting
echo %date% %time%
echo ========================================

call venv\Scripts\activate.bat
python -m src.main

echo ========================================
echo Completed: %date% %time%
echo Exit Code: %ERRORLEVEL%
echo ========================================
"@

$batchPath = "$AppPath\run_summarizer.bat"
Set-Content -Path $batchPath -Value $batchScript
Write-Host "Created startup script: $batchPath" -ForegroundColor Green

# Remove existing task if present
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing scheduled task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create scheduled task action
$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$batchPath`" >> `"$logsPath\summarizer_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log`" 2>&1" `
    -WorkingDirectory $AppPath

# Create hourly trigger starting at specified time
# Note: Using 9999 days instead of [TimeSpan]::MaxValue to avoid XML duration overflow on some Windows versions
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At $StartTime `
    -RepetitionInterval (New-TimeSpan -Hours $IntervalHours) `
    -RepetitionDuration (New-TimeSpan -Days 9999)

# Run as SYSTEM account
$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

# Task settings optimized for batch job
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -RestartCount 3 `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

# Register the task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "M365 Email Summarizer - Hourly email digest from shared mailbox (every $IntervalHours hour(s))" | Out-Null

Write-Host "Scheduled task created: $TaskName" -ForegroundColor Green
Write-Host "  Runs every $IntervalHours hour(s)" -ForegroundColor White

# Optionally run now
if ($RunNow) {
    Write-Host ""
    Write-Host "Running task now..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 3

    $task = Get-ScheduledTask -TaskName $TaskName
    Write-Host "Status: $($task.State)" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "SUCCESS! Scheduled task configured" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "The email summarizer will run every $IntervalHours hour(s)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Logs location: $logsPath" -ForegroundColor White
Write-Host ""
Write-Host "Management commands:" -ForegroundColor Cyan
Write-Host "  Run now:  .\deploy\manage_service.ps1 -Action run-now"
Write-Host "  Status:   .\deploy\manage_service.ps1 -Action status"
Write-Host "  Remove:   .\deploy\manage_service.ps1 -Action remove"
Write-Host "  Logs:     Get-Content $logsPath\*.log -Tail 50"
Write-Host ""
Write-Host "To change interval, re-run with -IntervalHours parameter:" -ForegroundColor Yellow
Write-Host "  .\deploy\setup_scheduled_task.ps1 -IntervalHours 2" -ForegroundColor White
