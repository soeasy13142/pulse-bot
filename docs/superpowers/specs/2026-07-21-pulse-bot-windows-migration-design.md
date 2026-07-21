---
tags:
  - pulse
  - design-spec
  - windows-migration
created: 2026-07-21
updated: 2026-07-21
status: draft
source: "设计文档 — Pulse Bot Mac→Windows 迁移"
---

# Pulse Bot Windows Migration — Design Spec

> **目的**：将 Pulse Bot 的主力同步客户端从 Mac 迁移到 Windows，并让 bot 本身可以选择在 Windows 或 VPS 上运行。
> **状态**：draft（待用户复核）
> **范围**：Python 代码平台兼容、Windows 服务化（NSSM）、同步脚本增强、文档更新

## 1. 背景

### 1.1 问题

Pulse Bot 原设计是 VPS 跑 bot + Mac 做同步客户端（launchd 每 5 分钟 git pull）。Mac launchd 因 macOS `~/Downloads/` sandbox 路径限制无法加载（EPERM 126），即使已授权 Full Disk Access 仍然失败。此问题已验证为 sandbox/Downloads provenance 限制，不是脚本错误。

### 1.2 决策

- **主力同步客户端**：Mac → Windows（Windows 无 sandbox 限制）
- **Bot 运行方式**：用户自由选择 VPS（现有 systemd）或 Windows（NSSM）
- **Mac**：不再提供自动同步脚本，用户需手动 `git pull`

### 1.3 约束

- Python 3.11+，python-telegram-bot v20+
- KISS / DRY / YAGNI：不引入不必要的抽象层
- 测试覆盖率 ≥ 80%
- 不破坏现有 VPS 部署路径
- Mac 代码不删除，只标注弃用

## 2. 架构

### 2.1 双模式部署

```
模式 A: VPS 跑 bot + Windows 客户端同步
────────────────────────────────────────
手机 → Telegram → [VPS: systemd pulse-bot]
                    → render Pulse Card → git commit + push
                                               ↓
                    Windows: Task Scheduler 每 5min git pull
                    → Obsidian Pulse Dashboard 显示

模式 B: 全跑在 Windows
────────────────────────────────────────
手机 → Telegram → [Windows: NSSM pulse-bot service]
                    → render Pulse Card → 写入本地 vault
                    → git commit + push (可选)
                    → Obsidian 实时显示
```

### 2.2 模块结构（改动后）

```
pulse_bot/
├── bot.py              # 无改动 — 通过 import 间接用 lifecycle/observability
├── lifecycle.py        # 信号处理兼容 Windows（条件注册 SIGHUP）
├── observability.py    # sdnotify 条件导入，Windows 上 WatchdogPinger 为 no-op
├── config.py           # 无改动
├── card.py             # 无改动
├── git_sync.py         # 无改动
├── dead_letter.py      # 无改动
├── intent.py           # 无改动
└── __init__.py         # 无改动

requirements/
├── requirements.txt          # 完整依赖（含 sdnotify，用于 VPS）
└── requirements-windows.txt  # Windows 依赖（不含 sdnotify）

scripts/
├── pulse-pull.ps1            # 增强：日志轮转 + 原生通知 + -Diagnose
└── pulse-bot-service.ps1     # 新增：NSSM 服务管理

systemd/
└── pulse-bot.service         # 不变
```

## 3. Python 代码改动

### 3.1 `observability.py` — sdnotify 条件导入

**改动**：`import sdnotify` 改为 try/except 保护，新增模块级标记 `_HAS_SDNOTIFY`。

```python
try:
    import sdnotify
    _HAS_SDNOTIFY = True
except ImportError:
    _HAS_SDNOTIFY = False
```

**WatchdogPinger 启动逻辑**：

```python
class WatchdogPinger:
    def start(self) -> None:
        if not _HAS_SDNOTIFY:
            self._enabled = False
            return
        # 原有逻辑不变...
```

WatchdogPinger 已有 `NOTIFY_SOCKET` 检测（无 systemd 环境自动降级），加 `_HAS_SDNOTIFY` 防止 Windows 上 ImportError。

### 3.2 `lifecycle.py` — 信号处理兼容

**改动**：`SIGHUP` 改为条件注册（Windows 无此信号）。

```python
# 当前
for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    loop.add_signal_handler(sig, handler)

# 改为
for sig in (signal.SIGTERM, signal.SIGINT):
    if hasattr(signal, "SIGHUP"):
        loop.add_signal_handler(sig, handler)
```

`signal.SIGHUP` 在 Windows 上不存在，`hasattr` 返回 False 自动跳过。

### 3.3 `requirements.txt` — 拆分

**当前**：单文件 `requirements.txt`，含 `sdnotify>=0.1.1`。

**改为**：

- `requirements.txt`：完整依赖（VPS systemd 环境），不动
- `requirements-windows.txt`：不含 `sdnotify`，其余一致

```txt
# requirements-windows.txt
python-telegram-bot>=20.7
python-dotenv>=1.0.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pyyaml>=6.0.1
python-json-logger>=2.0.7
```

> sdnotify 依赖 Linux systemd 的 socket 接口，pip install 在 Windows 上会报编译错误。Windows 用户安装 `requirements-windows.txt` 即可。

### 3.4 `bot.py` — 无改动理由

`bot.py` 通过 `from pulse_bot.observability import WatchdogPinger` 和 `from pulse_bot.lifecycle import ShutdownCoordinator` 使用这两个模块。由于 observability 和 lifecycle 的兼容性改动都在内部完成，`bot.py` 外部行为不变，无需修改。

## 4. Windows Bot 服务化（NSSM）

### 4.1 NSSM 简介

NSSM（Non-Sucking Service Manager）是一个轻量级 Windows 服务管理器，将任意命令行程序注册为 Windows 服务。单个 `nssm.exe`，无需安装，放在 PATH 即可。

- 官网：https://nssm.cc
- 安装方式：`winget install nssm` 或下载 nssm.exe 放在 PATH

### 4.2 脚本：`scripts/pulse-bot-service.ps1`

新增脚本，管理 Pulse Bot 在 Windows 上的服务生命周期。

**命令接口**：

| 参数 | 作用 |
|------|------|
| `-Install` | 注册 NSSM 服务 PulseBot，配置 python 路径、环境变量、日志路径 |
| `-Start` | 启动服务 |
| `-Stop` | 停止服务 |
| `-Restart` | 重启服务 |
| `-Status` | 查询服务状态 |
| `-Uninstall` | 停止并移除服务 |

**Install 注册参数**：

| NSSM 参数 | 值 |
|-----------|-----|
| `Application` | `C:\full\path\to\.venv\Scripts\python.exe` |
| `AppParameters` | `-m pulse_bot.bot` |
| `AppDirectory` | `C:\full\path\to\vault` |
| `AppEnvironmentExtra` | `PYTHONPATH`、`TELEGRAM_BOT_TOKEN`、`VAULT_REPO_DIR`、`DEAD_LETTER_PATH`、`LOG_FORMAT`、`LOG_LEVEL` |
| `AppStdout` | `%LOCALAPPDATA%\PulseBot\bot-service.log` |
| `AppStderr` | `%LOCALAPPDATA%\PulseBot\bot-service.log` |
| `AppRotateFiles` | 1（启用日志轮转） |
| `AppRotateSeconds` | 86400（每天轮转） |

**NSSM 检测**：脚本在 Install 前检查 `Get-Command nssm -ErrorAction SilentlyContinue`，未找到则提示用户安装。

### 4.3 与 systemd 的对比

| 能力 | systemd (VPS) | NSSM (Windows) |
|------|--------------|----------------|
| 自动重启 | Restart=on-failure | AppExit=Restart |
| 日志管理 | journald | AppRotateFiles + 自定义滚轮 |
| 看门狗 | WatchdogSec=30 + sdnotify | 无等价物（WatchdogPinger 在 Windows 上为 no-op） |
| 环境变量 | EnvironmentFile | AppEnvironmentExtra |
| 开机自启 | systemctl enable | nssm install 注册为 SCM 服务 |

## 5. Windows 同步脚本增强

### 5.1 现有脚本 `pulse-pull.ps1` 能力

- git pull --rebase --autostash
- 冲突检测 + CONFLICT 标记文件
- Task Scheduler 自安装（`-Install` / `-Uninstall`）

### 5.2 增强项

| 增强 | 实现方式 |
|------|---------|
| **日志轮转** | 脚本启动时检查日志文件大小，超过 1 MB 自动重命名为 `.1.log`，新建空日志 |
| **日志级别** | 增加 `-Verbose` 参数输出详细日志（git 命令输出），默认只输出概要 |
| **桌面通知** | 冲突时弹出 Windows 原生气泡通知（NotifyIcon → ShowBalloonTip），标题 `"Pulse Bot Sync"`，内容 `"⚠ Git 同步冲突，需要手动处理"` |
| **一键诊断** | `-Diagnose` 参数：检测 git remote 可通性、NSSM 服务状态、日志摘要、vault 目录存在性、磁盘空间 |
| **信息摘要** | `-Info` 参数：显示最近 N 条同步记录、最后一次成功/失败时间、当前积压卡片数 |

### 5.3 桌面通知注意事项

- 原生 NotifyIcon 仅在 Windows 10/11 上完全支持
- 通知只在交互式用户会话中可见（Task Scheduler 运行时不可见），因此通知设计为**额外辅助**，不依赖通知判断同步状态
- 用户可在脚本中通过 `$ENABLE_TOAST = $false` 关闭通知

## 6. 文档更新

### 6.1 `docs/setup-windows.md`

重写为完整的 Windows 部署指南，包含：

1. **前置条件**：Python 3.11+、Git、vault clone、NSSM
2. **安装方式 A：仅同步客户端**（VPS + Windows pull）→ 现有 `pulse-pull.ps1 -Install`
3. **安装方式 B：全栈 Windows**（bot 也跑在 Windows 上）→ `pulse-bot-service.ps1 -Install`
4. **验证**：发测试消息 → 检查服务日志 → 检查 vault 文件
5. **故障排查**：常见问题表
6. **卸载**

### 6.2 `docs/deployment.md`

保持 VPS 部署章节不动，新增 **"Windows-only 部署"** 独立章节，与 VPS 章节并列。

### 6.3 `docs/runbook.md`

新增 Windows 环境故障排查：

- F8: NSSM 服务未运行
- F9: 同步脚本桌面通知不弹出
- F10: Windows 端 Git 认证失败

### 6.4 架构图（README / CLAUDE.md）

README 架构图改为双模式示意（VPS + Windows 并列），不增加复杂度。

### 6.5 保留的 Mac 引用

以下引用**有意保留**（说明过渡历史）：

- `docs/usage.md`："Mac 用户请手动 git pull"
- `docs/runbook.md`："原 Mac launchd 因 sandbox 限制 deferred"
- `docs/deployment.md`："Mac 用户请手动 git pull"
- `CONTRIBUTING.md`："Mac launchd 方案因 macOS sandbox 限制 deferred"

## 7. 测试策略

| 测试类型 | 范围 | 执行方式 |
|---------|------|---------|
| 单元测试 | observability.py 的 `_HAS_SDNOTIFY` 逻辑（mock ImportError） | pytest |
| 单元测试 | lifecycle.py 信号注册兼容性（mock `hasattr`） | pytest |
| 集成测试 | Windows 脚本语法正确性（PSParse） | `pwsh -Command "Get-Command scripts/pulse-pull.ps1; Get-Command scripts/pulse-bot-service.ps1"` |
| 手动测试 | Windows bot 启动/停止/重启 | 操作验证 |
| 手动测试 | NSSM 服务注册/日志轮转 | 操作验证 |
| 回归测试 | VPS 路径不受影响（全部现有 pytest） | `pytest --cov=pulse_bot tests/` |

### 7.1 覆盖率要求

- 整体覆盖率 ≥ 80%
- 新增代码覆盖率 ≥ 90%（现有模块不改动不要求新增行覆盖）

## 8. 回滚方案

| 组件 | 回滚方式 |
|------|---------|
| Python 代码 | `git revert` 相关 commit |
| NSSM 服务 | `scripts/pulse-bot-service.ps1 -Uninstall` |
| Task Scheduler | `scripts/pulse-pull.ps1 -Uninstall` |
| 文档 | `git revert` 相关 commit |

## 9. 风险点

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Windows 上 Python asyncio 信号处理不完整 | 中 | 中 | `lifecycle.py` 已用 `hasattr` 保护；Windows 用 Task Scheduler/NSSM 重启替代信号处理 |
| NSSM 的 AppExit 不如 systemd Restart= 可靠 | 低 | 中 | 配合 Task Scheduler 定期检查服务状态作为二次保障（Option，不内置） |
| 桌面通知在 Task Scheduler 无用户会话时静默 | 高 | 低 | 通知是辅助手段，主要靠日志和 CONFLICT 标记文件 |
| Windows 上 git pull 需要 SSH 或 HTTPS 认证 | 中 | 低 | setup-windows.md 已有 Git Credential Manager 指引 |
