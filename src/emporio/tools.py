"""Tool definitions (plain JSON Schema, handed to Gemini as function declarations) and dispatch."""

from typing import Callable

from emporio import policies, store


def _fn(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    """Arguments not listed in `required` are optional: the model simply leaves them out."""
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required if required is not None else list(properties),
        },
    }


def _optional(type_: str, description: str, **extra) -> dict:
    return {"type": type_, "description": description, **extra}


def store_tools() -> list[dict]:
    return [
        _fn(
            "search_products",
            "Busca instrumentos no catálogo com preço, promoção e disponibilidade atuais. "
            "Use para perguntas sobre opções, faixas de preço, tipos de instrumento ou marcas.",
            {
                "query": _optional("string", "Texto livre: marca, modelo ou característica. Omita para listar só por filtros."),
                "category": _optional("string", "Categoria do catálogo.", enum=store.category_names()),
                "min_price": _optional("number", "Preço mínimo em reais."),
                "max_price": _optional("number", "Preço máximo em reais."),
                "string_type": _optional("string", "Tipo de corda, para violões e ukuleles.", enum=["nylon", "aco"]),
                "electric": _optional("boolean", "true para elétrico/eletroacústico, false para acústico puro."),
                "include_unavailable": {
                    "type": "boolean",
                    "description": "true só se o cliente perguntar por itens esgotados ou descontinuados.",
                },
            },
            required=[],
        ),
        _fn(
            "get_product",
            "Detalhes de um produto: preço, promoção, estoque, especificações e alternativas se estiver indisponível. "
            "Use quando o cliente cita um modelo específico.",
            {
                "product_id": _optional("integer", "ID do produto, se já conhecido."),
                "name": _optional("string", "Nome ou modelo como o cliente escreveu."),
            },
            required=[],
        ),
        _fn(
            "lookup_order",
            "Status, itens, rastreio e previsão de entrega de um pedido. Exige o número do pedido e o e-mail "
            "ou telefone do cliente; peça os dois antes de chamar.",
            {
                "order_id": {"type": "integer", "description": "Número do pedido."},
                "email_or_phone": {"type": "string", "description": "E-mail ou telefone cadastrado."},
            },
        ),
        _fn(
            "check_return",
            "Verifica, com as datas reais do pedido, se cabe devolução por arrependimento, troca por preferência "
            "ou troca por defeito. Exige número do pedido e e-mail ou telefone.",
            {
                "order_id": {"type": "integer", "description": "Número do pedido."},
                "email_or_phone": {"type": "string", "description": "E-mail ou telefone cadastrado."},
                "reason": {
                    "type": "string",
                    "enum": ["arrependimento", "preferencia", "defeito"],
                    "description": "arrependimento: desistiu da compra. preferencia: quer outro modelo/cor. defeito: veio com problema.",
                },
            },
        ),
        _fn(
            "simulate_payment",
            "Calcula PIX, débito, boleto e o parcelamento permitido para um valor ou produto.",
            {
                "amount": _optional("number", "Valor da compra em reais."),
                "product_id": _optional("integer", "ID do produto; usa o preço atual com promoção."),
            },
            required=[],
        ),
    ]


def policy_tool(mode: str) -> dict:
    if mode == "sections":
        return _fn(
            "get_store_policy",
            "Lê uma seção do manual de políticas da loja. Use para regras de pagamento, trocas e devoluções, "
            "frete, promoções, garantia, privacidade e atendimento.",
            {"section": {"type": "string", "enum": policies.section_keys(), "description": "Seção do manual."}},
        )
    if mode == "rag":
        return _fn(
            "search_store_policy",
            "Busca no manual de políticas da loja os trechos mais relevantes para a pergunta. Use para regras de "
            "pagamento, trocas e devoluções, frete, promoções, garantia, privacidade e atendimento.",
            {"question": {"type": "string", "description": "A dúvida do cliente, reescrita de forma completa."}},
        )
    raise ValueError(f"Unknown POLICY_MODE: {mode}")


def dispatcher(mode: str) -> dict[str, Callable]:
    handlers = {
        "search_products": store.search_products,
        "get_product": store.get_product,
        "lookup_order": store.lookup_order,
        "check_return": store.check_return,
        "simulate_payment": store.simulate_payment,
    }
    if mode == "sections":
        handlers["get_store_policy"] = policies.get_section
    else:
        handlers["search_store_policy"] = policies.search
    return handlers


def run(handlers: dict[str, Callable], name: str, args: dict) -> dict:
    try:
        args = {k: v for k, v in (args or {}).items() if v is not None}
        for key in ("product_id", "order_id"):  # Gemini sends integers as floats
            if key in args:
                args[key] = int(args[key])
        return handlers[name](**args)
    except Exception as exc:  # the model gets the error and can recover or apologise
        return {"erro": f"Falha ao executar {name}: {exc}"}
