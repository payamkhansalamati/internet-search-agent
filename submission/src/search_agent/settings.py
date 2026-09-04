from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["openai", "ollama"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    search_max_results: int = Field(5, ge=1, le=10)
    http_timeout_seconds: float = Field(20, gt=0, le=120)
    max_document_bytes: int = Field(25_000_000, ge=1024)
    index_path: Path = Path("data/index")
    embedding_provider: Literal["huggingface", "fastembed"] = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    semantic_weight: float = Field(0.7, ge=0, le=1)
    retrieval_top_k: int = Field(18, ge=1, le=30)
    docling_ocr: bool = True
    docling_table_mode: Literal["fast", "accurate"] = "accurate"
    parsing_fallback_enabled: bool = True
    manifest_path: Path = Path("data/manifest.json")
    companies_path: Path = Path("config/companies.yaml")
    glossary_path: Path = Path("config/sustainability_glossary.yaml")
    glossary_review_path: Path = Path("config/glossary-review-queue.json")
    glossary_history_path: Path = Path("config/glossary-history")
    cors_origins: list[str] = ["http://localhost:8501"]
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
