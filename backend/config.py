from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    database_url: str = "postgresql://postgres:retailmind_dev@localhost:5432/retailmind"
    analytics_database_url: str = "postgresql://analytics_reader:change_me@localhost:5432/retailmind"
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    chroma_path: str = "data/chroma"
    embedding_model: str = "all-MiniLM-L6-v2"
    document_top_k: int = 5


settings = Settings()
