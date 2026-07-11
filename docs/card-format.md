---
tags:
  - documentation
  - card-format
created: 2026-07-11
updated: 2026-07-11
status: active
source: "docs/ 完整性审计 v0.1.1"
---

# Pulse Card Format

> 当你看到 `00_Inbox/_pulse/<timestamp>_<uuid>_<slug>.md` 时，里面长什么样。
> 这些字段由 `pulse_bot/card.py::render_card()` 自动生成。

## 文件命名

```
00_Inbox/_pulse/2026-07-11_141532_a1b2c3_想做个-skills-管理器.md
└───────────┘ └────┘ └─────────┘ └────┘ └──────────────────┘
   目录         日期时间  UUID6位     slug (NFKC + kebab-case)
                 UTC        hex
```

| 段 | 生成方式 | 说明 |
|----|---------|------|
| 日期时间 | `when.strftime("%Y-%m-%d_%H%M%S")` | UTC |
| UUID 6 位 | `uuid.uuid4().hex[:6]` | 防同秒重复 |
| slug | `make_slug(text)`, 见下 | 处理空白/特殊字符 |

### slug 规则（`make_slug` 实现）

1. NFKC Unicode 规范化（中英文混排兼容）
2. lowercase ASCII-only
3. `[^\w\s-]` → 删除（中文保留，非 ASCII 字符允许）
4. 空白与下划线 → 连字符
5. strip leading/trailing `-`
6. truncate 50 char + 再 rstrip `-`
7. **如果结果为空**（输入全是特殊字符）→ 回落 `"idea"`

例子：

| 输入 | 输出 |
|------|------|
| `想做个 skills 管理器` | `想做个-skills-管理器` |
| `要做!todo:  -  !!!` | `要todo` |
| `???!!!"` | `idea`（回落） |
| `a really really long text...（超过 50 字符）` | 前 50 字符后 rstrip `-` |

## frontmatter 字段

每张 Pulse Card 的开头：

```yaml
---
tags:
  - pulse
  - inbox
created: 2026-07-11T14:15:32Z        # ISO 8601 UTC，rfc3339
updated: 2026-07-11T14:15:32Z
source: "telegram:123456789"            # bot 收到消息时 user_id
status: pulse                          # 永远是 "pulse"，除非 /promote 把它改成别的
raw_text: |                            # YAML block scalar（多行原文）
  这是用户在 Telegram
  发来的原始消息
  可以跨多行
intent: idea                           # question / task / idea / reference
captured_at: 2026-07-11T14:15:32Z      # 与 created 相同字段，2 种写法都保留向后兼容
---
```

### 字段语义

| 字段 | 值 | 用途 |
|------|----|------|
| `tags` | `[pulse, inbox]` 固定 | Obsidian 索引、Dashboard 筛选 |
| `created` / `updated` | ISO 8601 UTC | Dataview 排序、`dur(7 days)` 计算 |
| `source` | `telegram:<user_id>` | 反查是谁发起的 |
| `status` | `pulse` 默认 | /promote 后改成 `promoted` / `archived` |
| `raw_text` | block scalar | 单字段内保留原始换行 |
| `intent` | 4 类 | Dashboard 分组、过滤 |
| `captured_at` | 与 created 同 | 历史兼容字段 |

> ⚠ **dataview 兼容性**：`captured_at` 和 `created` 是历史遗留双字段，Dashboard 默认用 `created`。新分析脚本请用 `created`，避免被时区相关的边缘 case 坑。

## body 部分

```
## ${first_line_80chars}

> 这是 2026-07-11 14:15 通过 Telegram 捕获的碎片想法。
> 尚未规范化。处理时调用 vault-enhance 或手动编辑。

### 原始消息
${原始 text，无处理}

### 后续处理
<!-- 在这里由人或 agent 补：tags、链接、关联计划等 -->
```

### 章节约定

- `## <首行>`：人类/Eye-friendly 的标题。首行超过 80 字符会被截。
- `### 原始消息`：完整原文，避免 frontmatter `raw_text` 的 YAML 转义干扰阅读。
- `### 后续处理`：留给人或 agent 补 tags / wikilinks / 关联。

## 处理流程（建议）

```
1. 复制卡片内容（除 frontmatter 与 ## 标题）
2. 判断 intent：
   - question → 直接在 Obsidian 里回答或链接到答案所在笔记
   - task     → 转为正式 TODO（[[10_Tasks]]）
   - idea     → 评估：想做 → [[94_Plans]]；不想做 → archive
   - reference → 归档到 [[50_References]]
3. 编辑原卡片：
   - status: promoted / archived
   - updated: <new ISO timestamp>
   - 在 `### 后续处理` 添加链接
4. git commit + push
```

详见 `docs/usage.md` 的"处理 Pulse Card 的工作流"。
