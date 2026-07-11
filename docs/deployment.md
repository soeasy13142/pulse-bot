# Pulse Bot Deployment Runbook

> 本文档描述如何在 VPS 上完成 pulse-bot 部署并验证 Telegram → vault 端到端流程。
> 前置：[[setup.md]] 已完成（VPS 已具备 Python 3.11+、pulse-bot system user、SSH deploy key、vault clone）。

## 部署目标

- Telegram 用户发送消息 → bot 收到 → 写入 `00_Inbox/_pulse/<timestamp>_<slug>.md` → commit → push 到 git remote
- Mac 端通过手动或自动 `git pull` 拿到 Pulse Card → Obsidian 内 Pulse Dashboard 显示

## 部署步骤

### 1. 复制 bot 代码到 VPS

代码位于独立仓库 [pulse-bot](https://github.com/soeasy13142/pulse-bot)（v0.1 起从原 vault subtree split 出来）。

```bash
# 在本地（或直接在 VPS 上 clone 都行）
git clone https://github.com/soeasy13142/pulse-bot.git /tmp/pulse-bot-app

# 在 VPS
sudo mv /tmp/pulse-bot-app /opt/pulse-bot/app
sudo chown -R pulse-bot:pulse-bot /opt/pulse-bot/app
ls -la /opt/pulse-bot/app/pulse_bot/   # 应看到 bot.py / card.py / config.py / dead_letter.py / git_sync.py / intent.py
```

### 2. 配置 vault 仓库

pulse-bot 服务进程需要在 `/opt/pulse-bot/vault` 下有 vault 的 git working tree（systemd unit 的 `WorkingDirectory` 与 `ReadWritePaths` 都指这里）。

```bash
sudo -u pulse-bot -i
cd /opt/pulse-bot
# 如果 setup.md 已 clone 过则跳过；否则：
# git clone git@github.com:<user>/my_obsidian.git vault
cd vault
git config user.email "pulse-bot@<vps-hostname>"
git config user.name "Pulse Bot"
# 验证 push 权限
git push --dry-run
```

期望：`Everything up-to-date` 或类似成功信息，无认证失败。

### 3. 安装 Python 依赖

```bash
sudo -u pulse-bot -i
cd /opt/pulse-bot/app
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# 验证
python -c "import telegram; print(telegram.__version__)"   # 应 ≥ 20.7
```

### 4. 配置环境变量

systemd unit 通过 `EnvironmentFile=/opt/pulse-bot/.env` 加载环境变量。

```bash
sudo -u pulse-bot -i
cp /opt/pulse-bot/app/pulse_bot/.env.example /opt/pulse-bot/.env
chmod 600 /opt/pulse-bot/.env
nano /opt/pulse-bot/.env
```

填入：
```bash
TELEGRAM_BOT_TOKEN=<your-token-from-botfather>
VAULT_REPO_DIR=/opt/pulse-bot/vault
GIT_REMOTE=origin
GIT_BRANCH=master
LOG_LEVEL=INFO
DEAD_LETTER_PATH=/opt/pulse-bot/dead_letter.jsonl
```

**注意**：`TELEGRAM_BOT_TOKEN` 是必需的（`config.py` 启动时校验）。`DEAD_LETTER_PATH` 可选，默认值就是上面那个 — 改路径时记得让 `pulse-bot` 用户对目录有写权限。

### 4.5 在 vault 仓库安装 pre-commit 安全 hook（强烈建议）

这是 v0.1 的安全机制：bot 的 commit 一旦试图把文件写到 `00_Inbox/_pulse/` 以外，hook 会直接终止 commit，防止 bot 故障时污染其他目录。

```bash
# 在本地（vault 仓库根目录）
cp /opt/pulse-bot/app/docs/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# 测试 hook
git config user.name "Pulse Bot"
echo "test" > 00_Inbox/_pulse/test.md && git add 00_Inbox/_pulse/test.md && git commit -m "test allowed"   # 应成功
echo "test" > Other/test.md && git add Other/test.md && git commit -m "test blocked"                        # 应被拦截
git reset HEAD~1   # 撤掉 init test commit
```

> hook 通过 `git config user.name` 识别 bot 提交（值需为 "Pulse Bot"，与 `systemd/pulse-bot.service` 启动时配置的 `git config user.name "Pulse Bot"` 一致）。人类提交不受影响。详见 `docs/hooks/README.md`。

> 注意：这步必须在 VPS 端的 vault `/opt/pulse-bot/vault` 仓库里也装一次（不只是你本地 vault），否则 VPS 端推送没拦截。

### 5. 配置白名单（config.yaml）

`config.py` 优先加载 `PULSE_BOT_CONFIG` 指向的 YAML 文件（默认 `/etc/pulse-bot/config.yaml`），其中必须含 `allowed_user_ids`。

```bash
sudo mkdir -p /etc/pulse-bot
sudo nano /etc/pulse-bot/config.yaml
```

写入：
```yaml
telegram_token: "<your-token>"   # 可选：覆盖 env
allowed_user_ids:
  - 123456789   # 你的 Telegram user_id（向 @userinfobot 询问）
```

权限：
```bash
sudo chown root:pulse-bot /etc/pulse-bot/config.yaml
sudo chmod 640 /etc/pulse-bot/config.yaml
```

### 6. 安装并启动 systemd service

```bash
sudo cp /opt/pulse-bot/app/systemd/pulse-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pulse-bot          # 开机自启
sudo systemctl start pulse-bot           # 立即启动
sudo systemctl status pulse-bot          # 验证状态
```

期望状态：`active (running)`。

### 7. 健康检查

```bash
# 查看实时日志
sudo journalctl -u pulse-bot -f

# 期望看到：
# Pulse Bot starting...
# （无 traceback）
```

如果启动失败，常见原因：

| 错误 | 原因 | 修复 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN must be set` | `.env` 缺失或权限不对 | 检查 `/opt/pulse-bot/.env` 内容 + 600 权限 |
| `allowed_user_ids must be set` | config.yaml 缺失或格式错 | 检查 `/etc/pulse-bot/config.yaml` 是合法 YAML |
| `Permission denied: /opt/pulse-bot/vault` | vault 目录权限错 | `sudo chown -R pulse-bot:pulse-bot /opt/pulse-bot/vault` |
| `ModuleNotFoundError: No module named 'pulse_bot'` | PYTHONPATH 未生效 | 确认 systemd unit 含 `Environment="PYTHONPATH=/opt/pulse-bot/app"` |

### 8. E2E 测试（关键验收）

1. **打开 Telegram**，找到你的 bot（用户名由 BotFather 创建）
2. **发送**：`/start`
   - 期望：bot 回显 `Pulse Bot commands:` 帮助文本
3. **发送**：`测试一下 pulse bot`
   - 期望：bot 回显 `✓ Captured: 测试一下 pulse bot`
4. **发送**：`/recent`
   - 期望：bot 列出 "1. [reference] 测试一下 pulse bot"（无关键字命中，intent 默认 reference）
5. **发送**：`想做开源项目`（中文"想"关键字命中 idea）
   - 期望：`✓ Captured: 想做开源项目`
6. **发送**：`要修 vault 的 frontmatter`（"要"关键字命中 task）
   - 期望：`✓ Captured: 要修 vault 的 frontmatter`
7. **发送**：`为什么 Dataview 这么慢？`（问号命中 question）
   - 期望：`✓ Captured: 为什么 Dataview 这么慢？`

### 9. 验证 Mac 端同步

由于 M2-T2 launchd 受 macOS `~/Downloads/` 路径限制目前 deferred（见 [[setup.md#遗留问题]] 与 plan 文件 M2-T2 节），**v0.1 Mac 端用手动 git pull**：

```bash
# 在 Mac（Vault 根目录）
cd <your-vault-repo>
git pull --rebase --autostash
git log --oneline -5    # 看 VPS 端刚 push 的几个 commit 是否落到本地
```

期望：
- `git pull` 退出码 0
- 最近 5 个 commit 里看到步骤 8 的 4 张 Pulse Card（`pulse: ...` 前缀）

> **可选优化**：如果不想每次手动 pull，可以在 Mac 上用 cron / launchd（自己写 wrapper 调用 `git pull`）。本仓库不提供 Mac 端脚本（M2 deferred）。Windows 用户见 [[setup-windows.md]] 用 `pulse-pull.ps1`。

### 10. 在 Obsidian 内验证 Dashboard

**首次使用**：把仓库里的 `templates/dashboards/Pulse-Dashboard.md` 复制到 vault 的 `91_System/Dashboards/Pulse-Dashboard.md`（模板内有详细安装步骤），按你 vault 的实际路径调整 Dataview 查询里的 `FROM "00_Inbox/_pulse"`。

打开 dashboard 路径，三块 Dataview 查询都应渲染：

| 区块 | 期望内容 |
|---|---|
| 🔥 最近 7 天 | 步骤 8 创建的 4 张 Pulse Card |
| 📦 全部待处理 | 同上（v0.1 还没 promote 过） |
| ⏰ 超过 30 天未处理 | 空（卡片刚创建） |

## 卸载（如需）

```bash
sudo systemctl stop pulse-bot
sudo systemctl disable pulse-bot
sudo rm /etc/systemd/system/pulse-bot.service
sudo systemctl daemon-reload
sudo rm -rf /opt/pulse-bot
sudo userdel pulse-bot
sudo rm -rf /etc/pulse-bot
```

## 下一步

- 运维与监控：[[runbook.md]]
- 终端用户使用说明：[[usage.md]]