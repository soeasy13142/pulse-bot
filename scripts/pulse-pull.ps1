# scripts/pulse-pull.ps1
# Pulse Bot Windows Sync Script
# Triggered by Task Scheduler every 5 minutes.
# Replaces Mac launchd (com.user.pulse-pull) on Windows.
#
# Install:
#   1. Edit $VAULT_DIR below to point to your vault
#   2. Run: .\pulse-pull.ps1 -Install
#
# Manual run:
#   .\pulse-pull.ps1

param(
    [switch]$Install,
    [switch]$Uninstall
)

$VAULT_DIR = "$env:USERPROFILE\my_obsidian"
$LOG_DIR = "$env:LOCALAPPDATA\PulseBot"
$LOG_FILE = "$LOG_DIR\pulse-sync.log"
$CONFLICT_MARKER = "$LOG_DIR\pulse-sync.CONFLICT"

# Ensure log directory exists
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp pulse-pull: $Message" | Out-File -FilePath $LOG_FILE -Append -Encoding utf8
    Write-Host "$timestamp $Message"
}

function Install-TaskScheduler {
    $taskName = "PulseBotSync"
    $scriptPath = $MyInvocation.MyCommand.Path
    if (-not $scriptPath) { $scriptPath = "$PSScriptRoot\pulse-pull.ps1" }

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
    $trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 5) -At (Get-Date).AddMinutes(1) -RepetitionDuration ([TimeSpan]::MaxValue)
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force
    Write-Log "Task Scheduler '$taskName' installed (5-min interval)."
    Write-Host "✅ Task Scheduler '$taskName' installed. Runs every 5 minutes."
}

function Uninstall-TaskScheduler {
    $taskName = "PulseBotSync"
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Log "Task Scheduler '$taskName' uninstalled."
        Write-Host "🗑 Task Scheduler '$taskName' uninstalled."
    } else {
        Write-Host "ℹ Task '$taskName' not found."
    }
}

# Install/uninstall mode
if ($Install) { Install-TaskScheduler; return }
if ($Uninstall) { Uninstall-TaskScheduler; return }

# --- Main sync logic ---
if (-not (Test-Path $VAULT_DIR)) {
    Write-Log "ERROR: vault directory not found at $VAULT_DIR"
    exit 1
}

Write-Log "starting"
Set-Location $VAULT_DIR

# Remove old conflict marker if it exists
if (Test-Path $CONFLICT_MARKER) { Remove-Item $CONFLICT_MARKER -Force }

try {
    $output = git pull --rebase --autostash 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Log "success"
    } else {
        $outputStr = $output | Out-String
        Write-Log "CONFLICT or error — manual review needed"
        Write-Log "--- git output ---"
        $output | ForEach-Object { Write-Log "  $_" }
        Write-Log "--- end git output ---"

        # Create conflict marker file
        "Conflict detected at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n$outputStr" |
            Out-File -FilePath $CONFLICT_MARKER -Encoding utf8
        exit 1
    }
}
catch {
    Write-Log "EXCEPTION: $_"
    exit 1
}
