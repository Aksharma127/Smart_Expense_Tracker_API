"""Application configuration.

Single source of truth for runtime settings.
Imported by deps.py to wire up the repository — never hardcoded elsewhere.
"""

from pathlib import Path

# Project root is two levels above this file (src/core/config.py → project root)
_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]


class Settings:
    """Holds all application-level configuration values."""

    DATA_FILE_PATH: Path = _PROJECT_ROOT / "data" / "expenses.json"


settings = Settings()
