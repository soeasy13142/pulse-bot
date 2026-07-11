---
tags:
  - documentation
  - architecture
created: 2026-07-11
updated: 2026-07-11
status: active
source: "docs/ 完整性审计 v0.1.1"
---

# Pulse Bot Architecture

> 给开发者的架构图与关键不变量清单。读者默认了解 telegram-bot、git、JSONL 基础。

## 模块依赖图

```
                          ┌─────────────────┐
                          │  Telegram Bot    │
                          │   (external)    │
                          └────────┬────────┘
                                   │ Update
                                   ▼
                          ┌─────────────────┐
                          │   bot.py        │
                          │ (entry + cmd)   │
                          └────┬─────┬──────┘
                               │     │
        ┌──────────────────────┘     └─────────────────────┐
        ▼                                                    ▼
┌─────────────────┐                                  ┌─────────────────┐
│   card.py       │                                  │  git_sync.py    │
│ - make_slug     │                                  │ - GitSync       │
│ - build_path    │                                  │ - commit_and_push│
│ - render_card   │                                  │   (3 retries)   │
└────────┬────────┘                                  └────────┬────────┘
         │                                                    │
         │ text + intent                                      │ repo_dir
         ▼                                                    ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              vault repo (file system + git)                  │
    │   路径: 00_Inbox/_pulse/<timestamp>_<uuid>_<slug>.md         │
    └─────────────────────────────────────────────────────────────┘

        ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
        │   intent.py     │   │   config.py     │   │ dead_letter.py  │
        │ - infer_intent  │   │ - load_config   │   │ - enqueue       │
        │   (4 类)        │   │   (env+YAML)    │   │ - flush         │
        └─────────────────┘   └─────────────────┘   └─────────────────┘
              ▲                    ▲                       ▲
              │ text                │ dict                   │ path
              └────────────────────┴───────────────────────┘
                              bot.py 调用
```

## 模块职责

| 模块 | 单一职责 | 公共 API |
|------|---------|----------|
| `bot.py` | Telegram 监听器、命令路由、命令处理 | `main()`, `handle_message()`, `recent_command()`, `help_command()` |
| `card.py` | 把"一段文字"渲染成 Pulse Card | `make_slug(text)`, `build_card_path(text, when)`, `render_card(text, user_id, intent, when)` |
| `config.py` | 加载配置（env + YAML），启动时校验 | `load_config(path=None) -> dict` |
| `dead_letter.py` | 推送失败的卡片持久化队列（JSONL 行存储） | `DeadLetterQueue(path)`: `.enqueue()`, `.flush(sync)`, `.count`, `.pending_paths` |
| `git_sync.py` | 包装 `git add / commit / push`，加 3 次重试 | `GitSync(repo_dir, remote_name, branch, retries=3, dry_run=False)`: `.commit_and_push(path, message)` |
| `intent.py` | 4 类优先级关键词匹配 | `infer_intent(text) -> "idea"\|"task"\|"question"\|"reference"` |

## 关键不变量

### 1. 模块级状态：`_recent_cards`
- `bot.py` 顶层有 `_recent_cards: list[dict]`（最多 20 张）
- 仅在内存中，**进程重启后丢失**
- 单进程安全：**多进程部署会状态分裂**（每个进程有各自的 _recent_cards）
- 测试需在 setup/teardown 清空

### 2. 死信队列持久化
- `DeadLetterQueue` 把每条推送失败的卡片写到 JSONL（每行一个 JSON 对象）
- 路径由 `config['dead_letter_path']` 决定，default `/opt/pulse-bot/dead_letter.jsonl`
- 触发 flush 时机：**进程启动** + **每条新消息处理前**
- 启动 flush 是为了处理"上次进程崩在 push 期间"的积压
- 消息前 flush 是为了处理"卡了几条但当前 push 没事"的 stale 状态

### 3. 路径硬编码 vs 配置化
| 项 | 是否可配置 | 配置键 |
|-----|---------|--------|
| vault repo 目录 | ✅ | `VAULT_REPO_DIR` env / YAML |
| git remote 名 | ✅ | `GIT_REMOTE` env / YAML |
| git branch | ✅ | `GIT_BRANCH` env / YAML |
| dead_letter 文件路径 | ✅（v0.1.1+） | `DEAD_LETTER_PATH` env / YAML |
| 白名单 user_ids | ✅ | YAML `allowed_user_ids` 必需 |
| telegram token | ✅ | `TELEGRAM_BOT_TOKEN` env / YAML 必需 |
| 卡片输出目录 | ❌ 硬编码 `00_Inbox/_pulse/` | 想改得改 `card.build_card_path()` |

### 4. 安全约束（systemd）
- `pulse-bot` system user，不可登录
- `ProtectSystem=strict` + `ReadWritePaths=/opt/pulse-bot/vault` — bot 进程**仅能写** vault 目录
- `Pre-commit hook`（见 `docs/hooks/`）— 即使 systemd 被绕过，git 提交也会校验路径
- 两层防护都存在：任一失效另一层仍生效

### 5. git commit 粒度
- 每条 Pulse Card = 一次 commit，message = `pulse: <first_line_50chars>`
- bot 不 squash、不 rebase、不 amend
- 冲突时 bot 不自动解决 — 见 [[runbook.md#f7-死信队列-dead-letter-queue-异常]]

## 调用流（text 消息）

```
1. Telegram 推 → python-telegram-bot → bot.handle_message(update, ctx)
2. _is_authorized(user_id, config["allowed_user_ids"])  → false 则 reply Unauthorized
3. text = strip; 可能是 "/p xxx" 形式 → 剥前缀
4. _get_dead_letter(config) → DeadLetterQueue 实例
5. dl.flush(sync) → 尝试把过去积压的 dead letter 重试 push
6. intent = infer_intent(text)
7. card_content = render_card(text, user_id, intent, when=now)
8. card_path = build_card_path(text, when)
9. full_path = config["vault_repo_dir"] / card_path
10. full_path.parent.mkdir(parents=True, exist_ok=True)
11. full_path.write_text(card_content, encoding="utf-8")
12. sync = GitSync(...) → sync.commit_and_push(full_path, "pulse: ...")
13. success = True → reply "✓ Captured: ..."
14. success = False → dl.enqueue(...) → reply "⚠ Saved locally but push failed"
15. _recent_cards.insert(0, {path, text, intent, when}) → cap at 20
```

## 测试组织

| 测试文件 | 目标 |
|---------|------|
| `test_card.py` | slug 边界（中文/超长/重名/空字符串） |
| `test_config.py` | env 优先 vs YAML 优先 + 路径类型 + 校验 |
| `test_intent.py` | 4 类关键词 + 优先级 |
| `test_git_sync.py` | 重试 / add 失败 / commit 失败 / push 失败 |
| `test_dead_letter.py` | enqueue / flush / 持久化 |
| `test_bot.py` | 用户授权 / 命令处理 / 错误回复 |
| `test_integration.py` | 端到端 + 失败注入 |
| `test_smoke_e2e.py` | 离线 E2E（不依赖 Telegram） |

## 后续重构候选（v0.2+）

1. `_recent_cards` 改 sqlite，进程间共享
2. `_get_dead_letter` 改 singleton + 启动时初始化（避免每条消息读盘）
3. `bot.py` 拆成 `bot/main.py`、`bot/handlers.py`、`bot/state.py`
4. /promote 命令加 LLM-assisted intent 分类
5. image/voice attachment support
