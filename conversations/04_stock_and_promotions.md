# Stock and promotions

Out-of-stock product with alternatives, an active promotion and the PIX rule (policy 6.2).

Model `gemini-3.5-flash`, policy mode `sections`, clock pinned to 31/10/2026 10:00 (Saturday). Tool calls are shown as they happened.

**Cliente:** Vocês têm o violão Giannini GF-3D?

> 🔧 `get_product({"name": "Giannini GF-3D"})`

**Tom:** No momento, o violão **Giannini GF-3D** está esgotado em nosso estoque.

Mas temos algumas alternativas disponíveis bem bacanas com cordas de aço:

• **Shelby SGD-195E Elétrico Aço Sunburst** – R$ 799,00 (ou R$ 759,05 no PIX)
• **Tagima Dallas Tuner Aço Natural** – R$ 749,00 (ou R$ 711,55 no PIX)
• **Tagima Woodstock Dreadnought Natural** – R$ 899,00 (ou R$ 854,05 no PIX)

Algum desses te interessa? Se quiser, posso te passar mais detalhes!

<sub>2.8 s</sub>

**Cliente:** E o ukulele Ohana CK-20, quanto tá?

> 🔧 `get_product({"name": "Ohana CK-20"})`

**Tom:** O ukulele **Ohana CK-20 Concert Natural** está em promoção!

Ele está de R$ 549,00 por **R$ 439,20** (20% de desconto). Lembrando que, por já estar em promoção, este valor não acumula os 5% de desconto no PIX.

Temos ele disponível em estoque! Posso te ajudar com mais alguma informação sobre ele?

<sub>2.1 s</sub>

**Cliente:** Se eu pagar no PIX ganho mais 5% em cima?

> 🔧 `get_store_policy({"section": "pagamento"})`
> 🔧 `get_store_policy({"section": "promocoes"})`

**Tom:** Não, o desconto de 5% no PIX não se aplica a produtos que já estão em promoção. 

Como o ukulele Ohana CK-20 já está com 20% de desconto (de R$ 549,00 por R$ 439,20), o valor final fica em R$ 439,20 mesmo para pagamento no PIX.

Posso te ajudar com mais alguma coisa?

<sub>3.1 s</sub>
