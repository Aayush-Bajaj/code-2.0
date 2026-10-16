import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Base Directory: root of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)


class Settings(BaseModel):
    # Gemini Configuration
    GEMINI_API_KEY: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    GEMINI_MODEL: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))

    # Mock & Offline switches
    MOCK_LLM: bool = Field(default_factory=lambda: os.getenv("MOCK_LLM", "0").lower() in ("1", "true", "yes"))
    MOCK_VISION: bool = Field(default_factory=lambda: os.getenv("MOCK_VISION", "0").lower() in ("1", "true", "yes"))
    DEMO_OFFLINE: bool = Field(default_factory=lambda: os.getenv("DEMO_OFFLINE", "0").lower() in ("1", "true", "yes"))

    # System Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    CACHE_DIR: Path = BASE_DIR / "data" / "cache"
    FIXTURES_DIR: Path = BASE_DIR / "tests" / "fixtures"
    FACTORS_FILE: Path = BASE_DIR / "data" / "factors" / "factors.csv"

    # Inference device – 'cpu' by default; set DEVICE=cuda in .env to use GPU
    # (Blackwell RTX 5050 requires cu128+; do NOT switch to cuda until that build is ready)
    DEVICE: str = Field(default_factory=lambda: os.getenv("DEVICE", "cpu"))

    # HuggingFace Hub Authentication Token
    HF_TOKEN: str = Field(default_factory=lambda: os.getenv("HF_TOKEN", ""))

    # App Environment
    ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    LOG_LEVEL: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


# Singleton settings instance
settings = Settings()

# Automatically propagate HF_TOKEN into environment for huggingface libraries
if settings.HF_TOKEN:
    os.environ["HF_TOKEN"] = settings.HF_TOKEN
    os.environ["HUGGING_FACE_HUB_TOKEN"] = settings.HF_TOKEN

