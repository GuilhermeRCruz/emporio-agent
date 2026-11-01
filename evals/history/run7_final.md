# Eval report

Model `gemini-3.5-flash`, judge `gemini-2.5-flash`, clock pinned to 2026-10-31T10:00:00, run on 2026-11-01 02:25.

| Policy mode | Cases passed | Policy cases passed | Right section retrieved | Mean latency | p95 latency | Mean latency on policy cases | Mean input tokens | Cached input |
|---|---|---|---|---|---|---|---|---|
| sections | 30/30 | 10/10 | 10/10 | 2.56s | 4.10s | 2.41s | 6161 | 0% |
| rag_parent | 10/11 | 9/10 | 10/10 | 3.25s | 3.55s | 3.23s | 6018 | 0% |

## Failures, sections

None.

## Failures, rag_parent

* `policy_mouthpiece_exchange`: judge: The assistant's reply states that mouthpieces are not exchanged but fails to mention hygiene reasons as required by the rubric.
