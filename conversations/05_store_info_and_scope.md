# Store info and scope

Store facts answered without tools, accessories and unrelated questions declined.

Model `gemini-3.5-flash`, policy mode `sections`, clock pinned to 31/10/2026 10:00 (Saturday). Tool calls are shown as they happened.

**Cliente:** Qual o endereço da loja? Vocês abrem hoje?

> 🔧 `get_store_policy({"section": "horario"})`

**Tom:** Estamos na Rua 14 de Maio, 3200, Centro, Campo Grande/MS.

Sim, estamos abertos hoje! Aos sábados funcionamos das 09:00 às 13:00, então pode passar aqui até às 13h.

Posso te ajudar com mais alguma coisa?

<sub>2.0 s</sub>

**Cliente:** Vocês vendem cordas e palhetas?

> 🔧 `get_store_policy({"section": "sobre_a_loja"})`

**Tom:** Não vendemos acessórios como cordas e palhetas, trabalhamos exclusivamente com instrumentos musicais. 

Recomendo procurar uma loja especializada em acessórios musicais na cidade para encontrar o que precisa!

Se quiser ajuda para escolher algum instrumento, estou à disposição.

<sub>1.9 s</sub>

**Cliente:** Valeu! Ah, e quem ganhou a Copa de 2002?

**Tom:** Por nada! Mas só posso te ajudar com dúvidas e informações sobre a nossa loja e os nossos instrumentos. 

Se precisar de ajuda com algum instrumento musical, estou por aqui!

<sub>0.9 s</sub>
