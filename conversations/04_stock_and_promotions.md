# Stock and promotions

Out-of-stock product with alternatives, an active promotion and the PIX rule (policy 6.2).

Model `gemini-3.5-flash`, policy mode `sections`, clock pinned to 31/10/2026 10:00 (Saturday). Tool calls are shown as they happened.

**Cliente:** Vocês têm o violão Giannini GF-3D?

> 🔧 `get_product({"name": "Giannini GF-3D"})`

**Tom:** O violão Giannini GF-3D Dreadnought Sunburst está temporariamente esgotado em nosso estoque. 

Mas temos algumas alternativas parecidas e disponíveis no momento:

• Shelby SGD-195E Elétrico Aço Sunburst - R$ 799,00 (ou R$ 759,05 no PIX)
• Tagima Dallas Tuner Aço Natural - R$ 749,00 (ou R$ 711,55 no PIX)
• Tagima Woodstock Dreadnought Natural - R$ 899,00 (ou R$ 854,05 no PIX)

Alguma dessas opções te agrada ou posso te ajudar com outro modelo?

<sub>2.4 s</sub>

**Cliente:** E o ukulele Ohana CK-20, quanto tá?

> 🔧 `get_product({"name": "Ohana CK-20"})`

**Tom:** O ukulele Ohana CK-20 Concert Natural está em promoção! 

De R$ 549,00 por **R$ 439,20** (20% de desconto).

Lembrando que por estar em promoção, ele não acumula o desconto adicional do PIX.

Posso te ajudar com mais alguma dúvida sobre ele ou outro instrumento?

<sub>2.4 s</sub>

**Cliente:** Se eu pagar no PIX ganho mais 5% em cima?

> 🔧 `get_store_policy({"section": "pagamento"})`
> 🔧 `get_store_policy({"section": "promocoes"})`

**Tom:** Não, o desconto de 5% do PIX não se aplica sobre produtos que já estão em promoção. 

Como o ukulele Ohana CK-20 já está com desconto promocional (por R$ 439,20), o valor final dele no PIX continua sendo R$ 439,20.

Posso te ajudar a fechar o pedido ou esclarecer mais alguma dúvida?

<sub>3.0 s</sub>
