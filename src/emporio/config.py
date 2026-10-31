import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DB_PATH = PROCESSED_DIR / "emporio.db"
POLICIES_PATH = PROCESSED_DIR / "policies.json"
EMBEDDINGS_PATH = PROCESSED_DIR / "policy_embeddings.npy"

load_dotenv(ROOT / ".env")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
POLICY_MODE = os.getenv("POLICY_MODE", "sections")
STORE_TIMEZONE = "America/Campo_Grande"


def now() -> datetime:
    """Store-local time. EMPORIO_NOW (ISO format) pins it for tests and evals."""
    tz = ZoneInfo(STORE_TIMEZONE)
    pinned = os.getenv("EMPORIO_NOW")
    if pinned:
        return datetime.fromisoformat(pinned).replace(tzinfo=tz)
    return datetime.now(tz)
