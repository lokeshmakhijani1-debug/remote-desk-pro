from pydantic import model_validator
from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    app_env:str="development"
    app_secret_key:str="development-only-change-me-use-32-bytes-minimum"
    database_url:str="sqlite:///./remote_desk.db"
    cors_origins:str="http://localhost:5173"
    public_base_url:str="http://localhost:8000"
    stun_url:str="stun:stun.l.google.com:19302"
    turn_url:str=""
    turn_username:str=""
    turn_credential:str=""
    features_unlocked:bool=True
    max_concurrent_sessions:int=50
    session_ttl_seconds:int=2592000
    device_password_ttl_seconds:int=86400
    model_config=SettingsConfigDict(env_file=".env",extra="ignore")
    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.app_env.lower() in {"production","prod"} and (self.app_secret_key.startswith("development-only-") or len(self.app_secret_key)<32):
            raise ValueError("APP_SECRET_KEY must be a unique random value of at least 32 characters in production.")
        return self
    @property
    def cors_list(self)->list[str]:
        return [v.strip() for v in self.cors_origins.split(",") if v.strip()]
settings=Settings()
