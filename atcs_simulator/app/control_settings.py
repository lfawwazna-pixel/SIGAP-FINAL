from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from contracts.configuration import PROJECT_ROOT


class ControlSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / '.env', extra='ignore')
    sigap_control_api_key: SecretStr = SecretStr('')
    atcs_enable_test_source: bool = False

    @property
    def configured(self):
        return len(self.sigap_control_api_key.get_secret_value()) >= 32
