# Pulse Bot

> **Turbopump** 开发辅助机器人 — 用于 Telegram 的消息捕获与项目管理助手。
>
> 在 10 秒内捕获一个想法；之后再整理。

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-73%2F73%20passing-brightgreen.svg)](#测试)
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](#测试)

[**English**](README.md) | [**中文**](README.zh.md)

---

## 它能做什么

**Pulse Bot** 让你通过 Telegram 捕获转瞬即逝的想法，自动将其写入你的 Obsidian 仓库作为 **Pulse Card**（即未加工的碎片化记录，存储在 `00_Inbox/_pulse/` 目录中）。之后在电脑前，你再决定每张卡的命运：升级为完整笔记、归档、或丢弃。

核心理念：**将捕获与整理分离**。大多数笔记系统失败的原因是它们强迫你在记录的同时进行整理。Pulse 将两者解耦，让你可以无摩擦地捕获，稍后再决定哪些值得整理。

## 工作流程

```
[你，在手机上]                 [VPS]                        [Vault git 仓库]
      │                            │                              │
      │  "想做个开源项目"          │                              │
      ├───────────────────────────►│                              │
      │                            │  渲染 Card                   │
      │                            │  写入 00_Inbox/_pulse/       │
      │                            │  git add + commit            │
      │                            ├─────────────────────────────►│
      │  ✓ 已捕获                  │                              │
      │◄───────────────────────────┤                              │
      │                                                              │
      │            [你，在电脑前]                                      │
      │                  │                                           │
      │                  │  git pull                                  │
      │                  │◄──────────────────────────────────────────┤
      │                  │                                           │
      │                  ▼                                           │
      │            在 Obsidian 中打开 Pulse Dashboard                │
      │            （通过 Dataview 查询 _pulse/ 目录）               │
```

**端到端 SLA**：
- 手机 → VPS commit：< 5 秒（通过 Telegram polling）
- VPS → Mac：取决于同步方式。**Windows**：通过 Task Scheduler + `pulse-pull.ps1` 周期 ≤ 5 分钟。**Mac**：手动 `git pull` 即时；通过 cron 时 ≤ 5 分钟。
- Linux VPS 同机：即时（commit + push 同一台机器）。

## 功能特性

- **10 秒捕获**：打开 Telegram → 发送消息 → 完成。
- **自动意图推断**：根据关键词将卡片自动标记为 `idea` / `task` / `question` / `reference`。
- **用户授权**：通过 `allowed_user_ids` 配置白名单。
- **Git 驱动同步**：每张卡片 = 一次提交。完整的 git 历史记录。
- **推送失败重试**：3 次重试，指数退避。
- **systemd 加固**：以非特权用户运行，`ProtectSystem=strict`，`ReadWritePaths` 仅限 vault。
- **73 项测试，90% 覆盖率**：从第一天起就采用 TDD 开发。

## 快速开始

### 1. 在 VPS 上克隆本仓库

```bash
git clone https://github.com/soeasy13142/pulse-bot.git /opt/pulse-bot/app
cd /opt/pulse-bot/app
```

### 2. 安装依赖

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置

```bash
# Bot Token（从 @BotFather 获取）
export TELEGRAM_BOT_TOKEN="<你的-token>"

# Vault 路径（在此处克隆你的 Obsidian 仓库）
export VAULT_REPO_DIR="/opt/pulse-bot/vault"

# 白名单（你的 Telegram 用户 ID — 向 @userinfobot 查询）
cat > /etc/pulse-bot/config.yaml <<EOF
allowed_user_ids:
  - 123456789
EOF
```

### 4. 运行

```bash
python -m pulse_bot.bot
```

生产环境部署请参见 [`docs/deployment.md`](docs/deployment.md) 的 systemd 配置说明。

## 项目结构

```
pulse-bot/
├── __init__.py              # 项目元数据
├── requirements.txt         # Python 依赖
├── pytest.ini               # pytest 配置
├── pulse_bot/               # Python 包（可作为 `pulse_bot` 导入）
│   ├── __init__.py
│   ├── bot.py               # Telegram 监听器 + 命令处理器
│   ├── card.py              # Pulse Card 生成（slug、路径、渲染）
│   ├── config.py            # 配置加载器（环境变量 + YAML）
│   ├── dead_letter.py       # 失败的推送的持久化死信队列
│   ├── git_sync.py          # GitSync 带重试机制
│   └── intent.py            # 意图推断
├── systemd/
│   └── pulse-bot.service    # 带加固的 systemd 单元
├── tests/                   # 69 项测试，90% 覆盖率
│   ├── test_bot.py
│   ├── test_card.py
│   ├── test_config.py
│   ├── test_dead_letter.py
│   ├── test_git_sync.py
│   ├── test_intent.py
│   ├── test_integration.py
│   └── test_smoke_e2e.py    # 离线 E2E 冒烟测试
├── templates/
│   └── dashboards/
│       └── Pulse-Dashboard.md  # 复制到 vault 的 91_System/Dashboards/
├── scripts/
│   ├── pulse-pull.ps1           # Windows 同步脚本（Task Scheduler）
│   └── pulse-pull-task.xml      # Windows Task Scheduler 导出
└── docs/
    ├── setup.md             # VPS 环境搭建
    ├── setup-windows.md     # Windows 同步配置指南
    ├── deployment.md        # 部署手册 + E2E 测试
    ├── runbook.md           # 监控与故障排查
    ├── usage.md             # 用户使用指南
    └── hooks/
        ├── pre-commit       # Pre-commit 钩子模板（阻止 bot 写入 _pulse/ 外的路径）
        └── README.md        # 钩子安装指南
```

## 命令

| 命令 | 说明 |
|---|---|
| `/start` / `/help` | 显示帮助 |
| `/p <text>` | 创建 Pulse Card（或者直接发送纯文本） |
| `/recent [N]` | 列出最近 N 张卡片（默认 10，范围 1–20） |

## 测试

```bash
source .venv/bin/activate
pytest --cov=pulse_bot --cov-report=term-missing tests/
```

预期：所有测试通过，覆盖率 ≥ 80%。顶部徽章显示当前的确切数量。

## 文档

- [用户使用指南](docs/usage.md) — 日常如何使用 Pulse Bot
- [部署手册](docs/deployment.md) — VPS 部署 + E2E 测试步骤
- [运维手册](docs/runbook.md) — 监控、日志、故障排查
- [VPS 环境搭建](docs/setup.md) — 初始环境准备

## 项目来源

Pulse Bot 最初构建于个人 Obsidian 仓库 [soeasy13142/my_obsidian](https://github.com/soeasy13142/my_obsidian)。实现历史通过 `git subtree split` 保留。完整设计背景请参见原始[实施计划](https://github.com/soeasy13142/my_obsidian/blob/master/91_System/94_Plans/2026-07-11_23-15_pulse-system-implementation-plan_nogit.md)。

## 许可

MIT © 2026 Charlie Pan — 参见 [LICENSE](LICENSE)。
