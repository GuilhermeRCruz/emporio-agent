# Late order complaint

Order status with a delivery date that has already passed, followed by a complaint.

Model `gemini-3.5-flash`, policy mode `sections`, clock pinned to 31/10/2026 10:00 (Saturday). Tool calls are shown as they happened.

**Cliente:** Boa tarde, queria saber onde está meu pedido 8. Telefone (67) 99654-7821

> 🔧 `lookup_order({"email_or_phone": "(67) 99654-7821", "order_id": 8})`
> 🔧 `register_ticket({"order_id": 8, "summary": "Pedido 8 com entrega atrasada. Previsão era 28/02/2026. Código de rastreio BRJL5544332BR.", "contact": "(67) 99654-7821", "reason": "atraso_na_entrega"})`

**Tom:** Olá, Ana! Bom dia!

O seu pedido 8 (Kala KA-C Concert Mogno) consta como enviado com o código de rastreio **BRJL5544332BR**. 

Pedimos desculpas pelo transtorno, pois vi que a previsão de entrega era até 28/02/2026 e o pedido está atrasado.

Para resolver isso o quanto antes, abri o chamado **#1** para a nossa equipe verificar diretamente com a transportadora. O prazo de retorno da equipe é de até 24 horas úteis. 

Posso te ajudar com mais alguma coisa por enquanto?

<sub>4.0 s</sub>

**Cliente:** Já era pra ter chegado faz tempo, to bem chateada

> 🔧 `get_store_policy({"section": "horario"})`

**Tom:** Entendo perfeitamente o seu chateamento, Ana, e peço mil desculpas por essa situação. Não é essa a experiência que queremos para você.

Como hoje é sábado e a nossa loja está aberta até as 13:00, o chamado que abri sob o número **#1** já está com a nossa equipe para verificarmos o atraso junto à transportadora com prioridade. O prazo máximo de retorno é de até 24 horas úteis.

Assim que a equipe tiver uma resposta da transportadora, entraremos em contato com você pelo seu telefone cadastrado.

<sub>9.6 s</sub>
