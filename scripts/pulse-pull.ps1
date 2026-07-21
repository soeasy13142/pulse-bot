# scripts/pulse-pull.ps1
# Pulse Bot Windows Sync Script
# Triggered by Task Scheduler every 5 minutes.
# This is the PRIMARY sync method for Pulse Bot v0.1.
# Replaces the deferred Mac launchd (com.user.pulse-pull) which was blocked by macOS sandbox.
#
# Install:
#   1. Edit $VAULT_DIR below to point to your vault
#   2. Run: .\pulse-pull.ps1 -Install
#
# Manual run:
#   .\pulse-pull.ps1

param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Diagnose,
    [switch]$Info
)

Add-Type -AssemblyName System.Windows.Forms

$ENABLE_TOAST = $true  # Set to $false to disable desktop notifications

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

function Invoke-Diagnose {
    Write-Host "=== Pulse Bot Sync Diagnostics ==="

    # 1. Git installation
    Write-Host "`n[1/6] Git..."
    try {
        $gitVer = git --version
        Write-Host "  ✅ $gitVer"
    } catch {
        Write-Host "  ❌ Git not found in PATH"
    }

    # 2. Vault directory
    Write-Host "`n[2/6] Vault directory..."
    if (Test-Path $VAULT_DIR) {
        Write-Host "  ✅ $VAULT_DIR"
    } else {
        Write-Host "  ❌ Not found: $VAULT_DIR"
    }

    # 3. Git remote connectivity
    Write-Host "`n[3/6] Git remote..."
    try {
        Push-Location $VAULT_DIR
        $remote = git remote -v 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ Remote configured:"
            $remote | ForEach-Object { Write-Host "     $_" }
            $fetchResult = git fetch --dry-run 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✅ Remote reachable"
            } else {
                Write-Host "  ❌ Remote unreachable: $fetchResult"
            }
        } else {
            Write-Host "  ❌ No git remote configured"
        }
        Pop-Location
    } catch { Write-Host "  ❌ $_" }

    # 4. NSSM service status
    Write-Host "`n[4/6] NSSM service..."
    try {
        $nssmCheck = Get-Command nssm -ErrorAction Stop
        $svcStatus = & nssm status PulseBot 2>&1
        Write-Host "  ✅ NSSM found: $($nssmCheck.Source)"
        Write-Host "  PulseBot service: $svcStatus"
    } catch {
        Write-Host "  ⚠ NSSM not installed (ok if sync-only mode)"
    }

    # 5. Sync logs
    Write-Host "`n[5/6] Recent sync log..."
    if (Test-Path $LOG_FILE) {
        $lines = Get-Content $LOG_FILE -Tail 5
        $lines | ForEach-Object { Write-Host "  $_" }
    } else {
        Write-Host "  - No sync log yet"
    }

    # 6. Disk space
    Write-Host "`n[6/6] Disk space..."
    try {
        $drive = (Get-Item $VAULT_DIR).PSDrive.Name + ":"
        $disk = Get-PSDrive -Name (Get-Item $VAULT_DIR).PSDrive.Name
        $freeGB = [math]::Round($disk.Free / 1GB, 1)
        Write-Host "  ✅ $freeGB GB free on $drive"
    } catch {
        Write-Host "  ❌ Could not determine disk space: $($_.Exception.Message)"
    }
}

function Show-Info {
    $logExists = Test-Path $LOG_FILE
    $conflictExists = Test-Path $CONFLICT_MARKER

    Write-Host "=== Pulse Bot Sync Info ==="
    Write-Host "Vault: $VAULT_DIR"
    Write-Host "Log file: $LOG_FILE"
    Write-Host "Log exists: $logExists"
    Write-Host "Conflict marker: $(if ($conflictExists) { '⚠ YES' } else { '✅ None' })"

    if ($logExists) {
        $logContent = Get-Content $LOG_FILE
        $lastEntry = $logContent | Select-Object -Last 1
        $successCount = ($logContent | Select-String "success").Count
        $conflictCount = ($logContent | Select-String "CONFLICT").Count

        Write-Host "Total syncs: $($logContent.Count)"
        Write-Host "Successful: $successCount"
        Write-Host "Conflicts: $conflictCount"
        Write-Host "Last entry: $lastEntry"
    }

    # Check NSSM service
    try {
        $svc = Get-Service PulseBot -ErrorAction SilentlyContinue
        if ($svc) {
            Write-Host "Bot service: $($svc.Status)"
        }
    } catch {}
}

# Install/uninstall mode
if ($Install) { Install-TaskScheduler; return }
if ($Uninstall) { Uninstall-TaskScheduler; return }
if ($Diagnose) { Invoke-Diagnose; return }
if ($Info) { Show-Info; return }

# --- Main sync logic ---

# Log rotation: archive if over 1 MB
if (Test-Path $LOG_FILE) {
    $logSize = (Get-Item $LOG_FILE).Length
    if ($logSize -gt 1MB) {
        $archiveFile = "$LOG_DIR\pulse-sync.1.log"
        Move-Item $LOG_FILE $archiveFile -Force
        Write-Host "Log rotated: $archiveFile"
    }
}

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

        # Desktop notification (non-blocking)
        if ($ENABLE_TOAST) {
            $notification = New-Object System.Windows.Forms.NotifyIcon
            $notification.Icon = [System.Drawing.SystemIcons]::Warning
            $notification.BalloonTipTitle = "Pulse Bot Sync"
            $notification.BalloonTipText = "Git conflict detected in vault — manual review needed"
            $notification.Visible = $true
            $notification.ShowBalloonTip(5000)
            Start-Sleep -Milliseconds 100
            $notification.Dispose()
        }

        exit 1
    }
}
catch {
    Write-Log "EXCEPTION: $_"
    exit 1
}
