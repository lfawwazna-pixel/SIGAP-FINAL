from pydantic import Field, SecretStr, field_validator
from urllib.parse import urlsplit
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
    sigap_adaptive_synthetic: bool = False
    sigap_adaptive_video: bool = True
    sigap_media_dir: str = str(PROJECT_ROOT / 'work' / 'media')
    sigap_camera_urls: dict[str, SecretStr] = {}
    sigap_yolo_enabled: bool = False
    sigap_yolo_model: str = str(PROJECT_ROOT / 'models' / 'sigap_yolo26s' / 'best.pt')
    sigap_vision_python: str = ''
    sigap_tomtom_api_key: SecretStr = SecretStr('')
    sigap_tomtom_poll_seconds: int = Field(default=120, ge=60, le=300)
    sigap_analytics_config: str = str(PROJECT_ROOT/'configs/traffic-analytics.json')
    sigap_analytics_store: str = str(PROJECT_ROOT/'work/analytics/traffic.sqlite3')
    sigap_session_seconds: int = Field(default=28800, ge=60, le=86400)
    sigap_cookie_secure: bool = False  # Local HTTP only; HTTPS deployments must enable this.
    sigap_allowed_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    @field_validator('sigap_camera_urls')
    @classmethod
    def camera_urls(cls, values):
        for direction, secret in values.items():
            url = urlsplit(secret.get_secret_value())
            if direction not in 'UTSB' or len(direction) != 1 or url.scheme not in ('rtsp', 'http', 'https') or not url.hostname:
                raise ValueError('Camera mapping requires U/T/S/B and an RTSP or HTTP(S) URL')
        return values

    def database_url(self) -> URL | None:
        password = self.postgres_password.get_secret_value()
        if not password:
            return None
        return URL.create("postgresql+psycopg", username=self.postgres_user, password=password,
                          host=self.sigap_db_host, port=self.sigap_db_port, database=self.postgres_db)
