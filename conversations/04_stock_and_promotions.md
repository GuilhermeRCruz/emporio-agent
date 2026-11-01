# Stock and promotions

Out-of-stock product with alternatives, an active promotion and the PIX rule (policy 6.2).

Model `gemini-3.5-flash`, policy mode `sections`, clock pinned to 31/10/2026 10:00 (Saturday). Tool calls are shown as they happened.

**Cliente:** Vocês têm o violão Giannini GF-3D?

> 🔧 `get_product({"name": "Giannini GF-3D"})`

**Tom:** O violão Giannini GF-3D Dreadnought Sunburst está temporariamente esgotado em nosso estoque. 

Mas temos algumas alternativas parecidas disponíveis pra você dar uma olhada:

• Shelby SGD-195E Elétrico Aço Sunburst - R$ 799,00 (ou R$ 759,05 no PIX)
• Tagima Dallas Tuner Aço Natural - R$ 749,00 (ou R$ 711,55 no PIX)
• Tagima Woodstock Dreadnought Natural - R$ 899,00 (ou R$ 854,05 no PIX)

Quer mais detalhes sobre algum desses modelos?

<sub>2.6 s</sub>

**Cliente:** E o ukulele Ohana CK-20, quanto tá?

> 🔧 `get_product({"name": "Ohana CK-20"})`

**Tom:** O ukulele Concert Ohana CK-20 tá em promoção! 

Ele tá de R$ 549,00 por **R$ 439,20** (20% de desconto). 

*Nota: como ele já está em promoção, não se aplica o desconto extra do PIX.*

Temos 6 unidades dele em estoque no momento. Quer garantir o seu ou saber mais detalhes sobre ele?

<sub>2.1 s</sub>

**Cliente:** Se eu pagar no PIX ganho mais 5% em cima?

> 🔧 `get_store_policy({"section": "pagamento"})`
> 🔧 `get_store_policy({"section": "promocoes"})`

**Tom:** Não, o desconto de 5% no PIX não se aplica a produtos que já estão em promoção. 

Como o ukulele Ohana CK-20 já está com 20% de desconto (de R$ 549,00 por R$ 439,20), o valor final dele no PIX continua sendo R$ 439,20.

Posso te ajudar com mais alguma dúvida sobre ele ou outra coisa?

<sub>3.2 s</sub>
