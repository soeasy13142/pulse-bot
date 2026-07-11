---
tags:
  - pulse
  - documentation
  - deployment
created: 2026-07-10
updated: 2026-07-10
status: done
source: "[[2026-07-09_22-30_pulse-system-design_ec7217b]]"
topic: "VPS Setup for Pulse Bot"
---

# Pulse Bot VPS Setup

> 本文档描述如何在 VPS 上准备 pulse-bot 的运行环境。
> 不包含实际部署步骤（见 [[deployment.md]]）。

## 系统要求

- OS: Ubuntu 22.04+ (或任意主流 Linux)
- RAM: 512 MB 足够
- Python: 3.11+
- Git: 2.30+
- 用户：需要 sudo 权限运行首次安装；pulse-bot 服务本身以非特权用户运行

## 安装步骤

### 1. 系统包

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git openssh-client
```

### 2. 创建 system user

```bash
sudo useradd --system --shell /bin/bash --home /opt/pulse-bot --create-home pulse-bot
sudo mkdir -p /opt/pulse-bot
sudo chown pulse-bot:pulse-bot /opt/pulse-bot
```

### 3. 生成 bot 专用 SSH key

```bash
sudo -u pulse-bot ssh-keygen -t ed25519 -C "pulse-bot@<vps-hostname>" -f /opt/pulse-bot/.ssh/id_ed25519 -N ""
sudo -u pulse-bot cat /opt/pulse-bot/.ssh/id_ed25519.pub
```

把输出的公钥添加到 vault git remote 的 deploy keys（只读或可写）：
- GitHub: repo → Settings → Deploy keys → Add
- 勾选 "Allow write access"

### 4. 配置 known_hosts

```bash
sudo -u pulse-bot -i
ssh-keyscan github.com >> ~/.ssh/known_hosts
```

### 5. 测试 git 访问

```bash
sudo -u pulse-bot -i
git -C /opt/pulse-bot clone git@github.com:<user>/my_obsidian.git
```

如果 clone 成功，VPS 准备完成。

## 下一步

继续 [[deployment.md]] 完成 bot 服务部署。

> **首次部署后建议**：在 vault 仓库里安装 pre-commit 安全 hook（详见 [[deployment#45-在-vault-仓库安装-pre-commit-安全-hook强烈建议]]），可阻止 bot 在故障情况下写入 `00_Inbox/_pulse/` 之外的目录。