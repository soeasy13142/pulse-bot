# Pulse Bot Operations Runbook

> 监控、日志、故障排查手册。运维人员（你 + agent）的日常参考。
> 部署文档见 [[deployment.md]]；终端用户使用说明见 [[usage.md]]。

## 服务架构概览

```
Telegram User
     │
     ▼
[Telegram API] ◀──── polling ────▶ [pulse-bot service] (systemd)
                                         │
                                         ├─ render Pulse Card → write to vault
                                         └─ git add → commit → push (retry × 3)
                                                              │
                                                              ▼
                                                       [vault git remote]
                                                              │
                                          ┌───────────────────┘
                                          ▼
                              [Mac: manual git pull]
                                          │
                                          ▼
                          [Obsidian: Pulse Dashboard via Dataview]
```

故障可能在任何节点爆发。本 runbook 按"症状 → 排查路径 → 修复"组织。

## 健康检查

### 快速检查（30 秒）

```bash
sudo systemctl status pulse-bot
sudo journalctl -u pulse-bot --since "5 minutes ago"
```

期望：`active (running)` + 无 ERROR/WARNING 日志。

### 详细检查

```bash
# 1. 进程是否真活着
systemctl show pulse-bot -p MainPID,ActiveEnterTimestamp,RestartCount

# 2. 内存 / CPU
systemctl show pulse-bot -p MemoryCurrent,CPUUsageNSec

# 3. 最近 50 条日志
sudo journalctl -u pulse-bot -n 50 --no-pager
```

异常信号：
- `RestartCount > 0` → 进程反复崩溃，查日志找根因
- `MemoryCurrent > 500 MB` → 异常，可能有 leak
- 日志反复出现相同 traceback → 配置或权限问题

## 日志管理

### journald 默认行为

- 默认按大小/时间自动 rotate
- 持久化在 `/var/log/journal/`（如果启用了 persistent storage）

### 手动清理

```bash
# 只保留最近 7 天
sudo journalctl --vacuum-time=7d

# 只保留最近 500 MB
sudo journalctl --vacuum-size=500M
```

### 实时跟踪

```bash
sudo journalctl -u pulse-bot -f
```

### 导出日志（排查用）

```bash
# 导出最近 1 小时到文件
sudo journalctl -u pulse-bot --since "1 hour ago" > /tmp/pulse-bot-debug.log
```

## 故障排查

### F1: Bot 不响应 Telegram 消息

**症状**：发消息无回复；`/start` 无回显。

**排查路径**：

```bash
# 1. 进程是否运行
sudo systemctl status pulse-bot
# 期望：active (running)

# 2. 是否有最近错误
sudo journalctl -u pulse-bot -n 100 | grep -i error

# 3. Token 是否有效
sudo -u pulse-bot cat /opt/pulse-bot/.env | grep TOKEN
# 复制 token，去 https://api.telegram.org/bot<TOKEN>/getMe 验证
# 期望：返回 JSON 含 "ok": true 和 bot 信息

# 4. 网络是否可达 Telegram API
curl -s https://api.telegram.org/bot<TOKEN>/getMe
```

**常见根因**：
- `.env` 文件被误删或权限错（`chmod 600` + `chown pulse-bot:pulse-bot`）
- token 失效（去 BotFather 重新生成）
- VPS 防火墙拦截出站 HTTPS（`curl https://api.telegram.org` 测试）

### F2: Push 失败（卡片卡在本地）

**症状**：bot 回 `⚠ Saved locally but push failed. Will retry.`；Mac 端 pull 不到卡片。

**排查路径**：

```bash
# 1. 看 push 相关日志
sudo journalctl -u pulse-bot | grep -i "push\|git"

# 2. 手动测试 push（以 pulse-bot 用户）
sudo -u pulse-bot -i
cd /opt/pulse-bot/vault
git status
git push
```

**常见根因**：

| 错误信息 | 原因 | 修复 |
|---|---|---|
| `Permission denied (publickey)` | SSH deploy key 未配 / 失效 | 重新生成 key 并加到 GitHub deploy keys |
| `Host key verification failed` | known_hosts 缺 github.com | `sudo -u pulse-bot ssh-keyscan github.com >> /opt/pulse-bot/.ssh/known_hosts` |
| `non-fast-forward` | 本地 commit 领先 remote（极少见，bot 只 append） | `cd /opt/pulse-bot/vault && git pull --rebase && git push` |
| `Could not resolve host` | DNS 故障 | `cat /etc/resolv.conf` + `ping github.com` |
| `Repository not found` | remote URL 错 | `git remote -v` + 修正 |

### F3: systemd 启动失败

**症状**：`systemctl status pulse-bot` 显示 `failed` 或 `inactive (dead)`。

**排查路径**：

```bash
# 1. 看完整错误
sudo journalctl -u pulse-bot -n 50 --no-pager

# 2. 手动跑一遍看真实错误
sudo -u pulse-bot /opt/pulse-bot/.venv/bin/python -m pulse_bot.bot
# Ctrl+C 退出

# 3. 检查 systemd unit 完整性
sudo systemd-analyze verify /etc/systemd/system/pulse-bot.service
```

**常见根因**：
- `ModuleNotFoundError: No module named 'pulse_bot'` → `PYTHONPATH=/opt/pulse-bot/app` 未生效
- `Permission denied` on `/opt/pulse-bot/vault` → 权限或 SELinux/AppArmor
- `.env` 缺 `TELEGRAM_BOT_TOKEN` → 重新填

### F4: Mac 端 Pull 失败（卡片不到本地）

**症状**：VPS 上 vault 有新文件，但 Mac `git pull` 失败。

**排查路径**：

```bash
# 1. 手动 pull 看错误
cd /Users/charliepan/Downloads/my_obsidian
git pull --rebase --autostash

# 2. 看历史 log
tail -20 ~/Library/Logs/pulse-sync.log
```

**常见根因**：
- **冲突**：Mac 本地有未 commit 修改 → `git status` 查看 → 处理冲突后重新 pull
- **网络**：VPN / 代理问题
- **Mac 端 launchd 未加载（M2-T2 deferred）**：v0.1 在 Mac vault 根目录手动 `git pull`（见下条命令）

### F5: Bot 收到未授权消息

**症状**：日志出现 `Unauthorized. Ask the owner to add your user_id.`

**这是预期行为**——`bot.py` 的 `_is_authorized` 检查 `user_id in config["allowed_user_ids"]`。

如果是你自己的账号被拒：

```bash
# 1. 查你的 Telegram user_id（向 @userinfobot 发消息即得）
# 2. 编辑白名单
sudo nano /etc/pulse-bot/config.yaml
# 在 allowed_user_ids 列表加你的 ID
# 3. 重启服务
sudo systemctl restart pulse-bot
```

### F6: 磁盘空间耗尽

**症状**：bot 突然停止写文件；日志报 `No space left on device`。

```bash
# 检查
df -h /opt/pulse-bot/vault

# Pulse Card 单文件 < 5 KB，1 万张才 ~50 MB
# 通常不是 Pulse Card 把盘占满，检查：
du -sh /var/log/journal/
du -sh /opt/pulse-bot/vault/.git/
```

修复：

```bash
# 清理 journal
sudo journalctl --vacuum-time=3d

# Git GC（如果 vault 很大）
sudo -u pulse-bot git -C /opt/pulse-bot/vault gc --aggressive --prune=now
```
### F7: 死信队列（Dead Letter Queue）异常

**症状**：bot 长期回 `⚠ Saved locally but push failed`；磁盘上 `/opt/pulse-bot/dead_letter.jsonl` 持续增大。

**背景**：v0.1 每条推送失败的消息会被记录到死信队列（JSONL 行存储）。Bot 启动时 + 每条新消息处理前会自动 flush。文件路径默认 `/opt/pulse-bot/dead_letter.jsonl`，可被 `$DEAD_LETTER_PATH` 或 YAML `dead_letter_path:` 覆盖。

**排查路径**：

```bash
# 1. 看积压条数（每条是一行 JSON）
sudo wc -l /opt/pulse-bot/dead_letter.jsonl
sudo tail -5 /opt/pulse-bot/dead_letter.jsonl

# 2. 手动 flush：重启 bot 会自动 flush
sudo systemctl restart pulse-bot
sudo journalctl -u pulse-bot --since "10 seconds ago" | grep -i dead

# 3. 完全清空（极端情况：积压卡都是已无关的，且 vault 已正确状态）
sudo systemctl stop pulse-bot
sudo mv /opt/pulse-bot/dead_letter.jsonl /opt/pulse-bot/dead_letter.jsonl.bak
sudo systemctl start pulse-bot
# 再手动 rm /opt/pulse-bot/dead_letter.jsonl.bak

# 4. 改路径：如需把队列挪到另一个盘
sudo systemctl edit pulse-bot   # 加 [Service] 段 Environment="DEAD_LETTER_PATH=/var/lib/pulse-bot/dead_letter.jsonl"
sudo systemctl restart pulse-bot
```

**常见根因**：

| 错误 | 原因 | 修复 |
|---|---|---|
| 队列只涨不消 | `git push` 一直失败（鉴权/DNS） | 见 [[#f2-push-失败-卡片卡在本地]] |
| 队列文件在但 flush 不掉 | vault 状态错乱 | `sudo -u pulse-bot git -C /opt/pulse-bot/vault fsck` |
| 队列文件丢失 | DLQ 是单独 JSONL 文件，重启会保留，不会丢 | 见 [[#f7-死信队列-dead-letter-queue-异常]] |

## 维护操作

### 重启服务

```bash
sudo systemctl restart pulse-bot
```

### 部署新代码

```bash
# 在本地
cd /Users/charliepan/Downloads/my_obsidian
# 修改 91_System/93_Scripts/pulse-bot/...
git commit -am "feat(pulse-bot): ..."
git push

# 在 VPS
sudo -u pulse-bot -i
cd /opt/pulse-bot/vault
git pull
# 然后手动同步新代码（参考 deployment.md 第 1 步）
```

### 添加白名单用户

参考 F5 流程。

### Mac 端自动同步

M2-T2 Mac launchd 方案 deferred（macOS `~/Downloads/` sandbox 路径限制）。v0.1 当前**不提供 Mac 脚本**，由用户自行选择：

**选项 A：手动 `git pull`（最稳）**

```bash
# 在 Mac（Vault 根目录）
cd <your-vault-repo>
git pull --rebase --autostash
```

想"接近实时"的话配一个 Apple Shortcut / Automator workflow 绑定到菜单栏，点击触发 `git pull`。

**选项 B：cron（无人值守）**

```cron
*/5 * * * * cd /Users/<你>/path/to/vault && git pull --rebase --autostash > /tmp/pulse-pull.log 2>&1
```

`crontab -e` 粘贴上面，把 `<你>` 和路径替换掉。每 5 分钟尝试一次 pull；如果 vault 有未 commit 改动，`git pull --rebase --autostash` 会自动 stash + rebase + apply。

**选项 C：launchd（需要自己写 wrapper）**

launchd 在 macOS sandbox 下无法直接 `cd` 到用户 Downloads 之类受限路径。可以写一个 wrapper 脚本（不在本仓库）放在 `~/Library/Application Support/PulseBot/` 下，配合 `com.user.pulse-pull.plist`。本仓库不提供模板，因为组合因人而异。

**Mac 上看不到 Mac Cards 时**：

1. 先手动 `git pull --rebase --autostash` 看是否本机网络/VPN 问题
2. 在 VPS 端 `cd /opt/pulse-bot/vault && git log --oneline -5` 看 push 是否真到了 remote
3. 远程浏览器看 GitHub 仓库最近 commits
4. 如果都 OK 但 Mac 没拿到 → 检查 cron/launchd 日志

### 备份策略

```bash
# vault 本身就是 git 仓库，所有 Pulse Card 已在 git 历史中
# 建议额外备份 /etc/pulse-bot/config.yaml（白名单）
sudo cp /etc/pulse-bot/config.yaml /root/backup-config-$(date +%F).yaml
```

## 监控告警（v0.2 可选）

v0.1 未集成。v0.2 候选方案：

- **systemd OnFailure** 触发 webhook（如 Discord / Slack）
- **独立 cron** 每 5 分钟检查 `systemctl is-active pulse-bot`，失败时发通知
- **journald 监控**：用 `journalctl -u pulse-bot -p err` + 邮件告警

## 安全注意事项

- **Token 不入仓**：`.env` 在 `.gitignore` 中，绝不 commit
- **SSH key 限制**：`pulse-bot` 用户的 SSH key 只加到 vault repo 的 deploy keys，**不要**给全账号访问
- **systemd hardening**：service 文件已启用 `NoNewPrivileges` / `PrivateTmp` / `ProtectSystem=strict` / `ProtectHome=true` / `ReadWritePaths=/opt/pulse-bot/vault`，**不要**随意去掉
- **白名单必填**：`config.py` 启动时校验 `allowed_user_ids` 非空，防止 bot 公网暴露

## 下一步

- 终端用户使用说明：[[usage.md]]