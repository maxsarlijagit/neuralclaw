"""Configuration management for NeuralClaw."""

from pathlib import Path
from typing import Optional

import yaml
import appdirs

# Default config location
DEFAULT_CONFIG_PATH = Path(appdirs.user_config_dir("neuralclaw")) / "config.toml"


def get_config_dir() -> Path:
    """Get NeuralClaw config directory."""
    config_dir = Path(appdirs.user_config_dir("neuralclaw"))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get config file path, defaulting to config.toml in config dir."""
    return get_config_dir() / "config.toml"


class Config:
    """NeuralClaw configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or get_config_path()
        self._data = {}
        self._load()

    def _load(self) -> None:
        """Load config from YAML file."""
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                self._data = yaml.safe_load(f) or {}
        else:
            self._data = {}

    def save(self) -> None:
        """Save config to YAML file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump(self._data, f, default_flow_style=False)

    def get(self, key: str, default=None):
        """Get a top-level config key."""
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        """Set a top-level config key."""
        self._data[key] = value

    @property
    def search_method(self) -> str:
        """Get search method: keyword or embeddings."""
        return self._data.get("search", {}).get("method", "keyword")

    @property
    def embeddings_model(self) -> str:
        """Get the embeddings model name."""
        return self._data.get("search", {}).get("embeddings_model", "mxbai-embed-large")

    @property
    def ollama_base_url(self) -> str:
        """Get Ollama base URL."""
        return self._data.get("ollama", {}).get("base_url", "http://localhost:11434")

    @property
    def ollama_enabled(self) -> bool:
        """Check if Ollama is enabled."""
        return self._data.get("ollama", {}).get("enabled", False)


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load NeuralClaw configuration."""
    return Config(config_path)


def get_default_config() -> dict:
    """Return the default config as a dict."""
    return {
        "search": {
            "method": "keyword",
            "embeddings_model": "mxbai-embed-large",
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "enabled": False,
        },
    }


def ensure_config() -> Config:
    """Ensure config exists with defaults, load it."""
    config = load_config()
    if not config.config_path.exists():
        config._data = get_default_config()
        config.save()
    return config