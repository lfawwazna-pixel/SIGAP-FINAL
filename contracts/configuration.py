from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from contracts.models import IntersectionConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ConfigurationLocation(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")
    sigap_config_path: str = "configs/intersection.json"


def load_config(path: str | Path | None = None) -> IntersectionConfig:
    resolved = Path(path or ConfigurationLocation().sigap_config_path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    return IntersectionConfig.model_validate_json(resolved.read_text(encoding="utf-8"))
