---
tags:
  - plan
  - pulse
  - implementation
created: 2026-07-09
updated: 2026-07-11
status: done
source: "[[2026-07-09_22-30_pulse-system-design_ec7217b]]"
topic: "Pulse System 实施计划"
---

# Pulse System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于已落地的设计 spec，构建一个由 Telegram bot 驱动的 Obsidian 碎片想法捕获系统，让用户在 10 秒内把任何灵感写入 vault，所有规范化延后到 promote 时刻。

**Architecture:** 6 个 milestone（M1 本地基础设施 → M6 文档沉淀）。Telegram bot 在云 VPS 运行，消息自动 commit 到 vault git remote；Mac 端 launchd 每 5 分钟 `git pull` 同步；Obsidian 内嵌 Pulse Dashboard 用 Dataview 列出所有未 promote 的卡片；`/promote` 命令触发完整规范化流程（生成 Plan + 创建正式笔记 + 归档原卡片）。

**Tech Stack:**
- Python 3.11+（pulse-bot 服务）
- `python-telegram-bot` v20+（Telegram SDK）
- pytest + pytest-telegram-bot（测试）
- systemd（VPS 守护）
- launchd（Mac 守护）
- git（同步机制）
- Dataview（Obsidian 内查询）

**Spec Reference:** `91_System/94_Plans/2026-07-09_22-30_pulse-system-design_ec7217b.md`

---

## Global Constraints

从 spec 中提炼的项目级约束（每条任务都隐含遵守）：

1. **vault 命名规范**：新文件遵循 v1 规范；`_pulse/` 目录属"自由命名"类别（CLAUDE.md §File Naming Convention）
2. **frontmatter 必填**：`tags`、`created`、`updated`、`status`、`source`
3. **Commit 频率**：每类改动一个 commit，不批量
4. **Commit message 格式**：`<type>: <description>`（CLAUDE.md §Git Workflow）
5. **测试覆盖率**：≥ 80%（CLAUDE.md §Testing）
6. **Pre-commit hook**：commit 前自动检查 broken wikilinks（已部署在 `.git/hooks/pre-commit`）
7. **Plan-First**：任何稍复杂任务先写计划（CLAUDE.md §Plan-First Principle）
8. **决策权在用户**：agent 不替用户决定分类、归档（CLAUDE.md §Communication Principles）
9. **安全**：bot 仅响应白名单 user_id；仅能写 `_pulse/` 路径
10. **Git 同步**：所有 Pulse Card 通过 git push/pull 同步，单条想法 = 单个 commit

---

## 文件结构

实施前要新建/修改的所有文件，按里程碑分组：

### 新增文件

```
00_Inbox/_pulse/.gitkeep                              # M1
91_System/91_Templates/pulse-card.md                  # M6
91_System/Dashboards/Pulse-Dashboard.md               # M1
91_System/93_Scripts/pulse-pull.sh                    # M2
91_System/93_Scripts/pulse-pull.plist                 # M2
91_System/93_Scripts/pulse-bot/__init__.py            # M4
91_System/93_Scripts/pulse-bot/bot.py                 # M4
91_System/93_Scripts/pulse-bot/card.py                # M4
91_System/93_Scripts/pulse-bot/git_sync.py            # M4
91_System/93_Scripts/pulse-bot/intent.py              # M4
91_System/93_Scripts/pulse-bot/config.py              # M4
91_System/93_Scripts/pulse-bot/requirements.txt       # M4
91_System/93_Scripts/pulse-bot/systemd/pulse-bot.service  # M4
91_System/93_Scripts/pulse-bot/tests/__init__.py      # M4
91_System/93_Scripts/pulse-bot/tests/test_card.py     # M4
91_System/93_Scripts/pulse-bot/tests/test_intent.py   # M4
91_System/93_Scripts/pulse-bot/tests/test_git_sync.py # M4
91_System/93_Scripts/pulse-bot/tests/test_bot.py      # M4
91_System/93_Scripts/pulse-bot/tests/test_integration.py  # M4
91_System/93_Scripts/pulse-bot/docs/setup.md          # M3
91_System/93_Scripts/pulse-bot/docs/deployment.md     # M5
91_System/93_Scripts/pulse-bot/docs/runbook.md        # M5
```

### 修改文件

```
91_System/CURRENT.md         # M1 加入 Pulse 章节；M6 标记上线
CLAUDE.md                    # M6 加入 Pulse System 段落
91_System/README.md          # M6 加入架构描述
```

### 测试文件

所有 `tests/test_*.py` 都用 pytest。集成测试在 tmp git repo 中跑。

---

## Task 编号约定

- **M1-T1.1** = Milestone 1, Task 1.1
- 每个 Task 是一个独立 commit 单元
- 每个 Task 内含 2-5 分钟的 Step
- Step 编号 T1.1.1, T1.1.2 ...

---

# Milestone 1：本地基础设施

> ✅ **完成**（2026-07-09，3 commits: e4bc9ba / 9106f95 / e820118）
> **目标**：创建 `_pulse/` 目录、Card 模板、Dashboard，不依赖任何外部服务。
> **commit 聚合**：M1 完成后一个聚合 commit（多个原子 commit 可独立回退）。

---

## Task M1-T1：创建 `_pulse/` 目录

> ✅ **完成**：commit `e4bc9ba` (2026-07-09)

**Files:**
- Create: `00_Inbox/_pulse/.gitkeep`

**Interfaces:** 无（纯目录创建）

- [x] **Step 1：创建目录**

```bash
mkdir -p /Users/charliepan/Downloads/my_obsidian/00_Inbox/_pulse
touch /Users/charliepan/Downloads/my_obsidian/00_Inbox/_pulse/.gitkeep
```

- [x] **Step 2：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 00_Inbox/_pulse/.gitkeep
git commit -m "chore(vault): scaffold _pulse/ directory for fragment capture"
```

---

## Task M1-T2：创建 Pulse Dashboard

> ✅ **完成**：commit `9106f95` (2026-07-09)

**Files:**
- Create: `91_System/Dashboards/Pulse-Dashboard.md`

**Interfaces:** 无

- [x] **Step 1：创建 Dashboards 目录**

```bash
mkdir -p /Users/charliepan/Downloads/my_obsidian/91_System/Dashboards
```

- [x] **Step 2：写 Dashboard 文件**

```markdown
---
tags:
  - dashboard
  - pulse
created: 2026-07-09
updated: 2026-07-09
status: done
source: "[[2026-07-09_22-30_pulse-system-design_ec7217b]]"
type: dashboard
---

# 💡 Pulse Dashboard

> 所有未 promote 的碎片想法。重访这里就能找回上下文。

## 🔥 最近 7 天

\`\`\`dataview
TABLE created, intent, tags
FROM "00_Inbox/_pulse"
WHERE status = "pulse" AND created >= date(today) - dur(7 days)
SORT created DESC
LIMIT 20
\`\`\`

## 📦 全部待处理

\`\`\`dataview
LIST
FROM "00_Inbox/_pulse"
WHERE status = "pulse"
SORT created DESC
\`\`\`

## ⏰ 超过 30 天未处理（建议降级或归档）

\`\`\`dataview
LIST
FROM "00_Inbox/_pulse"
WHERE status = "pulse" AND created <= date(today) - dur(30 days)
\`\`\`
```

写文件：

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/Dashboards/Pulse-Dashboard.md <<'EOF'
...（上面内容原样写入）...
EOF
```

- [x] **Step 3：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/Dashboards/Pulse-Dashboard.md
git commit -m "feat(vault): add Pulse Dashboard with Dataview queries"
```

---

## Task M1-T3：更新 CURRENT.md 加入 Pulse 章节

> ✅ **完成**：commit `e820118` (2026-07-09)

**Files:**
- Modify: `91_System/CURRENT.md`

**Interfaces:** 无

- [x] **Step 1：在 CURRENT.md 的"活跃计划"表格下方加 Pulse 章节**

找到 "活跃计划" 表格，表格下方插入：

```markdown
## 💡 Pulse 系统状态

| 阶段 | 状态 | 备注 |
|------|------|------|
| 设计 spec | ✅ done | [[2026-07-09_22-30_pulse-system-design_ec7217b]] |
| 实施计划 | 🚧 in-progress | [[2026-07-09_22-45_pulse-system-implementation-plan]] |
| 本地基础设施 (M1) | ⏳ pending | _pulse/ + Dashboard |
| 本地同步 (M2) | ⏳ pending | launchd pull job |
| VPS 准备 (M3) | ⏳ pending | 部署环境文档 |
| Bot 服务 (M4) | ⏳ pending | Python 包 |
| 部署 + E2E (M5) | ⏳ pending | 实跑 Telegram → vault |
| 文档沉淀 (M6) | ⏳ pending | CLAUDE.md 集成 |

> 所有 Pulse 相关文件 → `91_System/94_Plans/` (含 spec/plan)
> Pulse Card 存放点 → `00_Inbox/_pulse/`
> Dashboard → [[91_System/Dashboards/Pulse-Dashboard|Pulse Dashboard]]
```

- [x] **Step 2：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/CURRENT.md
git commit -m "docs(vault): add Pulse system status section to CURRENT.md"
```

---

# Milestone 2：本地同步脚本（Mac launchd）

> 🚧 **部分完成**（2026-07-09，2 commits: 70d3bbb / 9a45664）
> **T2 状态**：plist 已 commit，launchd 未加载（macOS Downloads/ 限制，见 M2-T2 注释）
> **目标**：写 `pulse-pull.sh` 和 `pulse-pull.plist`，让 Mac 每 5 分钟自动 git pull。

---

## Task M2-T1：创建 pull 脚本

> ✅ **完成**：commit `70d3bbb` (2026-07-09)

**Files:**
- Create: `91_System/93_Scripts/pulse-pull.sh`

**Interfaces:** 无（系统脚本）

- [x] **Step 1：写脚本**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-pull.sh <<'EOF'
#!/usr/bin/env bash
# Pulse sync: pull latest Pulse Cards from remote.
# Triggered by launchd every 5 minutes.
set -euo pipefail

VAULT_DIR="/Users/charliepan/Downloads/my_obsidian"
LOG_FILE="$HOME/Library/Logs/pulse-sync.log"

cd "$VAULT_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] pulse-pull: starting" >> "$LOG_FILE"

if git pull --rebase --autostash >> "$LOG_FILE" 2>&1; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] pulse-pull: success" >> "$LOG_FILE"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] pulse-pull: CONFLICT or error - manual review needed" >> "$LOG_FILE"
  exit 1
fi
EOF
```

- [x] **Step 2：设为可执行**

```bash
chmod +x /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-pull.sh
```

- [x] **Step 3：手动测试**

```bash
bash /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-pull.sh
echo "Exit code: $?"
tail -5 ~/Library/Logs/pulse-sync.log
```

期望：退出码 0，日志显示 "success"。

- [x] **Step 4：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-pull.sh
git commit -m "feat(vault): add pulse-pull.sh for vault sync from remote"
```

---

## Task M2-T2：创建 launchd plist

> ⚠️ **部分完成（已写入但 launchd 未加载）**：commit `9a45664` (2026-07-09)
> **原因**：macOS Sequoia 15.4 + `~/Downloads/` 路径组合导致 launchd 执行 plist 时 EPERM 126。即便已授权 Full Disk Access，问题依旧。同样的 plist 在 `/tmp/` 路径下能正常 load——确认为 sandbox/Downloads provenance 限制（已验证，非脚本错误）。
> **绕过方案**：手动 `bash /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-pull.sh` 即可触发同步。可考虑在 `/usr/local/bin/` 或 `~/.local/bin/` 部署 shim 脚本绕开 Downloads 限制（待解决）。
> **追踪**：见 `.superpowers/sdd/progress.md` 的 M2 部分。

**Files:**
- Create: `91_System/93_Scripts/pulse-pull.plist`

**Interfaces:** 无

- [x] **Step 1：写 plist**

```xml
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-pull.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.user.pulse-pull</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-pull.sh</string>
  </array>
  <key>StartInterval</key>
  <integer>300</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/pulse-pull.out.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/pulse-pull.err.log</string>
</dict>
</plist>
EOF
```

- [x] **Step 2：复制到 launchd 目录并加载** （**实际失败**，见任务开头说明）

```bash
cp /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-pull.plist ~/Library/LaunchAgents/com.user.pulse-pull.plist
launchctl load ~/Library/LaunchAgents/com.user.pulse-pull.plist
launchctl list | grep pulse-pull
```

期望：输出含 `com.user.pulse-pull` 的行。**实际**：EPERM exit 126，plist 未生效。

- [x] **Step 3：手动触发验证** （plist 未加载，launchctl start 无效；如需验证脚本本体可手动 `bash pulse-pull.sh`）

```bash
launchctl start com.user.pulse-pull
sleep 2
tail -10 ~/Library/Logs/pulse-sync.log
```

期望：日志新增一条 "success"。**实际**：launchd 调度未发生。

- [x] **Step 4：提交** （仅提交 plist 文件本身）

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-pull.plist
git commit -m "feat(vault): add pulse-pull.plist launchd config (5min interval)"
```

---

# Milestone 3：VPS 准备（文档）

> ✅ **完成**（2026-07-09，1 commit: efd49fe）
> **目标**：产出 VPS 设置文档，含 Python 安装、SSH key 生成、system user 创建。
> **注意**：M3 只产出文档，实际部署在 M5。

---

## Task M3-T1：写 VPS 设置文档

> ✅ **完成**：commit `efd49fe` (2026-07-09)

**Files:**
- Create: `91_System/93_Scripts/pulse-bot/docs/setup.md`

**Interfaces:** 无（运维文档）

- [x] **Step 1：写文档**

```markdown
# Pulse Bot VPS Setup

> 本文档描述如何在 VPS 上准备 pulse-bot 的运行环境。
> 不包含实际部署步骤（见 [[deployment.md]]）。

## 系统要求

- OS: Ubuntu 22.04+ (或任意主流 Linux)
- RAM: 512 MB 足够
- Python: 3.11+
- Git: 2.30+
- 用户：需要 sudo 权限运行首次安装；pulse-bot 服务本身以非特权用户运行

## 安装步骤

### 1. 系统包

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git openssh-client
```

### 2. 创建 system user

```bash
sudo useradd --system --shell /bin/bash --home /opt/pulse-bot --create-home pulse-bot
sudo mkdir -p /opt/pulse-bot
sudo chown pulse-bot:pulse-bot /opt/pulse-bot
```

### 3. 生成 bot 专用 SSH key

```bash
sudo -u pulse-bot ssh-keygen -t ed25519 -C "pulse-bot@<vps-hostname>" -f /opt/pulse-bot/.ssh/id_ed25519 -N ""
sudo -u pulse-bot cat /opt/pulse-bot/.ssh/id_ed25519.pub
```

把输出的公钥添加到 vault git remote 的 deploy keys（只读或可写）：
- GitHub: repo → Settings → Deploy keys → Add
- 勾选 "Allow write access"

### 4. 配置 known_hosts

```bash
sudo -u pulse-bot -i
ssh-keyscan github.com >> ~/.ssh/known_hosts
```

### 5. 测试 git 访问

```bash
sudo -u pulse-bot -i
git -C /opt/pulse-bot clone git@github.com:<user>/my_obsidian.git
```

如果 clone 成功，VPS 准备完成。

## 下一步

继续 [[deployment.md]] 完成 bot 服务部署。
```

写文件：

```bash
mkdir -p /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/docs
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/docs/setup.md <<'EOF'
...（上面内容原样写入）...
EOF
```

- [x] **Step 2：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-bot/docs/setup.md
git commit -m "docs(pulse-bot): add VPS setup guide"
```

---

# Milestone 4：Bot 服务本体（Python 包，TDD）

> ✅ **完成**（2026-07-09，10 commits incl. 1 fix-up: dd3dd2d / 0bf9565 / 5f9e655 / 69a82f4 / 550bd93 / 4687953 / 5277dd7 / 0045f36 / 2c8c833 / 9e25c56）
> **最终状态**：5 模块完整 + bot.py + systemd service + 测试；40/40 tests pass；92% 覆盖率（超出 plan 80% 要求）。M4 中所有 Critical/Important 问题均已修复；Minor 详见 `.superpowers/sdd/progress.md` ledger。
> **目标**：写完整的 `pulse-bot` Python 包，含 5 个模块 + systemd service + 测试。

> ⚠️ **实际文件结构（plan doc drift 已修正，2026-07-11）**：
>
> 由于 `pulse-bot` 含连字符不可作为 Python 模块名，M4 实际采用嵌套包结构：
>
> ```
> 91_System/93_Scripts/pulse-bot/
> ├── __init__.py              # 项目级 metadata（__version__）
> ├── requirements.txt
> ├── pulse_bot/               # ← 实际 Python 包（下划线）
> │   ├── __init__.py          # 包 marker
> │   ├── bot.py
> │   ├── card.py
> │   ├── config.py
> │   ├── git_sync.py
> │   └── intent.py
> ├── systemd/
> │   └── pulse-bot.service
> ├── tests/
> │   ├── test_bot.py
> │   ├── test_card.py
> │   ├── test_config.py        # 新增（M4-T9）
> │   ├── test_git_sync.py
> │   ├── test_intent.py
> │   └── test_integration.py
> └── docs/
>     ├── setup.md              # M3-T1
>     ├── deployment.md         # M5-T1
>     ├── runbook.md            # M5-T2
>     └── usage.md              # M5-T3
> ```
>
> **import 写法**：所有 import 用 `from pulse_bot.X import ...`（下划线）。
> **systemd ExecStart**：`/opt/pulse-bot/.venv/bin/python -m pulse_bot.bot`（下划线）。
> 下方 M4-T2 步骤 1 等提到的 `pulse-bot/card.py` 是原 plan 路径，**实际为 `pulse-bot/pulse_bot/card.py`**。

---

## Task M4-T1：脚手架 Python 包

> ✅ **完成**：commit `dd3dd2d` (2026-07-09)
> **Reviewer 笔记**：Minor — `__init__.py` 与 `requirements.txt` 缺 trailing newline（PEP-8 W292）

**Files:**
- Create: `91_System/93_Scripts/pulse-bot/__init__.py`
- Create: `91_System/93_Scripts/pulse-bot/requirements.txt`
- Create: `91_System/93_Scripts/pulse-bot/tests/__init__.py`

**Interfaces:** 无

- [x] **Step 1：创建目录结构**

```bash
mkdir -p /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/tests
mkdir -p /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/systemd
```

- [x] **Step 2：写 `__init__.py`**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/__init__.py <<'EOF'
"""Pulse Bot - Telegram-driven fragment capture for Obsidian vault."""
__version__ = "0.1.0"
EOF

cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/tests/__init__.py <<'EOF'
EOF
```

- [x] **Step 3：写 requirements.txt**

```text
python-telegram-bot>=20.7
python-dotenv>=1.0.0
pytest>=7.4.0
pytest-cov>=4.1.0
pyyaml>=6.0.1
```

- [x] **Step 4：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-bot/
git commit -m "chore(pulse-bot): scaffold Python package structure"
```

---

## Task M4-T2：实现 slug 生成（TDD）

> ✅ **完成**：commit `0bf9565` (2026-07-09)
> **结构调整**：计划原指定 `pulse-bot/__init__.py` 作为 Python 包入口，但 `pulse-bot` 含连字符不可作为 Python 模块名。Implementer 改为嵌套 `pulse-bot/pulse_bot/`（下划线，可导入）+ `pulse-bot/__init__.py` 只放项目级 metadata（__version__）。下游 task 统一用 `from pulse_bot.card import ...`，向前兼容。
> **Reviewer 笔记**：5 Minor（详见 `.superpowers/sdd/progress.md` M4-T2 节）。

**Files:**
- Create: `91_System/93_Scripts/pulse-bot/card.py`
- Create: `91_System/93_Scripts/pulse-bot/tests/test_card.py`

**Interfaces:**
- Consumes: 无
- Produces: `make_slug(text: str) -> str`（URL-safe，kebab-case，≤ 50 字符）

- [x] **Step 1：写失败测试**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/tests/test_card.py <<'EOF'
import pytest
from pulse_bot.card import make_slug, build_card_path, render_card

def test_make_slug_basic_ascii():
    """ASCII 文本应转为 kebab-case."""
    assert make_slug("Hello World") == "hello-world"

def test_make_slug_chinese():
    """中文应保留但限制长度."""
    slug = make_slug("想做个 skills 管理器")
    # 中文保留或转 pinyin；最简方案：保留 unicode，去掉特殊字符
    assert len(slug) > 0
    assert len(slug) <= 50

def test_make_slug_special_chars():
    """特殊字符应替换为破折号."""
    slug = make_slug("What's up?! @#$")
    assert "?" not in slug
    assert "@" not in slug
    assert "!" not in slug

def test_make_slug_length_limit():
    """超过 50 字符应截断."""
    long_text = "a" * 100
    slug = make_slug(long_text)
    assert len(slug) <= 50

def test_make_slug_empty_after_cleanup():
    """纯特殊字符应返回 fallback 'idea'."""
    assert make_slug("!@#$%") == "idea"
EOF
```

- [x] **Step 2：跑测试，确认失败**

```bash
cd /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot
python3 -m venv .venv
source .venv/bin/activate
pip install pytest
PYTHONPATH=. pytest tests/test_card.py -v
```

期望：5 个 test 全部 FAIL（`make_slug` 未定义）。

- [x] **Step 3：写最小实现**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/card.py <<'EOF'
"""Pulse Card generation: filename, frontmatter, body."""
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

SLUG_MAX_LEN = 50
SLUG_FALLBACK = "idea"


def make_slug(text: str) -> str:
    """Convert text to URL-safe kebab-case slug, max 50 chars."""
    # Normalize unicode (NFC form)
    text = unicodedata.normalize("NFKC", text)
    # Lowercase ASCII only
    text = text.lower()
    # Replace non-alphanumeric with hyphen
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    # Collapse whitespace and hyphens
    text = re.sub(r"[\s_]+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    # Truncate
    text = text[:SLUG_MAX_LEN].rstrip("-")
    return text if text else SLUG_FALLBACK
EOF
```

- [x] **Step 4：跑测试，确认通过**

```bash
cd /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_card.py::test_make_slug_basic_ascii tests/test_card.py::test_make_slug_chinese tests/test_card.py::test_make_slug_special_chars tests/test_card.py::test_make_slug_length_limit tests/test_card.py::test_make_slug_empty_after_cleanup -v
```

期望：5 个 test 全部 PASS。

- [x] **Step 5：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-bot/card.py 91_System/93_Scripts/pulse-bot/tests/test_card.py
git commit -m "feat(pulse-bot): add make_slug with TDD"
```

---

## Task M4-T3：实现 Pulse Card 文件生成（TDD）

**Files:**
- Modify: `91_System/93_Scripts/pulse-bot/card.py`
- Modify: `91_System/93_Scripts/pulse-bot/tests/test_card.py`

**Interfaces:**
- Consumes: `make_slug(text: str) -> str`（Task M4-T2）
- Produces: `build_card_path(text: str, when: datetime) -> Path`、`render_card(text: str, user_id: int, intent: str, when: datetime) -> str`

- [x] **Step 1：追加失败测试**

```bash
cat >> /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/tests/test_card.py <<'EOF'

from datetime import datetime, timezone

def test_build_card_path_format():
    """Card path 格式: YYYY-MM-DD_HHMMSS_<slug>.md."""
    when = datetime(2026, 7, 9, 20, 23, 45, tzinfo=timezone.utc)
    path = build_card_path("想做个 skills 管理器", when)
    assert path.name.startswith("2026-07-09_202345_")
    assert path.name.endswith(".md")
    assert path.parent.name == "_pulse"

def test_render_card_includes_required_fields():
    """渲染的卡片包含所有必填 frontmatter 字段."""
    when = datetime(2026, 7, 9, 20, 23, 45, tzinfo=timezone.utc)
    card = render_card("想做个 skills 管理器", user_id=12345, intent="idea", when=when)
    assert "tags:" in card
    assert "- pulse" in card
    assert "- inbox" in card
    assert "status: pulse" in card
    assert 'source: "telegram:12345"' in card
    assert "intent: idea" in card
    assert "raw_text:" in card
    assert "想做个 skills 管理器" in card

def test_render_card_includes_timestamp():
    """渲染的卡片包含原始消息段."""
    when = datetime(2026, 7, 9, 20, 23, 45, tzinfo=timezone.utc)
    card = render_card("测试消息", user_id=999, intent="task", when=when)
    assert "### 原始消息" in card
    assert "测试消息" in card
    assert "### 后续处理" in card
EOF
```

- [x] **Step 2：跑测试，确认失败**

```bash
cd /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_card.py -v
```

期望：3 个新 test FAIL（`build_card_path` / `render_card` 未定义）。

- [x] **Step 3：追加实现**

```bash
cat >> /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/card.py <<'EOF'


def build_card_path(text: str, when: datetime) -> Path:
    """Build full path for a Pulse Card: 00_Inbox/_pulse/<timestamp>_<slug>.md."""
    ts = when.strftime("%Y-%m-%d_%H%M%S")
    slug = make_slug(text)
    filename = f"{ts}_{slug}.md"
    return Path("00_Inbox/_pulse") / filename


def render_card(text: str, user_id: int, intent: str, when: datetime) -> str:
    """Render full Pulse Card markdown content."""
    ts_iso = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_human = when.strftime("%Y-%m-%d %H:%M")
    first_line = text.strip().split("\n")[0][:80]
    safe_first_line = first_line.replace('"', '\\"')

    frontmatter = f"""---
tags:
  - pulse
  - inbox
created: {ts_iso}
updated: {ts_iso}
source: "telegram:{user_id}"
status: pulse
raw_text: |
  {text}
intent: {intent}
captured_at: {ts_iso}
---

## {safe_first_line}

> 这是 {ts_human} 通过 Telegram 捕获的碎片想法。
> 尚未规范化。处理时调用 vault-enhance 或手动编辑。

### 原始消息
{text}

### 后续处理
<!-- 在这里由人或 agent 补：tags、链接、关联计划等 -->
"""
    return frontmatter
EOF
```

- [x] **Step 4：跑测试，确认通过**

```bash
cd /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_card.py -v
```

期望：8 个 test 全部 PASS（5 个 slug + 3 个新增）。

- [x] **Step 5：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-bot/card.py 91_System/93_Scripts/pulse-bot/tests/test_card.py
git commit -m "feat(pulse-bot): add build_card_path and render_card with TDD"
```

---

## Task M4-T4：实现意图推断（TDD）

> ✅ **完成**：commit `69a82f4` (2026-07-09)

**Files:**
- Create: `91_System/93_Scripts/pulse-bot/intent.py`
- Create: `91_System/93_Scripts/pulse-bot/tests/test_intent.py`

**Interfaces:**
- Consumes: 无
- Produces: `infer_intent(text: str) -> str`（返回 `idea` / `task` / `question` / `reference`）

- [x] **Step 1：写失败测试**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/tests/test_intent.py <<'EOF'
from pulse_bot.intent import infer_intent


def test_infer_idea_chinese():
    """含"想"的句子应判为 idea."""
    assert infer_intent("想做个 skills 管理器") == "idea"
    assert infer_intent("想做开源项目") == "idea"


def test_infer_task_chinese():
    """含"要"/"需要"的句子应判为 task."""
    assert infer_intent("要修一下 vault 的 frontmatter") == "task"
    assert infer_intent("需要写 plan 文件") == "task"


def test_infer_question_chinese():
    """含问号的句子应判为 question."""
    assert infer_intent("为什么 Dataview 查询这么慢？") == "question"


def test_infer_reference_default():
    """无关键字的句子应默认为 reference."""
    assert infer_intent("看了本书") == "reference"
    assert infer_intent("claude code obsidian") == "reference"


def test_infer_priority_order():
    """问号优先于其他关键字."""
    assert infer_intent("想做 X？") == "question"
EOF
```

- [x] **Step 2：跑测试，确认失败**

```bash
cd /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_intent.py -v
```

期望：5 个 test 全部 FAIL（`infer_intent` 未定义）。

- [x] **Step 3：写最小实现**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/intent.py <<'EOF'
"""Intent inference for Pulse Cards."""


def infer_intent(text: str) -> str:
    """Infer intent from text content.
    
    Priority: question > task > idea > reference
    """
    text = text.strip()
    
    # Question: contains question mark
    if "？" in text or "?" in text:
        return "question"
    
    # Task: contains "要" / "需要" / "todo"
    task_keywords = ["要", "需要", "todo", "TODO", "待"]
    if any(kw in text for kw in task_keywords):
        return "task"
    
    # Idea: contains "想" / "想做" / "打算"
    idea_keywords = ["想", "想做", "打算", "可以考虑"]
    if any(kw in text for kw in idea_keywords):
        return "idea"
    
    # Default
    return "reference"
EOF
```

- [x] **Step 4：跑测试，确认通过**

```bash
cd /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_intent.py -v
```

期望：5 个 test 全部 PASS。

- [x] **Step 5：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-bot/intent.py 91_System/93_Scripts/pulse-bot/tests/test_intent.py
git commit -m "feat(pulse-bot): add infer_intent with TDD"
```

---

## Task M4-T5：实现 git 同步模块（TDD）

> ✅ **完成**：commit `550bd93` (2026-07-09)
> **Reviewer 笔记**：测试改写。Brief 的 `test_commit_and_push_retries_on_failure` 原写法会"虚 PASS"（git add 先失败，永远不到 push 重试逻辑）。Implementer 改用 Option B：保留真实 add/commit，但 monkeypatch push 调用，断言重试次数。Reviewer 验证 OK。

**Files:**
- Create: `91_System/93_Scripts/pulse-bot/git_sync.py`
- Create: `91_System/93_Scripts/pulse-bot/tests/test_git_sync.py`

**Interfaces:**
- Consumes: 文件路径（已写入 staging area）
- Produces: `GitSync` 类，方法 `commit_and_push(file_path: Path, message: str, retries: int = 3) -> bool`

- [x] **Step 1：写失败测试**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/tests/test_git_sync.py <<'EOF'
import subprocess
from pathlib import Path
import pytest
from pulse_bot.git_sync import GitSync


@pytest.fixture
def tmp_git_repo(tmp_path):
    """Create a tmp git repo with one commit."""
    repo = tmp_path / "vault"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("# test")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    return repo


def test_commit_and_push_creates_commit(tmp_git_repo):
    """写入新文件 → 调用 commit_and_push → 应产生新 commit."""
    sync = GitSync(repo_dir=tmp_git_repo, remote_name="origin", branch="master")
    new_file = tmp_git_repo / "new_idea.md"
    new_file.write_text("# new idea")
    sync.commit_and_push(new_file, message="pulse: new idea")
    
    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=tmp_git_repo, capture_output=True, text=True
    )
    assert "pulse: new idea" in log.stdout


def test_commit_and_push_dry_run_no_actual_push(tmp_git_repo):
    """无 remote 时不应抛错（dry run 模式）。"""
    sync = GitSync(repo_dir=tmp_git_repo, remote_name="origin", branch="master", dry_run=True)
    new_file = tmp_git_repo / "idea2.md"
    new_file.write_text("idea 2")
    result = sync.commit_and_push(new_file, message="pulse: idea 2")
    assert result is True
    
    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=tmp_git_repo, capture_output=True, text=True
    )
    assert "pulse: idea 2" in log.stdout


def test_commit_and_push_retries_on_failure(tmp_git_repo, monkeypatch):
    """push 失败 3 次后应返回 False."""
    sync = GitSync(repo_dir=tmp_git_repo, remote_name="origin", branch="master", retries=2)
    
    # 模拟 push 失败（remote 不存在）
    def fake_run(*args, **kwargs):
        class Result:
            returncode = 1
            stderr = "fatal: could not push"
            stdout = ""
        return Result()
    
    monkeypatch.setattr("subprocess.run", fake_run)
    new_file = tmp_git_repo / "idea3.md"
    new_file.write_text("idea 3")
    result = sync.commit_and_push(new_file, message="pulse: idea 3")
    assert result is False
EOF
```

- [x] **Step 2：跑测试，确认失败**

```bash
cd /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_git_sync.py -v
```

期望：3 个 test 全部 FAIL（`GitSync` 未定义）。

- [x] **Step 3：写最小实现**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/git_sync.py <<'EOF'
"""Git operations for pulse-bot: commit + push with retry."""
import subprocess
import time
from pathlib import Path


class GitSync:
    """Wrapper around git add/commit/push with retry logic."""
    
    def __init__(
        self,
        repo_dir: Path,
        remote_name: str = "origin",
        branch: str = "master",
        retries: int = 3,
        dry_run: bool = False,
    ):
        self.repo_dir = Path(repo_dir)
        self.remote_name = remote_name
        self.branch = branch
        self.retries = retries
        self.dry_run = dry_run
    
    def commit_and_push(
        self, file_path: Path, message: str
    ) -> bool:
        """Add file, commit, push with retries. Returns True on success."""
        file_path = Path(file_path)
        if not file_path.exists():
            return False
        
        # git add
        add_result = subprocess.run(
            ["git", "add", str(file_path)],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        if add_result.returncode != 0:
            return False
        
        # git commit
        commit_result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        if commit_result.returncode != 0:
            return False
        
        if self.dry_run:
            return True
        
        # git push with retries
        for attempt in range(self.retries):
            push_result = subprocess.run(
                ["git", "push", self.remote_name, self.branch],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
            )
            if push_result.returncode == 0:
                return True
            if attempt < self.retries - 1:
                time.sleep(2 ** attempt)  # exponential backoff
        
        return False
EOF
```

- [x] **Step 4：跑测试，确认通过**

```bash
cd /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_git_sync.py -v
```

期望：3 个 test 全部 PASS。

- [x] **Step 5：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-bot/git_sync.py 91_System/93_Scripts/pulse-bot/tests/test_git_sync.py
git commit -m "feat(pulse-bot): add GitSync with retry logic (TDD)"
```

---

## Task M4-T6：实现 config 模块

> ✅ **完成**：commit `4687953` (2026-07-09) + fix-up `5277dd7` (2026-07-09, "确保 vault_repo_dir 是 Path 类型并接受 str 参数")
> **Reviewer 笔记**：发现 2 Important 问题（vault_repo_dir 类型在 env=Path / YAML=str 间不一致、`path` 参数签名不接受 str），已在 fix-up commit 修复，reviewer re-review 通过。

**Files:**
- Create: `91_System/93_Scripts/pulse-bot/config.py`
- Create: `91_System/93_Scripts/pulse-bot/.env.example`

**Interfaces:**
- Consumes: 环境变量
- Produces: `load_config() -> dict`（返回配置 dict）

- [x] **Step 1：写 config.py**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/config.py <<'EOF'
"""Configuration loader for pulse-bot."""
import os
from pathlib import Path
import yaml


DEFAULT_CONFIG_PATH = Path("/etc/pulse-bot/config.yaml")


def load_config(path: Path = None) -> dict:
    """Load configuration from YAML file or environment variables."""
    config_path = path or Path(os.getenv("PULSE_BOT_CONFIG", str(DEFAULT_CONFIG_PATH)))
    
    config = {
        "telegram_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "allowed_user_ids": [],
        "vault_repo_dir": Path(os.getenv("VAULT_REPO_DIR", "/opt/pulse-bot/vault")),
        "git_remote": os.getenv("GIT_REMOTE", "origin"),
        "git_branch": os.getenv("GIT_BRANCH", "master"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }
    
    if config_path.exists():
        with open(config_path) as f:
            yaml_config = yaml.safe_load(f) or {}
        config.update(yaml_config)
    
    # Validate required fields
    if not config["telegram_token"]:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set")
    if not config["allowed_user_ids"]:
        raise ValueError("allowed_user_ids must be set")
    
    return config
EOF
```

- [x] **Step 2：写 .env.example**

```text
TELEGRAM_BOT_TOKEN=your-token-from-botfather
VAULT_REPO_DIR=/opt/pulse-bot/vault
GIT_REMOTE=origin
GIT_BRANCH=master
LOG_LEVEL=INFO
PULSE_BOT_CONFIG=/etc/pulse-bot/config.yaml
```

- [x] **Step 3：写 .env.example 到 git**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/.env.example <<'EOF'
TELEGRAM_BOT_TOKEN=your-token-from-botfather
VAULT_REPO_DIR=/opt/pulse-bot/vault
GIT_REMOTE=origin
GIT_BRANCH=master
LOG_LEVEL=INFO
PULSE_BOT_CONFIG=/etc/pulse-bot/config.yaml
EOF
```

- [x] **Step 4：把 .env 加到 .gitignore**

```bash
echo ".env" >> /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/.gitignore
```

- [x] **Step 5：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-bot/config.py 91_System/93_Scripts/pulse-bot/.env.example 91_System/93_Scripts/pulse-bot/.gitignore
git commit -m "feat(pulse-bot): add config loader"
```

---

## Task M4-T7：实现 bot.py（Telegram 主循环）

> ✅ **完成**：commit `0045f36` (2026-07-09)
> **Reviewer 笔记**：5 Minor——未使用 `Path` import；`load_config` / `write_text` / `mkdir` 无 try/except（被推到 M4-T9 范围）；help 文案中提及未实现的 `/dashboard`；`/recent [N]` 提了但 N 参数解析未实现；first_line 长度限制 50 vs 40 不一致。

**Files:**
- Create: `91_System/93_Scripts/pulse-bot/bot.py`

**Interfaces:**
- Consumes: `load_config()`, `render_card()`, `infer_intent()`, `GitSync()`
- Produces: `main()` 入口；Telegram command handlers (`/p`, `/recent`, `/help`)

- [x] **Step 1：写 bot.py**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/bot.py <<'EOF'
"""Pulse Bot main module: Telegram listener and dispatcher."""
import logging
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from pulse_bot.card import build_card_path, render_card
from pulse_bot.git_sync import GitSync
from pulse_bot.intent import infer_intent
from pulse_bot.config import load_config

logger = logging.getLogger(__name__)

# In-memory recent cards for /recent command
_recent_cards: list[dict] = []


def _is_authorized(user_id: int, allowed_ids: list[int]) -> bool:
    return user_id in allowed_ids


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle plain text message: create a Pulse Card."""
    config = load_config()
    user_id = update.effective_user.id
    
    if not _is_authorized(user_id, config["allowed_user_ids"]):
        await update.message.reply_text("Unauthorized. Ask the owner to add your user_id.")
        return
    
    text = update.message.text.strip()
    if not text:
        return
    
    # Strip /p prefix if present
    if text.startswith("/p "):
        text = text[3:].strip()
    elif text == "/p":
        await update.message.reply_text("Usage: /p <your idea>")
        return
    
    when = datetime.now(timezone.utc)
    intent = infer_intent(text)
    
    # Render card
    card_content = render_card(text, user_id=user_id, intent=intent, when=when)
    
    # Build path and write
    card_path = build_card_path(text, when)
    full_path = config["vault_repo_dir"] / card_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(card_content, encoding="utf-8")
    
    # Commit + push
    sync = GitSync(
        repo_dir=config["vault_repo_dir"],
        remote_name=config["git_remote"],
        branch=config["git_branch"],
    )
    first_line = text.split("\n")[0][:50]
    success = sync.commit_and_push(full_path, message=f"pulse: {first_line}")
    
    # Track in memory
    _recent_cards.insert(0, {
        "path": str(card_path),
        "text": text,
        "intent": intent,
        "when": when.isoformat(),
    })
    if len(_recent_cards) > 20:
        _recent_cards.pop()
    
    if success:
        await update.message.reply_text(f"✓ Captured: {first_line}")
    else:
        await update.message.reply_text("⚠ Saved locally but push failed. Will retry.")


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List recent Pulse Cards."""
    if not _recent_cards:
        await update.message.reply_text("No recent cards.")
        return
    
    lines = ["Recent Pulse Cards:"]
    for i, card in enumerate(_recent_cards[:10], 1):
        first_line = card["text"].split("\n")[0][:40]
        lines.append(f"{i}. [{card['intent']}] {first_line}")
    await update.message.reply_text("\n".join(lines))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help text."""
    help_text = """Pulse Bot commands:

/p <text> - Create a Pulse Card (or just send plain text)
/recent [N] - List recent N cards (default 10)
/promote <card-id> - Promote a card to a real note (TODO: M4-T8)
/dashboard - Link to Obsidian dashboard
/help - Show this message

Capture takes <10 seconds. Just send your idea!
"""
    await update.message.reply_text(help_text)


def main() -> None:
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    config = load_config()
    
    app = Application.builder().token(config["telegram_token"]).build()
    
    # Command handlers
    app.add_handler(CommandHandler("p", handle_message))
    app.add_handler(CommandHandler("recent", recent_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", help_command))
    
    # Plain text → pulse card
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Pulse Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
EOF
```

- [x] **Step 2：手动 smoke test（不连 Telegram）**

```bash
cd /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot
source .venv/bin/activate
PYTHONPATH=. python3 -c "from pulse_bot import bot; print('Import OK')"
```

期望：输出 "Import OK"，无 import error。**实际**：smoke test green。

- [x] **Step 3：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-bot/bot.py
git commit -m "feat(pulse-bot): add bot.py with Telegram handlers"
```

---

## Task M4-T8：实现 systemd service 文件

> ✅ **完成**：commit `2c8c833` (2026-07-09)
> **Reviewer 笔记**：2 Minor——service file 缺 trailing newline（典型问题）；`EnvironmentFile=/opt/pulse-bot/.env` 应用前导 `-` 标记为可选，或在部署文档中明确要求先建 .env。

**Files:**
- Create: `91_System/93_Scripts/pulse-bot/systemd/pulse-bot.service`

**Interfaces:** 无（systemd unit file）

- [x] **Step 1：写 service 文件**

```ini
[Unit]
Description=Pulse Bot - Telegram fragment capture for Obsidian vault
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pulse-bot
Group=pulse-bot
WorkingDirectory=/opt/pulse-bot/vault
Environment="PYTHONPATH=/opt/pulse-bot/app"
EnvironmentFile=/opt/pulse-bot/.env
ExecStart=/opt/pulse-bot/.venv/bin/python -m pulse_bot.bot
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/pulse-bot/vault

[Install]
WantedBy=multi-user.target
```

写文件：

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/systemd/pulse-bot.service <<'EOF'
...（上面内容原样写入）...
EOF
```

- [x] **Step 2：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-bot/systemd/pulse-bot.service
git commit -m "feat(pulse-bot): add systemd service file"
```

---

## Task M4-T9：写完整测试套件 + 覆盖率检查

> ✅ **完成**：commit `9e25c56` (2026-07-09)
> **最终状态**：40/40 tests pass；92% 覆盖率（按模块 card 100% / config 100% / git_sync 100% / intent 100% / bot 82%）。
> **Controller 介入**：Implementer subagent 提前退出，留下 `test_integration.py` 在 `sync = GitSync(...` 截断，且未跑 pytest。Controller 修复未完成文件、新增 6 项测试（test_config.py 7 tests + 4 git_sync edge cases + 4 bot handler async tests）、安装 pytest-asyncio、安装 coverage。最终 commit 由 controller 完成。
> **遗留 Minor**：bot.py 的 main() 与 `if __name__` 块未覆盖（行 120-138, 142）——需要 mock python-telegram-bot Application，v0.1 接受缺口。

**Files:**
- Create: `91_System/93_Scripts/pulse-bot/tests/test_bot.py`
- Create: `91_System/93_Scripts/pulse-bot/tests/test_integration.py`

**Interfaces:** 无（仅测试）

- [x] **Step 1：写 bot 测试**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/tests/test_bot.py <<'EOF'
"""Tests for bot.py command parsing and authorization."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from pulse_bot.bot import _is_authorized


def test_is_authorized_true():
    assert _is_authorized(12345, [12345, 67890]) is True


def test_is_authorized_false():
    assert _is_authorized(99999, [12345, 67890]) is False


def test_is_authorized_empty_list():
    assert _is_authorized(12345, []) is False
EOF
```

- [x] **Step 2：写集成测试**

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/tests/test_integration.py <<'EOF'
"""End-to-end integration tests."""
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from pulse_bot.card import build_card_path, render_card
from pulse_bot.git_sync import GitSync
from pulse_bot.intent import infer_intent


def test_full_pipeline_no_remote(tmp_path):
    """完整流程：生成 card → 写入文件 → commit（dry-run）。"""
    repo = tmp_path / "vault"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("# test")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    
    text = "想做个 skills 管理器"
    when = datetime(2026, 7, 9, 20, 23, 45, tzinfo=timezone.utc)
    intent = infer_intent(text)
    
    card_content = render_card(text, user_id=12345, intent=intent, when=when)
    card_path = build_card_path(text, when)
    full_path = repo / card_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(card_content, encoding="utf-8")
    
    sync = GitSync(repo_dir=repo, remote_name="origin", branch="master", dry_run=True)
    success = sync.commit_and_push(full_path, message=f"pulse: {text[:50]}")
    assert success is True
    
    # Verify file is in repo
    assert full_path.exists()
    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=repo, capture_output=True, text=True
    )
    assert "pulse: " in log.stdout
EOF
```

- [x] **Step 3：跑全部测试 + 覆盖率**

```bash
cd /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot
source .venv/bin/activate
pip install python-telegram-bot python-dotenv pyyaml pytest pytest-cov
PYTHONPATH=. pytest --cov=pulse_bot --cov-report=term-missing tests/
```

期望：所有测试 PASS，覆盖率 ≥ 80%。**实际**：40/40 PASS，92% 覆盖率。

- [x] **Step 4：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-bot/tests/
git commit -m "test(pulse-bot): add full test suite with integration test"
```

---

# Milestone 5：部署 + 集成测试（文档）

> **目标**：产出部署文档，描述实际跑通 Telegram → vault 的步骤。

---

## Task M5-T1：写部署 runbook

**Files:**
- Create: `91_System/93_Scripts/pulse-bot/docs/deployment.md`

**Interfaces:** 无（运维文档）

- [ ] **Step 1：写文档**

```markdown
# Pulse Bot Deployment Runbook

> 本文档描述如何在 VPS 上完成 pulse-bot 部署。
> 前置：[[setup.md]] 已完成（VPS 已准备）。

## 部署步骤

### 1. 复制 bot 代码到 VPS

```bash
# 在本地
cd /Users/charliepan/Downloads/my_obsidian
scp -r 91_System/93_Scripts/pulse-bot/ pulse-bot@<vps-host>:/tmp/pulse-bot/

# 在 VPS
sudo mv /tmp/pulse-bot /opt/pulse-bot/app
sudo chown -R pulse-bot:pulse-bot /opt/pulse-bot/app
```

### 2. 配置 vault 仓库

```bash
sudo -u pulse-bot -i
cd /opt/pulse-bot
git clone git@github.com:<user>/my_obsidian.git vault
cd vault
git config user.email "pulse-bot@example.com"
git config user.name "Pulse Bot"
```

### 3. 安装 Python 依赖

```bash
sudo -u pulse-bot -i
cd /opt/pulse-bot/app
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
sudo -u pulse-bot -i
cp /opt/pulse-bot/app/.env.example /opt/pulse-bot/.env
chmod 600 /opt/pulse-bot/.env
nano /opt/pulse-bot/.env
# 编辑填入 TELEGRAM_BOT_TOKEN
```

### 5. 配置白名单

```bash
sudo nano /etc/pulse-bot/config.yaml
# 写入:
# telegram_token: "your-token"
# allowed_user_ids:
#   - 12345  # 你的 Telegram user_id
```

### 6. 安装 systemd service

```bash
sudo cp /opt/pulse-bot/app/systemd/pulse-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pulse-bot
sudo systemctl start pulse-bot
sudo systemctl status pulse-bot
```

期望：`active (running)`。

### 7. E2E 测试

1. 打开 Telegram，找到 bot
2. 发送：`/help` → 应回显命令列表
3. 发送：`测试一下 pulse bot` → 应回显 "✓ Captured: 测试一下 pulse bot"
4. 在本地 Mac：`bash /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-pull.sh`
5. 在 Obsidian 打开 Pulse Dashboard，应看到新卡片

## 日志查看

```bash
sudo journalctl -u pulse-bot -f
```

## 重启服务

```bash
sudo systemctl restart pulse-bot
```

## 下一步

继续 [[runbook.md]] 了解监控与运维。
```

写文件：

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/docs/deployment.md <<'EOF'
...（上面内容原样写入）...
EOF
```

- [ ] **Step 2：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-bot/docs/deployment.md
git commit -m "docs(pulse-bot): add deployment runbook"
```

---

## Task M5-T2：写运维 runbook（监控 + log rotation）

**Files:**
- Create: `91_System/93_Scripts/pulse-bot/docs/runbook.md`

**Interfaces:** 无（运维文档）

- [ ] **Step 1：写文档**

```markdown
# Pulse Bot Operations Runbook

> 监控、log rotation、故障排查。

## 健康检查

每分钟 systemd 自动重启失败的进程。手动检查：

```bash
sudo systemctl status pulse-bot
sudo journalctl -u pulse-bot --since "1 hour ago"
```

## Log Rotation

journald 默认按大小/时间自动 rotate。如需手动：

```bash
sudo journalctl --vacuum-time=7d
```

## 故障排查

### Bot 不响应

1. `sudo systemctl status pulse-bot` — 看进程状态
2. `sudo journalctl -u pulse-bot -n 100` — 看最近日志
3. 检查 token：`sudo -u pulse-bot cat /opt/pulse-bot/.env`

### Push 失败

1. `sudo journalctl -u pulse-bot | grep push` — 找错误
2. 手动测试 push：`sudo -u pulse-bot -i; cd /opt/pulse-bot/vault; git push`
3. 检查 SSH key：`sudo -u pulse-bot ssh -T git@github.com`

### Mac 端 pull 失败

1. 查看 `~/Library/Logs/pulse-sync.log`
2. 手动 pull：`cd /Users/charliepan/Downloads/my_obsidian && git pull`
3. 解决冲突后 commit

## 监控告警（可选 v0.2）

- systemd OnFailure 触发邮件 / webhook
- 简单 cron 检查服务存活
```

写文件：

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/93_Scripts/pulse-bot/docs/runbook.md <<'EOF'
...（上面内容原样写入）...
EOF
```

- [ ] **Step 2：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/93_Scripts/pulse-bot/docs/runbook.md
git commit -m "docs(pulse-bot): add operations runbook"
```

---

# Milestone 6：文档与规则沉淀

> **目标**：把 Pulse 系统集成到 CLAUDE.md，加结构化模板，更新 README 和 CURRENT.md。

---

## Task M6-T1：更新 CLAUDE.md 加 Pulse 段落

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:** 无（文档）

- [ ] **Step 1：在 CLAUDE.md 末尾追加 Pulse System 段落**

打开 `/Users/charliepan/Downloads/my_obsidian/CLAUDE.md`，在文件末尾追加：

```markdown
## Pulse System (碎片想法捕获)

`Pulse` 是 vault 内的一个子项目，用 Telegram bot + git 同步实现"10 秒内捕获碎片想法"。

### 核心约定

- **Pulse Card 存放点**：`00_Inbox/_pulse/`
- **Dashboard**：`91_System/Dashboards/Pulse-Dashboard.md`（用 Dataview 查询）
- **状态值**：`pulse`（专属状态，不参与 inbox 7 天清空规则）
- **同步机制**：bot 在云 VPS 运行，commit 到 git remote；Mac launchd 每 5 分钟 pull

### 何时使用

- 洗澡、吃饭、睡前等"无电脑在手"场景产生的想法
- 临时性、不确定值不值得做的灵感
- 任何不想被规范化摩擦劝退的瞬间想法

### 何时**不**用

- 已经明确要做的项目（直接走 Plan-First）
- 重要技术内容笔记（用 learning-note 模板）
- 已有完整结构的笔记（用 vault-enhance 升级）

### 处理流程

1. **捕获**：Telegram 发消息 → bot 自动创建 Pulse Card
2. **重访**：定期打开 Pulse Dashboard，决定每张卡的命运
3. **转正**：调用 `/promote` 命令 → 走 Plan-First → 创建正式笔记
4. **归档**：原 Pulse Card 移入 `90_Archive/_pulse_archive/`

### Agent 协作

- agent 见到 `status: pulse` 的笔记时，**不主动建议归档或规范化**
- agent 在月扫时**不**把 `_pulse/` 计入 inbox 7 天规则
- agent 见到 `/promote` 命令请求时，先走 Plan-First 流程再执行

### 详见

- 设计 spec：`91_System/94_Plans/2026-07-09_22-30_pulse-system-design_ec7217b.md`
- 实施计划：`91_System/94_Plans/2026-07-09_22-45_pulse-system-implementation-plan.md`
- Bot 部署文档：`91_System/93_Scripts/pulse-bot/docs/`
```

- [ ] **Step 2：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add CLAUDE.md
git commit -m "docs: integrate Pulse System rules into CLAUDE.md"
```

---

## Task M6-T2：创建 pulse-card 结构化模板

**Files:**
- Create: `91_System/91_Templates/pulse-card.md`

**Interfaces:** 无（模板）

- [ ] **Step 1：写模板**

```markdown
<%*
// Pulse Card template - manually use when creating cards outside Telegram
const when = tp.date.now("YYYY-MM-DD[T]HH:mm:ss[Z]");
const userId = tp.user.prompt("Telegram user ID (optional)") || "manual";
const intent = tp.user.prompt("Intent (idea/task/question/reference)", "idea");
-%>
---
tags:
  - pulse
  - inbox
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
source: "manual"
status: pulse
raw_text: |
  <% tp.file.cursor() %>
intent: <% intent %>
captured_at: <% when %>
---

## <% tp.file.title %>

> 这是 <% tp.date.now("YYYY-MM-DD HH:mm") %> 手动捕获的碎片想法。
> 尚未规范化。处理时调用 vault-enhance 或手动编辑。

### 原始消息
<% tp.file.cursor() %>

### 后续处理
<!-- 在这里由人或 agent 补：tags、链接、关联计划等 -->
```

写文件：

```bash
cat > /Users/charliepan/Downloads/my_obsidian/91_System/91_Templates/pulse-card.md <<'EOF'
...（上面内容原样写入）...
EOF
```

- [ ] **Step 2：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/91_Templates/pulse-card.md
git commit -m "feat(vault): add pulse-card template for manual capture"
```

---

## Task M6-T3：更新 CURRENT.md 标记 Pulse 上线

**Files:**
- Modify: `91_System/CURRENT.md`

**Interfaces:** 无（文档）

- [ ] **Step 1：找到 Pulse 系统状态段，把状态从 pending 改为 done**

把：

```markdown
| 实施计划 | 🚧 in-progress | [[2026-07-09_22-45_pulse-system-implementation-plan]] |
```

改为：

```markdown
| 实施计划 | ✅ done | [[2026-07-09_22-45_pulse-system-implementation-plan]] |
```

同时把所有 milestone 状态从 `⏳ pending` 改为 `✅ done`（如果 M1-M6 都已完成）。

- [ ] **Step 2：提交**

```bash
cd /Users/charliepan/Downloads/my_obsidian
git add 91_System/CURRENT.md
git commit -m "docs: mark Pulse system implementation plan as done"
```

---

## Task M6-T4：跑 vhealth-scanner 验证无回归

**Files:** 无

**Interfaces:** 无

- [ ] **Step 1：跑 scanner**

```bash
cd /Users/charliepan/Downloads/my_obsidian
python3 91_System/93_Scripts/vhealth-scanner.py
```

期望：无新增 broken wikilinks；frontmatter 全合规；Pulse 相关笔记健康。

- [ ] **Step 2：如有 broken wikilinks，立即修复并提交**

（具体修复取决于扫描报告）

---

# Acceptance Checklist (DoD v0.1)

完成所有 task 后，按 spec §12 验收标准逐条核验：

- [ ] **D1**：Telegram 消息 → vault 出现 Pulse Card（E2E + 手工）
- [ ] **D2**：从发送到 Mac 端可看到 ≤ 10 分钟（launchd 间隔验证）—— **🚫 M2-T2 deferred 阻塞，需解决 launchd 限制**
- [ ] **D3**：一条想法 → 一个 commit，message 含首句预览（`git log` 检查）—— **❓ unit-tested，但未实跑 E2E**
- [ ] **D4**：push 失败 → 3 次重试 + dead-letter 不丢数据（故障注入）—— **❓ unit-tested（test_git_sync: 6/6 edge cases），未实跑 E2E**
- [ ] **D5**：Pre-commit hook 阻止 bot 改写 `_pulse/` 外文件（单元测试）—— **❌ 未做，需 M5-T1 留意**
- [ ] **D6**：Mac 端冲突 → 不自动解决，写日志告警（故障注入）—— **❌ 未做，M2-T2 deferred 阻塞**
- [ ] **D7**：Dashboard 三块 Dataview 全部渲染（Obsidian 截图）—— **❓ Dataview 块写入，需 Obsidian 实际打开验证**
- [x] **D8**：测试覆盖率 ≥ 80%（`pytest --cov`）—— **✅ 92%（card 100% / config 100% / git_sync 100% / intent 100% / bot 82%）**
- [ ] **D9**：`vhealth-scanner.py` 无新增 broken wikilinks —— **⏳ 计划在 M6-T4 跑**
- [ ] **D10**：CLAUDE.md 加入 "Pulse System" 段落（grep 验证）—— **❌ 未做（M6-T1 范围）**

---

# Self-Review

完成 plan 后的自审检查：

**1. Spec 覆盖**：
- §3 Pulse Card 文件形态 → M4-T2, M4-T3 ✅
- §4 Pulse Bot 命令与流程 → M4-T7 ✅
- §5 本地同步 → M2-T1, M2-T2 ✅
- §6 Dashboard → M1-T2 ✅
- §7 Promote 命令 → v0.1 不实现（明确范围外，spec §15）
- §8 异常处理 → 通过 GitSync 重试（M4-T5） + launchd log（M2-T1） ✅
- §9 安全权限 → config 白名单（M4-T6） + systemd hardening（M4-T8） ✅
- §10 测试策略 → 每个模块都有 TDD，M4-T9 跑覆盖率 ✅
- §11 部署里程碑 → M1-M6 全覆盖 ✅
- §12 验收标准 → Acceptance Checklist ✅
- §13 风险登记 → 文档已含，不在 plan 中重复

**2. 占位符扫描**：
- 全 plan 无 "TBD" / "TODO" / "implement later"
- 所有 Step 含具体代码或命令
- 无 "similar to Task N"

**3. 类型一致性**：
- `make_slug(text: str) -> str` 在 M4-T2 定义，M4-T3 引用
- `build_card_path(text: str, when: datetime) -> Path` 在 M4-T3 定义，M4-T7 引用
- `render_card(text: str, user_id: int, intent: str, when: datetime) -> str` 在 M4-T3 定义，M4-T7 引用
- `infer_intent(text: str) -> str` 在 M4-T4 定义，M4-T7 引用
- `GitSync.commit_and_push(file_path, message) -> bool` 在 M4-T5 定义，M4-T7 引用
- `load_config() -> dict` 在 M4-T6 定义，M4-T7 引用

一致性 OK。

---

# ⏰ 追加待办（M5 完成后务必插入"使用说明"任务）

> 来源：用户 2026-07-10 session 末补充需求。

M5（部署文档）写完后、开始 M6 之前，**必须插入 M5-T3 任务：撰写终端用户使用说明**，包含：

- Telegram bot 的端到端用法（首次对话 → 发想法 → /recent → /help → /promote）
- Pulse Card 在 Obsidian 内打开后的二次处理路径（如何 decide fate：promote / 归档 / 丢弃）
- 可选：典型场景示例（洗澡时的灵感、睡前复盘、临时待办），
- 可选：FAQ / 常见坑（v0.1 已知 M2-T2 launchd 限制 → Mac 端需手动 `bash pulse-pull.sh`）

**位置候选**：
- `91_System/93_Scripts/pulse-bot/docs/usage.md`（与 deployment.md / runbook.md 同目录）——推荐
- `40_Life/44_Tech-Thoughts/TECH_Pulse-Bot-Usage.md`（个人笔记形态）

**为什么独立成 task**：这是面向"作为终端用户的我"而非"作为运维的我"的内容，文档受众不同。技术运维文档写在 `docs/`；使用说明写在 `docs/usage.md` 但语气更亲用户。

**触发时机判断**：
- ❌ M4 完成 → 还不需要写（bot 还没部署）
- ✅ M5 完成 → **立刻插入 M5-T3**（用户在 M5-T1/T2 完成后会自然想起"还要用呢"）
- ⏸️ M6 完成后 → 如果还没写，再提醒一次

**注意**：在 M5 收尾时（任务执行前），agent 必须主动询问用户："现在是不是插入 M5-T3 (撰写使用说明) 的时机？"

---

# Execution Handoff

Plan 已完成并保存到 `91_System/94_Plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md`。

两种执行方式可选：

1. **Subagent-Driven (推荐)** — 每个 task 派遣独立 subagent，task 间 review
2. **Inline Execution** — 当前 session 内批量执行，checkpoints review