# Pulse Bot Windows Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Pulse Bot's primary sync client from Mac to Windows, make Python code run on both Windows and Linux, and support dual deployment (VPS or full Windows).

**Architecture:** Hybrid platform-agnostic approach — same Python code detects platform at runtime. systemd features (sdnotify, WatchdogPinger) are conditionally imported/activated. Windows bot runs as NSSM service. Windows sync uses enhanced Task Scheduler script. VPS path unchanged.

**Tech Stack:** Python 3.11+, python-telegram-bot v20+, NSSM, PowerShell 5.1+, Task Scheduler

## Global Constraints

1. Python 3.11+; python-telegram-bot v20+
2. Test coverage ≥ 80% (existing ~94%)
3. KISS / DRY / YAGNI — no abstraction layer for platform differences
4. Do NOT break existing VPS + systemd deployment path
5. Mac code not deleted — only annotated as deprecated in docs
6. TDD for all Python changes (RED → GREEN → REFACTOR)
7. Type hints required on all new/modified public functions
8. No hardcoded secrets — use env vars or config
9. Commit prefix: `feat(windows):` for feature, `chore:` for deps, `docs:` for docs

---

## File Map

```
Modified files:
  pulse_bot/observability.py     # sdnotify conditional import, _HAS_SDNOTIFY flag
  pulse_bot/lifecycle.py         # register_signal_handlers safe on Windows (catch NotImplementedError)
  pulse_bot/bot.py               # wrap register_signal_handlers + WatchdogPinger for Windows compat
  scripts/pulse-pull.ps1         # Enhanced: log rotation, desktop notifications, -Diagnose, -Info
  tests/test_observability.py    # Test _HAS_SDNOTIFY behavior + Windows-compat paths
  docs/setup-windows.md          # Rewrite: dual-mode (sync-only + full Windows bot)
  docs/deployment.md             # Add "Windows-only deployment" section
  docs/runbook.md                # Add Windows F8/F9/F10 troubleshooting
  README.md                      # Architecture: add dual-mode diagram

Created files:
  requirements-windows.txt       # Windows deps (no sdnotify)
  scripts/pulse-bot-service.ps1  # NSSM service management

Unchanged (need-to-know for context):
  pulse_bot/config.py            # Already cross-platform
  pulse_bot/card.py              # Already cross-platform  
  pulse_bot/git_sync.py          # Already cross-platform
  pulse_bot/dead_letter.py       # Already cross-platform
  pulse_bot/intent.py            # Already cross-platform
  systemd/pulse-bot.service      # VPS path — unchanged
  tests/test_lifecycle.py        # Existing tests pass unchanged
  plans/                         # Historical archives — read-only
```

---

### Task 1: Python Cross-Platform Compatibility

**Files:**
- Modify: `pulse_bot/observability.py:1-10` — conditional sdnotify import
- Modify: `pulse_bot/lifecycle.py:67-74` — signal handler Windows compat
- Modify: `pulse_bot/bot.py:265-275` — guard systemd calls on Windows
- Create: `requirements-windows.txt`
- Modify: `tests/test_observability.py` — add _HAS_SDNOTIFY tests
- Test: `tests/test_observability.py`, `tests/test_lifecycle.py`

**Interfaces:**
- Consumes: Existing `WatchdogPinger.__init__(interval)`, `WatchdogPinger.start()`, `WatchdogPinger.stop()`, `register_signal_handlers(loop, coord)`, `main()`
- Produces: `observability._HAS_SDNOTIFY: bool` module-level flag; `lifecycle.register_signal_handlers` safe on Windows; `bot.main()` runs on Windows

- [ ] **Step 1: Modify observability.py — conditional sdnotify import**

Change line 10 from bare import to guarded import:

```python
# Replace:
import sdnotify

# With:
try:
    import sdnotify
    _HAS_SDNOTIFY = True
except ImportError:
    _HAS_SDNOTIFY = False
```

Add `_HAS_SDNOTIFY` check to `WatchdogPinger.start()`:

```python
def start(self) -> None:
    if not self._enabled or not _HAS_SDNOTIFY:
        if not _HAS_SDNOTIFY:
            logging.getLogger(__name__).info("watchdog disabled (sdnotify not available)")
        elif not self._enabled:
            logging.getLogger(__name__).info("watchdog disabled (NOTIFY_SOCKET not set)")
        return
    self._thread = threading.Thread(target=self._loop, daemon=True, name="watchdog-pinger")
    self._thread.start()
```

- [ ] **Step 2: Modify lifecycle.py — Windows-safe signal handlers**

`loop.add_signal_handler()` raises `NotImplementedError` on Windows. Wrap in try/except:

```python
def register_signal_handlers(
    loop: asyncio.AbstractEventLoop, coord: ShutdownCoordinator
) -> None:
    """Install asyncio-native SIGTERM/SIGINT handlers that request shutdown.

    No-op on platforms that don't support add_signal_handler (e.g., Windows).
    """
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, coord.request_shutdown)
        except NotImplementedError:
            logger.warning("signal handling not supported on this platform")
            return  # one failure → all will fail; stop early
```

- [ ] **Step 3: Modify bot.py — guard WatchdogPinger on Windows**

Change `main()` to handle `_HAS_SDNOTIFY`:

```python
from pulse_bot.observability import setup_logging, WatchdogPinger, _HAS_SDNOTIFY
# Already imported — just add _HAS_SDNOTIFY to the import
```

No structural change needed — `WatchdogPinger` is already guarded by its internal `start()` method. The import line is the only change (adding `_HAS_SDNOTIFY` to the existing import).

Update line 25:
```python
from pulse_bot.observability import setup_logging, WatchdogPinger, _HAS_SDNOTIFY
```

No other changes needed in bot.py — `register_signal_handlers` is now self-guarding, and `WatchdogPinger` self-guards.

- [ ] **Step 4: Create requirements-windows.txt**

```txt
python-telegram-bot>=20.7
python-dotenv>=1.0.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pyyaml>=6.0.1
python-json-logger>=2.0.7
```

- [ ] **Step 5: Write tests for conditional sdnotify import**

```python
# Add to tests/test_observability.py

def test_watchdog_noop_without_sdnotify(monkeypatch):
    """WatchdogPinger.start() is a no-op when _HAS_SDNOTIFY is False."""
    from pulse_bot import observability as obs_mod
    from pulse_bot.observability import WatchdogPinger

    monkeypatch.setattr(obs_mod, "_HAS_SDNOTIFY", False)
    monkeypatch.setenv("NOTIFY_SOCKET", "/tmp/fake.sock")
    pinger = WatchdogPinger(interval=0.05)
    pinger.start()
    # Should not raise; thread should not be created
    assert pinger._thread is None or not pinger._thread.is_alive()
    pinger.stop()


def test_watchdog_uses_sdnotify_when_available(monkeypatch):
    """WatchdogPinger notifies systemd when both NOTIFY_SOCKET and sdnotify are available."""
    from pulse_bot import observability as obs_mod
    from pulse_bot.observability import WatchdogPinger

    monkeypatch.setattr(obs_mod, "_HAS_SDNOTIFY", True)
    fake_notifications: list[str] = []

    class FakeNotifier:
        def notify(self, msg: str) -> None:
            fake_notifications.append(msg)

    monkeypatch.setattr(obs_mod.sdnotify, "SystemdNotifier", lambda: FakeNotifier())
    monkeypatch.setenv("NOTIFY_SOCKET", "/tmp/fake.sock")

    pinger = WatchdogPinger(interval=0.05)
    pinger.start()
    import time
    time.sleep(0.15)
    pinger.stop()

    assert any("WATCHDOG=1" in n for n in fake_notifications)
```

- [ ] **Step 6: Write tests for Windows-safe signal handlers**

```python
# Add to tests/test_lifecycle.py

def test_register_signal_handlers_noop_on_unsupported_platform(monkeypatch):
    """register_signal_handlers does not crash when add_signal_handler raises NotImplementedError."""
    from pulse_bot.lifecycle import ShutdownCoordinator, register_signal_handlers

    coord = ShutdownCoordinator()
    loop = asyncio.new_event_loop()

    def fake_add_signal_handler(sig, handler):
        raise NotImplementedError("signal handling not supported")

    monkeypatch.setattr(loop, "add_signal_handler", fake_add_signal_handler)
    # Should not raise:
    register_signal_handlers(loop, coord)
    loop.close()
```

- [ ] **Step 7: Run full test suite and verify coverage**

```bash
pytest --cov=pulse_bot tests/ -v
```

Expected: All tests pass, coverage ≥ 80%.

- [ ] **Step 8: Commit**

```bash
git add pulse_bot/observability.py pulse_bot/lifecycle.py pulse_bot/bot.py requirements-windows.txt tests/test_observability.py tests/test_lifecycle.py
git commit -m "feat(windows): make Python code cross-platform (sdnotify optional, signal handler safe on Windows)"
```

---

### Task 2: Windows Sync Script Enhancement

**Files:**
- Modify: `scripts/pulse-pull.ps1`

**Interfaces:**
- Consumes: Existing script interface (`-Install`, `-Uninstall`, no args = run)
- Produces: Enhanced script with `-Diagnose`, `-Info`, log rotation, desktop notification on conflict

- [ ] **Step 1: Read current script**

Read `scripts/pulse-pull.ps1` to understand current state (line count, function locations).

- [ ] **Step 2: Add log rotation**

At the top of the sync function, before writing to the log file:

```powershell
# Log rotation: archive if over 1 MB
if (Test-Path $LOG_FILE) {
    $logSize = (Get-Item $LOG_FILE).Length
    if ($logSize -gt 1MB) {
        $archiveFile = "$LOG_DIR\pulse-sync.1.log"
        Move-Item $LOG_FILE $archiveFile -Force
        Write-Host "Log rotated: $archiveFile"
    }
}
```

- [ ] **Step 3: Add desktop notification on conflict**

After detecting a conflict (exit code != 0 from git pull), add native Windows notification:

```powershell
# Desktop notification (non-blocking)
$notification = New-Object System.Windows.Forms.NotifyIcon
$notification.Icon = [System.Drawing.SystemIcons]::Warning
$notification.BalloonTipTitle = "Pulse Bot Sync"
$notification.BalloonTipText = "Git conflict detected in vault — manual review needed"
$notification.Visible = $true
$notification.ShowBalloonTip(5000)
Start-Sleep -Milliseconds 100
$notification.Dispose()
```

Add `Add-Type -AssemblyName System.Windows.Forms` at the top of the script (after existing param block).

Also add an opt-out toggle near the top:

```powershell
$ENABLE_TOAST = $true  # Set to $false to disable desktop notifications
```

Wrap notification block in `if ($ENABLE_TOAST) { ... }`.

- [ ] **Step 4: Add -Diagnose parameter**

Add a new parameter and diagnostic function:

```powershell
param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Diagnose,
    [switch]$Info  # will be Step 5
)
```

```powershell
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
    $drive = (Get-Item $VAULT_DIR).PSDrive.Name + ":"
    $disk = Get-PSDrive -Name (Get-Item $VAULT_DIR).PSDrive.Name
    $freeGB = [math]::Round($disk.Free / 1GB, 1)
    Write-Host "  ✅ $freeGB GB free on $drive"
}
```

Add dispatch:

```powershell
if ($Diagnose) { Invoke-Diagnose; return }
```

- [ ] **Step 5: Add -Info parameter**

```powershell
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
```

- [ ] **Step 6: Verify syntax**

```bash
pwsh -NoProfile -Command "Get-Command scripts/pulse-pull.ps1; & .\scripts\pulse-pull.ps1 -Diagnose"
```

Expected: Script loads without parse errors, `-Diagnose` runs the diagnostic function.

- [ ] **Step 7: Commit**

```bash
git add scripts/pulse-pull.ps1
git commit -m "feat(windows): enhance pulse-pull.ps1 with log rotation, desktop notifications, -Diagnose, -Info"
```

---

### Task 3: Windows Bot Service Script (NSSM)

**Files:**
- Create: `scripts/pulse-bot-service.ps1`

**Interfaces:**
- `-Install`: Register PulseBot as NSSM service
- `-Start`: Start the service
- `-Stop`: Stop the service
- `-Restart`: Restart the service
- `-Status`: Show service status
- `-Uninstall`: Stop + remove service

- [ ] **Step 1: Create the script header and configuration**

```powershell
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
```

- [ ] **Step 2: Write helper functions**

```powershell
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
```

- [ ] **Step 3: Write Install function**

```powershell
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
    
    # Build environment variable string
    $envStr = ""
    foreach ($var in $ENV_VARS) {
        $envStr += " $var"
    }
    
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
```

- [ ] **Step 4: Write Start/Stop/Restart/Status/Uninstall functions**

```powershell
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
```

- [ ] **Step 5: Write dispatch and save file**

```powershell
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
```

- [ ] **Step 6: Verify syntax**

```bash
pwsh -NoProfile -Command "Get-Command scripts/pulse-bot-service.ps1"
```

Expected: No parse errors.

- [ ] **Step 7: Commit**

```bash
git add scripts/pulse-bot-service.ps1
git commit -m "feat(windows): add pulse-bot-service.ps1 — NSSM service management for Windows bot"
```

---

### Task 4: Documentation

**Files:**
- Modify: `docs/setup-windows.md`
- Modify: `docs/deployment.md`
- Modify: `docs/runbook.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: All previous task outputs
- Produces: Complete Windows deployment documentation

#### 4a: `docs/setup-windows.md` — Rewrite for dual-mode

Structure:

```markdown
# Pulse Bot Windows Setup

> Windows 是 v0.1 的主力同步客户端。

## 前置条件
- Windows 10/11, Git for Windows, Python 3.11+
- Obsidian vault 已克隆到本地
- NSSM（仅全栈安装需要）: https://nssm.cc/download

## 安装方式 A：仅同步客户端（VPS + Windows pull）
（现有内容：pulse-pull.ps1 -Install + 配置修改 + Task Scheduler + 日志查看 + 卸载）

## 安装方式 B：全栈 Windows（bot 也跑在 Windows 上）
先完成方式 A 的同步配置，再：
1. 创建 Python 虚拟环境 + 安装依赖（requirements-windows.txt）
2. 配置环境变量（.env）
3. 注册 NSSM 服务：`scripts/pulse-bot-service.ps1 -Install`
4. 启动服务：`scripts/pulse-bot-service.ps1 -Start`
5. 验证：发 Telegram 消息 → 检查服务日志 → 检查 vault 文件
6. 开机自启：NSSM 注册时自动设为 Auto Start

## 故障排查
（常见问题表 + 诊断命令）

## 卸载
（Task Scheduler 卸载 + NSSM 卸载）
```

- [ ] **Step 1: Rewrite `docs/setup-windows.md`**

Write new content following the structure above. Keep existing sync-only section (Approach A), add new Approach B (full Windows) section.

- [ ] **Step 2: Add Windows chapter to `docs/deployment.md`**

Insert after existing VPS deployment steps:

```markdown
## Windows-only 部署

pulse-bot 可以完全跑在 Windows 上，无需 VPS。
（步骤：克隆仓库 → venv → pip install requirements-windows.txt → 配置 .env → NSSM 注册 → 启动）
```

- [ ] **Step 3: Add Windows troubleshooting to `docs/runbook.md`**

Append to existing troubleshooting sections:

```markdown
### F8: NSSM 服务未运行
**症状**：bot 不响应消息；`scripts/pulse-bot-service.ps1 -Status` 显示 Stopped。
**排查**：（检查日志、重启服务、检查 .env 配置）

### F9: 桌面通知不弹出
**症状**：同步冲突时没有 Toast 通知。
**原因**：Task Scheduler 运行时不在用户会话中（通知需要交互式会话）。
**解决**：这是预期行为。冲突仍以 CONFLICT 标记文件为依据，通知仅作为辅助。

### F10: Windows 端 Git 认证失败
**症状**：同步日志显示 "ERROR: git pull" 或认证提示。
**解决**：（Git Credential Manager、SSH key、HTTPS 三种方案说明）
```

- [ ] **Step 4: Update README.md architecture diagram**

Current diagram shows `[You, at desk]` (platform-agnostic). Add a note below:

```markdown
**Two deployment modes:**
- **VPS + Windows**: Bot runs on VPS under systemd; Windows syncs via Task Scheduler every 5 min
- **All-on-Windows**: Bot runs as NSSM service on Windows; vault updated in real-time
```

- [ ] **Step 5: Commit**

```bash
git add docs/setup-windows.md docs/deployment.md docs/runbook.md README.md
git commit -m "docs(windows): update docs for dual-mode deployment (VPS or full Windows)"
```

---

## Verification Plan

After all tasks are complete:

```bash
# 1. Full test suite (Python)
pytest --cov=pulse_bot tests/ -v
# Expected: all pass, coverage >= 80%

# 2. Script syntax check
pwsh -NoProfile -Command "Get-Command scripts/pulse-pull.ps1"
pwsh -NoProfile -Command "Get-Command scripts/pulse-bot-service.ps1"
# Expected: no parse errors

# 3. VPS path regression
# (Manual) Deploy on Linux, verify bot starts and processes messages normally

# 4. Manual Windows smoke test
# Install NSSM → register service → send Telegram message → verify Pulse Card created
```

## Rollback Plan

| Scenario | Rollback |
|----------|----------|
| Python code breaks VPS | `git revert` the Python compat commit; re-deploy |
| Script syntax error | Fix and recommit |
| Docs wrong | `git revert` the docs commit |
| NSSM service broken | `scripts/pulse-bot-service.ps1 -Uninstall` → fix → reinstall |
