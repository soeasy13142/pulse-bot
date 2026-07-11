"""Tests for pulse_bot.config module."""
import os
from pathlib import Path
import pytest
from pulse_bot.config import load_config


@pytest.fixture
def env_setup(monkeypatch):
    """Set up env vars for config tests."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
    monkeypatch.setenv("VAULT_REPO_DIR", "/tmp/test-vault")
    monkeypatch.setenv("GIT_REMOTE", "test-origin")
    monkeypatch.setenv("GIT_BRANCH", "test-branch")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


@pytest.fixture
def minimal_yaml(tmp_path):
    """YAML with only allowed_user_ids (other fields from env)."""
    yaml_file = tmp_path / "minimal.yaml"
    yaml_file.write_text("allowed_user_ids:\n  - 999\n")
    return yaml_file


@pytest.fixture
def yaml_config(tmp_path):
    """Create a YAML config file for testing."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "telegram_token: yaml-token\n"
        "allowed_user_ids:\n"
        "  - 100\n"
        "  - 200\n"
        "vault_repo_dir: /yaml/path\n"
    )
    return config_file


def test_load_config_from_env_plus_minimal_yaml(env_setup, minimal_yaml):
    """Most config from env vars; only allowed_user_ids from YAML (required field)."""
    config = load_config(path=minimal_yaml)
    assert config["telegram_token"] == "test-token-123"
    assert config["vault_repo_dir"] == Path("/tmp/test-vault")
    assert config["git_remote"] == "test-origin"
    assert config["git_branch"] == "test-branch"
    assert config["log_level"] == "DEBUG"
    assert config["allowed_user_ids"] == [999]


def test_load_config_vault_repo_dir_is_path(env_setup, minimal_yaml):
    """vault_repo_dir should always be a Path instance."""
    config = load_config(path=minimal_yaml)
    assert isinstance(config["vault_repo_dir"], Path)


def test_load_config_yaml_overrides_env(env_setup, yaml_config):
    """YAML values should override env vars."""
    config = load_config(path=yaml_config)
    # YAML telegram_token wins over env (YAML is higher priority)
    assert config["telegram_token"] == "yaml-token"
    assert config["allowed_user_ids"] == [100, 200]
    # vault_repo_dir from YAML, wrapped as Path
    assert config["vault_repo_dir"] == Path("/yaml/path")
    assert isinstance(config["vault_repo_dir"], Path)


def test_load_config_missing_token_raises(monkeypatch):
    """No telegram_token anywhere → ValueError."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("VAULT_REPO_DIR", "/tmp")
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        load_config(path="/nonexistent/path.yaml")


def test_load_config_empty_yaml_file(tmp_path, env_setup):
    """Empty YAML file should be handled gracefully (not crash) — but still needs allowed_user_ids."""
    empty_yaml = tmp_path / "empty.yaml"
    empty_yaml.write_text("")
    with pytest.raises(ValueError, match="allowed_user_ids"):
        load_config(path=empty_yaml)
    # Confirms empty YAML is treated as no YAML, so missing allowed_user_ids still raises


def test_load_config_accepts_str_path(env_setup, yaml_config):
    """load_config should accept str path (defensive conversion)."""
    config = load_config(path=str(yaml_config))
    assert config["telegram_token"] == "yaml-token"


def test_load_config_pulses_bot_config_env(monkeypatch, yaml_config):
    """PULSE_BOT_CONFIG env var should be honored when path arg is None."""
    monkeypatch.setenv("PULSE_BOT_CONFIG", str(yaml_config))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    config = load_config()
    # YAML overrides env for telegram_token (per design)
    assert config["telegram_token"] == "yaml-token"


def test_load_config_allowed_user_ids_int_rejected(env_setup, tmp_path):
    """YAML `allowed_user_ids: 12345` (scalar int) must raise, not crash later on first message."""
    yaml_file = tmp_path / "int.yaml"
    yaml_file.write_text("allowed_user_ids: 12345\n")
    with pytest.raises(ValueError, match="allowed_user_ids"):
        load_config(path=yaml_file)


def test_load_config_allowed_user_ids_str_rejected(env_setup, tmp_path):
    """YAML `allowed_user_ids: \"12345\"` (scalar str) must raise, not crash on int-in-str check."""
    yaml_file = tmp_path / "str.yaml"
    yaml_file.write_text('allowed_user_ids: "12345"\n')
    with pytest.raises(ValueError, match="allowed_user_ids"):
        load_config(path=yaml_file)


def test_load_config_allowed_user_ids_empty_list_rejected(env_setup, tmp_path):
    """YAML `allowed_user_ids: []` (empty list) must raise — no users = no access."""
    yaml_file = tmp_path / "empty.yaml"
    yaml_file.write_text("allowed_user_ids: []\n")
    with pytest.raises(ValueError, match="allowed_user_ids"):
        load_config(path=yaml_file)


def test_load_config_vault_repo_dir_null_falls_back_to_env(env_setup, tmp_path):
    """YAML `vault_repo_dir:` (null) must fall back to env/default, not crash Path(None)."""
    yaml_file = tmp_path / "null.yaml"
    yaml_file.write_text("allowed_user_ids:\n  - 999\nvault_repo_dir:\n")
    config = load_config(path=yaml_file)
    assert config["vault_repo_dir"] == Path("/tmp/test-vault")
    assert isinstance(config["vault_repo_dir"], Path)


def test_load_config_dead_letter_path_default(env_setup, minimal_yaml):
    """No DEAD_LETTER_PATH anywhere → default /opt/pulse-bot/dead_letter.jsonl, Path instance."""
    monkeypatch = pytest.MonkeyPatch() if False else None  # placeholder
    import os as _os
    _os.environ.pop("DEAD_LETTER_PATH", None)
    config = load_config(path=minimal_yaml)
    assert config["dead_letter_path"] == Path("/opt/pulse-bot/dead_letter.jsonl")
    assert isinstance(config["dead_letter_path"], Path)


def test_load_config_dead_letter_path_from_env(env_setup, minimal_yaml, monkeypatch):
    """DEAD_LETTER_PATH env var overrides default."""
    monkeypatch.setenv("DEAD_LETTER_PATH", "/custom/dead_letter.jsonl")
    config = load_config(path=minimal_yaml)
    assert config["dead_letter_path"] == Path("/custom/dead_letter.jsonl")


def test_load_config_dead_letter_path_from_yaml(env_setup, tmp_path):
    """YAML `dead_letter_path:` should wrap as Path and win over env/default."""
    yaml_file = tmp_path / "dlp.yaml"
    yaml_file.write_text(
        "allowed_user_ids:\n  - 7\n"
        "dead_letter_path: /yaml/dlp.jsonl\n"
    )
    config = load_config(path=yaml_file)
    assert config["dead_letter_path"] == Path("/yaml/dlp.jsonl")
    assert isinstance(config["dead_letter_path"], Path)