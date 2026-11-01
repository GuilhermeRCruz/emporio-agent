"""Hand-off queue for the human team (complaints, late deliveries, cases the manual does not cover).

The agent only says a case was registered after this returns, so it never promises an action
that did not happen. Kept next to the conversation history because the store DB is read-only.
"""

import sqlite3

from emporio.config import now
from emporio.history import HISTORY_PATH

REASONS = ["reclamacao", "atraso_na_entrega", "devolucao_ou_troca", "caso_nao_coberto", "atendimento_humano"]
RESPONSE_TIME = "até 24 horas úteis"  # manual 7.3


def _connect() -> sqlite3.Connection:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(HISTORY_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            reason TEXT NOT NULL,
            summary TEXT NOT NULL,
            order_id INTEGER,
            contact TEXT,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'aberto'
        )
        """
    )
    return conn


def register_ticket(reason: str, summary: str, order_id: int | None = None, contact: str | None = None) -> dict:
    if reason not in REASONS:
        return {"erro": f"Motivo inválido. Use: {', '.join(REASONS)}"}
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO tickets (reason, summary, order_id, contact, created_at) VALUES (?, ?, ?, ?, ?)",
            (reason, summary, order_id, contact, now().isoformat(timespec="minutes")),
        )
    return {"chamado": f"#{cursor.lastrowid}", "status": "aberto", "retorno_da_equipe": RESPONSE_TIME}
