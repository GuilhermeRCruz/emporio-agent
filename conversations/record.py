"""Plays scripted customer conversations against the real agent and saves them as Markdown.

    python conversations/record.py

The transcripts in this folder were produced by this script, unedited. The clock is pinned
to Saturday 31/10/2026 10:00 (store open) so dates in the answers are reproducible.
"""

import json
import os
from pathlib import Path

os.environ.setdefault("EMPORIO_NOW", "2026-10-31T10:00:00")

from emporio import config  # noqa: E402
from emporio.agent import Agent  # noqa: E402

HERE = Path(__file__).parent

SCRIPTS = {
    "01_catalog_and_payment": (
        "Searching the catalog with filters, then simulating installments for the chosen guitar.",
        [
            "Oi! Quais opções de violões disponíveis custando até R$1000?",
            "Prefiro corda de nylon. Quais desses são de nylon?",
            "Gostei do Yamaha C40. Dá pra parcelar em 10x?",
        ],
    ),
    "02_regret_return_policy": (
        "Non-trivial: the agent asks for identification, then applies the 7-day regret rule "
        "to the real delivery date of the order and offers the warranty path.",
        [
            "Me arrependi da minha compra, posso devolver meu pedido?",
            "É o pedido 4, meu e-mail é lucas.mendes@jmail.com",
            "E se o violão estiver com defeito, aí muda alguma coisa?",
        ],
    ),
    "03_late_order_complaint": (
        "Order status with a delivery date that has already passed, followed by a complaint.",
        [
            "Boa tarde, queria saber onde está meu pedido 8. Telefone (67) 99654-7821",
            "Já era pra ter chegado faz tempo, to bem chateada",
        ],
    ),
    "04_stock_and_promotions": (
        "Out-of-stock product with alternatives, an active promotion and the PIX rule (policy 6.2).",
        [
            "Vocês têm o violão Giannini GF-3D?",
            "E o ukulele Ohana CK-20, quanto tá?",
            "Se eu pagar no PIX ganho mais 5% em cima?",
        ],
    ),
    "05_store_info_and_scope": (
        "Store facts answered without tools, accessories and unrelated questions declined.",
        [
            "Qual o endereço da loja? Vocês abrem hoje?",
            "Vocês vendem cordas e palhetas?",
            "Valeu! Ah, e quem ganhou a Copa de 2002?",
        ],
    ),
}


def record(name: str, description: str, turns: list[str]) -> str:
    agent = Agent()
    lines = [
        f"# {name.split('_', 1)[1].replace('_', ' ').capitalize()}",
        "",
        f"{description}",
        "",
        f"Model `{agent.model}`, policy mode `{agent.policy_mode}`, clock pinned to "
        f"{config.now():%d/%m/%Y %H:%M} (Saturday). Tool calls are shown as they happened.",
        "",
    ]
    for turn in turns:
        reply = agent.ask(turn)
        lines += [f"**Cliente:** {turn}", ""]
        for call in reply.tool_calls:
            args = json.loads(call.arguments)
            lines.append(f"> 🔧 `{call.name}({json.dumps(args, ensure_ascii=False)})`")
        if reply.tool_calls:
            lines.append("")
        lines += [f"**Tom:** {reply.text}", "", f"<sub>{reply.seconds:.1f} s</sub>", ""]
    return "\n".join(lines)


def main() -> None:
    for name, (description, turns) in SCRIPTS.items():
        (HERE / f"{name}.md").write_text(record(name, description, turns), encoding="utf-8")
        print(f"wrote conversations/{name}.md")


if __name__ == "__main__":
    main()
