"""Deterministic checks of the data layer. No LLM involved."""

import pytest

from emporio import store


@pytest.fixture(autouse=True)
def pinned_clock(monkeypatch):
    monkeypatch.setenv("EMPORIO_NOW", "2026-10-31T10:00:00")


def names(result):
    return [p["nome"] for p in result["produtos"]]


def test_price_lookup_by_name():
    product = store.get_product(name="Takamine GD20")
    assert product["nome"].startswith("Takamine GD20")
    assert product["preco"] == "R$ 2.199,00"
    assert product["preco_pix"] == "R$ 2.089,05"


def test_fuzzy_name_with_typo():
    assert store.get_product(name="takamine gd 20")["id"] == 95


def test_guitars_up_to_1000_only_available_and_sorted():
    result = store.search_products(category="violões", max_price=1000, limit=50)
    prices = [float(p["preco"][3:].replace(".", "").replace(",", ".")) for p in result["produtos"]]
    assert prices == sorted(prices) and max(prices) <= 1000
    assert all(p["disponibilidade"] == "disponivel" for p in result["produtos"])
    assert "Giannini GF-3D Dreadnought Sunburst" not in names(result)  # out of stock


def test_active_promotion_blocks_pix_discount():
    product = store.get_product(product_id=121)  # Ohana CK-20, 20% off
    assert product["preco"] == "R$ 439,20"
    assert "preco_pix" not in product
    assert "20% off" in product["promocao"]


def test_inactive_promotion_is_ignored():
    assert "promocao" not in store.get_product(product_id=95)  # Takamine, only expired promos


def test_out_of_stock_suggests_alternatives():
    product = store.get_product(product_id=96)
    assert product["disponibilidade"] == "esgotado"
    assert product["alternativas"]
    assert all(a["disponibilidade"] == "disponivel" for a in product["alternativas"])


def test_empty_category_is_explicit():
    result = store.search_products(category="Cordas Orquestrais")
    assert result["total_encontrado"] == 0
    assert "nenhum produto" in result["aviso"]


def test_order_requires_matching_contact():
    assert "erro" in store.lookup_order(8, "someone@else.com")
    order = store.lookup_order(8, "anacarol.ferreira@coldmail.com")
    assert order["status"] == "enviado"
    assert "atencao" in order  # due 28/02/2026, still shipped


def test_order_accepts_phone_without_formatting():
    assert store.lookup_order(8, "67996547821")["pedido"] == 8


def test_regret_return_after_deadline():
    result = store.check_return(4, "lucas.mendes@jmail.com", "arrependimento")
    assert result["elegivel"] is False
    assert result["prazo_final"] == "29/12/2025"


def test_regret_return_inside_deadline(monkeypatch):
    monkeypatch.setenv("EMPORIO_NOW", "2025-12-26T10:00:00")
    result = store.check_return(4, "lucas.mendes@jmail.com", "arrependimento")
    assert result["elegivel"] is True


def test_return_of_undelivered_order_goes_to_staff():
    result = store.check_return(13, "(67) 99456-7890", "arrependimento")  # pending order
    assert result["elegivel"] is None
    assert "equipe" in result["motivo"]


def test_defect_after_30_days_points_to_manufacturer_warranty():
    result = store.check_return(4, "lucas.mendes@jmail.com", "defeito")
    assert result["elegivel"] is False
    assert "fabricante" in result["alternativa"]


def test_installment_tiers():
    assert "até 12x" in store.simulate_payment(amount=2199)["credito"]
    assert "até 6x" in store.simulate_payment(amount=500)["credito"]  # 500/6 = 83 >= 80
    assert "até 3x" in store.simulate_payment(amount=159.9)["credito"]
    assert store.simulate_payment(amount=2500)["combinar_formas"] is True


def test_ticket_is_persisted(tmp_path, monkeypatch):
    from emporio import tickets

    monkeypatch.setattr(tickets, "HISTORY_PATH", tmp_path / "state.db")
    first = tickets.register_ticket("reclamacao", "Cliente reclamou do atendimento", contact="a@b.com")
    second = tickets.register_ticket("atraso_na_entrega", "Pedido 8 atrasado", order_id=8)
    assert first["chamado"] == "#1" and second["chamado"] == "#2"
    assert "24 horas úteis" in first["retorno_da_equipe"]
    assert "erro" in tickets.register_ticket("qualquer", "x")
