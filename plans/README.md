---
tags:
  - plan
  - meta
  - naming-spec
created: 2026-07-08
updated: 2026-07-11
status: done
source: "plans directory naming convention, originally from my_obsidian vault"
topic: "plans/ 文件夹命名规范"
---

# 94_Plans — 计划文件存放区

本目录专门存放**针对本 Obsidian 知识库的计划文件**（审计计划、补全计划、重构计划、迁移计划等）。
由用户于 2026-07-06 设立，作为以后所有计划文件的统一存放点。

## 命名规范

```
YYYY-MM-DD_HH-MM_<topic-kebab>_<commit-ref>.md
```

| 段 | 说明 | 示例 |
|---|---|---|
| `YYYY-MM-DD_HH-MM` | 最后修改日期+时分（Obsidian 文件列表按此排序） | `2026-07-07_14-03` |
| `<topic-kebab>` | 简短问题/主题，kebab-case | `hcip-hcia-bidirectional-links` |
| `<commit-ref>` | 针对的提交哈希（多个用 `-` 连接）；非提交相关用 `nogit` | `7c65964-7186aa2` |

> 编写日期保存在 frontmatter `created:`，最后修改日期同步写入 `updated:` 与文件名前缀；同分钟内按文件名次序排列。

**完整示例**：`2026-07-06_19-28_hcip-hcia-bidirectional-links_7c65964-7186aa2.md`

## 规则

- 文件名不含空格，主题段用 `-`，主段间用 `_`。
- 每个计划文件必须含 YAML frontmatter（`tags` / `created` / `status` / `source` 等，遵循 `CLAUDE.md` 的 frontmatter schema）。
- frontmatter 的 `source` 字段写明针对的提交 / 起因。
- 计划状态：`draft`（待确认）→ `in-progress`（执行中）→ `done`（已完成）/ `archived`（归档）。
- 计划被确认并执行后，更新 frontmatter `status` 与 `updated`，不要删除文件（保留历史）。

6. **`README.md` 是命名规范定义文件本身，豁免按规范命名** — 它是规范的源头，而不是规范的对象。
