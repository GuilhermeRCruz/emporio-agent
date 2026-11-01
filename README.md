# Empório da Música: customer service agent

Tom is a text agent that answers customers of Empório da Música, a fictional musical instrument
store in Campo Grande/MS. It looks up prices, stock, promotions and orders in the store's data,
applies the rules of the store's policy manual, and politely declines what is out of scope.

```
Você: Quanto custa o Takamine GD20?
  ↳ get_product({"name": "Takamine GD20"})
Tom: O violão Takamine GD20 Dreadnought Natural custa R$ 2.199,00. Se pagar no Pix,
     sai por R$ 2.089,05! Temos 5 unidades em estoque.
```

## Quick start

Requirements: Python 3.11+ and a Gemini API key (the free tier is enough:
https://aistudio.google.com/apikey).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # then paste your key in GEMINI_API_KEY
python -m emporio.ingest        # builds data/processed/emporio.db (takes < 1 s)
emporio --trace                 # chat in the terminal, showing tool calls and latency
```

Other commands:

```bash
emporio --mode rag --trace      # same agent, policies looked up with RAG
emporio --session ana           # saves the conversation and resumes it next time
pytest                          # 16 deterministic tests of the data layer, no LLM
python evals/run.py             # 25 end-to-end cases on both policy modes (uses the API)
```

## Architecture

```
                         ┌──────────────── Gemini 2.5 Flash (function calling) ────────────────┐
 customer message ──►    │ system prompt: persona, fixed store facts, 9 service rules          │
 + store clock           │ tools: search_products · get_product · lookup_order · check_return   │
                         │        simulate_payment · get_store_policy | search_store_policy    │
                         └──────────────┬───────────────────────────────────┬──────────────────┘
                                        │                                   │
                          store.py (SQLite, read-only)          policies.py (manual)
                          catalog view: final price,            sections: lookup by key
                          PIX price, availability               rag: Gemini embeddings,
                          FTS5 + fuzzy name search                    top 3 subsections
                          order/return/payment rules in code
```

`python -m emporio.ingest` turns the raw files into query-ready artifacts once:

* **CSV → SQLite** with typed columns, the `specs` JSON flattened into filterable columns
  (string type, electric), accent-free names for search, and a `catalog` view that already
  resolves category, active promotion, final price, PIX price and availability.
* **PDF → sections and chunks**: the manual is parsed in layout mode (tables keep their columns),
  headers and footers are dropped, and it is split into its 10 sections and 25 subsection chunks
  (`data/processed/policies.json`, committed so the parsing can be reviewed).
* **Data quality report**: inconsistencies are listed in `data/processed/data_quality.md`
  instead of being silently fixed.

RESULTS_PLACEHOLDER
