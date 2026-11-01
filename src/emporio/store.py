"""Read-only queries over the store database. Every number the agent quotes comes from here."""

import json
import math
import sqlite3
from datetime import date, timedelta
from functools import lru_cache

from rapidfuzz import fuzz, process

from emporio.config import DB_PATH, now
from emporio.text import brl, digits, normalize

ORDER_STATUS = {
    "pending": "aguardando pagamento",
    "confirmed": "pagamento confirmado, em separação",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}

PAYMENT_METHOD = {
    "pix": "PIX",
    "debit": "cartão de débito",
    "boleto": "boleto",
}

RETURN_WINDOW_DAYS = 7  # policy 4.1 and 4.3
DEFECT_WINDOW_DAYS = 30  # policy 4.2
LEGAL_WARRANTY_DAYS = 90  # policy 8.1


@lru_cache(maxsize=1)
def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise RuntimeError("Database not found. Run `python -m emporio.ingest` first.")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@lru_cache(maxsize=1)
def category_names() -> list[str]:
    return [r["name"] for r in connect().execute("SELECT name FROM categories ORDER BY category_id")]


def _payment_label(method: str | None) -> str | None:
    if not method:
        return None
    if method.startswith("credit_"):
        return f"cartão de crédito em {method.removeprefix('credit_')}"
    return PAYMENT_METHOD.get(method, method)


def _quote(row: sqlite3.Row) -> dict:
    """Compact product card. Prices are preformatted so the model copies, never computes."""
    out = {
        "id": row["product_id"],
        "nome": row["name"],
        "categoria": row["category"],
        "disponibilidade": row["availability"],
        "estoque": row["stock_quantity"],
        "preco": brl(row["final_price"]),
    }
    if row["discount_percent"]:
        out["promocao"] = (
            f"{row['promotion']}: {row['discount_percent']:g}% off, de {brl(row['list_price'])} "
            f"por {brl(row['final_price'])} (sem desconto extra no PIX)"
        )
    else:
        out["preco_pix"] = brl(row["pix_price"])
    return out


def _text_matches(query: str) -> list[int]:
    """Ranked product ids for free text: FTS (all words, then any word), then fuzzy names."""
    terms = [t for t in normalize(query).replace('"', " ").split() if t]
    if not terms:
        return []
    conn = connect()
    for joiner in (" AND ", " OR "):
        fts_query = joiner.join(f'"{t}"*' for t in terms)
        ids = [
            r[0]
            for r in conn.execute(
                "SELECT product_id FROM product_search WHERE product_search MATCH ? "
                "ORDER BY bm25(product_search, 0, 10, 1)",
                (fts_query,),
            )
        ]
        if ids:
            return [int(i) for i in ids]

    # Typos and odd spacing ("takamine gd 20", "fender strato")
    names = {r["product_id"]: normalize(r["name"]) for r in conn.execute("SELECT product_id, name FROM products")}
    hits = process.extract(normalize(query), names, scorer=fuzz.WRatio, limit=8, score_cutoff=70)
    return [key for _, _, key in hits]


def search_products(
    query: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    string_type: str | None = None,
    electric: bool | None = None,
    include_unavailable: bool = False,
    limit: int = 5,
) -> dict:
    sql = "SELECT * FROM catalog WHERE 1=1"
    params: list = []
    if category:
        match = process.extractOne(normalize(category), {c: normalize(c) for c in category_names()}, scorer=fuzz.WRatio)
        if not match or match[1] < 80:
            return {"erro": f"Categoria desconhecida. Categorias: {', '.join(category_names())}"}
        sql += " AND category = ?"
        params.append(match[2])
    if min_price is not None:
        sql += " AND final_price >= ?"
        params.append(min_price)
    if max_price is not None:
        sql += " AND final_price <= ?"
        params.append(max_price)
    if string_type:
        sql += " AND string_type = ?"
        params.append("aco" if normalize(string_type) in ("aco", "steel") else "nylon")
    if electric is not None:
        sql += " AND electric = ?"
        params.append(int(electric))
    if not include_unavailable:
        sql += " AND availability = 'disponivel'"

    rows = {r["product_id"]: r for r in connect().execute(sql, params)}

    if query:
        ranked = [rows[i] for i in _text_matches(query) if i in rows]
    else:
        ranked = sorted(rows.values(), key=lambda r: r["final_price"])

    result = {"total_encontrado": len(ranked), "produtos": [_quote(r) for r in ranked[:limit]]}
    if category and not rows:
        empty = connect().execute(
            "SELECT COUNT(*) FROM products p JOIN categories c USING (category_id) WHERE c.name = ?",
            (params[0],),
        ).fetchone()[0]
        if empty == 0:
            result["aviso"] = "A loja não tem nenhum produto desta categoria no catálogo atual."
    if len(ranked) > limit:
        result["aviso"] = f"Mostrando os {limit} primeiros de {len(ranked)}. Refine a busca se precisar."
    return result


def get_product(product_id: int | None = None, name: str | None = None) -> dict:
    conn = connect()
    row = None
    if product_id is not None:
        row = conn.execute("SELECT * FROM catalog WHERE product_id = ?", (product_id,)).fetchone()
    elif name:
        ids = _text_matches(name)
        if ids:
            row = conn.execute("SELECT * FROM catalog WHERE product_id = ?", (ids[0],)).fetchone()
    if row is None:
        return {"erro": "Produto não encontrado no catálogo."}

    out = _quote(row)
    out["descricao"] = row["description"]
    out["especificacoes"] = json.loads(row["specs_json"])

    # Policy 7.3: out of stock or discontinued -> suggest similar available products
    if row["availability"] != "disponivel":
        out["observacao"] = {
            "esgotado": "Temporariamente sem estoque.",
            "descontinuado": "Não faz mais parte do catálogo.",
            "em breve": "Ainda não chegou à loja, sem data definida.",
        }[row["availability"]]
        alternatives = conn.execute(
            """
            SELECT * FROM catalog
            WHERE category_id = ? AND availability = 'disponivel' AND product_id != ?
              AND (string_type IS ? OR ? IS NULL)
            ORDER BY ABS(final_price - ?) LIMIT 3
            """,
            (row["category_id"], row["product_id"], row["string_type"], row["string_type"], row["final_price"]),
        ).fetchall()
        out["alternativas"] = [_quote(a) for a in alternatives]
    return out


def _find_customer_order(order_id: int, email_or_phone: str) -> tuple[sqlite3.Row | None, str | None]:
    """Returns the order only when the contact matches its customer (LGPD, policy 9)."""
    conn = connect()
    row = conn.execute(
        "SELECT o.*, c.name AS customer_name, c.email, c.phone_digits, c.city "
        "FROM orders o JOIN customers c USING (customer_id) WHERE o.order_id = ?",
        (order_id,),
    ).fetchone()
    contact = email_or_phone.strip().lower()
    if row is not None:
        if "@" in contact:
            ok = contact == row["email"]
        else:
            # accept with or without country code / area code: compare the last 8 digits
            d = digits(contact)
            ok = len(d) >= 8 and row["phone_digits"].endswith(d[-8:])
        if ok:
            return row, None
    # Same message for "no such order" and "wrong contact", so order ids cannot be probed
    return None, "Não encontrei um pedido com esse número para esse e-mail ou telefone."


def lookup_order(order_id: int, email_or_phone: str) -> dict:
    row, error = _find_customer_order(order_id, email_or_phone)
    if error:
        return {"erro": error}

    items = connect().execute(
        "SELECT p.name, oi.quantity FROM order_items oi JOIN products p USING (product_id) WHERE order_id = ?",
        (order_id,),
    ).fetchall()
    out = {
        "pedido": row["order_id"],
        "cliente": row["customer_name"].split()[0],
        "data_do_pedido": _br_date(row["order_date"]),
        "status": ORDER_STATUS.get(row["status"], row["status"]),
        "itens": [f"{i['quantity']}x {i['name']}" for i in items],
        "total": brl(row["total_brl"]),
        "pagamento": _payment_label(row["payment_method"]),
    }
    if row["tracking_code"]:
        out["codigo_rastreio"] = row["tracking_code"]
    if row["estimated_delivery"]:
        out["previsao_entrega"] = _br_date(row["estimated_delivery"])
        if row["status"] == "shipped" and date.fromisoformat(row["estimated_delivery"]) < now().date():
            out["atencao"] = (
                "A previsão de entrega já passou e o pedido ainda consta como enviado. "
                "Peça desculpas e abra um chamado com register_ticket para a equipe verificar com a transportadora."
            )
    if row["notes"]:
        out["observacao"] = row["notes"]
    return out


def check_return(order_id: int, email_or_phone: str, reason: str) -> dict:
    """Applies policies 4.1 to 4.4 and 8.1 to a real order.

    The data has no actual receipt date, so the estimated delivery date stands in
    for it (documented assumption).
    """
    row, error = _find_customer_order(order_id, email_or_phone)
    if error:
        return {"erro": error}

    today = now().date()
    base = {"pedido": order_id, "status": ORDER_STATUS[row["status"]], "hoje": _br_date(today.isoformat())}

    if row["status"] == "cancelled":
        return base | {"elegivel": False, "motivo": "O pedido já está cancelado, não há o que devolver."}
    if row["status"] != "delivered":
        return base | {
            "elegivel": None,
            "motivo": "O pedido ainda não foi entregue. O manual não trata cancelamento antes da "
            "entrega: abra um chamado com register_ticket para a equipe decidir.",
        }

    received = date.fromisoformat(row["estimated_delivery"])
    days = (today - received).days
    base |= {"recebido_em": _br_date(received.isoformat()), "dias_desde_o_recebimento": days}

    reason = normalize(reason)
    if reason in ("arrependimento", "preferencia"):
        deadline = received + timedelta(days=RETURN_WINDOW_DAYS)
        rule = "4.1 Direito de Arrependimento" if reason == "arrependimento" else "4.3 Trocas por Preferência"
        result = base | {"regra": rule, "prazo_final": _br_date(deadline.isoformat()), "elegivel": days <= RETURN_WINDOW_DAYS}
        if days <= RETURN_WINDOW_DAYS:
            result["condicoes"] = (
                "Embalagem original, sem sinais de uso, com acessórios e manuais. "
                + (
                    "Reembolso na mesma forma de pagamento em até 10 dias úteis, frete de devolução por conta da loja."
                    if reason == "arrependimento"
                    else "Sujeito à disponibilidade do produto desejado; diferença de valor cobrada ou reembolsada."
                )
            )
        else:
            result["motivo"] = f"O prazo de {RETURN_WINDOW_DAYS} dias corridos terminou em {_br_date(deadline.isoformat())}."
            if days <= LEGAL_WARRANTY_DAYS:
                result["alternativa"] = "Se houver defeito de fabricação, ainda vale a garantia legal de 90 dias."
        return result

    if reason == "defeito":
        purchase = date.fromisoformat(row["order_date"])
        store_deadline = purchase + timedelta(days=DEFECT_WINDOW_DAYS)
        warranty_deadline = received + timedelta(days=LEGAL_WARRANTY_DAYS)
        base["comprado_em"] = _br_date(purchase.isoformat())
        if today <= store_deadline:
            return base | {
                "regra": "4.2 Trocas por Defeito",
                "elegivel": True,
                "prazo_final": _br_date(store_deadline.isoformat()),
                "condicoes": "Defeito de fabricação; mau uso, quedas, umidade e modificações não são cobertos.",
            }
        return base | {
            "regra": "4.2 Trocas por Defeito e 8. Garantia",
            "elegivel": False,
            "motivo": (
                f"A troca direta na loja vale até 30 dias corridos contados da data da COMPRA "
                f"({_br_date(purchase.isoformat())}), ou seja, terminou em {_br_date(store_deadline.isoformat())}."
            ),
            "alternativa": (
                "Acionar a garantia do fabricante (6 meses a 2 anos, conforme o certificado). "
                "A loja pode intermediar se o cliente pedir."
                + (
                    f" A garantia legal de 90 dias vai até {_br_date(warranty_deadline.isoformat())}."
                    if today <= warranty_deadline
                    else ""
                )
            ),
        }

    return {"erro": "Motivo inválido. Use arrependimento, defeito ou preferencia."}


def simulate_payment(amount: float | None = None, product_id: int | None = None) -> dict:
    """Payment options for a purchase (policy 3 and 6.2).

    The manual conflicts on installments: the table says 'minimum installment R$ 100'
    for credit cards, section 3.1 gives tiers. We follow 3.1, the more specific rule:
    up to 3x needs installments of at least R$ 50, 4x-6x at least R$ 80, 7x-12x at least R$ 100.
    """
    has_promo = False
    if product_id is not None:
        row = connect().execute("SELECT * FROM catalog WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            return {"erro": "Produto não encontrado."}
        amount, has_promo = row["final_price"], row["discount_percent"] is not None
    if not amount or amount <= 0:
        return {"erro": "Informe o valor ou o produto."}

    max_installments = 1
    for n in range(12, 1, -1):
        minimum = 100 if n >= 7 else 80 if n >= 4 else 50
        if amount / n >= minimum:
            max_installments = n
            break

    out = {
        "valor": brl(amount),
        "pix": "sem desconto extra (produto já está em promoção)" if has_promo else f"{brl(amount * 0.95)} (5% off)",
        "debito": brl(amount),
        "boleto": f"{brl(amount)} (compensação em até 3 dias úteis)",
        "credito": (
            f"até {max_installments}x sem juros de {brl(math.floor(amount / max_installments * 100) / 100)}"
            if max_installments > 1
            else "somente à vista (valor baixo demais para parcelar)"
        ),
        "combinar_formas": amount > 2000,
    }
    return out


def _br_date(iso: str) -> str:
    y, m, d = iso[:10].split("-")
    return f"{d}/{m}/{y}"
