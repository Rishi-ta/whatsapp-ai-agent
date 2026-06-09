from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    All configuration is read from environment variables.
    pydantic-settings automatically reads from .env file.
    """
    secret_key: str = "change-this-in-production"
    access_token_expire_days: int = 30

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    gemini_requests_per_minute: int = 15

    # Gemini
    gemini_api_key: str = ""

    # Twilio WhatsApp
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = "whatsapp:+14155238886"

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma_db"
    chroma_collection_name: str = "rag_documents"

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # App
    max_upload_size_mb: int = 50
    top_k_results: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()



