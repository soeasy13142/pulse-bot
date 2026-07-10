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
        # Ensure vault_repo_dir is always Path regardless of YAML source type
        config["vault_repo_dir"] = Path(config["vault_repo_dir"])

    # Validate required fields
    if not config["telegram_token"]:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set")
    if not config["allowed_user_ids"]:
        raise ValueError("allowed_user_ids must be set")

    return config
