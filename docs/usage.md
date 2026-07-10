# Pulse Bot — User Guide

> 写给"作为终端用户的你"的快速上手指南。
> 深度使用笔记（含场景、反思、FAQ）见 `40_Life/44_Tech-Thoughts/TECH_Pulse-Bot-Usage.md`。
> 部署/运维见 [[deployment.md]] / [[runbook.md]]。

## 它是什么

一个 Telegram bot，让你**在 10 秒内**把任何碎片想法写到 Obsidian vault 里——不用打开电脑、不用打开 Obsidian、不用关心命名/标签/格式。

想法先变成**"Pulse Card"**（临时卡片，存在 `00_Inbox/_pulse/`），等你方便时再决定它的命运（变成正式笔记 / 归档 / 丢弃）。

## 何时用它

| 场景 | 例子 |
|---|---|
| 洗澡/吃饭/走路时的灵感 | "想做个 skills 管理器" |
| 睡前的零散想法 | "明天要修 vault 的 frontmatter" |
| 临时待办，怕忘 | "待：问张三开票" |
| 看到一个东西想记下来 | "claude code obsidian" |
| 一个开放问题，没答案 | "为什么 Dataview 这么慢？" |

## 何时**不**用它

| 场景 | 替代方案 |
|---|---|
| 明确要做的项目（结构化任务） | 直接走 Plan-First：写计划文件 |
| 重要技术内容（要学习、参考） | 用 `learning-note` 模板写正式笔记 |
| 已有完整结构的笔记升级 | 用 `vault-enhance` skill |

**判断标准**：如果这条想法**你愿意花 5 分钟以上整理**，就别用 Pulse，直接写正式笔记。Pulse 是为了"懒得整理但想记下来"的场景。

## 怎么用（3 步上手）

### 1. 在 Telegram 找你的 bot

在 BotFather 创建 bot 时给你的用户名（如 `@my_pulse_bot`）。如果已部署，直接打开对话即可。

### 2. 发送第一条消息

**最简方式**：直接发文字，不用任何命令。

```
想做个 skills 管理器
```

bot 立刻回：
```
✓ Captured: 想做个 skills 管理器
```

卡片已经写入 vault（v0.1 在 VPS 端 → 5 分钟内 Mac 端可见，取决于 [[runbook|F2]]）。

**带命令的方式**（可选）：
```
/p 想做个 skills 管理器
```
效果完全一样。`/p` 只是显式声明"这是一条 pulse"。

### 3. 在 Obsidian 内处理

打开 `91_System/Dashboards/Pulse-Dashboard.md`，看到刚创建的卡片：

```
00_Inbox/_pulse/2026-07-11_223045_想做个-skills-管理器.md
```

点开 → 阅读原始消息 → 决定命运：
- **想正式做** → 用 vault-enhance 升级，或手动规范化
- **暂时不重要** → 留在 dashboard 下次再看
- **过期了** → 删除 / 移到 `90_Archive/_pulse_archive/`

## 命令一览

| 命令 | 作用 |
|---|---|
| `/start` 或 `/help` | 显示帮助 |
| `/p <text>` | 创建 Pulse Card（与直接发文字等价） |
| `/recent` | 列出最近 10 张 Pulse Card（bot 内存中） |
| `/recent 20` | 列出最近 20 张 |
| `/promote <card-id>` | 把 Pulse Card 转正为正式笔记（**v0.1 暂未实现，需手动处理**） |

> **关于 `/recent`**：bot 在内存里保存最近 20 张 Card，**重启 bot 会清空**。要看完整列表，去 Obsidian 看 Pulse Dashboard（用 Dataview）。

## 自动推断的 intent

bot 会根据关键词自动给卡片打 intent 标签（影响后续处理优先级）：

| 关键词 | intent | 含义 |
|---|---|---|
| 含 `?` 或 `？` | `question` | 开放问题 |
| 含 `要` / `需要` / `todo` / `待` | `task` | 待办事项 |
| 含 `想` / `想做` / `打算` / `可以考虑` | `idea` | 灵感、想法 |
| 其他 | `reference` | 资料、引用、随手记 |

**例子**：
- `想做开源项目` → `idea`
- `要修 vault 的 frontmatter` → `task`
- `为什么 Dataview 这么慢？` → `question`
- `claude code obsidian` → `reference`

**优先级**：`question > task > idea > reference`。混合内容由最强信号决定。

## 处理 Pulse Card 的工作流（推荐）

建议每天/每周抽 10 分钟打开 Pulse Dashboard，按这个顺序处理：

```
1. 先看 question 类 → 直接回答或在 Obsidian 内展开
2. 再看 task 类 → 转化正式待办 / 直接做
3. 然后看 idea 类 → 想做的转 plan / 不做的归档 / 觉得好的写学习笔记
4. 最后看 reference 类 → 该归档归档 / 该链接就链接
```

不强制每天都处理，但**30 天以上的卡片应该决策**（dashboard 第三块专门列出这类）。

## 已知限制（v0.1）

- **`/promote` 未实现**：手动升级 Pulse Card → 正式笔记（详见 `TECH_Pulse-Bot-Usage.md` 的"工作流"节）
- **Mac launchd 自动 pull deferred**：手动 `bash pulse-pull.sh` 触发（详见 [[runbook|F4]]）
- **多用户**：bot 仅响应白名单 user_id；多人用需在 config.yaml 加 ID 并重启
- **附件**：v0.1 不支持图片/文件，只处理纯文本

## FAQ

**Q：消息发错了怎么办？**
A：在 Obsidian 内删除对应 Pulse Card 即可。git 提交历史会保留，但 vault 工作树干净。

**Q：bot 不回消息？**
A：见 [[runbook|F1]]。

**Q：能不能发图片？**
A：v0.1 不支持。图片类想法先在 Telegram 保存或描述，等后续版本。

**Q：bot 收消息但 vault 没出现？**
A：见 [[runbook|F2]]（push 失败）。

**Q：我不想让某些消息被 bot 收到？**
A：bot 只响应你（白名单用户）的消息；别人发消息会被拒。

**Q：能改 bot 的名字吗？**
A：去 @BotFather → `/setname`。

## 延伸阅读

- 设计 spec：`91_System/94_Plans/2026-07-09_22-30_pulse-system-design_ec7217b.md`
- 实施计划：`91_System/94_Plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md`
- 深度使用笔记：`40_Life/44_Tech-Thoughts/TECH_Pulse-Bot-Usage.md`