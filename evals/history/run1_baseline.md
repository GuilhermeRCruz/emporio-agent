# Eval report

Model `gemini-2.5-flash`, judge `gemini-2.5-flash`, clock pinned to 2026-10-31T10:00:00, run on 2026-11-01 00:41.

| Policy mode | Cases passed | Policy cases passed | Right section retrieved | Mean latency | p95 latency | Mean latency on policy cases | Mean input tokens | Cached input |
|---|---|---|---|---|---|---|---|---|
| sections | 22/25 | 5/7 | 5/7 | 1.41s | 2.21s | 1.40s | 3159 | 56% |
| rag | 5/8 | 4/7 | 5/7 | 1.80s | 2.50s | 1.82s | 3422 | 65% |

## Failures, sections

* `policy_warranty_strings`: policy section 'garantia' not retrieved
* `policy_pix_on_promotion`: policy section 'promocoes' not retrieved
* `scope_accessories`: judge: The assistant says the store only sells instruments, not accessories like strings, but does not suggest a specialised accessories store.

## Failures, rag

* `policy_warranty_strings`: policy section 'garantia' not retrieved
* `policy_pix_on_promotion`: policy section 'promocoes' not retrieved
* `policy_privacy`: judge: The assistant's reply states data is not shared for marketing but does not mention LGPD or the customer's right to request data deletion.
