# Pulse Bot

Telegram-driven fragment capture for [Obsidian](https://obsidian.md/) vaults. Capture a thought in 10 seconds via Telegram; normalize it later.

- **Python**: 3.11+, [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v20+
- **Status**: v0.1, 73 tests, 90% coverage, not yet deployed
- **License**: MIT
- **Repo**: https://github.com/soeasy13142/pulse-bot

## Quick Start

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest --cov=pulse_bot --cov-report=term-missing tests/
```

## Module Boundaries

| Module | Responsibility | Must NOT import or call |
|--------|---------------|------------------------|
| `bot.py` | Telegram listener, command routing | Card rendering, git, config loading |
| `card.py` | Slug, path, card render | Telegram, git, config, intent |
| `config.py` | Load env + YAML config | Any IO beyond config files |
| `dead_letter.py` | Persistent JSONL queue for failed pushes | Telegram concepts |
| `git_sync.py` | Git commit+push with 3-retry | Telegram, card content |
| `intent.py` | infer_intent(text) → idea/task/question/reference | Any state (pure function) |

**Test mirror**: each module has a corresponding `tests/test_<module>.py` file.

## Key Conventions

- **TDD required**: RED → GREEN → IMPROVE for every change
- **Type hints**: required on all public functions
- **Immutability**: prefer new objects over mutation
- **Coverage ≥ 80%**: verify with `pytest --cov=pulse_bot tests/`
- **No silent failures**: handle errors explicitly at every boundary
- **Config via env + YAML**: never hardcode secrets or paths
- **One module per file**: split before ~400 lines

## DO / DON'T

### ✅ DO
- DO use **AskUserQuestion** as the default reflex for any uncertainty
- DO write a plan in `.claude/plans/` before multi-file changes or new modules
- DO run code-reviewer + python-reviewer before every commit
- DO start with failing test → implement → refactor (TDD)
- DO fast local commits; squash before push (>3 related commits → rebase)

### ❌ DON'T
- DON'T assume user intent — ask when there's any ambiguity
- DON'T modify files in `plans/` — those are read-only historical archives
- DON'T push without user confirmation
- DON'T skip TDD on new features or bug fixes
- DON'T write speculative code (YAGNI)
- DON'T silently swallow exceptions

## Architecture (Compact)

```
Telegram → bot.py → card.py (render) → git_sync.py (commit+push) → vault repo
                     ├─ intent.py (tag card)
                     └─ dead_letter.py (on push failure)
```

- Every Pulse Card = one git commit
- Dead letter queue retries on next message if push fails
- systemd unit with `ProtectSystem=strict`, `ReadWritePaths` limited to vault
- Whitelist via `allowed_user_ids` — bot refuses start without it
- Pre-commit hook template blocks writes outside `_pulse/` (manual install)

## Reference

| Doc | For |
|-----|-----|
| `README.md` | Project overview, commands, full layout |
| `CONTRIBUTING.md` | Full contributor guide (TDD details, commit format, debug) |
| `docs/deployment.md` | VPS deployment runbook |
| `docs/usage.md` | End-user guide |
| `docs/runbook.md` | Monitoring & troubleshooting |
| `docs/architecture.md` | Full module dependency graph & invariants |
| `docs/card-format.md` | Pulse Card file format & frontmatter spec |
| `plans/README.md` | Naming spec for plan files |
| `plans/2026-07-09_22-45_pulse-system-implementation-plan_nogit.md` | Original v0.1/v0.2 roadmap |

### Original vault

Code extracted from [soeasy13142/my_obsidian](https://github.com/soeasy13142/my_obsidian) via `git subtree split`.
