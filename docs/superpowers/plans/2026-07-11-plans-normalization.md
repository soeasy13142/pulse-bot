# plans/ 文件夹文件名规范化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `plans/` 目录下 100% 文件名遵循 `plans/README.md` 定义的命名规范，唯一例外是 `README.md` 本身；并同步所有本仓强引用 + 在规范文档中显式记录 README 例外条款。

**Architecture:** 4 个 task 按"数据迁移 → 引用更新 → 规则补丁 → 整体验证"流水线。每个 task 收尾一个 commit，commit 粒度符合 SPEC §6。

**Tech Stack:** git（仅 rename / commit / log）、grep（引用同步验证）、pytest（确认改动未影响测试）。

## Global Constraints

| 约束 | 值 | 出处 |
|---|---|---|
| 命名规范 | `YYYY-MM-DD_HH-MM_<topic-kebab>_<commit-ref>.md` | `plans/README.md` |
| commit-ref 取值 | `nogit`（与现有 review-fixes 文件一致策略） | User decision (SPEC §7) |
| 例外 | `plans/README.md` 是规范定义文件本身，豁免按规范命名 | User decision (SPEC §7) |
| Commit 类型前缀 | `chore` / `docs` | SPEC §6 |
| 改动范围 | 仅本仓；my_obsidian 仓库路径不在本仓 scope | SPEC §3.4 |
| 切勿动 | `.DS_Store`（系统文件，不属本次 scope） | SPEC §3.4 |

## 警示（实施时遇到立即停下）

实施中如发现 SPEC 之外的异常链接/文本（例如 CLAUDE.md 第 496 行指向不存在的 `plans/2026-07-11_01-05_plans-naming-spec_nogit.md`，应实际指向 `plans/README.md`），**停下 AskUserQuestion**，不要纳入本次 commit；除非用户明确批准。

---

### Task 1：重命名 plans/ 下 2 个历史归档

**Files:**
- Rename: `plans/pulse-system-design.md` → `plans/2026-07-09_22-30_pulse-system-design_nogit.md`
- Rename: `plans/pulse-system-implementation-plan.md` → `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md`

**Consumes:** 现存的 2 个历史归档（含完整 frontmatter + 内容）
**Produces:** 2 个规范命名的新文件路径；旧路径消失

- [ ] **Step 1: 验证源文件与 frontmatter**

读取 2 个源文件，确认 frontmatter 完整（tags / created / updated / status / source）、确认无外部强引用指向它们（除已知的 7 处之外）。

```bash
ls -la plans/pulse-system-design.md plans/pulse-system-implementation-plan.md
head -15 plans/pulse-system-design.md
head -15 plans/pulse-system-implementation-plan.md
```

预期：2 个文件均存在；frontmatter 包含 `created: 2026-07-09`；source 字段分别含 `[[2026-07-09_22-30_pulse-system-design_ec7217b]]` 和 `[[2026-07-09_22-45_pulse-system-implementation-plan]]`。

- [ ] **Step 2: 重命名第 1 个文件**

```bash
cd /Users/charliepan/Downloads/pulse-bot
git mv plans/pulse-system-design.md plans/2026-07-09_22-30_pulse-system-design_nogit.md
```

预期：git 自动识别为 rename，无冲突输出。

- [ ] **Step 3: 重命名第 2 个文件**

```bash
cd /Users/charliepan/Downloads/pulse-bot
git mv plans/pulse-system-implementation-plan.md plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md
```

预期：git 自动识别为 rename，无冲突输出。

- [ ] **Step 4: 验证目录结构**

```bash
cd /Users/charliepan/Downloads/pulse-bot
ls plans/
git status --short
```

预期：
- `plans/` 下 4 个文件：`README.md`、`2026-07-09_22-30_pulse-system-design_nogit.md`、`2026-07-09_22-45_pulse-system-implementation-plan_nogit.md`、`2026-07-11_00-56_pulse-bot-review-fixes_nogit.md`
- `git status` 显示 2 个 rename：`plans/pulse-system-design.md → plans/2026-07-09_22-30_pulse-system-design_nogit.md` 和 `plans/pulse-system-implementation-plan.md → plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md`
- 没有未追踪的 plans/ 文件

- [ ] **Step 5: Commit 重命名**

```bash
cd /Users/charliepan/Downloads/pulse-bot
git commit -m "chore(plans): rename historical archives to follow naming spec

Rename plans/pulse-system-design.md and plans/pulse-system-implementation-plan.md
to the YYYY-MM-DD_HH-MM_<topic>_nogit.md format defined by plans/README.md.

Refs: docs/superpowers/specs/2026-07-11-plans-normalization-design.md §2"
```

预期：commit 创建成功；git log 显示新 HEAD。

---

### Task 2：同步 7 处强引用（CLAUDE.md 5 处 + SKILL.md 2 处）

**Files:**
- Modify: `CLAUDE.md`（行 57-58、228、384、388、492，共 5 处）
- Modify: `.claude/skills/pulse-bot-dev/SKILL.md`（行 161-162，共 2 处）

**Consumes:** 重命名后的 2 个新文件名
**Produces:** 所有引用 plans/ 下原名的位置都改为新名；不存在外部 docs/ 引用（仅本仓强引用 7 处）

- [ ] **Step 1: 定位所有强引用位置（行号可能因人而异，必须重核）**

```bash
cd /Users/charliepan/Downloads/pulse-bot
grep -n "pulse-system-design\.md\|pulse-system-implementation-plan\.md" \
     --include="*.md" -r . | grep -v "^./plans/"
```

预期：每个命中行前都有文件路径 + 行号，如 `./CLAUDE.md:57`、`.claude/skills/pulse-bot-dev/SKILL.md:161`。记录精确行号。

如果命中数 ≠ 7（即不等于 CLAUDE.md 5 + SKILL.md 2），**停下**：可能 spec 没覆盖到所有点，向用户报告。

- [ ] **Step 2: 更新 CLAUDE.md 行 57-58（Project Layout 树形图）**

打开 `CLAUDE.md`，定位到行 57-58，将：

```markdown
    ├── pulse-system-design.md
    └── pulse-system-implementation-plan.md
```

替换为：

```markdown
    ├── 2026-07-09_22-30_pulse-system-design_nogit.md
    └── 2026-07-09_22-45_pulse-system-implementation-plan_nogit.md
```

- [ ] **Step 3: 更新 CLAUDE.md 行 228（DON'T #7）**

定位到 DON'T #7 段，将：

```markdown
   - `plans/pulse-system-design.md` 和 `plans/pulse-system-implementation-plan.md` 是 v0.1 历史归档, **只读**
   - 历史归档引用 → 用相对路径, 不要搬动 / 删除
```

替换为：

```markdown
   - `plans/2026-07-09_22-30_pulse-system-design_nogit.md` 和 `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` 是 v0.1 历史归档, **只读**
   - 历史归档引用 → 用相对路径, 不要搬动 / 删除
   - 这两个文件已按命名规范重命名完成，不要再次搬动
```

- [ ] **Step 4: 更新 CLAUDE.md 行 384、388（v0.1 状态 / v0.2 候选引用）**

定位到行 384 与 388，分别将：

```markdown
See `plans/pulse-system-implementation-plan.md` for full v0.1 status.
```

```markdown
Candidates (see `plans/pulse-system-implementation-plan.md` §v0.2):
```

替换为：

```markdown
See `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` for full v0.1 status.
```

```markdown
Candidates (see `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` §v0.2):
```

- [ ] **Step 5: 更新 CLAUDE.md 行 492（项目根 plans/ 段）**

定位到行 492，将：

```markdown
- **项目根 `plans/`**: `pulse-system-design.md` 和 `pulse-system-implementation-plan.md` 是 v0.1/v0.2 历史归档 → **只读**, 不要修改
```

替换为：

```markdown
- **项目根 `plans/`**: `2026-07-09_22-30_pulse-system-design_nogit.md` 和 `2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` 是 v0.1/v0.2 历史归档 → **只读**, 不要修改
```

- [ ] **Step 6: 更新 .claude/skills/pulse-bot-dev/SKILL.md 行 161-162**

打开 `.claude/skills/pulse-bot-dev/SKILL.md`，定位到行 161-162，将：

```markdown
- `plans/pulse-system-design.md` — Design decisions
- `plans/pulse-system-implementation-plan.md` — Implementation history
```

替换为：

```markdown
- `plans/2026-07-09_22-30_pulse-system-design_nogit.md` — Design decisions
- `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` — Implementation history
```

- [ ] **Step 7: 验证强引用清零**

```bash
cd /Users/charliepan/Downloads/pulse-bot
grep -n "pulse-system-design\.md\|pulse-system-implementation-plan\.md" \
     --include="*.md" -r . | grep -v "^./plans/"
grep -n "pulse-system-implementation-plan\.md\|pulse-system-design\.md" \
     --include="*.md" -r . | grep -v "^./plans/"
```

预期：两条命令均零输出（除可能异常发现的 stale link，详见"警示"章节）。

如果仍有命中，停下：要么是 SPEC §3.4 中明确不动的 Obsidian 路径（grep `91_System/94_Plans` 确认），要么是 SPEC 未覆盖的新发现。

- [ ] **Step 8: Commit 引用同步**

```bash
cd /Users/charliepan/Downloads/pulse-bot
git add CLAUDE.md .claude/skills/pulse-bot-dev/SKILL.md
git commit -m "docs(pulse-bot): update strong references to renamed archives

CLAUDE.md and pulse-bot-dev SKILL.md referenced plans/pulse-system-design.md
and plans/pulse-system-implementation-plan.md by their old names. Update
those 7 spots to use the new spec-compliant filenames.

Refs: docs/superpowers/specs/2026-07-11-plans-normalization-design.md §3"
```

预期：commit 创建成功；git log 显示新 HEAD。

---

### Task 3：补 README.md 例外条款（plans/README.md + CLAUDE.md）

**Files:**
- Modify: `plans/README.md`（"规则"小节末尾新增第 6 条）
- Modify: `CLAUDE.md`（"项目根 plans/ 命名规范"段下新增 README 例外段）

**Consumes:** 已完成的命名规范 + README 例外决策（SPEC §7 决策 2）
**Produces:** 规范定义文件自身闭合 — 未来不会再出现"README 自身要不要规范化"的歧义

- [ ] **Step 1: 在 plans/README.md "规则"小节末尾新增 README 例外**

读取 `plans/README.md` 的"规则"小节（行 36-40），定位到现有 5 条规则之后，将：

```markdown
- 计划被确认并执行后，更新 frontmatter `status` 与 `updated`，不要删除文件（保留历史）。
```

替换为：

```markdown
- 计划被确认并执行后，更新 frontmatter `status` 与 `updated`，不要删除文件（保留历史）。

6. **`README.md` 是命名规范定义文件本身，豁免按规范命名** — 它是规范的源头，而不是规范的对象。
```

- [ ] **Step 2: 在 CLAUDE.md "项目根 plans/ 命名规范" 段下新增 README 例外**

读取 CLAUDE.md 行 494-515（"项目根 plans/ 命名规范"段 + "规则"列表），定位到第一个"###"小节标题（"### 何时创建 plan"）之前，将：

```markdown
**规则**：

- 文件名不含空格，主题段用 `-`，主段间用 `_`。
- 每个计划文件必须含 YAML frontmatter（`tags` / `created` / `updated` / `status` / `source` 等）。
- `created` / `updated` 同步写入 frontmatter 与文件名前缀。
- `source` 字段写明针对的提交 / 起因。
- 计划状态：`draft`（待确认）→ `in-progress`（执行中）→ `done`（已完成）/ `archived`（归档）。
- 计划被确认并执行后，更新 frontmatter `status` 与 `updated`，**不要删除文件**（保留历史）。

### 何时创建 plan
```

替换为：

```markdown
**规则**：

- 文件名不含空格，主题段用 `-`，主段间用 `_`。
- 每个计划文件必须含 YAML frontmatter（`tags` / `created` / `updated` / `status` / `source` 等）。
- `created` / `updated` 同步写入 frontmatter 与文件名前缀。
- `source` 字段写明针对的提交 / 起因。
- 计划状态：`draft`（待确认）→ `in-progress`（执行中）→ `done`（已完成）/ `archived`（归档）。
- 计划被确认并执行后，更新 frontmatter `status` 与 `updated`，**不要删除文件**（保留历史）。

**README 例外**：本目录下 `README.md` 是命名规范的**定义文件**本身，豁免按本规范命名（参见 `plans/README.md` 规则第 6 条）。它是规范的源头，而不是规范的对象。

### 何时创建 plan
```

- [ ] **Step 3: 验证规则同步**

```bash
cd /Users/charliepan/Downloads/pulse-bot
grep -n "README.md" plans/README.md | head -10
grep -n "README 例外\|豁免\|README.md 是命名" CLAUDE.md
```

预期：
- `plans/README.md` 中能找到"豁免按规范命名"或"README.md 是命名规范定义文件本身"
- `CLAUDE.md` 中能找到 "**README 例外**"

- [ ] **Step 4: Commit 规则补丁**

```bash
cd /Users/charliepan/Downloads/pulse-bot
git add plans/README.md CLAUDE.md
git commit -m "docs(plans): document README.md exception in both spec sources

Make the README.md naming-exemption explicit in two places:
- plans/README.md rule §6 (canonical source)
- CLAUDE.md '项目根 plans/ 命名规范' 段 (project-wide reference)

Prevents the same ambiguity from arising again on the next plan file review.

Refs: docs/superpowers/specs/2026-07-11-plans-normalization-design.md §7 (decision 2 + 6)"
```

预期：commit 创建成功；git log 显示新 HEAD。

---

### Task 4：整体验证

**Files:** 无（只读验证）
**Consumes:** 前 3 个 task 完成的 3 个 commit
**Produces:** 验收报告；任何残留问题抛回用户

- [ ] **Step 1: 目录结构验证**

```bash
cd /Users/charliepan/Downloads/pulse-bot
ls -la plans/
```

预期输出：

```
README.md
2026-07-09_22-30_pulse-system-design_nogit.md
2026-07-09_22-45_pulse-system-implementation-plan_nogit.md
2026-07-11_00-56_pulse-bot-review-fixes_nogit.md
```

- [ ] **Step 2: 全仓强引用最终清零**

```bash
cd /Users/charliepan/Downloads/pulse-bot
grep -rn "pulse-system-design\.md\|pulse-system-implementation-plan\.md" \
     --include="*.md" . | grep -v "^./plans/"
```

预期：零输出。

- [ ] **Step 3: 测试套件验证（确认 .md 改动不影响代码）**

```bash
cd /Users/charliepan/Downloads/pulse-bot
pytest --cov=pulse_bot --cov-report=term-missing
```

预期：40/40 测试通过，覆盖率维持 92%（与基线一致）。

- [ ] **Step 4: 三个新 commit 列表**

```bash
cd /Users/charliepan/Downloads/pulse-bot
git log --oneline -4
```

预期输出格式（commit hash 因时而异）：

```
<HEAD-hash> docs(plans): document README.md exception in both spec sources
<prev-hash> docs(pulse-bot): update strong references to renamed archives
<prev-hash> chore(plans): rename historical archives to follow naming spec
<prev-hash> docs(plans): write plans/ normalization design spec
```

- [ ] **Step 5: 验收报告**

向用户报告：

- ✅ / ❌ Task 1：重命名 2 个文件
- ✅ / ❌ Task 2：同步 7 处强引用（CLAUDE.md 5 + SKILL.md 2）
- ✅ / ❌ Task 3：补 README 例外条款（plans/README.md + CLAUDE.md）
- ✅ / ❌ Task 4：最终验证（4 条检查 + commit 列表）
- 任何异常 / 残留：列出

如验收全部 ✅，本次 brainstorm 子任务完成，告知用户"plans/ 文件夹 100% 合规"，后续子任务待用户发话开始。
