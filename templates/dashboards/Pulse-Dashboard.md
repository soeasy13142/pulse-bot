---
tags:
  - dashboard
  - pulse
  - inbox
created: 2026-07-11
updated: 2026-07-11
status: active
source: "pulse-bot/templates/dashboards/Pulse-Dashboard.md"
type: dashboard
---

# 💡 Pulse Dashboard

> 所有未 promote 的碎片想法。重访这里就能找回上下文。
>
> **使用前**：先把本文件复制到你的 vault 仓库的
> `91_System/Dashboards/Pulse-Dashboard.md`，根据实际 vault 结构
> 调整 `FROM` 路径（例如 `00_Inbox/_pulse` → 你 vault 里的实际 inbox 路径）。

## 🔥 最近 7 天

```dataview
TABLE created, intent, tags
FROM "00_Inbox/_pulse"
WHERE status = "pulse" AND created >= date(today) - dur(7 days)
SORT created DESC
LIMIT 20
```

## 📦 全部待处理

```dataview
LIST
FROM "00_Inbox/_pulse"
WHERE status = "pulse"
SORT created DESC
```

## ⏰ 超过 30 天未处理（建议降级或归档）

```dataview
LIST
FROM "00_Inbox/_pulse"
WHERE status = "pulse" AND created <= date(today) - dur(30 days)
```

---

## 安装步骤

```bash
# 1. 在 vault 仓库根目录
mkdir -p 91_System/Dashboards

# 2. 复制本模板到 vault
cp path/to/pulse-bot/templates/dashboards/Pulse-Dashboard.md \
   91_System/Dashboards/Pulse-Dashboard.md

# 3. 编辑文件，把 FROM "00_Inbox/_pulse" 改为你 vault 的实际路径

# 4. 在 Obsidian 里安装 Dataview 插件（社区插件）
#    Settings → Community plugins → Dataview

# 5. 打开 91_System/Dashboards/Pulse-Dashboard.md，三块查询应渲染
```

## 自定义

- **改时间窗**：编辑 `dur(7 days)` / `dur(30 days)`
- **改排序字段**：`SORT created DESC` 改为 `SORT intent ASC, created DESC` 等
- **加更多视图**：用 `TABLE` 替换 `LIST` 用更详细的列
- **筛选特定 intent**：
  ```dataview
  LIST
  FROM "00_Inbox/_pulse"
  WHERE status = "pulse" AND intent = "question"
  ```
