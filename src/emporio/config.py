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
EMBEDDINGS_PATH = PROCESSED_DIR / "policy_embeddings.npz"

load_dotenv(ROOT / ".env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
POLICY_MODE = os.getenv("POLICY_MODE", "sections")
STORE_TIMEZONE = "America/Campo_Grande"


def now() -> datetime:
    """Store-local time. EMPORIO_NOW (ISO format) pins it for tests and evals."""
    tz = ZoneInfo(STORE_TIMEZONE)
    pinned = os.getenv("EMPORIO_NOW")
    if pinned:
        return datetime.fromisoformat(pinned).replace(tzinfo=tz)
    return datetime.now(tz)
