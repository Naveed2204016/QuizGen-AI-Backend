from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "QuizGen AI API"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_prefix: str = "/api/v1"
    frontend_origins: str = "http://localhost:5500,http://127.0.0.1:5500"
    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str | None = None
    groq_api_key: str
    groq_model: str = "qwen/qwen3.6-27b"
    groq_timeout_seconds: float = 60
    qdrant_path: str = "./data/qdrant"
    qdrant_collection: str = "quizgen_chunks"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    max_upload_mb: int = 20
    max_questions: int = 50
    ocr_enabled: bool = True
    ocr_language: str = "eng"
    ocr_dpi: int = 300
    tesseract_cmd: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
