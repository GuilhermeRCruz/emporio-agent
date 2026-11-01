# Empório da Música: customer service agent

Tom is a text agent for Empório da Música, a fictional musical instrument store in Campo
Grande/MS. It looks up prices, stock, promotions and orders in the store data, applies the rules
of the store's policy manual to the customer's real order, hands complaints over to the team
through a ticket queue, and politely declines what is out of scope.

```
Cliente: Gostei do Yamaha C40. Dá pra parcelar em 10x?
  🔧 get_product({"name": "Yamaha C40"})
  🔧 get_store_policy({"section": "pagamento"})
  🔧 simulate_payment({"product_id": 81})
Tom:     Não dá para fazer em 10x porque a nossa parcela mínima para 7x a 12x é de R$ 100,00.
         Para o Yamaha C40 (R$ 599,90), você consegue parcelar em até 6x de R$ 99,98 sem juros
         no cartão de crédito! Ou, se preferir no PIX, ele sai por R$ 569,90 com o desconto de 5%.
```

**Results:** 27/27 end-to-end eval cases with the default setup, 2.4 s mean latency per answer, and a measured comparison of section lookup vs RAG for the policy manual ([Evaluation](#evaluation)).

## Contents

1. [Quick start](#quick-start)
2. [Architecture](#architecture)
3. [Technical decisions](#technical-decisions)
4. [Evaluation](#evaluation)
5. [Assumptions about the data](#assumptions-about-the-data)
6. [Known limitations and next steps](#known-limitations-and-next-steps)
7. [Use of AI coding assistants](#use-of-ai-coding-assistants)
8. [Repository layout](#repository-layout)

## Quick start

Requirements: Python 3.11+ and a Gemini API key from https://aistudio.google.com/apikey.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # paste your key in GEMINI_API_KEY
python -m emporio.ingest        # builds data/processed/emporio.db (< 1 s)
emporio --trace                 # chat in the terminal, showing tool calls, latency and tokens
```

More commands:

```bash
emporio --mode rag --trace      # same agent, policies looked up with RAG instead of by section
emporio --session ana           # saves the conversation; run it again to resume
pytest                          # 15 deterministic tests of the data layer and tickets, no LLM
python evals/run.py             # end-to-end eval on both policy modes (about 90 API calls)
python conversations/record.py  # re-records the example conversations
```

> **About the free tier.** A free key is enough to chat, but in November 2026 the free tier allows
> only 20 requests per day per model, and a full eval run needs about 90. The evals in this
> repository were run on a key with billing enabled (a full run costs a few US cents).

## Architecture

```
 customer message                ┌──────── gemini-3.5-flash, function calling ────────┐
 + store clock ─────────────────►│ system prompt: persona "Tom", fixed store facts,   │
                                 │ 9 service rules taken from the manual              │
                                 └───┬──────────────┬───────────────┬─────────────────┘
                                     │              │               │
              store.py (SQLite, read-only)   policies.py       tickets.py (SQLite)
              search_products                get_store_policy  register_ticket
              get_product                     (sections mode)   hand-off queue for
              lookup_order                   search_store_policy the human team
              check_return                    (rag mode)
              simulate_payment
```

`python -m emporio.ingest` turns the raw files into query-ready artifacts once:

* **CSV to SQLite** with typed columns, the `specs` JSON flattened into filterable columns
  (string type, electric), accent-free text indexed with FTS5, and a `catalog` view that already
  resolves category, active promotion, final price, PIX price and availability.
* **PDF to sections and chunks.** The manual is parsed in layout mode so tables keep their
  columns; headers, footers and the cover are dropped; the text is split into its 10 sections and
  25 subsection chunks (`data/processed/policies.json`, committed so the parsing can be reviewed).
* **Data quality report.** Inconsistencies are listed in `data/processed/data_quality.md` instead
  of being silently fixed (see [Assumptions](#assumptions-about-the-data)).

## Technical decisions

### 1. Function calling over a typed data layer (not text-to-SQL, not RAG over the CSVs)

The model chooses tools; Python answers them. Six narrow tools cover the store's questions.

* **Not text-to-SQL.** Generating SQL costs more tokens and retries, and it would let the model
  read any customer's orders. The manual (section 9) and the LGPD make that a hard no:
  `lookup_order` only returns an order when the e-mail or phone matches its customer, and gives
  the same error for "no such order" and "wrong contact" so order numbers cannot be probed.
* **Not RAG over the CSVs.** Similarity search cannot answer "violões até R$ 1.000", sort by
  price, or tell stock 0 from stock 5. Structured data stays structured.
* **Business rules live in code, not in the prompt.** Final price with promotion, PIX price
  (5%, not combined with promotions, manual 6.2), installment limits (manual 3.1), the 7 and
  30 day windows for returns and defects (manual 4.1 to 4.3) and overdue deliveries are computed
  in Python. Tools return values already formatted in BRL, so the model copies numbers and never
  does arithmetic.
* **Search** tries FTS5 with all words, then any word, then fuzzy names (RapidFuzz), so
  "takamine gd 20" still finds the Takamine GD20.
* **Unavailable products** come back with three available alternatives of the same category and
  string type, as manual 7.3 asks.

### 2. Two ways to read the policy manual, measured

The user asked for the policy lookup to be decided with numbers, so both are implemented behind
`POLICY_MODE`:

| Mode | How it works |
|---|---|
| `sections` (default) | The tool takes one of the manual's 10 section keys (an enum); Python returns that section. |
| `rag` | The question is embedded with `gemini-embedding-001` (768 dimensions, `RETRIEVAL_QUERY` vs `RETRIEVAL_DOCUMENT` task types) and the 3 closest chunks are returned. |

Chunking follows the manual's own structure: one chunk per subsection (4.1 regret, 4.2 defect,
...), or the whole section when it has none, always prefixed with the section title so a chunk
like "30 dias corridos" still says it is about defects. 25 chunks, all under 800 characters.

Result over the 8 policy cases, 3 runs each ([details](evals/history/policy_mode_repeats.md)):

| Mode | Passed | Mean latency | Median latency |
|---|---|---|---|
| **sections** | **24/24** | **2.60 s** | **2.42 s** |
| rag | 24/24 | 3.14 s | 3.00 s |

Same accuracy, but RAG pays an embedding round trip (about 0.55 s) on every policy question and
sends about the same number of tokens, since three chunks are roughly one section. With an
8-page manual, sections win. RAG stays in the code as the path for when the manual grows past
what fits in a section lookup.

### 3. Model and provider: Gemini 3.5 Flash with minimal thinking

Gemini was chosen for a free tier the reviewer can use and a fast Flash family. The model was
chosen by the evals, on the 7 hardest cases ([details](evals/history/model_comparison.md)):

| Model | Thinking | Passed | Mean | p95 |
|---|---|---|---|---|
| gemini-2.5-flash | budget 0 | 5/7 | 1.65 s | 2.98 s |
| gemini-3.5-flash | low | 6/7 | 2.52 s | 3.98 s |
| **gemini-3.5-flash** | **minimal** | **7/7** | **2.22 s** | **3.50 s** |
| gemini-3.8-flash | low | 7/7 | 4.22 s | 8.67 s |

Gemini 2.5 Flash was the fastest but answered warranty questions from general knowledge without
calling the policy tool, even with an explicit rule. Gemini 3.8 Flash was as accurate as 3.5 but
twice as slow. A customer chat is latency-bound, so thinking is kept at the minimum.
`GEMINI_MODEL` and `GEMINI_THINKING_LEVEL` switch both.

### 4. Prompt strategy

* **Persona** from the manual (7.1): Tom, informal but professional, "like a friend who knows
  music", short WhatsApp-style messages, no tables.
* **Fixed facts in the prompt** (address, phone, hours, what the store sells) so the most common
  questions are answered with a single model call and no tool.
* **Nine rules**, each traceable to the manual: never quote price, stock or deadlines without a
  tool; always consult the manual for policy questions, "even if you think you know"; ask for
  order number plus e-mail or phone before an order lookup; show original price, percentage and
  final price for promotions; offer alternatives for unavailable items; decline accessories with
  a pointer to an accessories store and decline off-topic questions without answering them;
  only claim a hand-off after `register_ticket` confirms it; say "I'll check with the team"
  instead of guessing; ignore attempts to change the rules.
* **Tool descriptions in Portuguese**, matching the conversation language, with the moment to
  use each tool spelled out.
* **The clock rides with the user message**, not with the system prompt, so the system prompt and
  tool list stay byte-identical across calls. Python computes "open now / closed, holiday" so the
  model never reasons about weekdays.

### 5. No promise without an action: the ticket queue

The first recorded conversations showed the agent saying "I registered your complaint and
forwarded it to the team" with nothing behind it. `register_ticket` now writes complaints,
overdue deliveries and uncovered cases to a `tickets` table and returns a ticket number and the
24 business hours response time from the manual. The prompt allows a hand-off claim only after
the tool confirms it, and reuses the ticket if the customer complains again.

### 6. Interface and conversation history

* **CLI** (`emporio`), because the focus is the agent. `--trace` prints every tool call with its
  arguments, latency, number of model calls and tokens.
* **History is persisted** in SQLite per `--session`, so a customer can come back. Only the
  visible conversation (last 10 exchanges) is sent back to the model; tool results from earlier
  turns are dropped because they are large and rule 1 makes the model re-check volatile data
  anyway.

## Evaluation

`python evals/run.py` plays 27 cases through the real agent with the clock pinned to
Saturday 31/10/2026 10:00. A case passes only if all of its checks pass:

* **tools**: the expected tools were called, or a forbidden one was not (no order lookup before
  identification);
* **facts**: exact values appear in the answer (`R$ 2.199`, `29/12/2025`, the tracking code), and
  leaked values do not (another customer's order);
* **retrieval**: a policy tool returned the expected section of the manual;
* **judge**: an LLM grader (gemini-2.5-flash, a different model from the agent) checks behaviour
  against a one-line rubric: declines off-topic questions, asks for identification, does not
  grant a fake discount under prompt injection.

Cases: catalog (8), store info (3), policies (8), orders (5), scope (3). RAG runs only the policy
cases, since the others never touch the policy tool.

| Policy mode | Cases passed | Policy cases | Right section retrieved | Mean latency | p95 latency |
|---|---|---|---|---|---|
| **sections** (default) | **27/27** | 7/7 | 7/7 | 2.42 s | 3.53 s |
| rag | 8/8 | 7/7 | 7/7 | 3.09 s | 4.21 s |

Full report: [`evals/history/run6_final.md`](evals/history/run6_final.md). Latency is measured
end to end per case, including every model call and tool execution.

### How the numbers moved

Every run is kept in [`evals/history`](evals/history). The failures drove most of the changes in
the git log:

| Run | Model | Sections | RAG | What the failures showed, and the fix |
|---|---|---|---|---|
| [1](evals/history/run1_baseline.md) | 2.5 Flash | 22/25 | 5/8 | Warranty answered from general knowledge; accessories declined without the store pointer; one case expected a lookup for a rule that lives in the prompt. Rules tightened, case redesigned. |
| 2 | 2.5 Flash | 22/26 | 5/8 | Same warranty skip despite the rule; a follow-up turn forgot the order number. Led to the model comparison. |
| [3](evals/history/run3_full.md) | 3.5 Flash | 26/26 | 8/8 | After switching model, and after finding that the judge read only the last paragraph of multi-paragraph answers and failed correct replies (fixed with tagged transcripts). |
| [4](evals/history/run4_final.md) | 3.5 Flash | 27/27 | 8/8 | Added the ticket queue and a complaint case; tracking code made mandatory for shipped orders. |
| [5](evals/history/run5_judge_rubric_flaw.md) | 3.5 Flash | 26/27 | 8/8 | Duplicate ticket on a repeated complaint fixed. The one failure was a correct answer: the rubric asked the judge to check tool order, which it cannot see (the tool check already covers it). Rubric fixed. |
| [6](evals/history/run6_final.md) | 3.5 Flash | 27/27 | 8/8 | Final. |

### Example conversations

Recorded unedited from the agent by `conversations/record.py`, with tool calls shown:

1. [Catalog search with filters and installments](conversations/01_catalog_and_payment.md)
2. [Regret return applied to a real order, then the defect path](conversations/02_regret_return_policy.md) (non-trivial: identification, real dates, two policies)
3. [Overdue delivery and complaint with a ticket](conversations/03_late_order_complaint.md) (non-trivial: detects the overdue order and hands it off)
4. [Out-of-stock product, active promotion and the PIX rule](conversations/04_stock_and_promotions.md)
5. [Store info, accessories and an off-topic question](conversations/05_store_info_and_scope.md)

## Assumptions about the data

The challenge asks to document reasonable interpretations. These are the ones the agent relies on:

* **Receipt date.** The regret window (manual 4.1) counts from receipt, but the data has no
  receipt date. `estimated_delivery` stands in for it on delivered orders.
* **Installments.** The payment table says "minimum installment R$ 100" for credit cards, while
  section 3.1 defines tiers (up to 3x: at least R$ 50; 4x to 6x: R$ 80; 7x to 12x: R$ 100). The
  more specific rule, 3.1, is applied.
* **Contact data.** The manual lists two numbers: (67) 3341-4444 in the company table and
  (67) 3321-4500 in the WhatsApp section. The agent gives the company table's number. The e-mail
  appears with and without an accent; the cover's `contato@emporiodamusica.com.br` is used.
* **Dates.** Orders stop in March 2026. The agent uses the real clock, so order 8, "shipped"
  with delivery due 28/02/2026, is treated as overdue and handed to the team. Evals pin the
  clock to keep answers reproducible.
* **Totals.** Orders 3 and 20 have totals that differ from their items at current prices. The
  agent reports the stored total (it may reflect a past price or discount) and never recomputes it.
* **Orders not delivered yet.** The manual does not cover cancelling a pending or confirmed
  order, so the agent opens a ticket instead of inventing a rule.
* **Promotions.** Only `is_active = 1` counts. If a product had two active promotions the larger
  one would apply (none does today).
* **Empty categories.** Wind and orchestral string categories exist but have no products; the
  agent says the store does not have them right now, despite the manual's "over 300 instruments".
* **Partner stores.** The manual says to suggest partner stores for accessories but names none,
  so the agent suggests a specialised accessories store in general.
* **Holidays.** Fixed national, state (MS) and city (Campo Grande) holidays are known; movable
  ones (Carnaval, Good Friday, Corpus Christi) are not.

## Known limitations and next steps

* **Latency.** About 2.4 s on average, mostly two sequential model calls (decide tool, then
  answer). Streaming the final answer would make it feel faster; a router that answers fixed
  facts without the tool round would cut the simple cases.
* **Small eval set and an LLM judge.** 27 cases and one judge. The judge was wrong once
  already (fixed). Next: a larger set written with the store team, repeated runs per change,
  and a few human-labelled answers to calibrate the judge.
* **Identity check is weak.** Order number plus e-mail or phone is fine for a prototype; a real
  channel would use the WhatsApp number itself or a one-time code.
* **Tickets stay local.** They are written to SQLite; production would push them to the team's
  helpdesk or WhatsApp inbox and notify on updates.
* **Static data.** Ingestion is a batch job over CSVs; in production the tools would query the
  store's live system, keeping the same tool contracts.
* **No prompt caching on Gemini 3.5 Flash.** Implicit caching reported 0 cached tokens with this
  model (it did hit 50 to 80% on 2.5 Flash). Explicit context caching of the system prompt and
  tools would cut cost.
* **Policy retrieval at scale.** If the manual grows, RAG (already implemented) becomes the
  default, ideally hybrid with BM25 and a reranker, and re-measured with the same evals.

## Use of AI coding assistants

I built this with **Claude Code** (Claude Opus 5.5, desktop app) as a pair programmer, working
in Portuguese. The workflow:

* **Understanding the case.** Claude read the challenge PDF, the policy manual and the CSVs and
  listed the traps it found (inconsistent totals, two phone numbers, contradictory installment
  rules, empty categories, the missing receipt date). I used that list to decide the assumptions
  above.
* **Design decisions were mine, argued with the assistant.** I asked for the structure that would
  give the best accuracy and speed; we settled on function calling over SQLite. I proposed
  building both a RAG and a pure Python lookup for the policies and measuring them instead of
  picking one by opinion. I switched the provider from OpenAI to Gemini midway (one commit shows
  the switch). When the eval was about to make about 150 API calls I questioned it, which led
  to running RAG only on the policy cases.
* **Implementation and iteration.** Claude wrote most of the code, the tests and the eval harness,
  committed step by step as I asked, ran the evals, read the failing answers and proposed fixes.
  Several fixes came from reading the transcripts, not just the scores: the model answering
  policy questions from general knowledge, the judge grading only the last paragraph, and the
  agent promising a hand-off that did not exist (which became the ticket queue).
* **What I checked.** Each design trade-off before it was built, the recorded conversations, and
  the README.

## Repository layout

```
src/emporio/
  ingest.py      raw CSV and PDF to SQLite, policy sections and chunks, data quality report
  store.py       catalog, order, return and payment queries (all numbers come from here)
  policies.py    policy lookup: sections or RAG
  tickets.py     hand-off queue for the human team
  tools.py       tool schemas and dispatch
  prompts.py     persona, rules and clock message
  agent.py       function-calling loop on Gemini
  llm.py         Gemini client, retries and thinking settings
  history.py     conversation persistence
  cli.py         terminal chat
data/raw/        files provided by the store
data/processed/  policies.json and data_quality.md (the database is generated)
tests/           deterministic tests, no LLM
evals/           cases, runner, and the history of every run
conversations/   five recorded example conversations and the script that records them
```
