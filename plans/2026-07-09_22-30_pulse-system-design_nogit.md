---
tags:
  - plan
  - pulse
  - system-design
created: 2026-07-09
updated: 2026-07-09
status: draft
source: "用户痛点：碎片想法丢失 / 规范化摩擦"
topic: "Pulse System 设计文档"
---

# Pulse System — 设计文档（Design Spec）

> **目的**：解决"洗澡/吃饭/睡前等碎片时间产生的零散想法容易丢失"的痛点。
> **状态**：draft（待用户复核）
> **范围**：仅设计文档本身；实施计划由 writing-plans skill 产出。

---

## 0. 背景与动机

### 用户痛点
在 AI Agent 时代，知识工作者的灵感产生节奏被极大压缩：
- 洗澡时、吃饭时、睡前一刹那，想到"做个 skills 管理器"、"开源几款 skills"、"想优化某流程"
- **当时无法及时变现**，后续想不起来
- 即使随手记到一个新 md 文档，又因 vault 规范化（命名、frontmatter、tags、入库路径、链接）浪费许多时间
- 结果：想法在规范化摩擦中被抛之脑后 → 用户感到惋惜

### 现有机制分析
- `00_Inbox/` 已存在 + `quick-capture.md` 模板（极简 5 行 frontmatter）
- CLAUDE.md 已规定 inbox 7 天清空、分类决定权在用户
- 但实测：**模板极简 ≠ 录入极简**。每次仍需选文件名、补 frontmatter、决入库路径
- 现有 `vault-enhance` skill 负责后期补 Mermaid/Dataview/callout，但需要"已写好的笔记"作为输入
- **缺失一环**：从"动念"到"已写好的笔记"之间的鸿沟

### 核心洞察
**捕获时只剩"打字"一个动作，其余全延后**。所有规范化成本集中在"想法被认定为值得做"的时刻，而非"动念"时刻。

---

## 1. 设计原则

| # | 原则 | 体现 |
|---|---|---|
| 1 | **Zero-friction capture** | 10 秒内完成，含最少 1 个动作（打字发送） |
| 2 | **Defer all standardization** | frontmatter 自动生成、命名自动生成、路径自动选择 |
| 3 | **Git as single source of truth** | 云端 bot + 本地 Mac 都通过 git 同步 |
| 4 | **Atomic thoughts** | 一条想法 = 一个 commit，便于回滚与合并 |
| 5 | **Reversible & safe** | bot 仅能写 `_pulse/` 路径，物理隔离 |
| 6 | **Promote by intent, not by default** | 想法默认保持 pulse 状态，仅在用户主动 promote 时规范化 |

---

## 2. 系统架构

### 2.1 拓扑图

```
┌──────────────────────────────────────────────────────────────────┐
│  捕获端（任何能发 Telegram 的设备）                                │
│  ├─ 手机（Telegram app / iOS 分享面板 → Telegram）               │
│  ├─ Mac 桌面（Telegram desktop / web）                           │
│  └─ 任意浏览器（web.telegram.org）                                │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTPS webhook / long polling
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  云端（VPS）                                                      │
│  ├─ pulse-bot (Python systemd)  ← Telegram Bot                   │
│  ├─ vault git remote (bare)     ← 复用现有 remote + deploy key    │
│  └─ ~/pulse-staging/            ← 临时 commit area                │
└──────────────────────────┬───────────────────────────────────────┘
                           │ git pull (每 5 分钟, launchd)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Mac 本地                                                        │
│  ├─ vault (本地 git repo)       ← 现有 my_obsidian                │
│  │   └─ 00_Inbox/_pulse/        ← Pulse Card 存放点              │
│  ├─ launchd job                 ← 定时 git pull                   │
│  └─ Obsidian                    ← 内嵌 Pulse Dashboard            │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 命名规范

| 名字 | 含义 |
|---|---|
| **Pulse** | 整套系统的代号（"脉搏"——一闪而过的想法） |
| `_pulse/` | vault 中碎片想法的存放目录（前缀下划线表示"非正式归档区"） |
| `inbox/pulse` 分支（备选） | vault git remote 上的专用同步分支（v0.1 不启用，直接 push master） |
| `pulse-bot` | 部署在 VPS 的 Telegram bot 服务名 |
| **Pulse Card** | 一条碎片想法的呈现单位（一个 .md 文件） |

---

## 3. Pulse Card（碎片想法的物理形态）

### 3.1 文件路径与命名

```
00_Inbox/_pulse/YYYY-MM-DD_HHMMSS_<short-slug>.md
```

| 段 | 来源 | 长度限制 |
|---|---|---|
| `YYYY-MM-DD` | UTC 日期 | 固定 |
| `HHMMSS` | UTC 时间 | 固定 |
| `<short-slug>` | 消息前 30 字符 URL-safe 化 | ≤ 50 字符 |

### 3.2 frontmatter 模板（5 字段，全部自动填）

```yaml
---
tags:
  - pulse
  - inbox
created: 2026-07-09T20:23:45Z
source: "telegram:<user_id>"
status: pulse                # 新状态值，仅用于 _pulse/ 目录
raw_text: |                  # 原始捕获内容（不可变）
  想做个 skills 管理器
intent: idea                 # 推测的意图：idea | task | reference | question
captured_at: 2026-07-09T20:23:45Z
---
```

| 字段 | 自动规则 |
|---|---|
| `tags` | 固定 `[pulse, inbox]` |
| `created` / `captured_at` | UTC ISO-8601 |
| `source` | `telegram:<numeric_user_id>` |
| `status` | 固定 `pulse` |
| `raw_text` | 用户原始消息（保留不可变） |
| `intent` | 基于关键字推断（"想做/想"→idea；"要做/需要"→task；"为什么/如何"→question；其他→reference） |

### 3.3 正文结构

```markdown
## <首句作为标题>

> 这是 2026-07-09 20:23 通过 Telegram 捕获的碎片想法。
> 尚未规范化。处理时调用 vault-enhance 或手动编辑。

### 原始消息
<用户原始输入>

### 后续处理
<!-- 在这里由人或 agent 补：tags、链接、关联计划等 -->
```

### 3.4 关键设计原则
- `raw_text` 字段保留**原始未改消息**——所有后期润色在独立 `### 后续处理` 段，不污染原文
- frontmatter 全部自动生成，用户**零输入**
- 文件结构只保证"可读、可检索"，不强制规范化

---

## 4. Pulse Bot（云端服务）

### 4.1 部署形态

| 项 | 规格 |
|---|---|
| OS | 任意 Linux 发行版（Ubuntu 22.04+ 推荐） |
| 运行时 | Python 3.11+ |
| 守护 | systemd（service file in `pulse-bot.service`） |
| 库 | `python-telegram-bot` v20+（v0.1 用 long polling，避免 HTTPS 域名成本） |
| 工作用户 | 独立 system user `pulse-bot`，无 sudo |

### 4.2 命令集

| 命令 | 行为 |
|---|---|
| `/p <text>` 或纯文本 | 创建 Pulse Card（默认模式） |
| `/tags <card-id> <tag>` | 给最近一条卡片追加 tag |
| `/recent [N]` | 列出最近 N 条卡片（手机端验证用） |
| `/promote <card-id>` | 把卡片 promote 成完整笔记 |
| `/dashboard` | 返回 Dashboard 的 Obsidian deep-link |
| `/help` | 命令列表 |

### 4.3 消息预处理

- 去除 `/p` 前缀（如果有）
- 去除前导/尾随空白
- 超长消息（>4000 字）截断 + 提醒
- 自动检测 intent（基于关键字，不强制）

### 4.4 git 推送流程（每条消息触发）

```
1. 写文件到本地 staging area: ~/pulse-staging/00_Inbox/_pulse/<file>
2. git add → git commit -m "pulse: <first 50 chars>"
3. git push origin master
4. 失败重试 3 次（指数退避），仍失败 → 写入 dead-letter 队列
5. 私聊通知 owner
```

---

## 5. 本地同步（Mac 端）

### 5.1 launchd 配置

- 文件：`91_System/93_Scripts/pulse-pull.plist`
- 触发：每 5 分钟（`StartInterval: 300`）
- 命令：`bash 91_System/93_Scripts/pulse-pull.sh`
- 工作目录：`/Users/charliepan/Downloads/my_obsidian`

### 5.2 pull 脚本

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /Users/charliepan/Downloads/my_obsidian
git pull --rebase --autostash 2>>~/Library/Logs/pulse-sync.log
```

### 5.3 冲突处理
- bot 只触碰 `_pulse/` 路径，理论上不冲突
- 防御：pull 时若 `_pulse/` 外有冲突，**不解决不退出**——日志告警 + 用户下次开 Obsidian 时由 agent 提醒

---

## 6. Pulse Dashboard（Obsidian 面板）

### 6.1 文件路径

`91_System/Dashboards/Pulse-Dashboard.md`

### 6.2 内容（3 块 Dataview）

```markdown
---
tags:
  - dashboard
  - pulse
created: 2026-07-09
status: done
type: dashboard
---

# 💡 Pulse Dashboard

> 所有未 promote 的碎片想法。

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

---

## 7. Promote 命令行为

触发 `/promote <card-id>` 时：

1. 读取对应 Pulse Card 的 frontmatter + 正文
2. **进入 Plan-First 流程**：在 `91_System/94_Plans/` 创建计划文件（status: draft）
3. 询问用户：目标文件夹 + domain tag
4. 创建正式笔记（路径由用户决定）
5. 把原 Pulse Card 内容复制到新笔记，结构化扩充：
   - 加正式 frontmatter（domain tags、source、topic）
   - 调用 `vault-enhance` skill（用户已同意的前提下）
6. 原 Pulse Card 文件：
   - status → `archived-pulse`
   - 添加 `promoted_to: [[正式笔记路径]]` 字段
   - 文件移入 `90_Archive/_pulse_archive/`
7. Dashboard 自动反映：列表里这条消失，归档计数 +1

---

## 8. 异常处理

| 场景 | 表现 | 处理 |
|---|---|---|
| Telegram 网络断 | bot 收不到消息 | Telegram 自动重发 |
| VPS 宕机 | 用户发消息无回应 | systemd 自动拉起 |
| git push 失败 | bot 报错到 Telegram | 重试 3 次 + dead-letter + 私聊通知 owner |
| Mac 端 git pull 冲突 | launchd 任务失败 | 写日志，agent 提醒用户 |
| 重复想法 | bot 创建新文件而非合并 | **不自动合并**——碎片阶段合并危险 |
| Bot token 泄露 | 冒充风险 | 环境变量、定期 rotate、审计日志 |

---

## 9. 安全 & 权限

- **bot 仅响应白名单 Telegram user_id**（在 `config.yaml` 配置）
- **bot 仅能写 `_pulse/` 路径**（pre-commit hook 强约束）
- **push 用专用 SSH deploy key**（不与日常 git key 共享）
- **VPS 不持久化消息原文**——commit 后即清理 staging
- **所有操作写日志**：`/var/log/pulse-bot/{access,error,push-retry}.log`

---

## 10. 测试策略

| 层 | 测试类型 | 工具 |
|---|---|---|
| 文件名生成 / slug 化 | 单元测试 | pytest |
| intent 推断 | 单元测试 | pytest |
| git push / pull 模拟 | 集成测试（tmp git repo） | pytest + pyfakefs |
| Telegram 命令解析 | 单元测试 | pytest + mock |
| Bot ↔ Telegram 协议 | E2E | pytest + Telegram test bot token |
| launchd job 行为 | shell 集成测试 | bats |

覆盖率目标：**≥ 80%**（符合项目 testing.md）。

---

## 11. 部署里程碑

### Milestone 1：本地基础设施（不动云端）
- `00_Inbox/_pulse/` 目录创建
- `91_System/Dashboards/Pulse-Dashboard.md`
- `91_System/CURRENT.md` 加入 Pulse 章节
- `CLAUDE.md` 加入 Pulse 规则段
- **commit**：`feat(vault): add pulse card infrastructure`

### Milestone 2：本地同步脚本
- `91_System/93_Scripts/pulse-pull.sh`
- `91_System/93_Scripts/pulse-pull.plist`
- launchd 注册
- **commit**：`feat(vault): add launchd pulse-sync job`

### Milestone 3：VPS 准备
- VPS 安装 Python 3.11+、git、openssh-client
- 生成 bot 专用 SSH key，添加到 vault remote deploy keys
- 创建 `pulse-bot` system user
- **commit**：`docs(vault): document pulse-bot VPS setup`

### Milestone 4：Bot 服务本体
- `91_System/93_Scripts/pulse-bot/` Python 包
  - `bot.py` — 入口 + Telegram 监听
  - `card.py` — Pulse Card 文件生成
  - `git_sync.py` — git add/commit/push 封装
  - `intent.py` — 意图推断
  - `config.py` — 环境变量加载
- `requirements.txt`、`systemd/pulse-bot.service`
- pytest 套件 + CI
- **commit**：`feat(vault): add pulse-bot Python package`

### Milestone 5：部署 + 集成测试
- VPS 上 `git clone vault` + 部署 service
- E2E：发消息 → vault 出现文件 → Mac 端 pull 看到 → Dashboard 渲染
- 监控：systemd 重启 + log rotation
- **commit**：`docs(vault): pulse-bot v0.1 deployment runbook`

### Milestone 6：文档 + 规则沉淀
- CLAUDE.md 加 "Pulse System" 段
- `91_System/91_Templates/pulse-card.md`（结构化模板）
- `91_System/README.md` 描述架构
- `CURRENT.md` 标记 Pulse 上线
- **commit**：`docs(vault): integrate pulse system into CLAUDE.md`

---

## 12. 验收标准（v0.1 Definition of Done）

| # | 标准 | 测量 |
|---|---|---|
| 1 | Telegram 消息 → vault 出现 Pulse Card | E2E + 手工 |
| 2 | 从发送到 Mac 端可看到 ≤ 10 分钟 | launchd 间隔验证 |
| 3 | 一条想法 → 一个 commit，message 含首句预览 | git log 检查 |
| 4 | push 失败 → 3 次重试 + dead-letter 不丢数据 | 故障注入 |
| 5 | Pre-commit hook 阻止 bot 改写 `_pulse/` 外文件 | 单元测试 |
| 6 | Mac 端冲突 → 不自动解决，写日志告警 | 故障注入 |
| 7 | Dashboard 三块 Dataview 全部渲染 | Obsidian 截图 |
| 8 | 测试覆盖率 ≥ 80% | `pytest --cov` |
| 9 | `vhealth-scanner.py` 无新增 broken wikilinks | scanner 报告 |
| 10 | CLAUDE.md 加入 "Pulse System" 段落 | grep 验证 |

---

## 13. 风险登记

| # | 风险 | 等级 | 缓解 |
|---|---|---|---|
| R1 | VPS 倒闭 / 服务商跑路 | 🟡 | bot 代码在 vault 内，换 VPS 重部署 < 30 分钟 |
| R2 | Telegram 政策变化封禁 bot | 🟢 | 多年稳定，bot 账号可换平台 |
| R3 | 1 周后忘了 Pulse Dashboard | 🟡 | CURRENT.md 持续提醒 |
| R4 | 卡片量大，Dataview 慢 | 🟢 | 单条 < 1 KB，1000 条 ≈ 1 MB |
| R5 | git remote 撤销权限 | 🟡 | 单元测试 + push 失败通知 |
| R6 | 误发敏感信息 | 🟡 | 不主动扫描；保留 `git filter-repo` 清理流程文档 |
| R7 | 用户手动改 `_pulse/`，bot 同步冲突 | 🟢 | pre-commit hook 区分身份 |
| R8 | Mac 端 Obsidian 未启动，pull 仍跑 | 🟢 | 期望行为 |

---

## 14. 与现有规则的一致性

| 现有规则 | 是否冲突 | 处理 |
|---|---|---|
| Inbox 7 天清空上限 | ✅ 兼容 | `_pulse/` 有独立 status，不受 7 天约束 |
| Plan-First | ✅ 兼容 | `/promote` 内部触发 Plan 生成 |
| 入库决定权在用户 | ✅ 兼容 | bot 只进 `_pulse/`；分类决定权仍在用户 |
| Commit frequency 高粒度 | ✅ 兼容 | 一条想法 = 一个 commit |
| 归档由用户决策 | ✅ 兼容 | promote 内含归档，但由用户触发 |
| Naming convention v1 | ✅ 兼容 | Pulse Card 属"自由命名"类别 |
| pre-commit hook 检查 broken wikilinks | ✅ 兼容 | Pulse Card 不含 wikilinks |

---

## 15. 范围边界

**v0.1 包含**：bot、git 同步、launchd pull、Dashboard、`/promote`、白名单、权限模型、测试 ≥ 80%

**v0.1 不包含**：
- 语音消息自动转写
- 图片 OCR
- AI 自动归档
- 多用户协作
- 日历/Reminder 联动
- 移动端 Obsidian 同步

---

## 16. 成本估算

| 项 | 成本 |
|---|---|
| VPS | $5/月 |
| Telegram Bot | 免费 |
| Python 库 | 免费 |
| 域名（可选） | $10/年 |
| **合计** | **< $10/月** |

---

## 17. 后续步骤

1. 用户复核本文档
2. 通过后调用 `superpowers:writing-plans` skill 撰写实施计划
3. 按 Milestone 1 → 6 顺序执行