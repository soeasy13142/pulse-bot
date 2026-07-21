# Contributing to Pulse Bot

> 项目开发上手指南。读者：第一次想改 `pulse_bot/*.py` 的人。

## Quick Start

```bash
# 1. Clone
git clone https://github.com/soeasy13142/pulse-bot.git
cd pulse-bot

# 2. venv + deps
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Run tests (must be green before any commit)
pytest --cov=pulse_bot --cov-report=term-missing tests/

# 期望: 73+ passed, coverage ≥ 90%
```

## TDD 强制流程

任何代码改动遵循 **RED → GREEN → IMPROVE**：

```bash
# 1. 写失败的测试
$EDITOR tests/test_<module>.py

# 2. 确认 RED
pytest tests/test_<module>.py -v -k "new_test_name"
# → 期望: 1 failed

# 3. 写实现（最小代码让测试通过）
$EDITOR pulse_bot/<module>.py

# 4. 确认 GREEN
pytest tests/test_<module>.py -v
# → 期望: 1 passed (其余测试也必须通过)

# 5. 重构（提取常量/改命名/去除 duplication）
# 每步后 re-run 全部测试

# 6. 覆盖率检查
pytest --cov=pulse_bot --cov-report=term-missing tests/
# → 期望: 不低于改动前水平（必须 ≥ 80%，项目现状 90%）
```

## 模块边界（先看这个再动手）

| 模块 | 不该出现 |
|------|---------|
| `card.py` | 任何 telegram / git / config 调用 |
| `config.py` | 任何 IO（除了读 YAML + env） |
| `git_sync.py` | 任何 telegram / card 内容生成 |
| `intent.py` | 任何状态依赖（pure function） |
| `dead_letter.py` | 任何 telegram 概念（只对文件操作） |
| `bot.py` | 业务渲染逻辑（交给 card.py） |

判断"该放哪个文件"的简单规则：**如果别的模块能直接重用** → 抽出来；否则留在调用方。

## Commit 规范

格式（来自 git-workflow.md）：

```
<type>(<scope>): <description>

<body 可选>
```

| type | 用在 |
|------|------|
| `feat` | 新功能 / 新模块 |
| `fix` | bug 修复 |
| `refactor` | 代码重构（不改行为） |
| `test` | 只改 tests |
| `docs` | 只改 docs / README / plan |
| `chore` | 依赖 / 配置 / 构建 / CI |
| `perf` | 性能优化 |

例子（实际项目历史）：

```
feat(pulse-bot): add make_slug with TDD
fix(pulse-bot): ensure vault_repo_dir is Path and accept str path arg
test(pulse-bot): add full test suite with integration test
docs(pulse-bot): add VPS setup guide
```

## 提交前 Checklist

- [ ] `pytest --cov=pulse_bot tests/` → 73+ passed, ≥ 90% coverage
- [ ] 改动的模块对应的 test 文件已更新
- [ ] `code-reviewer` agent 跑过（带"python-reviewer"双跑 Python 文件）
- [ ] 至少 1 个 commit 是 docs/docs/scripts/等非生产代码改动（如适用）
- [ ] 不夹带与本 commit 主题无关的代码（rewording、print cleanup 等单开）

## 推送（master 分支）

```bash
# 1. self-check
git log --oneline origin/master..HEAD
# → > 3 个本地 commit 且属于同一 feature → 用 git rebase -i squash

# 2. ask user before pushing
# (never git push without confirmation)
```

## Debug 模式

```bash
# 1. 单元测试：直接看 pytest 输出
pytest tests/test_card.py -v -k "edge_case_unicode"

# 2. 集成：手动启动 bot（小流量 + 断 git）
export TELEGRAM_BOT_TOKEN=fake-token-for-dry-run
export VAULT_REPO_DIR=/tmp/test-vault
export GIT_BRANCH=master
git -C /tmp/test-vault init  # 一次性
python -m pulse_bot.bot

# 3. 看 systemd 日志（在 VPS）
sudo journalctl -u pulse-bot -f

# 4. 看最近 dead letter 状态
sudo tail -10 /opt/pulse-bot/dead_letter.jsonl
```

## 给 Reviewer 的提示

调 `code-reviewer` / `python-reviewer` agent 时，可以指明：

```
Review pulse_bot/git_sync.py (commit abc1234).
特别关注:
- retry 逻辑是否真的覆盖了 transient failure vs permanent failure
- subprocess.run 的 cwd 与 timeout 设置
- error 路径是否吞掉异常
```

## 项目专属约束

（参考根 `CLAUDE.md` 中的 "Global Constraints"）

1. **测试覆盖率 ≥ 80%**，当前 90%
2. **TDD 强制**：先 RED 再 GREEN
3. **不可变性**：prefer 函数返回新对象，模块级状态尽量 singleton 且 lazy
4. **错误显式**：不静默；`except Exception: pass` 是红线
5. **Docs 同步**：改 config 字段要同步更新 `setup.md` / `.env.example`
6. **vault naming** 不改（`00_Inbox/_pulse/` 是 vault spec）
7. **commit message**：不夹带 "fixed typo" "rebase" 等隐含信息
8. **plan 文件**：所有 ≥2 文件的改动先在 `.claude/plans/` 留计划

## Notable internal refactors

下面这些 refactor 不影响用户行为，但对**修改 `bot.py` 的人**很关键 —— 旧符号已不存在：

| 旧符号 / 旧行为 | 新符号 / 新行为 | 原因 | commit |
|---|---|---|---|
| `pulse_bot.bot._dead_letter`（模块级 DeadLetterQueue singleton） | `pulse_bot.bot._get_dead_letter(config) -> DeadLetterQueue`（每次调用从 config 拿路径） | 测试隔离 + 允许多部署覆盖 `dead_letter_path` | `2d5287f` (2026-07-11) |
| 用户回执 `bash pulse-pull.sh` | `git pull --rebase --autostash` | `pulse-pull.sh` 在 v0.1 没实现（Mac launchd deferred） | `2d5287f` (2026-07-11) |

**测试时**不要 monkeypatch `_dead_letter`（已删），改成 monkeypatch `_get_dead_letter` 返回一个 fake：

```python
monkeypatch.setattr(bot_mod, "_get_dead_letter", lambda config: FakeDL(config["dead_letter_path"]))
```

外部脚本若 `from pulse_bot.bot import _dead_letter` 会 `ImportError` —— v0.1 没这种用法，但加新功能时请避免引入新的模块级 singleton。
