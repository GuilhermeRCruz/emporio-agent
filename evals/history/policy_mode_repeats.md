# Sections vs RAG, repeated

The 8 policy cases run 3 times per mode on 2026-11-01 (gemini-3.5-flash, minimal thinking,
judge gemini-2.5-flash), after the judge fix.

| Policy mode | Passed | Mean latency | Median latency | Mean input tokens | Model calls per case |
|---|---|---|---|---|---|
| sections | 24/24 | 2.60s | 2.42s | 4695 | 2.12 |
| rag | 24/24 | 3.14s | 3.00s | 4701 | 2.12 |

Per-run tables:

| Run | sections mean / p95 | rag mean / p95 |
|---|---|---|
| 1 | 2.50s / 3.62s | 3.15s / 3.91s |
| 2 | 2.58s / 3.94s | 3.17s / 4.20s |
| 3 | 2.74s / 3.76s | 3.11s / 3.90s |

Same accuracy. RAG pays about 0.55s per policy question for the query embedding round trip, and
sends about the same number of tokens (three chunks are roughly one section). Default: sections.
