from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from contracts.configuration import PROJECT_ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")
    postgres_db: str = "sigap"
    postgres_user: str = "sigap"
    postgres_password: SecretStr = SecretStr("")
    sigap_db_host: str = "127.0.0.1"
    sigap_db_port: int = Field(default=5432, ge=1, le=65535)
    sigap_atcs_base_url: str = "http://127.0.0.1:8001"
    sigap_control_api_key: SecretStr = SecretStr("")
    sigap_config_path: str = "configs/intersection.json"
    sigap_session_seconds: int = Field(default=28800, ge=60, le=86400)
    sigap_cookie_secure: bool = False  # Local HTTP only; HTTPS deployments must enable this.
    sigap_allowed_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    def database_url(self) -> URL | None:
        password = self.postgres_password.get_secret_value()
        if not password:
            return None
        return URL.create("postgresql+psycopg", username=self.postgres_user, password=password,
                          host=self.sigap_db_host, port=self.sigap_db_port, database=self.postgres_db)
