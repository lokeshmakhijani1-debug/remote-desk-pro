from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str = "development-only-change-me-use-32-bytes-minimum"
    database_url: str = "sqlite:///./remote_desk.db"
    cors_origins: str = "http://localhost:5173"
    public_base_url: str = "http://localhost:8000"
    stun_url: str = "stun:stun.l.google.com:19302"
    turn_url: str = ""
    turn_username: str = ""
    turn_credential: str = ""
    features_unlocked: bool = True
    max_concurrent_sessions: int = 50
    session_ttl_seconds: int = 2592000  # 30-day account token; established WebSocket sessions do not expire mid-session
    device_password_ttl_seconds: int = 86400  # 24-hour idle/password validity window
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_list(self) -> list[str]:
        return [v.strip() for v in self.cors_origins.split(",") if v.strip()]

settings = Settings()
