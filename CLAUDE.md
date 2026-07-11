# CLAUDE.md — Pulse Bot Project

This is the standalone Pulse Bot project. A Telegram-driven fragment capture bot for Obsidian vaults. Code extracted from `soeasy13142/my_obsidian` via `git subtree split` on 2026-07-11.

## Project Overview

Pulse Bot captures fleeting thoughts via Telegram and writes them to an Obsidian vault as "Pulse Cards" (raw fragments in `00_Inbox/_pulse/`). The philosophy: **separate capture from organization** — capture with zero friction, normalize when you decide each card's fate.

- **Repo**: https://github.com/soeasy13142/pulse-bot
- **License**: MIT
- **Status**: v0.1 (M1-M6 done, E2E not yet deployed)
- **Python**: 3.11+
- **Stack**: python-telegram-bot v20+, systemd, git

## Design Context & Architecture

> **Canonical source**: `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` — the original design document from the vault era. Read it when you need milestone-level detail, acceptance criteria, or historical context.

### Architecture (6 Milestones)

The system was built in 6 milestones:

| # | Milestone | Status |
|---|-----------|--------|
| M1 | Local infrastructure (`_pulse/` dir + Dashboard) | ✅ done |
| M2 | Windows auto-pull (Task Scheduler, 5min, replaces Mac launchd) | ✅ done (see `docs/setup-windows.md`, `scripts/pulse-pull.ps1`) |
| | Mac launchd auto-pull (5min interval) | ⚠️ deferred (macOS Downloads sandbox block) |
| M3 | VPS setup docs | ✅ done |
| M4 | Bot Python package (5 modules, TDD) | ✅ done |
| M5 | Deployment docs + runbook | ✅ done |
| M6 | Documentation & rules | ✅ done |

**Goal**: Let users capture any fleeting thought in under 10 seconds via Telegram. All normalization (tagging, categorizing, linking) happens later at promote time.

### Global Constraints (from original spec)

These are project invariants distilled from the design doc. Every task implicitly follows them:

1. **Vault naming convention**: new files follow v1 spec; `_pulse/` is "free naming" category
2. **Frontmatter required**: `tags`, `created`, `updated`, `status`, `source` on all Pulse Cards
3. **Commit frequency**: one commit per logical change, no batching
4. **Commit message format**: `<type>: <description>` (see Git Workflow)
5. **Test coverage**: ≥ 80% at all times
6. **Plan-First**: any non-trivial task starts with a plan (`.claude/plans/`)
7. **Decision rights belong to user**: agent never decides classification or archival without asking
8. **Security**: bot only responds to whitelisted `user_id`s; only writes to `_pulse/` path
9. **Git sync**: all Pulse Cards sync via git push/pull; one idea = one commit

### v0.1 Acceptance Status

Key DoD items from the original plan:

| Criterion | Status |
|-----------|--------|
| `docs/deployment.md` | ✅ Done |
| `docs/runbook.md` | ✅ Done |
| `docs/usage.md` | ✅ Done |
| `docs/setup.md` | ✅ Done |
| `docs/setup-windows.md` | ✅ Done (`scripts/pulse-pull.ps1` + Task Scheduler XML) |
| Telegram message → Pulse Card in vault (E2E) | ✅ Offline smoke test passing (3 tests in `tests/test_smoke_e2e.py`); actual VPS deployment pending |
| Send → Windows visible ≤ 5min (Task Scheduler, replaces Mac launchd) | ✅ Documented (see `docs/setup-windows.md`, `scripts/pulse-pull.ps1`) |
| One idea → one commit with preview message | ✅ Unit-tested |
| Push failure → 3 retries + dead letter queue | ✅ Unit-tested |
| Pre-commit hook blocks writes outside `_pulse/` | ✅ Template created (`docs/hooks/pre-commit` + README); install manually in vault repo |
| Git conflict handling | ✅ Windows sync script logs conflict + creates `.CONFLICT` marker; never auto-resolves |
| Dashboard Dataview rendering | ✅ Written, needs Obsidian verification |
| Test coverage ≥ 80% | ✅ 90% (69 tests) |
| CLAUDE.md Pulse System section | ✅ Done |

## Project Layout

```
pulse-bot/
├── README.md                          # Quick start + features
├── LICENSE                            # MIT
├── CLAUDE.md                          # This file (agent onboarding)
├── .gitignore
├── .claude/                           # Claude Code 项目级配置
│   ├── settings.local.json           # 权限白名单 (git/python/pytest 等)
│   ├── plans/                        # 活跃任务计划 (进行中的功能/重构)
│   └── skills/                       # 项目专属 skill
│       ├── pulse-bot-dev/            # 项目开发工作流
│       └── python-testing/           # Python 测试模式
├── requirements.txt
├── pytest.ini
├── __init__.py                        # Project metadata (__version__)
├── pulse_bot/                         # Python package (import as `pulse_bot`)
│   ├── __init__.py
│   ├── bot.py                         # Telegram listener + command handlers
│   ├── card.py                        # Pulse Card generation (slug, path, render)
│   ├── config.py                      # Config loader (env + YAML)
│   ├── dead_letter.py                 # Dead letter queue for failed pushes
│   ├── git_sync.py                    # GitSync with retry
│   ├── intent.py                      # Intent inference
│   ├── .env.example
│   └── .gitignore
├── scripts/                           # Platform-specific sync scripts
│   ├── pulse-pull.ps1                 # Windows PowerShell sync script (Task Scheduler)
│   └── pulse-pull-task.xml            # Windows Task Scheduler export
├── systemd/
│   └── pulse-bot.service              # systemd unit with hardening
├── tests/                             # 69 tests, 90% coverage (run pytest --cov to see current)
│   ├── __init__.py
│   ├── test_bot.py
│   ├── test_card.py
│   ├── test_config.py
│   ├── test_dead_letter.py
│   ├── test_git_sync.py
│   ├── test_intent.py
│   ├── test_integration.py
│   └── test_smoke_e2e.py             # Offline E2E smoke tests (full pipeline, dead letter, pre-commit hook)
├── docs/
│   ├── setup.md                       # VPS environment setup
│   ├── deployment.md                  # Deployment runbook + E2E test
│   ├── runbook.md                     # Monitoring + troubleshooting
│   ├── usage.md                       # End-user guide
│   ├── setup-windows.md               # Windows sync setup guide
│   └── hooks/
│       ├── pre-commit                 # Pre-commit hook template (blocks bot writes outside _pulse/)
│       └── README.md                  # Hook installation guide
└── plans/                             # Historical plans (read-only reference)
    ├── 2026-07-09_22-30_pulse-system-design_nogit.md
    └── 2026-07-09_22-45_pulse-system-implementation-plan_nogit.md
```

## Quick Start

```bash
# Clone
git clone https://github.com/soeasy13142/pulse-bot.git
cd pulse-bot

# Setup
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest --cov=pulse_bot --cov-report=term-missing tests/
# Expected: all tests pass, coverage >= 80% (see README badge for current exact counts)

# Run bot (requires TELEGRAM_BOT_TOKEN env var)
export TELEGRAM_BOT_TOKEN="<from-botfather>"
python -m pulse_bot.bot
```

See [`docs/deployment.md`](docs/deployment.md) for production VPS deployment.

## Development Workflow

### TDD is Mandatory

This project was built test-first from day one. Every new feature follows:

1. **Write failing test** in `tests/test_<module>.py`
2. **Run** `pytest tests/test_<module>.py -v` — confirm RED
3. **Write minimal implementation** in `pulse_bot/<module>.py`
4. **Run** `pytest tests/test_<module>.py -v` — confirm GREEN
5. **Refactor** while keeping tests green
6. **Verify coverage**: `pytest --cov=pulse_bot tests/` — must remain ≥ 80%

### File Organization

- **One module per file** under `pulse_bot/`
- **One test file per module** under `tests/` (mirror naming: `test_<module>.py`)
- **Integration tests** in `tests/test_integration.py` (uses tmp git repo)
- **Never** let a file exceed ~400 lines. Split before it does.

### Coding Style

- **Immutable**: prefer creating new objects over mutation
- **KISS**: simplest solution that works
- **DRY**: extract repeated logic into shared functions
- **YAGNI**: no speculative features
- **Type hints**: required on all public functions
- **No hardcoded secrets**: use env vars or config
- **No silent failures**: handle errors explicitly

### Imports & Module Naming

- Package: `pulse_bot` (underscore, importable)
- Files: snake_case (`git_sync.py`, not `gitsync.py`)
- Tests import via: `from pulse_bot.X import ...`

## DO and DON'T (行为规范)

> ## 🛑 FIRST PRINCIPLE: When in doubt, ASK.
>
> - **默认动作 = `AskUserQuestion`**, 不是"显然的假设"。
> - **触发阈值: 1% 不确定 = 不确定。** 即使 99% 把握, 只要用户没明说, 先问后做。
> - 永远不要根据 "通常做法"、"业内惯例"、"合理默认"、"我猜你想要 X" 直接执行。
> - 这条规则优先于本文件其他任何"方便行事"的偏好 —— **多问一次永远比返工便宜**。
>
> **触发 AskUserQuestion 的完整场景清单** (任何一项命中就问):
>
> - 需求描述有歧义 / 模糊 / 可多重解读
> - 找不到指定的文件 / 函数 / 命令 / 配置 / 路径
> - 多个合理方案并存 (库选型 / 命名风格 / 重构范围 / 激进 vs 保守)
> - 用户说的术语有多种含义 (e.g. `promote` = 晋升 / 升级 / 推广 / 提拔)
> - 输入参数、配置项、env var 不完整
> - API / CLI / 库用法不确定 (即使看起来"显然")
> - 命名约定不确定 (snake_case vs camelCase / 缩写 vs 全称)
> - git 操作意图不清 (commit 粒度 / 是否 push / 是否 force-push / squash 范围)
> - 错误处理策略不确定 (fail-fast vs log-and-continue / 是否重试 / 重试几次)
> - 测试范围 / 边界条件 / mock 策略不确定
> - 是否要写注释、docstring、README 不确定
>
> **怎么问**:
>
> - 必走 `AskUserQuestion` 工具, 不要在正文里用"问号句"问
> - 选项互斥、给出推荐 (推荐项放第 1 位, 标注 "Recommended")
> - 给出 "Other" 让用户自由补充 (工具会自动加)
> - 一次问 1–4 个相关问题, 不要一次塞 10 个
> - 推荐项基于事实 (项目规范 / 用户历史 / 行业惯例), 不是凭空偏好
> - 提问前先 `Read` / `Grep` 验证你掌握的事实, 不要基于过时记忆问

### ✅ DO (必须做)

1. **First-line reflex: AskUserQuestion** *(请配合上方 FIRST PRINCIPLE 块)*
   - 收到任何需求 → 先问自己: "我有没有任何 1% 不确定?" → 有 → 立刻 `AskUserQuestion`
   - 即使是看起来"显然"的小决策 (命名、参数顺序、日志格式、错误提示文案), 只要可能影响后续, 就问
   - 不要先动手发现错了再问 — 那叫 "在用户看不到的地方 fail"
   - 不确定时**永远**是 `AskUserQuestion` > 凭直觉 > 静默选择默认

2. **复杂任务必须先写 plan**
   - 任何涉及以下情况的任务, **动手前** 先在 `.claude/plans/<feature>-<YYYY-MM-DD>.md` 写计划文档:
     - 新增功能 / 新模块
     - 跨 ≥2 个文件的改动
     - 重构 / 架构调整
     - 不熟悉的需求 / 需要多轮迭代
   - 计划必须包含: 背景、目标、范围、文件改动清单、测试策略、回滚方案、风险点
   - 计划写完 → 实施 → 完成后更新计划状态 (✅) → 归档或删除
   - **计划阶段本身就要 `AskUserQuestion`** 验证假设, 不要计划里写一堆"合理默认"再让用户接受

3. **TDD 严格执行**
   - 任何新功能 / Bug 修复: 先写测试 → 红 → 最小实现 → 绿 → 重构 → 覆盖率 ≥80%

4. **代码审查前置**
   - commit 之前调用 `code-reviewer` agent (或 `/ecc:code-review`)
   - 修复所有 CRITICAL / HIGH 级别问题
   - 涉及 Python 文件额外调用 `python-reviewer`
   - **每次 code review 结束后必须留档**：在项目根 `plans/` 新建或更新 review 结果记录，文件名遵循 `plans/README.md` 规范，内容至少包含 scope、decision、findings、validation results、follow-up checklist

5. **本地高频 commit, 远端前整理**
   - 详见 "Git Workflow / Commit Frequency" 章节

6. **测试覆盖每个改动**
   - 修改任何生产代码 → 必须有对应测试更新
   - 覆盖率必须 ≥80% (使用 `pytest --cov` 验证)

7. **明确错误处理**
   - 显式 `try/except`, 不吞错
   - UI 层给友好提示, 服务层记录详细上下文
   - 失败立即 fail-fast

### ❌ DON'T (绝不做)

1. **不要替用户做决策 (AskUserQuestion 是默认动作, 不是例外)**
   - 任何"我觉得大概是…"、"通常做法是…"、"合理的默认是…"、"我猜你想要 X" — 都是违规信号, 立刻改用 `AskUserQuestion`
   - 即使有 99% 把握, 只要用户没明确说, 就先问后做 (1% 不确定就是不确定)
   - 不要在多个合理选项中"挑一个最像的" 直接执行
   - 不要"先做一种方案, 不行再换" — 错的, 先问再做
   - 不要在用户看不到的地方 fail-fast 后暗自选默认 — 用户会不知道发生过什么
   - 不要用代码里的 `TODO` / `# FIXME: confirm with user` 当作"问过"
   - 不要在响应正文里用"我打算…"、"我决定…"、"我的方案是…" 偷偷宣布结论 — 真要决定先问

2. **不要跳过 plan 直接动手**
   - 复杂任务不要"想想就开干"
   - 不要在脑子里规划 → 必须落到 `.claude/plans/` 文件里
   - 不要写完代码才补 plan (事后补的计划没有约束作用)

3. **不要把积攒的本地 commit 原样 push**
   - 不要把 10+ 个小 commit 直接推到 origin
   - 不要跳过 squash / rebase 步骤
   - 不要在用户没确认时自动 push

4. **不要写无用代码**
   - 不要写不会被调用的函数 (YAGNI)
   - 不要写"以备不时之需"的工具 / 抽象
   - 不要留 `print()` / `console.log` / `TODO` / 注释掉的死代码
   - 不要写 docstring 但内部是 pass

5. **不要硬编码**
   - 不要硬编码 secret / token / password / ssh key
   - 不要硬编码路径 (用 `pathlib.Path` + config)
   - 不要硬编码 magic number (用 `UPPER_SNAKE_CASE` 常量)

6. **不要静默失败**
   - 不要 `except: pass` 或 `except Exception: return None`
   - 不要吞掉异常不打印任何上下文
   - 不要在用户看不到的地方失败

7. **不要修改历史归档**
   - `plans/2026-07-09_22-30_pulse-system-design_nogit.md` 和 `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` 是 v0.1 历史归档, **只读**
   - 历史归档引用 → 用相对路径, 不要搬动 / 删除
   - 这两个文件已按命名规范重命名完成，不要再次搬动

8. **不要在没有 plan 的情况下做大改动**
   - 不要重构超过 100 行的代码不写 plan
   - 不要删除功能不写 plan (即使是 "明显没用" 的)
   - 不要升级依赖主版本不写 plan

### 决策路径速查

> 默认动作 = `AskUserQuestion`。下表列出**具体场景**与首选工具/路径,但**任何 1% 不确定都先问**。

| 遇到什么 | 怎么办 |
|---------|--------|
| **🛑 任何 1% 不确定 / 任何疑问 / 任何歧义** | **`AskUserQuestion` (默认动作)** |
| 需求不明确 / 有歧义 | `AskUserQuestion` |
| 多个方案并存 | `AskUserQuestion` + 推荐选项 |
| 不知道用哪个库 / API | `AskUserQuestion` 或 `context7-mcp` skill |
| 找不到文件 / 函数 / 配置 | 先 `Glob` / `Grep`, 找不到就 `AskUserQuestion` 确认路径 |
| 术语 / 命名 / 缩写含义不清 | `AskUserQuestion` |
| 输入参数 / 配置项 / env var 不全 | `AskUserQuestion` |
| 改动涉及 ≥2 文件 | 先 `.claude/plans/<name>.md` + `AskUserQuestion` 确认范围 |
| pytest 失败 | `/ecc:build-fix` 或 `build-error-resolver` agent |
| 写完一段代码 | `code-reviewer` agent |
| 准备 commit | `python-reviewer` + `code-reviewer` |
| 准备 push | `git log` 检查 + squash + `AskUserQuestion` 确认 |

## Git Workflow

### Commit Message Format

```
<type>(<scope>): <description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`

Examples (from this repo's history):
```
feat(pulse-bot): add make_slug with TDD
fix(pulse-bot): ensure vault_repo_dir is Path and accept str path arg
test(pulse-bot): add full test suite with integration test
docs(pulse-bot): add VPS setup guide
```

### Commit Frequency (本地频繁, 远端整理)

**本地提交 (Local commits)** —— 鼓励高频、小步、一次一逻辑:

- 一个测试通过 → 立刻 commit
- 重构中途、命名调整、注释补充 → 都可以独立 commit
- 一次 commit 只做一件事 (单一职责)
- 不要等所有功能完成才 commit
- 不要在 commit 里夹带无关改动 (格式化、依赖升级等单开)

**推送远端 (Push)** —— 推送前必须整理合并, 不允许把本地积攒的 N 个小 commit 原样推上去:

1. **推送前自查**: 先用 `git log --oneline origin/master..HEAD` 查看待推送的本地 commit 数
2. **整理策略**:
   - 如果待推送 ≤ 3 个 commit 且语义独立 → 可直接 push
   - 如果待推送 > 3 个 commit 或多个 commit 属于同一逻辑改动 → 必须先用 `git rebase -i origin/master` 合并 (squash/fixup), 再 push
   - Feature 分支合并回 master 前必须 squash
3. **推送确认**: push 之前主动问用户是否继续, 给出待推送 commit 摘要, 不要擅自 push
4. **绝不自动 push**: 永远不要在用户没确认的情况下 `git push`
5. **紧急修复除外**: hotfix 类小改动 (1-2 个 commit) 可直接 push, 但仍需事后告知用户

**典型工作流**:

```bash
# 1. 本地高频提交
git commit -m "feat(card): add slug generator"
git commit -m "test(card): cover unicode edge cases"
git commit -m "docs(card): document slug rules"

# 2. 推送前自查
git log --oneline origin/master..HEAD
# → 3 个 commit, 但都属于"slug 功能", 需要合并

# 3. 整理合并
git rebase -i origin/master
# → squash 掉后两个, 留下一个清晰的 feat commit

# 4. 询问用户后再 push
git push origin master
```

### Branch Strategy

- Single `master` branch (this is a small project)
- Feature branches for non-trivial work: `git checkout -b feature/<topic>`
- Squash feature branches before merge to keep history clean

## Testing

```bash
# Run all tests
pytest tests/

# Run specific module
pytest tests/test_card.py -v

# With coverage
pytest --cov=pulse_bot --cov-report=term-missing tests/

# Coverage report (HTML)
pytest --cov=pulse_bot --cov-report=html tests/
open htmlcov/index.html
```

### Test Patterns

- Use `tmp_path` fixture for filesystem operations
- Use `monkeypatch` for mocking subprocess / external calls
- Integration tests use a fresh tmp git repo (see `test_integration.py`)

## Deployment

The bot is designed to run on a VPS under systemd. Full deployment guide: [`docs/deployment.md`](docs/deployment.md).

Quick reference:

```bash
# On VPS, as root:
sudo useradd --system --shell /bin/bash --home /opt/pulse-bot --create-home pulse-bot
sudo mkdir -p /opt/pulse-bot
sudo chown pulse-bot:pulse-bot /opt/pulse-bot

# Copy app + clone vault
sudo cp -r /path/to/pulse-bot /opt/pulse-bot/app
sudo -u pulse-bot git clone <vault-repo> /opt/pulse-bot/vault

# Install deps + configure
sudo -u pulse-bot bash -c "cd /opt/pulse-bot/app && python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"

# Install systemd service
sudo cp /opt/pulse-bot/app/systemd/pulse-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pulse-bot
```

## Security

- **Whitelist required**: `allowed_user_ids` in `/etc/pulse-bot/config.yaml` — bot refuses to start without it
- **systemd hardening**: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome=true`, `ReadWritePaths=/opt/pulse-bot/vault` — do not weaken
- **SSH key isolation**: bot's deploy key only on vault repo, not user's personal account
- **Token in env, not code**: `.env` in `.gitignore`, never committed

## Known Limitations (v0.1)

- `/promote` command not implemented (manual upgrade path)
- No image/voice support (text only)
- Mac launchd auto-pull blocked by macOS sandbox (use Windows Task Scheduler or manual `bash pulse-pull.sh`)
- Single-user whitelist (multi-user needs config edit + restart)
- Pre-commit hook must be manually installed in vault repo (`cp docs/hooks/pre-commit <vault>/.git/hooks/pre-commit`)

See `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` for full v0.1 status.

## v0.2 Roadmap

Candidates (see `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` §v0.2):
1. `/promote` command with LLM-assisted intent classification
2. Image attachment support (OCR + raw image save)
3. Mac launchd shim script workaround
4. Pre-commit hook with file-path whitelist

## Claude Plugins (ECC) 使用规范

本项目使用 [ECC (Everything Claude Code)](https://github.com/affaan-m/ECC) 插件。完整的 ECC agent/command 列表见 [官方 README](https://github.com/affaan-m/ECC/blob/main/README.zh-CN.md)。

### 必备 Agents (本项目常用)

| Agent | 用途 | 强制触发场景 |
|-------|------|------------|
| `planner` | 实现规划 | 复杂功能、改动 ≥2 文件、新模块前 |
| `code-reviewer` | 代码质量审查 | 写完任何 `pulse_bot/*.py` 后、commit 前 |
| `python-reviewer` | Python 专项审查 | 修改 `.py` 文件后 (与 code-reviewer 配套) |
| `tdd-guide` | TDD 强制 | 新功能、Bug 修复 |
| `security-reviewer` | 安全审查 | 涉及 token、用户输入、文件系统、外部 API |
| `build-error-resolver` | 构建/测试错误 | `pytest` / `python` 报错时 |
| `refactor-cleaner` | 死代码清理 | 阶段性重构、定期维护 |
| `docs-lookup` | 文档查阅 | 遇到不确定的库 API / 配置项 |

### 必备 Commands (本项目常用)

| Command | 用途 |
|---------|------|
| `/plan` 或 `/ecc:plan` | 实现规划 (复杂任务**必须**先执行) |
| `/code-review` 或 `/ecc:code-review` | 代码审查 |
| `/build-fix` 或 `/ecc:build-fix` | 修复构建/测试错误 |
| `/refactor-clean` 或 `/ecc:refactor-clean` | 清理死代码 |
| `/security-scan` 或 `/ecc:security-scan` | 安全扫描 |
| `/test-coverage` 或 `/ecc:test-coverage` | 测试覆盖率分析 |
| `/update-docs` 或 `/ecc:update-docs` | 同步文档 |

### 标准化调用流程

```bash
# 1. 复杂任务开搞前先 plan
/ecc:plan "添加 /promote 命令"
# → 在 .claude/plans/promote-command-2026-07-11.md 生成计划文档

# 2. 写完代码立即审查 (本项目强制)
/ecc:code-review pulse_bot/bot.py
/ecc:python-review pulse_bot/bot.py

# 3. 测试失败立即修复
/ecc:build-fix
# 或显式调用 agent
# (Task tool, subagent_type=build-error-resolver)

# 4. 提交前安全扫描
/ecc:security-scan

# 5. 检查覆盖率
/ecc:test-coverage
```

### 本项目特殊约定

- **Python 改动审查链**: 任何 `pulse_bot/*.py` 修改 → `code-reviewer` → `python-reviewer` → commit
- **测试覆盖率门槛**: 不能低于 80% (当前 92%, 详见 pytest 输出)
- **Plan 文件落盘**: 所有 plan 必须写入 `.claude/plans/`, 不允许只在脑中/对话里规划
- **Skill 优先于猜测**: 遇到不确定的 Python 模式 / 测试写法 → 优先调 `python-testing` skill 或 `docs-lookup` agent

### 项目专属 Skill (`.claude/skills/`)

不依赖 ECC, 是本项目自己沉淀的工作流:

- `pulse-bot-dev` — 项目开发工作流 (TDD + commit + deploy 全流程)
- `python-testing` — Python 测试模式 (pytest fixture、mock、AAA 写法)

### 外部 Skill (按需加载)

- `superpowers:writing-plans` — Plan 结构标准
- `superpowers:executing-plans` — Plan 执行流程
- `superpowers:brainstorming` — 需求不明确时先 brainstorm
- `superpowers:test-driven-development` — TDD 红绿循环

## .claude 文件夹结构

```
.claude/
├── settings.local.json          # 项目级权限白名单 (git/python/pytest 等)
├── plans/                       # 活跃任务计划 (进行中的功能/重构)
│   └── .gitkeep
└── skills/                      # 项目专属 skill
    ├── pulse-bot-dev/
    │   └── SKILL.md
    └── python-testing/
        └── SKILL.md
```

### 各子目录用途

| 路径 | 用途 | 写入规范 |
|------|------|---------|
| `settings.local.json` | 权限白名单 + 环境变量 | 不要提交 secret 到这里 (用环境变量或 `.env`) |
| `plans/` | 当前活跃任务计划 | 命名: `<feature-name>-<YYYY-MM-DD>.md`, 完成后归档或删除 |
| `skills/` | 项目沉淀的开发模式 | 一个 skill 一个子目录, 必须包含 `SKILL.md` |

### plans/ vs 项目根 plans/ 的区别

- **`.claude/plans/`**: 进行中的功能计划、TDD 任务清单、临时设计草案 → **活跃**, 可写可改可删
- **项目根 `plans/`**: `2026-07-09_22-30_pulse-system-design_nogit.md` 和 `2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` 是 v0.1/v0.2 历史归档 → **只读**, 不要修改

### 项目根 `plans/` 命名规范

存放于项目根 `plans/` 目录下的计划文件按以下规范命名（详见 [`plans/README.md`](plans/README.md)）：

```
YYYY-MM-DD_HH-MM_<topic-kebab>_<commit-ref>.md
```

| 段 | 说明 | 示例 |
|---|---|---|
| `YYYY-MM-DD_HH-MM` | 最后修改日期+时分（按文件名排序） | `2026-07-11_01-05` |
| `<topic-kebab>` | 简短问题/主题，kebab-case | `plans-naming-spec` |
| `<commit-ref>` | 针对的提交哈希（多个用 `-` 连接）；非提交相关用 `nogit` | `7c65964-7186aa2` |

**规则**：

- 文件名不含空格，主题段用 `-`，主段间用 `_`。
- 每个计划文件必须含 YAML frontmatter（`tags` / `created` / `updated` / `status` / `source` 等）。
- `created` / `updated` 同步写入 frontmatter 与文件名前缀。
- `source` 字段写明针对的提交 / 起因。
- 计划状态：`draft`（待确认）→ `in-progress`（执行中）→ `done`（已完成）/ `archived`（归档）。
- 计划被确认并执行后，更新 frontmatter `status` 与 `updated`，**不要删除文件**（保留历史）。

**README 例外**：本目录下 `README.md` 是命名规范的**定义文件**本身，豁免按本规范命名（参见 `plans/README.md` 规则第 6 条）。它是规范的源头，而不是规范的对象。

### 何时创建 plan

满足以下任一条件 → 必须在 `.claude/plans/` 写计划:

- 涉及 ≥2 个文件改动
- 新增功能 / 新模块
- 重构 / 架构调整
- 依赖升级 (主版本)
- 用户需求不明确需要多轮探索
- 预计改动 > 100 行

详见 "DO and DON'T" 章节第 1 条。

## Related Links

- **Original vault** (where this code lived): https://github.com/soeasy13142/my_obsidian
- **Project development docs** (本项目开发文档):
  - **Implementation plan**: `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` — v0.1/v0.2 roadmap, module breakdown, milestone status
  - **Design spec**: `plans/2026-07-09_22-30_pulse-system-design_nogit.md` — system architecture, design decisions, rationale
