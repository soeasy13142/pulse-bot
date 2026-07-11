---
tags:
  - spec
  - plans
  - naming-normalization
created: 2026-07-11
updated: 2026-07-11
status: draft
source: "用户提议'规范化本项目'的子任务：plans/ 文件夹文件名规范化"
topic: "plans/ 目录文件名规范化设计"
---

# plans/ 文件夹文件名规范化设计

> **目的**：让 `plans/` 目录 100% 文件名遵循 `README.md` 定义的命名规范，唯一例外是 `README.md` 本身（命名规范的定义文件）。
> **状态**：draft（待用户复核）
> **范围**：仅 plans/ 文件夹文件名 + 关联强引用同步；其余文件夹、其他仓库留给后续子任务。

---

## 1. 命名规范（已存在于 `plans/README.md`）

```
YYYY-MM-DD_HH-MM_<topic-kebab>_<commit-ref>.md
```

- `<commit-ref>` = 文件首次出现的 commit 哈希（多值用 `-` 连接），或 `nogit`（无对应 commit 时）
- 文件名不含空格，主题段用 `-`，主段间用 `_`
- 文件必须含 YAML frontmatter（`tags` / `created` / `updated` / `status` / `source`）

**唯一例外**：`README.md` 是命名规范的定义文件，**豁免按规范命名**。

---

## 2. 命名映射

| 现名 | → | 新名 | 时间戳来源 |
|---|---|---|---|
| `plans/pulse-system-design.md` | → | `plans/2026-07-09_22-30_pulse-system-design_nogit.md` | 来自该文件 frontmatter `source` 字段 wikilink `[[2026-07-09_22-30_pulse-system-design_ec7217b]]` |
| `plans/pulse-system-implementation-plan.md` | → | `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` | 来自该文件内部 wikilink `[[2026-07-09_22-45_pulse-system-implementation-plan]]` |
| `plans/README.md` | → | （不变） | 例外 |
| `plans/2026-07-11_00-56_pulse-bot-review-fixes_nogit.md` | → | （不变） | 已合规 |

**commit-ref 取 `nogit` 的理由**：项目现状是本仓刚 subtree split 出来，本地有 1 仓但这些历史归档对应 commit 哈希不便核实；与现有 `review-fixes_nogit.md` 保持一致策略。

---

## 3. 引用同步清单（6 处强引用）

### 3.1 `CLAUDE.md`（5 处）

| 行 | 类型 | 操作 |
|---|---|---|
| 57-58 | Project Layout 树形图 | 两个文件名 → 用新名 |
| 228 | DON'T #7 | 两个文件名 → 用新名 + 把规则改为"已按规范重命名，不要再次搬动" |
| 384 | 见 v0.1 状态 | `plans/pulse-system-implementation-plan.md` → 用新名 |
| 388 | v0.2 候选链接 | `plans/pulse-system-implementation-plan.md` §v0.2 → 用新名 |
| 492 | 项目根 `plans/` 段 | "只读，不要修改" → "已按规范重命名完成，不要再次修改历史归档" |
| 534-535 | Related Links | 两个文件名 → 用新名 |

### 3.2 `.claude/skills/pulse-bot-dev/SKILL.md`（2 处，在同一段）

| 行 | 类型 | 操作 |
|---|---|---|
| 161-162 | 文件引用 | 两个文件名 → 用新名 |

### 3.3 `plans/README.md`（1 处规则补丁）

在"规则"小节新增第 6 条：

```markdown
6. **`README.md` 是命名规范定义文件本身，豁免按规范命名** — 它是规范的源头，而不是规范的对象。
```

### 3.4 不动的引用

- `plans/pulse-system-implementation-plan.md` 内部 8 处自引用：**全部**指向 Obsidian vault 路径 `91_System/94_Plans/...`，不是本仓 `plans/` → 不改（属于上一仓 my_obsidian，不在本仓 scope）
- `docs/setup.md` 行 9 / `docs/usage.md` 行 146-147 / 仓库根 `README.md` 行 152：均为 `91_System/94_Plans/...` 路径 → 同上，不改
- `.DS_Store`：系统文件，由项目根 `.gitignore` 覆盖（如未覆盖留待后续子任务，不属本次 scope）

---

## 4. 规则文档同步（CLAUDE.md）

CLAUDE.md 中"项目根 `plans/` 命名规范"段落（行 519-535 范围）原样保留并补充 README 例外：

> **`README.md` 例外**：本目录 `README.md` 是命名规范的定义文件，豁免按规范命名（参见 `plans/README.md` 规则第 6 条）。

---

## 5. 验证 + 回滚

### 5.1 验证步骤

```bash
# 1. 目录结构
ls plans/
# 期望: README.md + 3 个 2026-*-*.md
```

```bash
# 2. 强引用清零检查（强引用已全部改为新名）
grep -rn "pulse-system-design\.md\|pulse-system-implementation-plan\.md" \
     --include="*.md" \
     /Users/charliepan/Downloads/pulse-bot/ \
  | grep -v "/plans/"
# 期望: 零命中（plans/ 外不再出现旧文件名）
```

```bash
# 3. 测试不受影响
pytest --cov=pulse_bot --cov-report=term-missing
# 期望: 40/40 通过，覆盖率维持 92%
```

### 5.2 回滚

```bash
# 一个 commit 回滚全部改动
git revert HEAD~3..HEAD   # 或 git reset --hard HEAD~3（未推时）

# 或逆向操作
git mv plans/2026-07-09_22-30_pulse-system-design_nogit.md plans/pulse-system-design.md
git mv plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md plans/pulse-system-implementation-plan.md
git checkout -- CLAUDE.md .claude/skills/pulse-bot-dev/SKILL.md plans/README.md
```

---

## 6. Commit 粒度

3 个 commit：

1. `chore(plans): rename historical archives to follow naming spec`
2. `docs(pulse-bot): update strong references in CLAUDE.md and SKILL.md`
3. `docs(plans): add README.md exception to naming spec`

---

## 7. 设计决策记录

| 决策 | 选项 | 选定 | 理由 |
|---|---|---|---|
| 历史归档是否重命名 | 保留 / 全部重命名 / 软链接 | **全部重命名** | 用户明文要求"规范各文件文件名" |
| README.md 处理 | 重命名 / 保留 / 副本 | **保留** | 用户答复 + README 是命名规范的定义文件 |
| commit-ref 填法 | nogit / git log / 后查 | **nogit** | 用户答复 + 与现有 `review-fixes_nogit.md` 策略一致 |
| 实施范围 | 最小 / 完整 / 跨仓库 | **完整（仅本仓强引用）** | 用户选 A；规范化的最小完整单元 |
| 是否补 README 例外规则到 README 自身 | 补 / 不补 | **补** | 避免下次再出同样歧义；规范要"自我闭合" |
| 是否补 README 例外规则到 CLAUDE.md | 补 / 不补 | **补** | CLAUDE.md 也描述了 plans/ 命名规范，需同步 |
| 是否处理 `.DS_Store` | 处理 / 留待后续 | **留待后续** | 不属本次 scope；如需清理 → 单独子任务 |
| 是否处理 Obsidian vault 路径弱引用 | 处理 / 留待后续 | **留待后续** | 那是上一仓职责，不在本仓 scope |

---

## 8. 范围之外（留给后续 brainstorm 子任务）

- 其他文件夹的文件名 / 内容规范化（CLAUDE.md、README.md、.claude/、docs/、tests/、pulse_bot/ 等）
- `.DS_Store` 是否清理
- plans/README.md 的内容是否继续演进（例外的条款、规则的语言精确化等）
- 整个项目的"规范化"路线图（建立 metric、持续合规检查等）
- 跨仓库（my_obsidian vault）的归档副本如何与本仓 plans/ 双向同步
