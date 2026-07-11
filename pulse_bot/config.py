"""Configuration loader for pulse-bot."""
import os
from pathlib import Path
import yaml


DEFAULT_CONFIG_PATH = Path("/etc/pulse-bot/config.yaml")


def load_config(path: Path = None) -> dict:
    """Load configuration from YAML file or environment variables."""
    config_path = Path(path) if path else Path(os.getenv("PULSE_BOT_CONFIG", str(DEFAULT_CONFIG_PATH)))

    config = {
        "telegram_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "allowed_user_ids": [],
        "vault_repo_dir": Path(os.getenv("VAULT_REPO_DIR", "/opt/pulse-bot/vault")),
        "git_remote": os.getenv("GIT_REMOTE", "origin"),
        "git_branch": os.getenv("GIT_BRANCH", "master"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }

    if config_path.exists():
        with open(config_path) as f:
            yaml_config = yaml.safe_load(f) or {}
        config.update(yaml_config)
        # Defensive: YAML null → fall back to env/default; otherwise wrap as Path
        vrd = config["vault_repo_dir"]
        if vrd is None:
            config["vault_repo_dir"] = Path(os.getenv("VAULT_REPO_DIR", "/opt/pulse-bot/vault"))
        else:
            config["vault_repo_dir"] = Path(vrd)

    # Validate required fields
    if not config["telegram_token"]:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set")
    ids = config["allowed_user_ids"]
    if not isinstance(ids, list) or not ids or not all(isinstance(x, int) for x in ids):
        raise ValueError("allowed_user_ids must be a non-empty list[int]")

    return config
