# CLAUDE.md — Pulse Bot Project

This is the standalone Pulse Bot project. A Telegram-driven fragment capture bot for Obsidian vaults. Code extracted from `soeasy13142/my_obsidian` via `git subtree split` on 2026-07-11.

## Project Overview

Pulse Bot captures fleeting thoughts via Telegram and writes them to an Obsidian vault as "Pulse Cards" (raw fragments in `00_Inbox/_pulse/`). The philosophy: **separate capture from organization** — capture with zero friction, normalize when you decide each card's fate.

- **Repo**: https://github.com/soeasy13142/pulse-bot
- **License**: MIT
- **Status**: v0.1 (M1-M6 done, E2E not yet deployed)
- **Python**: 3.11+
- **Stack**: python-telegram-bot v20+, systemd, git

## Project Layout

```
pulse-bot/
├── README.md                          # Quick start + features
├── LICENSE                            # MIT
├── CLAUDE.md                          # This file (agent onboarding)
├── .gitignore
├── .claude/                           # Claude Code config
│   ├── settings.local.json
│   └── skills/                        # Project-specific skills
├── requirements.txt
├── pytest.ini
├── __init__.py                        # Project metadata (__version__)
├── pulse_bot/                         # Python package (import as `pulse_bot`)
│   ├── __init__.py
│   ├── bot.py                         # Telegram listener + command handlers
│   ├── card.py                        # Pulse Card generation (slug, path, render)
│   ├── config.py                      # Config loader (env + YAML)
│   ├── git_sync.py                    # GitSync with retry
│   ├── intent.py                      # Intent inference
│   ├── .env.example
│   └── .gitignore
├── systemd/
│   └── pulse-bot.service              # systemd unit with hardening
├── tests/                             # 40 tests, 92% coverage
│   ├── __init__.py
│   ├── test_bot.py
│   ├── test_card.py
│   ├── test_config.py
│   ├── test_git_sync.py
│   ├── test_intent.py
│   └── test_integration.py
├── docs/
│   ├── setup.md                       # VPS environment setup
│   ├── deployment.md                  # Deployment runbook + E2E test
│   ├── runbook.md                     # Monitoring + troubleshooting
│   └── usage.md                       # End-user guide
└── plans/                             # Historical plans (read-only reference)
    ├── pulse-system-design.md
    └── pulse-system-implementation-plan.md
```

## Quick Start

```bash
# Clone
git clone https://github.com/soeasy13142/pulse-bot.git
cd pulse-bot

# Setup
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest --cov=pulse_bot --cov-report=term-missing tests/
# Expected: 40/40 pass, 92% coverage

# Run bot (requires TELEGRAM_BOT_TOKEN env var)
export TELEGRAM_BOT_TOKEN="<from-botfather>"
python -m pulse_bot.bot
```

See [`docs/deployment.md`](docs/deployment.md) for production VPS deployment.

## Development Workflow

### TDD is Mandatory

This project was built test-first from day one. Every new feature follows:

1. **Write failing test** in `tests/test_<module>.py`
2. **Run** `pytest tests/test_<module>.py -v` — confirm RED
3. **Write minimal implementation** in `pulse_bot/<module>.py`
4. **Run** `pytest tests/test_<module>.py -v` — confirm GREEN
5. **Refactor** while keeping tests green
6. **Verify coverage**: `pytest --cov=pulse_bot tests/` — must remain ≥ 80%

### File Organization

- **One module per file** under `pulse_bot/`
- **One test file per module** under `tests/` (mirror naming: `test_<module>.py`)
- **Integration tests** in `tests/test_integration.py` (uses tmp git repo)
- **Never** let a file exceed ~400 lines. Split before it does.

### Coding Style

- **Immutable**: prefer creating new objects over mutation
- **KISS**: simplest solution that works
- **DRY**: extract repeated logic into shared functions
- **YAGNI**: no speculative features
- **Type hints**: required on all public functions
- **No hardcoded secrets**: use env vars or config
- **No silent failures**: handle errors explicitly

### Imports & Module Naming

- Package: `pulse_bot` (underscore, importable)
- Files: snake_case (`git_sync.py`, not `gitsync.py`)
- Tests import via: `from pulse_bot.X import ...`

## Git Workflow

### Commit Message Format

```
<type>(<scope>): <description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`

Examples (from this repo's history):
```
feat(pulse-bot): add make_slug with TDD
fix(pulse-bot): ensure vault_repo_dir is Path and accept str path arg
test(pulse-bot): add full test suite with integration test
docs(pulse-bot): add VPS setup guide
```

### Commit Frequency

- **Local commits**: small and frequent. One logical change per commit.
- **Push**: ask user before pushing. Never auto-push.
- **Before pushing**: consider squash/fixup if many small commits accumulate.

### Branch Strategy

- Single `master` branch (this is a small project)
- Feature branches for non-trivial work: `git checkout -b feature/<topic>`
- Squash feature branches before merge to keep history clean

## Testing

```bash
# Run all tests
pytest tests/

# Run specific module
pytest tests/test_card.py -v

# With coverage
pytest --cov=pulse_bot --cov-report=term-missing tests/

# Coverage report (HTML)
pytest --cov=pulse_bot --cov-report=html tests/
open htmlcov/index.html
```

### Test Patterns

- Use `tmp_path` fixture for filesystem operations
- Use `monkeypatch` for mocking subprocess / external calls
- Integration tests use a fresh tmp git repo (see `test_integration.py`)

## Deployment

The bot is designed to run on a VPS under systemd. Full deployment guide: [`docs/deployment.md`](docs/deployment.md).

Quick reference:

```bash
# On VPS, as root:
sudo useradd --system --shell /bin/bash --home /opt/pulse-bot --create-home pulse-bot
sudo mkdir -p /opt/pulse-bot
sudo chown pulse-bot:pulse-bot /opt/pulse-bot

# Copy app + clone vault
sudo cp -r /path/to/pulse-bot /opt/pulse-bot/app
sudo -u pulse-bot git clone <vault-repo> /opt/pulse-bot/vault

# Install deps + configure
sudo -u pulse-bot bash -c "cd /opt/pulse-bot/app && python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"

# Install systemd service
sudo cp /opt/pulse-bot/app/systemd/pulse-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pulse-bot
```

## Security

- **Whitelist required**: `allowed_user_ids` in `/etc/pulse-bot/config.yaml` — bot refuses to start without it
- **systemd hardening**: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome=true`, `ReadWritePaths=/opt/pulse-bot/vault` — do not weaken
- **SSH key isolation**: bot's deploy key only on vault repo, not user's personal account
- **Token in env, not code**: `.env` in `.gitignore`, never committed

## Known Limitations (v0.1)

- `/promote` command not implemented (manual upgrade path)
- No image/voice support (text only)
- Mac launchd auto-pull deferred (vault uses manual `git pull`)
- Single-user whitelist (multi-user needs config edit + restart)

See `plans/pulse-system-implementation-plan.md` for full v0.1 status.

## v0.2 Roadmap

Candidates (see `plans/pulse-system-implementation-plan.md` §v0.2):
1. `/promote` command with LLM-assisted intent classification
2. Image attachment support (OCR + raw image save)
3. Mac launchd shim script workaround
4. Pre-commit hook with file-path whitelist

## Agent Skills

Project skills available in `.claude/skills/`:
- `pulse-bot-dev` — Project-specific development workflow
- `python-testing` — Python testing patterns

External skills (auto-loaded when relevant):
- `ecc:code-reviewer` — Code quality review
- `ecc:security-reviewer` — Security audit
- `ecc:python-reviewer` — Python-specific review
- `superpowers:writing-plans` — Plan structure
- `superpowers:executing-plans` — Plan execution

## Related Links

- **Original vault** (where this code lived): https://github.com/soeasy13142/my_obsidian
- **Implementation plan**: `plans/pulse-system-implementation-plan.md`
- **Design spec**: `plans/pulse-system-design.md`