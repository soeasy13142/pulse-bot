# Pulse Bot Windows Setup

> Windows 是 v0.1 的主力同步客户端。

本指南提供两种 Windows 部署模式。选择适合你的方案：

| 模式 | 适用场景 | 依赖 |
|------|---------|------|
| **A：仅同步客户端** | Bot 跑在 VPS 上；Windows 只负责从 git remote pull | 无（仅需 Git for Windows） |
| **B：全栈 Windows** | Bot 直接跑在 Windows 上，无需 VPS | NSSM + Python 3.11+ |

---

## 前置条件

- Windows 10/11（64 位）
- Git for Windows（下载：https://git-scm.com/download/win）
- Python 3.11+（仅全栈安装需要，下载：https://www.python.org/downloads/）
- Obsidian vault 已克隆到本地（使用 SSH 或 HTTPS）
- Pulse Bot 代码已克隆到本地
- NSSM（仅全栈安装需要）：https://nssm.cc/download（或 `winget install nssm`）

---

## 安装方式 A：仅同步客户端（VPS + Windows pull）

如果你在 VPS 上运行 pulse-bot，Windows 只需要定时 `git pull` 来获取 Pulse Card。

### A1. 修改同步脚本中的 vault 路径

打开 `scripts/pulse-pull.ps1`，找到开头的 `$VAULT_DIR` 变量：

```powershell
$VAULT_DIR = "C:\Users\<你的用户名>\my_obsidian"
```

改为你的实际 vault 路径。

### A2. 手动测试同步

```powershell
cd C:\Path\To\pulse-bot
.\scripts\pulse-pull.ps1
```

期望输出：
```
pulse-pull: starting
pulse-pull: success
```

如果失败，检查：
- Git 是否安装并加入 PATH
- Vault 路径是否正确
- `git pull` 是否能正常执行（先手动试一次）

### A3. 安装 Task Scheduler 定时任务

**方法 A3a：用脚本一键安装（推荐）**

```powershell
cd C:\Path\To\pulse-bot
.\scripts\pulse-pull.ps1 -Install
```

这个命令会创建一个名为 `PulseBotSync` 的定时任务，每 5 分钟执行一次同步。

验证安装：
```powershell
Get-ScheduledTask -TaskName PulseBotSync | Format-List
```

**方法 A3b：手动导入 XML（高级）**

仓库提供了 `scripts/pulse-pull-task.xml`，里面硬编码的路径是占位符 `C:\Path\To\...\pulse-pull.ps1`，需要先替换再导入：

1. 编辑 `scripts/pulse-pull-task.xml`，把 `<Arguments>` 和 `<WorkingDirectory>` 改成你的实际路径
2. 打开「任务计划程序」 → 「导入任务」 → 选 `pulse-pull-task.xml`
3. 验证：右侧栏应看到 `PulseBotSync`

### A4. 查看同步日志

```powershell
Get-Content "$env:LOCALAPPDATA\PulseBot\pulse-sync.log" -Tail 10
```

---

## 安装方式 B：全栈 Windows（bot 也跑在 Windows 上）

先完成 [方式 A](#-安装方式-a仅同步客户端vps--windows-pull) 的同步配置（A1-A4），再继续以下步骤。

### B1. 创建 Python 虚拟环境 + 安装依赖

```powershell
cd C:\Path\To\pulse-bot
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### B2. 配置环境变量

复制 `.env.example` 并填入你的配置：

```powershell
cd C:\Path\To\pulse-bot
copy pulse_bot\.env.example .env
notepad .env
```

填入：
```
TELEGRAM_BOT_TOKEN=<your-token-from-botfather>
VAULT_REPO_DIR=C:\Users\<你的用户名>\my_obsidian
GIT_REMOTE=origin
GIT_BRANCH=master
LOG_LEVEL=INFO
DEAD_LETTER_PATH=%LOCALAPPDATA%\PulseBot\dead_letter.jsonl
```

> 注意：Windows 用 `%LOCALAPPDATA%`，bot 会自动展开。也可以在 `.env` 写绝对路径。

### B3. 编辑服务脚本配置

打开 `scripts\pulse-bot-service.ps1`，修改开头的配置：

```powershell
$BOT_DIR = "C:\Path\To\pulse-bot"                  # 改为你的 pulse-bot 仓库路径
$VENV_PYTHON = "$BOT_DIR\.venv\Scripts\python.exe"
$VAULT_DIR = "$env:USERPROFILE\my_obsidian"        # 改为你的 vault 路径
```

### B4. 注册 NSSM 服务

```powershell
cd C:\Path\To\pulse-bot
.\scripts\pulse-bot-service.ps1 -Install
```

期望输出：
```
Service 'PulseBot' installed. Run -Start to begin.
```

注册时 NSSM 自动设为 **Auto Start**（开机自启）。

### B5. 启动服务

```powershell
.\scripts\pulse-bot-service.ps1 -Start
```

验证服务状态：
```powershell
.\scripts\pulse-bot-service.ps1 -Status
```

期望：状态显示 `Running`，且日志中无错误。

### B6. 验证端到端流程

1. 打开 Telegram，找到你的 bot
2. 发送：`/start`
   - 期望：bot 回显帮助文本
3. 发送：`测试全栈 Windows 部署`
   - 期望：bot 回显 `✓ Captured: 测试全栈 Windows 部署`
4. 检查 vault 目录：
   ```powershell
   Get-ChildItem "$env:USERPROFILE\my_obsidian\00_Inbox\_pulse\" | Select-Object -Last 5
   ```
5. 检查冲突标记：
   ```powershell
   .\scripts\pulse-pull.ps1 -Info
   ```

### B7. 服务管理命令

| 操作 | 命令 |
|------|------|
| 查看状态 | `.\scripts\pulse-bot-service.ps1 -Status` |
| 停止服务 | `.\scripts\pulse-bot-service.ps1 -Stop` |
| 重启服务 | `.\scripts\pulse-bot-service.ps1 -Restart` |
| 查看服务日志 | `Get-Content "$env:LOCALAPPDATA\PulseBot\bot-service.log" -Tail 20` |
| 诊断 | `.\scripts\pulse-pull.ps1 -Diagnose`（检查 Git、NSSM、磁盘等） |
| 信息摘要 | `.\scripts\pulse-pull.ps1 -Info` |

---

## 日志说明

| 文件 | 路径 | 说明 |
|------|------|------|
| 同步日志 | `%LOCALAPPDATA%\PulseBot\pulse-sync.log` | 所有 `git pull` 操作记录 |
| 服务日志 | `%LOCALAPPDATA%\PulseBot\bot-service.log` | Bot 服务（NSSM）的标准输出和错误 |
| 冲突标记 | `%LOCALAPPDATA%\PulseBot\pulse-sync.CONFLICT` | 仅冲突时创建，存在即表示有冲突待解决 |
| 死信队列 | `%LOCALAPPDATA%\PulseBot\dead_letter.jsonl` | Push 失败的消息记录 |

---

## 故障排查

### 常见问题

| 症状 | 原因 | 解决 |
|------|------|------|
| `-Diagnose` 显示 Git 未找到 | Git for Windows 未安装或不在 PATH | 安装 Git，重启终端 |
| 同步日志报 "CONFLICT" | Git pull 发生冲突 | 手动解决后删除冲突标记文件 |
| Task Scheduler 不执行 | 任务被禁用或上次运行失败 | `Get-ScheduledTaskInfo` 查看上次运行结果 |
| NSSM 服务启动失败 | .env 配置错误或路径不对 | 运行 `-Status` 查看日志；重新检查 `.env` |
| Bot 不响应消息 | Token 无效或白名单未配置 | 验证 `TELEGRAM_BOT_TOKEN` 和 `allowed_user_ids` |
| 推送失败 | Git 认证失败 | 运行 `-Diagnose` 检查 remote 连通性 |

### 诊断命令

```powershell
# 一键诊断（Git、NSSM、磁盘、远程连通性）
.\scripts\pulse-pull.ps1 -Diagnose

# 查看服务日志
Get-Content "$env:LOCALAPPDATA\PulseBot\bot-service.log" -Tail 20

# 查看同步日志
Get-Content "$env:LOCALAPPDATA\PulseBot\pulse-sync.log" -Tail 20
```

### 桌面通知

同步冲突时 `pulse-pull.ps1` 会弹出 Windows Toast 通知。如果没有弹出，检查：
- Task Scheduler 是否配置为"允许与桌面交互"
- 系统通知中心是否开启了 Pulse Bot 的通知权限

> 注意：如果 Task Scheduler 以 `SYSTEM` 账号运行，桌面通知可能无法弹出。这是预期行为——冲突仍以 CONFLICT 标记文件为依据，通知仅作为辅助。

---

## 卸载

### 卸载同步任务

```powershell
cd C:\Path\To\pulse-bot
.\scripts\pulse-pull.ps1 -Uninstall
```

### 卸载 NSSM 服务

```powershell
cd C:\Path\To\pulse-bot
.\scripts\pulse-bot-service.ps1 -Uninstall
```

### 清理残留文件

```powershell
Remove-Item "$env:LOCALAPPDATA\PulseBot" -Recurse -Force
```
