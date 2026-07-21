---
tags:
  - documentation
  - index
created: 2026-07-11
updated: 2026-07-11
status: active
source: "docs/ 完整性审计 v0.1.1"
---

# Pulse Bot 文档索引

> **语言说明**：当前主要文档语种为 **中文**（`setup.md` / `setup-windows.md` / `deployment.md` / `runbook.md` / `usage.md`）。
> 英文社区用户建议用机器翻译 + 校对；如需英文版开 issue 标注。
>
> `README.md` / `README.zh.md` 是仓库入口，**双语文档**。

## 文档地图

```
读者：你作为终端用户
└── usage.md            ← 从这里开始

读者：你作为运维/部署者
├── setup.md            ← VPS 准备 (Python/system user/SSH key)
├── setup-windows.md    ← Windows 端 vault 自动 pull
├── deployment.md       ← 完整部署 + E2E 测试
└── runbook.md          ← 监控 + 故障排查 (F1–F7)

读者：你作为开发者
├── architecture.md     ← 模块依赖 + 关键不变量
├── card-format.md      ← Pulse Card 文件长什么样
└── CONTRIBUTING.md ← 开发上手 + TDD + commit
```

## 读顺序建议

**第一次用**：
1. `README.md`（仓库根）— 5 分钟读项目是什么
2. `usage.md` — 知道作为用户怎么用
3. `deployment.md` — 如果你要部署到 VPS

**部署后排查**：
- 状态异常 → `runbook.md`（按症状找 F 章）
- 路径/文件疑问 → `architecture.md` + `card-format.md`

**参与开发**：
- `CONTRIBUTING.md` 一遍
- 看 `tests/` 看现有测试模式
- 改任何 `pulse_bot/*.py` → 必须 TDD + 调 `python-reviewer` agent review

## 文档维护规则

- 改任何 `pulse_bot/*.py` → 对应的 `docs/` 可能要同步（如改了 config 字段 → setup.md 要更新）
- 文档改动本身**不需要写测试**
- 但**改动 > 50 行** 或新增 doc → 写到 `plans/` 留痕
- 历史归档 plans/ 只读，不改

## 关联规范

- `/.claude/rules/` 项目专属规则（CLAUDE.md 指向）
- `pulse-bot-dev` skill（项目开发工作流）
- `python-testing` skill（pytest 模式）
