# Model comparison

Run on 2026-11-01 over the 7 hardest cases (policy lookups the model tends to skip, multi-turn order
lookup, accessory redirection), sections mode, prompt as of commit "Tighten policy and accessory rules".
Judge: gemini-2.5-flash.

| Model | Thinking | Passed | Mean latency | p95 latency |
|---|---|---|---|---|
| gemini-2.5-flash | budget 0 | 5/7 | 1.65s | 2.98s |
| gemini-3.5-flash | low | 6/7 | 2.52s | 3.98s |
| **gemini-3.5-flash** | **minimal** | **7/7** | **2.22s** | **3.50s** |
| gemini-3.8-flash | low | 7/7 | 4.22s | 8.67s |
| gemini-3.8-flash | minimal | not supported (400) | | |

gemini-2.5-flash answered warranty questions from general knowledge without calling the policy tool,
even with an explicit rule, and skipped the accessory-store suggestion. gemini-3.8-flash is as accurate
as 3.5 Flash but twice as slow. Chosen default: gemini-3.5-flash with minimal thinking.
