from pathlib import Path

from dotenv import load_dotenv


BACKEND_ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_backend_environment() -> bool:
    """Fill missing environment values from backend/.env without searching parent directories."""
    return load_dotenv(dotenv_path=BACKEND_ENV_PATH, override=False)
