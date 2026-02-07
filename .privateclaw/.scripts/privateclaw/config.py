"""Shared configuration loading and path resolution for PrivateClaw."""

import fcntl
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger("privateclaw")


def _find_project_root() -> Path:
    """Walk up from the scripts directory to find the project root (parent of .privateclaw)."""
    scripts_dir = Path(__file__).resolve().parent.parent  # .privateclaw/.scripts/
    privateclaw_dir = scripts_dir.parent  # .privateclaw/
    return privateclaw_dir.parent  # project root


PROJECT_ROOT = _find_project_root()
PRIVATECLAW_DIR = PROJECT_ROOT / ".privateclaw"
CONFIG_PATH = PRIVATECLAW_DIR / "config.json"
ENV_PATH = PROJECT_ROOT / ".env"


def load_config() -> dict:
    """Load config.json and .env, returning the merged config dict."""
    load_dotenv(ENV_PATH)

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    return config


def get_root(config: dict) -> Path:
    root = config["paths"]["root"]
    if root == ".":
        return PROJECT_ROOT
    return Path(root)


def get_transcriptions_dir(config: dict) -> Path:
    return get_root(config) / config["paths"]["transcriptions"]


def get_flagged_dir(config: dict) -> Path:
    """Get the FLAGGED directory for files pending human review."""
    return get_root(config) / config["paths"].get("flagged", "FLAGGED")


def get_private_dir(config: dict) -> Path:
    """Get the PRIVATE directory for files that never leave."""
    return get_root(config) / config["paths"].get("private", "PRIVATE")


def get_openclaw_dir(config: dict) -> Path:
    """Get the OPENCLAW folder (Docker mount point)."""
    return get_root(config) / config["paths"].get("openclaw", "OPENCLAW")


def get_archive_dir(config: dict) -> Path:
    return get_root(config) / config["paths"]["archive"]


def get_openclaw_config_dir() -> Path:
    """Get the hidden OpenClaw config directory."""
    return PROJECT_ROOT / ".openclaw"


def get_huggingface_token(config: dict) -> str:
    env_var = config["transcription"]["huggingface_token_env"]
    token = os.environ.get(env_var, "")
    if not token:
        logger.warning(
            f"HuggingFace token not set. Set {env_var} in {ENV_PATH} for speaker diarization."
        )
    return token


def setup_logging(name: str) -> logging.Logger:
    """Set up logging to both console and log file."""
    log_dir = PRIVATECLAW_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    log = logging.getLogger("privateclaw")
    log.setLevel(logging.INFO)

    if not log.handlers:
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        log.addHandler(console)

        file_handler = logging.FileHandler(log_dir / f"{name}.log")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        log.addHandler(file_handler)

    return log


class FileLock:
    """Exclusive file lock to prevent concurrent runs of the same script."""

    def __init__(self, name: str):
        lock_dir = PRIVATECLAW_DIR / "logs"
        lock_dir.mkdir(exist_ok=True)
        self.lock_path = lock_dir / f"{name}.lock"
        self._lock_file = None

    def acquire(self) -> bool:
        self._lock_file = open(self.lock_path, "w")
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            self._lock_file.close()
            self._lock_file = None
            return False

    def release(self):
        if self._lock_file:
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None

    def __enter__(self):
        if not self.acquire():
            logger.info("Another instance is already running. Exiting.")
            sys.exit(0)
        return self

    def __exit__(self, *args):
        self.release()
