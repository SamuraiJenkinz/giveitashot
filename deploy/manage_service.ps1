# M365 Email Summarizer - Service Management Script
# Created by Kevin "Overlord of AI Bespoke Apps" Taylor

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("start", "stop", "status", "remove", "run-now", "logs", "test")]
    [string]$Action,

    [string]$TaskName = "M365EmailSummarizer",
    [string]$AppPath = "C:\m365incidents",
    [int]$LogLines = 50
)

$logsPath = "$AppPath\logs"

switch ($Action) {
    "run-now" {
        Write-Host "Running $TaskName now..." -ForegroundColor Cyan
        Start-ScheduledTask -TaskName $TaskName
        Start-Sleep -Seconds 2
        $task = Get-ScheduledTask -TaskName $TaskName
        Write-Host "Status: $($task.State)" -ForegroundColor Green
        Write-Host ""
        Write-Host "Check logs with: .\deploy\manage_service.ps1 -Action logs" -ForegroundColor Yellow
    }
    "start" {
        Write-Host "Enabling $TaskName..." -ForegroundColor Cyan
        Enable-ScheduledTask -TaskName $TaskName
        $task = Get-ScheduledTask -TaskName $TaskName
        Write-Host "Task enabled. State: $($task.State)" -ForegroundColor Green

        # Show next run time
        $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "Next run: $($taskInfo.NextRunTime)" -ForegroundColor White
    }
    "stop" {
        Write-Host "Disabling $TaskName..." -ForegroundColor Cyan
        Disable-ScheduledTask -TaskName $TaskName
        $task = Get-ScheduledTask -TaskName $TaskName
        Write-Host "Task disabled. State: $($task.State)" -ForegroundColor Green
    }
    "status" {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($task) {
            $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName

            Write-Host "========================================" -ForegroundColor Cyan
            Write-Host "M365 Email Summarizer - Status" -ForegroundColor Cyan
            Write-Host "========================================" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "Task Name:    $TaskName" -ForegroundColor White
            Write-Host "State:        $($task.State)" -ForegroundColor $(if ($task.State -eq "Ready") { "Green" } elseif ($task.State -eq "Running") { "Yellow" } else { "Red" })
            Write-Host "Last Run:     $($taskInfo.LastRunTime)" -ForegroundColor White
            Write-Host "Last Result:  $($taskInfo.LastTaskResult)" -ForegroundColor $(if ($taskInfo.LastTaskResult -eq 0) { "Green" } else { "Red" })
            Write-Host "Next Run:     $($taskInfo.NextRunTime)" -ForegroundColor White
            Write-Host ""

            # Show trigger info
            $triggers = $task.Triggers
            foreach ($trigger in $triggers) {
                if ($trigger.CimClass.CimClassName -eq "MSFT_TaskDailyTrigger") {
                    Write-Host "Schedule:     Daily at $($trigger.StartBoundary.Split('T')[1].Substring(0,5))" -ForegroundColor White
                }
            }

            # Show recent log if exists
            $latestLog = Get-ChildItem -Path $logsPath -Filter "*.log" -ErrorAction SilentlyContinue |
                         Sort-Object LastWriteTime -Descending |
                         Select-Object -First 1
            if ($latestLog) {
                Write-Host ""
                Write-Host "Latest log:   $($latestLog.Name)" -ForegroundColor White
                Write-Host "Log size:     $([math]::Round($latestLog.Length / 1KB, 2)) KB" -ForegroundColor White
            }
        } else {
            Write-Host "Task '$TaskName' not found" -ForegroundColor Red
            Write-Host "Run setup_scheduled_task.ps1 first" -ForegroundColor Yellow
        }
    }
    "remove" {
        $confirm = Read-Host "Remove scheduled task '$TaskName'? (y/N)"
        if ($confirm -eq 'y' -or $confirm -eq 'Y') {
            Write-Host "Removing $TaskName..." -ForegroundColor Yellow
            Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
            Write-Host "Task removed" -ForegroundColor Green
        } else {
            Write-Host "Cancelled" -ForegroundColor Yellow
        }
    }
    "logs" {
        $latestLog = Get-ChildItem -Path $logsPath -Filter "*.log" -ErrorAction SilentlyContinue |
                     Sort-Object LastWriteTime -Descending |
                     Select-Object -First 1

        if ($latestLog) {
            Write-Host "========================================" -ForegroundColor Cyan
            Write-Host "Latest Log: $($latestLog.Name)" -ForegroundColor Cyan
            Write-Host "========================================" -ForegroundColor Cyan
            Write-Host ""
            Get-Content $latestLog.FullName -Tail $LogLines
        } else {
            Write-Host "No log files found in $logsPath" -ForegroundColor Yellow
            Write-Host "Run the task first with: .\deploy\manage_service.ps1 -Action run-now" -ForegroundColor White
        }
    }
    "test" {
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "M365 Email Summarizer - Test Run" -ForegroundColor Cyan
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Running in dry-run mode (no email sent)..." -ForegroundColor Yellow
        Write-Host ""

        Push-Location $AppPath
        try {
            & "$AppPath\venv\Scripts\python.exe" -m src.main --dry-run
        } finally {
            Pop-Location
        }
    }
}
