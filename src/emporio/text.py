import re
import unicodedata


def normalize(text: str) -> str:
    """Lowercase, accent-free, single-spaced. Used for every text match."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


def digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


def brl(value: float) -> str:
    """Brazilian currency format: 2199.0 -> 'R$ 2.199,00'."""
    s = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {s}"
