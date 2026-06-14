from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: SecretStr = SecretStr("placeholder")
    adzuna_app_id: str = ""
    adzuna_app_key: SecretStr = SecretStr("")
    greenhouse_companies: str = ""
    lever_companies: str = ""
    themuse_api_key: str = ""  # optional — raises rate limits but not required
    jsearch_api_key: SecretStr = SecretStr("")
    indeed_api_key: SecretStr = SecretStr("")
    database_url: str = "sqlite:///./data/jobsearch.db"
    resume_storage_dir: str = "./data/resumes"
    log_level: str = "INFO"
    # Comma-separated list of allowed CORS origins
    cors_origins: list[str] = ["http://localhost:5173"]
    rendercv_theme: str = "engineeringresumes"
    worldbank_enabled: bool = True
    news_enabled: bool = True  # Google News RSS (+ Hacker News fallback); both keyless
    insights_cache_ttl_hours: int = 24


settings = Settings()
