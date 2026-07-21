# scripts/pulse-bot-service.ps1
# Pulse Bot Windows Service Manager — NSSM wrapper
#
# Requires NSSM (https://nssm.cc) in PATH.
#
# Usage:
#   .\scripts\pulse-bot-service.ps1 -Install
#   .\scripts\pulse-bot-service.ps1 -Start
#   .\scripts\pulse-bot-service.ps1 -Stop
#   .\scripts\pulse-bot-service.ps1 -Restart
#   .\scripts\pulse-bot-service.ps1 -Status
#   .\scripts\pulse-bot-service.ps1 -Uninstall

param(
    [switch]$Install,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$Status,
    [switch]$Uninstall
)

# --- Configuration (EDIT THESE) ---
$BOT_DIR = "C:\Path\To\pulse-bot"                  # Path to pulse-bot repo
$VENV_PYTHON = "$BOT_DIR\.venv\Scripts\python.exe" # Python executable in venv
$VAULT_DIR = "$env:USERPROFILE\my_obsidian"        # Path to Obsidian vault
$LOG_DIR = "$env:LOCALAPPDATA\PulseBot"
$SERVICE_NAME = "PulseBot"

$ENV_VARS = @(
    "PYTHONPATH=$BOT_DIR",
    "VAULT_REPO_DIR=$VAULT_DIR",
    "GIT_REMOTE=origin",
    "GIT_BRANCH=master",
    "LOG_LEVEL=INFO",
    "LOG_FORMAT=json",
    "DEAD_LETTER_PATH=$LOG_DIR\dead_letter.jsonl"
)

# --- Helper functions ---

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "$timestamp [$Status] $Message"
}

function Test-NssmAvailable {
    try {
        $null = Get-Command nssm -ErrorAction Stop
        return $true
    } catch {
        Write-Status "NSSM not found in PATH. Download from https://nssm.cc/download or install via: winget install nssm" "ERROR"
        return $false
    }
}

function Get-ServiceStatus {
    $svc = Get-Service $SERVICE_NAME -ErrorAction SilentlyContinue
    if ($svc) {
        return $svc.Status
    }
    return $null
}

# --- Service management functions ---

function Install-Service {
    if (-not (Test-NssmAvailable)) { return }

    if (Get-ServiceStatus) {
        Write-Status "Service '$SERVICE_NAME' already exists. Uninstall first or use -Restart." "WARN"
        return
    }

    # Validate paths
    if (-not (Test-Path $VENV_PYTHON)) {
        Write-Status "Python not found at $VENV_PYTHON. Run: python -m venv .venv" "ERROR"
        return
    }
    if (-not (Test-Path $BOT_DIR\pulse_bot\bot.py)) {
        Write-Status "bot.py not found at $BOT_DIR\pulse_bot\bot.py" "ERROR"
        return
    }
    if (-not (Test-Path $VAULT_DIR)) {
        Write-Status "Vault not found at $VAULT_DIR" "ERROR"
        return
    }

    # Ensure log directory
    if (-not (Test-Path $LOG_DIR)) {
        New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
    }

    $logFile = "$LOG_DIR\bot-service.log"

    Write-Status "Installing NSSM service '$SERVICE_NAME'..."

    # nssm install
    & nssm install $SERVICE_NAME $VENV_PYTHON "-m pulse_bot.bot"
    & nssm set $SERVICE_NAME AppDirectory $BOT_DIR
    & nssm set $SERVICE_NAME AppStdout $logFile
    & nssm set $SERVICE_NAME AppStderr $logFile
    & nssm set $SERVICE_NAME AppRotateFiles 1
    & nssm set $SERVICE_NAME AppRotateSeconds 86400
    & nssm set $SERVICE_NAME AppEnvironmentExtra $ENV_VARS

    # Auto-restart on crash (Exit code != 0)
    & nssm set $SERVICE_NAME AppExit Default Restart

    Write-Status "Service '$SERVICE_NAME' installed. Run -Start to begin." "OK"
}

function Start-Service {
    if (-not (Test-NssmAvailable)) { return }
    if (Get-ServiceStatus) {
        Write-Status "Starting '$SERVICE_NAME'..."
        & nssm start $SERVICE_NAME
        Write-Status "Service '$SERVICE_NAME' started." "OK"
    } else {
        Write-Status "Service '$SERVICE_NAME' not installed. Run -Install first." "ERROR"
    }
}

function Stop-Service {
    if (-not (Test-NssmAvailable)) { return }
    $status = Get-ServiceStatus
    if ($status) {
        Write-Status "Stopping '$SERVICE_NAME'..."
        & nssm stop $SERVICE_NAME
        Write-Status "Service '$SERVICE_NAME' stopped." "OK"
    } else {
        Write-Status "Service '$SERVICE_NAME' not installed." "WARN"
    }
}

function Restart-Service {
    Stop-Service
    Start-Sleep -Seconds 2
    Start-Service
}

function Show-Status {
    if (-not (Test-NssmAvailable)) { return }
    $status = Get-ServiceStatus
    if ($status) {
        Write-Host "=== Pulse Bot Service Status ==="
        Write-Host "Service: $SERVICE_NAME"
        Write-Host "Status: $status"
        Write-Host ""

        # Show process info from NSSM
        $nssmStatus = & nssm status $SERVICE_NAME 2>&1
        Write-Host "NSSM status: $nssmStatus"

        # Show log file
        $logFile = "$LOG_DIR\bot-service.log"
        if (Test-Path $logFile) {
            Write-Host "`nRecent logs (last 5 lines):"
            Get-Content $logFile -Tail 5 | ForEach-Object { Write-Host "  $_" }
        }
    } else {
        Write-Host "Service '$SERVICE_NAME' is not installed."
    }
}

function Uninstall-Service {
    if (-not (Test-NssmAvailable)) { return }
    $status = Get-ServiceStatus
    if ($status) {
        Write-Status "Stopping '$SERVICE_NAME'..."
        & nssm stop $SERVICE_NAME
        Start-Sleep -Seconds 2
    }
    Write-Status "Removing '$SERVICE_NAME'..."
    & nssm remove $SERVICE_NAME confirm
    Write-Status "Service '$SERVICE_NAME' removed." "OK"
}

# --- Dispatch ---
if ($Install) { Install-Service; return }
if ($Start) { Start-Service; return }
if ($Stop) { Stop-Service; return }
if ($Restart) { Restart-Service; return }
if ($Status) { Show-Status; return }
if ($Uninstall) { Uninstall-Service; return }

# No args = show usage
Write-Host @"
Pulse Bot Service Manager
Usage:
  -Install   Register PulseBot as NSSM service
  -Start     Start the service
  -Stop      Stop the service
  -Restart   Restart the service
  -Status    Show service status and recent logs
  -Uninstall Stop and remove the service

Requires NSSM (https://nssm.cc) in PATH.
"@
