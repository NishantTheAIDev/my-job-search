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
    database_url: str = "postgresql+psycopg://jobsearch:jobsearch@localhost:5432/jobsearch"
    # DB connection pool — sized for concurrent multi-user load on Postgres.
    db_pool_size: int = 10
    db_max_overflow: int = 20
    # Auth — JWT signing for our own email/password login. The get_current_user
    # dependency is the swap seam: to delegate auth to Supabase later, change only
    # how the token is verified, not these settings' shape.
    jwt_secret: SecretStr = SecretStr("dev-insecure-secret-change-me-in-production-env")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 24 * 7  # 7 days
    resume_storage_dir: str = "./data/resumes"
    log_level: str = "INFO"
    # Comma-separated list of allowed CORS origins
    cors_origins: list[str] = ["http://localhost:5173"]
    rendercv_theme: str = "engineeringresumes"
    worldbank_enabled: bool = True
    news_enabled: bool = True  # Google News RSS (+ Hacker News fallback); both keyless
    insights_cache_ttl_hours: int = 24


settings = Settings()
