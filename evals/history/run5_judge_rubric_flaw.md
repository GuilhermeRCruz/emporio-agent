# Eval report

Model `gemini-3.5-flash`, judge `gemini-2.5-flash`, clock pinned to 2026-10-31T10:00:00, run on 2026-11-01 01:06.

| Policy mode | Cases passed | Policy cases passed | Right section retrieved | Mean latency | p95 latency | Mean latency on policy cases | Mean input tokens | Cached input |
|---|---|---|---|---|---|---|---|---|
| sections | 26/27 | 7/7 | 7/7 | 2.34s | 3.39s | 2.27s | 4987 | 0% |
| rag | 8/8 | 7/7 | 7/7 | 3.47s | 4.41s | 3.33s | 5408 | 0% |

## Failures, sections

* `order_complaint_opens_ticket`: judge: The assistant claims the complaint was already registered before providing the ticket number, which violates the rubric's condition.

## Failures, rag

None.
