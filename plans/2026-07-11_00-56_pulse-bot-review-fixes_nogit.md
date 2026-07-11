---
tags:
  - plan
  - pulse
  - code-review
  - pulse-bot
created: 2026-07-11
updated: 2026-07-11
status: done
source: "code review of 91_System/93_Scripts/pulse-bot/ (2026-07-11)"
topic: "修复 pulse-bot code review 发现的 8 个 critical/high 问题"
---

# Pulse-Bot Code Review Fixes — Plan

> **状态**：draft（待用户确认后改 `in-progress`）
> **来源**：2026-07-11 对 `91_System/93_Scripts/pulse-bot/` 的 medium-effort code review
> **范围**：本次审查的 8 个 CONFIRMED primary findings（top-8）。次级 8 项作为 v0.2 候选，不在本 plan scope。

## Goal

消除 2026-07-11 code review 报告的 8 个 confirmed bug / 部署阻塞，按阶段推进，每类修复单独一次 commit。

## Architecture / Approach

按 bug 性质聚类成 4 个 phase，每个 phase 内每个修复点 = 1 个 commit：

| Phase | 主题 | commit 数 |
|---|---|---|
| 1 | Unblock Deployment（部署文档与 systemd 路径） | 2 |
| 2 | Security Hardening（授权校验） | 2 |
| 3 | Data Integrity（YAML / 文件冲突 / 配置兜底） | 3 |
| 4 | UX Honesty（"Will retry" 文案修正） | 1 |
| **合计** | | **8** |

每个 commit 必须自洽：现有测试通过 + 新增针对性测试覆盖。

## Tech Stack / Constraints

- 沿用现有 Python 3.11+ / pytest / python-telegram-bot v20+ 栈（无新依赖）
- 测试覆盖率保持 ≥ 80%（项目既有水准）
- Commit message 格式遵循 CLAUDE.md `git-workflow`：`fix(<scope>): <description>`
- 本次不引入新外部库；多行 YAML 修复用 `str.replace("\n", "\n  ")` 即可

## File Map

涉及修改文件清单（按 phase 分组）：

### Phase 1
- `91_System/93_Scripts/pulse-bot/systemd/pulse-bot.service`（line 13）
- `91_System/93_Scripts/pulse-bot/docs/deployment.md`（line 65）

### Phase 2
- `91_System/93_Scripts/pulse-bot/pulse_bot/config.py`（line 33-34）
- `91_System/93_Scripts/pulse-bot/pulse_bot/bot.py`（line 90, recent_command 函数体）
- `91_System/93_Scripts/pulse-bot/tests/test_config.py`（新增 3 个测试）
- `91_System/93_Scripts/pulse-bot/tests/test_bot.py`（新增 1 个测试）

### Phase 3
- `91_System/93_Scripts/pulse-bot/pulse_bot/card.py`（line 29-32 build_card_path；line 50-51 render_card）
- `91_System/93_Scripts/pulse-bot/pulse_bot/config.py`（line 28 Path 包装）
- `91_System/93_Scripts/pulse-bot/tests/test_card.py`（新增 2 个测试）
- `91_System/93_Scripts/pulse-bot/tests/test_config.py`（新增 1 个测试）

### Phase 4
- `91_System/93_Scripts/pulse-bot/pulse_bot/bot.py`（line 87）
- `91_System/93_Scripts/pulse-bot/tests/test_bot.py`（line 158-171 修正断言）

---

## Phase 1 — Unblock Deployment

解决"按 deployment.md 步骤 1-7 跑下来服务无法启动"的两个前置阻塞。

### Commit 1.1 — `fix(systemd): correct ExecStart path to match deployment.md`

**问题**（CRITICAL Finding #1）：
- `systemd/pulse-bot.service:13`：`ExecStart=/opt/pulse-bot/.venv/bin/python`
- `docs/deployment.md:49-51`：`cd /opt/pulse-bot/app && python3.11 -m venv .venv` → 实际生成 `/opt/pulse-bot/app/.venv/bin/python`
- 结果：`systemctl start pulse-bot` 找不到 python 二进制

**修复**：把 systemd ExecStart 改为 `/opt/pulse-bot/app/.venv/bin/python -m pulse_bot.bot`

**验证**：
```bash
grep ExecStart systemd/pulse-bot.service
# 期望: ExecStart=/opt/pulse-bot/app/.venv/bin/python -m pulse_bot.bot
```

### Commit 1.2 — `fix(docs): correct .env.example source path in deployment.md`

**问题**（CRITICAL Finding #2）：
- `docs/deployment.md:65`：`cp /opt/pulse-bot/app/.env.example /opt/pulse-bot/.env`
- 实际 `.env.example` 位于 `pulse_bot/.env.example` 子目录，部署后应在 `/opt/pulse-bot/app/pulse_bot/.env.example`

**修复**：把 cp 源路径改为 `pulse_bot/.env.example`（相对路径更稳）

**验证**：grep `\.env\.example` docs/deployment.md 期望看到 `pulse_bot/.env.example`

---

## Phase 2 — Security Hardening

### Commit 2.1 — `fix(config): validate allowed_user_ids is non-empty list`

**问题**（CRITICAL Finding #3 — 2026-07-11 核实修正）：
- `pulse_bot/config.py:33-34`：`if not config["allowed_user_ids"]: raise` 是真值检查，不是类型检查
- YAML 写成 `allowed_user_ids: 12345`（int）：`not 12345` 是 `False`，通过；首条消息 `_is_authorized(user_id, 12345)` 抛 `TypeError: argument of type 'int' is not iterable`（int 不是 iterable，`in` 拒绝）
- YAML 写成 `allowed_user_ids: "12345"`（str）：`not "12345"` 是 `False`，通过；首条消息 `_is_authorized(user_id, "12345")` 抛 `TypeError: 'in <string>' requires string as left operand, not int`（int `in` str 不做子串匹配，Python 拒绝跨类型 in — 计划 v0 误判为"子串匹配越权"，实测并非越权）
- **真实故障模式**：两条 YAML 都会让 bot 在首条消息时抛 TypeError 把 handler 打挂，是稳定性 bug 而非越权 bug。严重性仍 CRITICAL（部署即坏），但分类应为"Stability / Crash-on-first-message"，不是"Authorization Bypass"。

**修复**（`pulse_bot/config.py`）：
```python
# 原：
if not config["allowed_user_ids"]:
    raise ValueError("allowed_user_ids must be set")
# 改为：
ids = config["allowed_user_ids"]
if not isinstance(ids, list) or not ids or not all(isinstance(x, int) for x in ids):
    raise ValueError("allowed_user_ids must be a non-empty list[int]")
```

同时给 `pulse_bot/bot.py:_is_authorized` 加防御：
```python
def _is_authorized(user_id: int, allowed_ids) -> bool:
    if not isinstance(allowed_ids, list):
        return False
    return user_id in allowed_ids
```

**新增测试**（`tests/test_config.py`）：
- `test_load_config_allowed_user_ids_int_rejected`：YAML 写 `allowed_user_ids: 12345` → 期望 `pytest.raises(ValueError)`
- `test_load_config_allowed_user_ids_str_rejected`：YAML 写 `allowed_user_ids: "12345"` → 期望 `pytest.raises(ValueError)`
- `test_load_config_allowed_user_ids_empty_list_rejected`：YAML 写 `allowed_user_ids: []` → 期望 `pytest.raises(ValueError)`（覆盖原行为 + 新增"空列表"边界）

### Commit 2.2 — `fix(bot): gate /recent behind _is_authorized`

**问题**（CRITICAL Finding #4）：
- `pulse_bot/bot.py:90` `recent_command` 函数体没有调用 `_is_authorized`
- `_recent_cards` 是模块级 list，跨用户共享；非白名单用户发 `/recent` 可读到授权用户抓到的卡片摘要

**修复**（`pulse_bot/bot.py:90-100`）：
```python
async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List recent Pulse Cards."""
    config = load_config()
    if not _is_authorized(update.effective_user.id, config["allowed_user_ids"]):
        await update.message.reply_text("Unauthorized. Ask the owner to add your user_id.")
        return
    if not _recent_cards:
        ...
```

**新增测试**（`tests/test_bot.py`）：
- `test_recent_command_unauthorized`：mock 99999 用户，调 `/recent`，期望回复含 `"Unauthorized"`

---

## Phase 3 — Data Integrity

### Commit 3.1 — `fix(card): render multi-line text as valid YAML block scalar`

**问题**（HIGH Finding #5）：
- `pulse_bot/card.py:50-51`：`raw_text: |\n  {text}`，只对首行加 2 空格缩进
- 后续行（`\n` 后面的内容）在 0 缩进 → YAML 解析器认为块结束 → 把后续行当成顶层 key → frontmatter 损坏

**修复**（`pulse_bot/card.py:render_card`）：
```python
# 原：
raw_text: |
  {text}
# 改为：
raw_text: |
  {text.replace(chr(10), chr(10) + "  ")}
```

即对每一行加 2 空格前缀（含首行），确保整个 block scalar 内的所有行缩进一致。

**新增测试**（`tests/test_card.py`）：
- `test_render_card_multiline_yaml_parsable`：构造多行 text，调用 `render_card`，用 `yaml.safe_load` 解析输出卡的 frontmatter 段，期望成功且 `raw_text` 含全部行

### Commit 3.2 — `fix(card): prevent same-second filename collision`

**问题**（HIGH Finding #6）：
- `pulse_bot/card.py:29`：`ts = when.strftime("%Y-%m-%d_%H%M%S")` 只精确到秒
- 同秒内两条消息 slug 相同时 `full_path.write_text(...)`（bot.py:63）静默覆盖，无 `exist_ok` 检查

**修复**（`pulse_bot/card.py:build_card_path`）：
```python
import uuid
...
ts = when.strftime("%Y-%m-%d_%H%M%S")
suffix = uuid.uuid4().hex[:6]
filename = f"{ts}_{suffix}_{slug}.md"
```

方案选择：用 UUID 后缀（6 hex）保证全局唯一，不依赖毫秒精度（避免同一毫秒内的极端冲突）

**新增测试**（`tests/test_card.py`）：
- `test_build_card_path_no_collision_same_text_same_instant`：同一 `when` + 同一 text 调 `build_card_path` 两次（实际生产路径加 uuid 后缀不同），期望两个 path 不相等

### Commit 3.3 — `fix(config): defensive Path conversion when YAML nulls vault_repo_dir`

**问题**（HIGH Finding #7）：
- `pulse_bot/config.py:28`：`Path(config["vault_repo_dir"])`
- YAML 写 `vault_repo_dir:`（空值）→ safe_load 出 `None` → `Path(None)` 抛 `TypeError`
- 环境变量默认值 `Path(os.getenv("VAULT_REPO_DIR", "/opt/pulse-bot/vault"))`（line 17）已被 `config.update` 覆盖

**修复**（`pulse_bot/config.py:23-28`）：
```python
if config_path.exists():
    with open(config_path) as f:
        yaml_config = yaml.safe_load(f) or {}
    config.update(yaml_config)
    # Defensive: YAML null → fall back to env/default; otherwise wrap as Path
    vrd = config["vault_repo_dir"]
    if vrd is None:
        config["vault_repo_dir"] = Path(os.getenv("VAULT_REPO_DIR", "/opt/pulse-bot/vault"))
    else:
        config["vault_repo_dir"] = Path(vrd)
```

**新增测试**（`tests/test_config.py`）：
- `test_load_config_vault_repo_dir_null_falls_back_to_env`：YAML 写 `vault_repo_dir:`，环境变量设 `VAULT_REPO_DIR=/tmp/foo`，期望 `config["vault_repo_dir"] == Path("/tmp/foo")`

---

## Phase 4 — UX Honesty

### Commit 4.1 — `fix(bot): replace misleading "Will retry." with honest message`

**问题**（MEDIUM Finding #8）：
- `pulse_bot/bot.py:87`：`"⚠ Saved locally but push failed. Will retry."`
- 代码里没有任何重试队列/定时器/后台任务（git_sync.py 内的 3 次重试已是最后一次）

**修复**（`pulse_bot/bot.py:87`）：
```python
# 原：
await update.message.reply_text("⚠ Saved locally but push failed. Will retry.")
# 改为：
await update.message.reply_text(
    "⚠ Saved locally but push failed. "
    "Run `bash pulse-pull.sh` on VPS or check docs/runbook.md F2."
)
```

**修改测试**（`tests/test_bot.py:158-171`）：
- 更新 `test_handle_message_push_fails` 的断言：从 `assert "push failed" in msg or "⚠" in msg` 改为 `assert "push failed" in msg and "bash pulse-pull.sh" in msg`

---

## Verification Strategy

每个 commit 完成后立即跑：
```bash
python3 -m pytest 91_System/93_Scripts/pulse-bot/tests/ -v
```

全部 phase 完成后：
```bash
python3 -m pytest 91_System/93_Scripts/pulse-bot/tests/ --cov=pulse_bot --cov-report=term-missing
# 期望：覆盖率 ≥ 80%，全部测试通过
```

人工冒烟测试（可选，有 VPS 时）：
1. 按 deployment.md 步骤 1-7 走一遍，验证 systemd 能启动
2. 发 4 条 Telegram 消息（含多行 / 含中文 / 含问号）→ 验证 Pulse Card 渲染正常
3. 故意制造 push 失败 → 验证收到诚实文案

## Risks & Considerations

1. **commit 顺序敏感**：Phase 1 部署修复应在 Phase 2-4 之前；否则新代码无法在生产验证
2. **测试 isolation**：`_recent_cards` 是模块全局，Phase 2.2 新增测试需在 setUp/tearDown 清空（参考现有 `test_recent_command_with_cards` 模式）
3. **YAML 修复回归风险**：test_card.py 现有测试只检查子串，不解析 YAML；Phase 3.1 加 `yaml.safe_load` 验证避免未来退化
4. **多行缩进边界**：若 text 末尾带 `\n`，`text.replace("\n", "\n  ")` 会给末尾空行加缩进，YAML 解析时 trailing blank lines 通常无害；测试需覆盖带 trailing newline 的输入
5. **UUID 后缀长度**：6 hex = 24 bit = ~1677 万组合，每秒同秒内冲突概率忽略；但极端情况下仍可能；本方案接受此风险

## 与 v0.2 拆分的衔接

按 [[pulse-v1-standalone-repo-reminder|memory]], pulse-bot 计划在 E2E 实跑后拆为 standalone repo。本次 8 个 fix 在 vault 内修复后再 split；split 时：
- `systemd/` + `docs/deployment.md` + `pulse_bot/.env.example` 一起搬到 standalone repo
- standalone repo 继承已修代码，避免带着 bug 公开化

---

## Out of Scope（v0.2 候选，等本次 review 完成后再起 plan）

- `bot.py:97` `/recent N` 文档承诺支持 N 但代码硬编码 `[:10]`
- `bot.py:109/110` `/promote` 与 `/dashboard` 在 `/help` 中广告但 `main()` 无对应 `CommandHandler`
- `bot.py:120-123` `LOG_LEVEL` 环境变量读取后从未生效
- `bot.py:75-87` `_recent_cards.insert` 在 success 判断之前执行，与 push 失败回复自相矛盾
- `pulse_bot/.gitignore` 只排除 `.env`（5 字节），缺 `__pycache__/` `.venv/` `.pytest_cache/` `.coverage`
- `bot.py:30` `handle_message` 58 行 > 项目公约 50 行
- `bot.py:35/66` `load_config()` 与 `GitSync(...)` 每条消息重建；`bot.py:72` 阻塞 `commit_and_push` 直接在 async handler 内同步执行
- `bot.py:71` / `bot.py:98` / `card.py:39` 首行预览逻辑三处分歧（limit 50/40/80，strip 行为不一致）

---

## Decision Points（需用户在 `status: in-progress` 前确认）

1. **commit 顺序**：建议按 Phase 1 → 2 → 3 → 4 顺序提交。是否调整？
2. **Phase 3.2 冲突修复方案**：用 UUID 后缀 vs 毫秒 + 计数器。倾向 UUID（无状态、不需要持久化计数器），是否同意？
3. **Phase 4.1 新文案具体措辞**：上面给了建议文案，是否调整？
4. **测试覆盖率目标**：维持 80% 还是提升到 90%（本次新增 6 个测试应能保住 80% 基线）？

---

> **下一步**：用户确认上述 decision points 后，将本 plan 改 `status: in-progress`，按 phase 推进。每个 phase 完成时更新 frontmatter `status:` + `updated:`，最后全部完成时改 `status: done`。