from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_llm_model: str = "llama3.2:3b"
    max_upload_mb: int = 20
    chunk_size: int = 1000
    chunk_overlap: int = 150
    top_k: int = 6
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
