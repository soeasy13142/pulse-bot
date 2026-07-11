---
tags:
  - plan
  - code-review
  - pulse-bot
created: 2026-07-11
updated: 2026-07-11
status: done
source: "local code review requested by user on 2026-07-11; working tree diff against HEAD"
topic: "pulse-bot code review results"
---

# Pulse Bot Code Review Results — 2026-07-11 15:24

## Review Scope

- Mode: local review of uncommitted changes plus project-level spot-check.
- Changed files at gather time:
  - `CLAUDE.md`
  - `.claude/plans/.gitkeep`
- Additional files spot-checked for project-level behavior and consistency:
  - `pulse_bot/bot.py`
  - `pulse_bot/card.py`
  - `pulse_bot/config.py`
  - `pulse_bot/git_sync.py`
  - `pulse_bot/intent.py`
  - `systemd/pulse-bot.service`
  - relevant `README.md` / `docs/` command and test-count references

## Decision

**REQUEST CHANGES**

Reason: one HIGH user-visible behavior mismatch was found, plus MEDIUM/LOW documentation and help-text consistency issues.

## Findings

### HIGH

#### 1. `/recent [N]` 参数被文档承诺但实现完全忽略

- **位置**: `pulse_bot/bot.py:107`
- **相关文档**: `README.md:128`, `docs/usage.md:79`, `docs/usage.md:80`, `pulse_bot/bot.py:117`
- **问题**: 文档和 help 都声明 `/recent [N]` 或 `/recent 20` 可以控制返回数量，但实现固定使用 `_recent_cards[:10]`，没有读取 `context.args`。
- **影响**: 用户执行 `/recent 20` 仍只会看到 10 条，属于用户可见的命令行为错误。
- **建议修复**:
  - 在 `recent_command` 中解析 `context.args`。
  - 默认值 10。
  - 建议限制范围，例如 `1 <= N <= 20`，非法输入返回友好提示。
  - 增加测试覆盖：
    - `/recent` 返回 10 条以内；
    - `/recent 20` 返回最多 20 条；
    - `/recent abc` 返回 usage/error。

### MEDIUM

#### 2. Help 文案列出 `/dashboard`，但没有注册对应 handler

- **位置**: `pulse_bot/bot.py:120`
- **问题**: `help_command()` 显示 `/dashboard - Link to Obsidian dashboard`，但 `main()` 只注册了 `p`、`recent`、`help`、`start`。由于 plain text handler 使用 `~filters.COMMAND`，用户发送 `/dashboard` 会被 Telegram bot 忽略。
- **影响**: Help 暴露了一个不可用命令，用户体验会误导。
- **建议修复（二选一）**:
  - 如果 v0.1 不计划实现：从 help 文案删除 `/dashboard`。
  - 如果要保留：实现 `dashboard_command()`，注册 `CommandHandler("dashboard", dashboard_command)`，并加测试。

#### 3. 文档中的测试数量已经过期

- **位置**: `CLAUDE.md:43`, `CLAUDE.md:75`
- **相关位置**: `README.md:49`, `README.md:108`, `README.md:138`
- **问题**: 当前测试运行结果是 **48 tests, 92% coverage**，但文档仍写 **40 tests / 40/40**。
- **影响**: 新增的 `CLAUDE.md` 开发规范强调测试覆盖率，但同一文件保留了错误基线，会误导后续维护者和 agent。
- **建议修复**:
  - 更新为 `48 tests, 92% coverage`；或更稳妥地改成“当前覆盖率约 92%，以 pytest 输出为准”，避免每次新增测试都要同步改文档。

### LOW

#### 4. `CLAUDE.md` 文件末尾缺少 newline

- **位置**: `CLAUDE.md:537`
- **问题**: diff 显示 `\ No newline at end of file`。
- **影响**: 低风险样式问题，但会制造无意义 diff。
- **建议修复**: 文件末尾补一个换行。

## Validation Results

| Check | Result |
|---|---|
| Tests + coverage | Pass — `48 passed`, total coverage `92%` |
| Whitespace diff check | Pass — `git diff --check` 无输出 |
| Basic secret scan | Pass — 未发现明显 hardcoded token/private key pattern |
| Python review | Issues found above are behavior/docs consistency, not test failures |

## Follow-up Checklist

- [ ] 修复 `/recent [N]` 参数行为，并补测试。
- [ ] 删除或实现 `/dashboard`。
- [ ] 同步更新测试数量文档。
- [ ] 给 `CLAUDE.md` 补末尾 newline。
- [ ] 修复后重新运行 `pytest --cov=pulse_bot --cov-report=term-missing tests/`。
