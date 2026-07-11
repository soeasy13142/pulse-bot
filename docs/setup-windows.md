# Pulse Bot Windows Setup

> 本文档描述如何在 Windows 上配置 Pulse Bot 的 vault 自动同步。
> 替代 Mac 上被 sandbox 阻塞的 launchd 方案。

## 前置条件

- Windows 10/11（64 位）
- Git for Windows（下载：https://git-scm.com/download/win）
- Obsidian vault 已克隆到本地（使用 SSH 或 HTTPS）
- Pulse Bot 代码已克隆到本地（如果不需要运行 bot，只需同步脚本）

## 安装步骤

### 1. 修改同步脚本中的 vault 路径

打开 `scripts/pulse-pull.ps1`，找到开头的 `$VAULT_DIR` 变量：

```powershell
$VAULT_DIR = "C:\Users\<你的用户名>\my_obsidian"
```

改为你的实际 vault 路径。

### 2. 手动测试同步

```powershell
cd C:\Path\To\pulse-bot
.\scripts\pulse-pull.ps1
```

期望输出：（示例）
```
pulse-pull: starting
pulse-pull: success
```

如果失败，检查：
- Git 是否安装并加入 PATH
- Vault 路径是否正确
- `git pull` 是否能正常执行（先手动试一次）

### 3. 安装 Task Scheduler 定时任务

```powershell
cd C:\Path\To\pulse-bot
.\scripts\pulse-pull.ps1 -Install
```

这个命令会创建一个名为 `PulseBotSync` 的定时任务，每 5 分钟执行一次同步。

验证安装：
```powershell
Get-ScheduledTask -TaskName PulseBotSync | Format-List
```

### 4. 查看同步日志

```powershell
Get-Content "$env:LOCALAPPDATA\PulseBot\pulse-sync.log" -Tail 10
```

### 5. 卸载定时任务

```powershell
cd C:\Path\To\pulse-bot
.\scripts\pulse-pull.ps1 -Uninstall
```

## 日志说明

| 文件 | 路径 | 说明 |
|------|------|------|
| 同步日志 | `%LOCALAPPDATA%\PulseBot\pulse-sync.log` | 所有同步操作记录 |
| 冲突标记 | `%LOCALAPPDATA%\PulseBot\pulse-sync.CONFLICT` | 仅冲突时创建，存在即表示有冲突待解决 |

## 冲突处理

当 `git pull` 遇到冲突时，脚本会：
1. 写日志：标记 CONFLICT
2. 创建 `pulse-sync.CONFLICT` 标记文件（非空）
3. 不会自动解决冲突（安全优先）

用户操作：
```powershell
# 检测是否有冲突
if (Test-Path "$env:LOCALAPPDATA\PulseBot\pulse-sync.CONFLICT") {
    Write-Host "⚠ Pulse Bot 同步存在冲突，请手动解决！"
    Get-Content "$env:LOCALAPPDATA\PulseBot\pulse-sync.CONFLICT"
}

# 手动解决冲突
cd C:\Path\To\vault
git status  # 查看冲突文件
# 编辑冲突文件 → git add → git commit

# 解决后删除标记文件
Remove-Item "$env:LOCALAPPDATA\PulseBot\pulse-sync.CONFLICT"
```

## 故障排查

### 定时任务不执行

1. 检查 Task Scheduler 状态：
```powershell
Get-ScheduledTask -TaskName PulseBotSync | Get-ScheduledTaskInfo
```

2. 检查上次运行结果：
```powershell
Get-ScheduledTask -TaskName PulseBotSync | Get-ScheduledTaskInfo | Select-Object LastRunTime, LastTaskResult
# LastTaskResult 0 = 成功，非 0 = 失败
```

3. 手动触发测试：
```powershell
Start-ScheduledTask -TaskName PulseBotSync
```

### Git 认证失败

- SSH：检查 `~/.ssh/id_ed25519` 是否存在，ssh-agent 是否运行
- HTTPS：使用 Git Credential Manager（随 Git for Windows 自带）
