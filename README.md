# Pulse Bot

> Telegram-driven fragment capture for [Obsidian](https://obsidian.md/) vaults.
> Capture a thought in 10 seconds; normalize it later.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-57%2F57%20passing-brightgreen.svg)](#testing)
[![Coverage](https://img.shields.io/badge/coverage-93%25-brightgreen.svg)](#testing)

## What it does

Pulse Bot lets you capture fleeting thoughts via Telegram and have them automatically written to your Obsidian vault as **Pulse Cards** — unpolished, raw fragments stored in `00_Inbox/_pulse/`. Later, when you're at your desk, you decide each card's fate: promote it to a full note, archive it, or discard it.

The philosophy: **separate capture from organization**. Most note-taking systems fail because they force you to organize every thought the instant you record it. Pulse decouples these so you can capture without friction and decide what's worth curating later.

## How it works

```
[You, on phone]                 [VPS]                        [Vault git]
      │                            │                              │
      │  "想做开源项目"             │                              │
      ├───────────────────────────►│                              │
      │                            │  render Card                 │
      │                            │  write to 00_Inbox/_pulse/   │
      │                            │  git add + commit            │
      │                            ├─────────────────────────────►│
      │  ✓ Captured               │                              │
      │◄───────────────────────────┤                              │
      │                                                              │
      │            [You, at desk]                                    │
      │                  │                                           │
      │                  │  git pull                                  │
      │                  │◄──────────────────────────────────────────┤
      │                  │                                           │
      │                  ▼                                           │
      │            Open Pulse Dashboard in Obsidian                 │
      │            (Dataview query of _pulse/ folder)              │
```

## Features

- **10-second capture**: Open Telegram → send message → done.
- **Auto intent inference**: Tags each card as `idea` / `task` / `question` / `reference` based on keywords.
- **Per-user authorization**: Whitelist via `allowed_user_ids` config.
- **Git-backed sync**: Every card = one commit. Full history in git log.
- **Retry on push failure**: 3 retries with exponential backoff.
- **systemd-hardened**: Runs as unprivileged user, `ProtectSystem=strict`, `ReadWritePaths` limited to vault.
- **57 tests, 93% coverage**: Built with TDD from day one.

## Quick start

### 1. Clone this repo on your VPS

```bash
git clone https://github.com/soeasy13142/pulse-bot.git /opt/pulse-bot/app
cd /opt/pulse-bot/app
```

### 2. Install dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
# Bot token (get from @BotFather)
export TELEGRAM_BOT_TOKEN="<your-token>"

# Vault path (clone your Obsidian vault here)
export VAULT_REPO_DIR="/opt/pulse-bot/vault"

# Whitelist (your Telegram user ID — ask @userinfobot)
cat > /etc/pulse-bot/config.yaml <<EOF
allowed_user_ids:
  - 123456789
EOF
```

### 4. Run

```bash
python -m pulse_bot.bot
```

For production, see [`docs/deployment.md`](docs/deployment.md) for systemd setup.

## Project layout

```
pulse-bot/
├── __init__.py              # Project metadata
├── requirements.txt         # Python dependencies
├── pytest.ini               # pytest config
├── pulse_bot/               # Python package (importable as `pulse_bot`)
│   ├── __init__.py
│   ├── bot.py               # Telegram listener + command handlers
│   ├── card.py              # Pulse Card generation (slug, path, render)
│   ├── config.py            # Config loader (env + YAML)
│   ├── git_sync.py          # GitSync with retry
│   └── intent.py            # Intent inference
├── systemd/
│   └── pulse-bot.service    # systemd unit with hardening
├── tests/                   # 57 tests, 93% coverage (run pytest --cov to see current)
│   ├── test_bot.py
│   ├── test_card.py
│   ├── test_config.py
│   ├── test_git_sync.py
│   ├── test_intent.py
│   └── test_integration.py
└── docs/
    ├── setup.md             # VPS environment setup
    ├── deployment.md        # Deployment runbook + E2E test
    ├── runbook.md           # Monitoring + troubleshooting
    └── usage.md             # End-user guide
```

## Commands

| Command | Description |
|---|---|
| `/start` / `/help` | Show help |
| `/p <text>` | Create a Pulse Card (or just send plain text) |
| `/recent [N]` | List recent N cards (default 10, 1 ≤ N ≤ 20) |
| `/promote <id>` | Promote a card to a full note (v0.2) |

## Testing

```bash
source .venv/bin/activate
pytest --cov=pulse_bot --cov-report=term-missing tests/
```

Expected: all tests pass, coverage ≥ 80%. See badge at top for current exact counts.

## Documentation

- [End-user guide](docs/usage.md) — How to use Pulse Bot day-to-day
- [Deployment runbook](docs/deployment.md) — VPS setup + E2E test steps
- [Operations runbook](docs/runbook.md) — Monitoring, logs, troubleshooting
- [VPS setup](docs/setup.md) — Initial environment preparation

## Origin & context

Pulse Bot was originally built as part of a personal Obsidian vault at
[soeasy13142/my_obsidian](https://github.com/soeasy13142/my_obsidian). The
implementation history is preserved via `git subtree split`. See the original
[implementation plan](https://github.com/soeasy13142/my_obsidian/blob/master/91_System/94_Plans/2026-07-11_23-15_pulse-system-implementation-plan_nogit.md)
for full design context.

## License

MIT © 2026 Charlie Pan — see [LICENSE](LICENSE).