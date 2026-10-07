from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from contracts.configuration import PROJECT_ROOT


class ControlSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / '.env', extra='ignore')
    sigap_control_api_key: SecretStr = SecretStr('')
    atcs_enable_test_source: bool = False
    atcs_maximum_green_seconds: float = Field(default=180, ge=60, le=180)
    sigap_event_archive: str = str(PROJECT_ROOT/'work/history/events.sqlite3')

    @property
    def configured(self):
        return len(self.sigap_control_api_key.get_secret_value()) >= 32
