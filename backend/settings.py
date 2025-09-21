from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path

# Always anchor paths to this file's folder (backend/)
BASE_DIR = Path(__file__).parent.resolve()
DEFAULT_STORAGE = BASE_DIR / "storage"

def _sqlite_url(path: Path) -> str:
    # Ensure absolute sqlite URL
    return f"sqlite:///{path.resolve().as_posix()}"

class Settings(BaseSettings):
    # Storage (absolute, under backend/storage)
    DATA_DIR: Path = Field(default=DEFAULT_STORAGE)
    DB_URL: str = Field(default=_sqlite_url(DEFAULT_STORAGE / "db.sqlite3"))
    FAISS_INDEX_PATH: Path = Field(default=DEFAULT_STORAGE / "index" / "faiss.index")

    # Embeddings
    EMBEDDING_PROVIDER: str = Field(default="sentence-transformers")
    EMBEDDING_MODEL: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    OPENAI_API_KEY: str | None = None
    OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")

    # Chunking
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120

    # CORS
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    # LLM
    LLM_PROVIDER: str = Field(default="openai")
    OPENAI_CHAT_MODEL: str = Field(default="gpt-4o-mini")

    class Config:
        # Read .env from backend/.env no matter where we start
        env_file = BASE_DIR / ".env"
        case_sensitive = False

settings = Settings()

# Create folders on startup (under backend/storage)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
(settings.DATA_DIR / "index").mkdir(parents=True, exist_ok=True)
(settings.DATA_DIR / "docs").mkdir(parents=True, exist_ok=True)
