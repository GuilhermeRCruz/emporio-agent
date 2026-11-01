"""Runs every case in evals/cases.json against the agent, once per policy mode.

    python evals/run.py                    both modes
    python evals/run.py --modes rag        one mode
    python evals/run.py --only order_      cases whose id starts with a prefix

Each case passes only if every check passes:
    tools / tools_any / forbid_tools   which tools the agent called
    must_include / must_not_include    exact facts in the final answer (accent and case insensitive)
    policy_section                     a policy tool was called and returned the expected section
    judge                              an LLM grader checks behaviour against a one-line rubric

The clock is pinned to Saturday 31/10/2026 10:00 so date-based answers are stable.
"""

import argparse
import json
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("EMPORIO_NOW", "2026-10-31T10:00:00")
os.environ.setdefault("EMPORIO_STATE_DB", str(Path(__file__).parent / "results" / "state.db"))

from google.genai import types  # noqa: E402

from emporio import config, llm, policies  # noqa: E402
from emporio.agent import Agent  # noqa: E402
from emporio.text import normalize  # noqa: E402

EVALS_DIR = Path(__file__).parent
POLICY_TOOLS = {"get_store_policy", "search_store_policy"}
JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "gemini-2.5-flash")

JUDGE_PROMPT = """\
You grade a customer service assistant of a Brazilian musical instrument store.
Read the conversation and decide if the assistant's final reply, the whole text inside
<final_reply>, satisfies the rubric. Replies can have several paragraphs; consider all of them.
Be strict about the facts in the rubric and lenient about wording and tone.
Answer only with JSON: {"pass": true|false, "reason": "<one sentence>"}"""


def judge(turns: list[str], answers: list[str], rubric: str) -> tuple[bool, str]:
    # Explicit tags: with plain "Assistant:" prefixes the judge read the last paragraph
    # of a multi-paragraph answer as the whole reply and failed correct answers.
    earlier = "\n".join(
        f"<customer>{u}</customer>\n<assistant>{a}</assistant>" for u, a in zip(turns[:-1], answers[:-1])
    )
    transcript = f"{earlier}\n<customer>{turns[-1]}</customer>\n<final_reply>{answers[-1]}</final_reply>"
    response = llm.client().models.generate_content(
        model=JUDGE_MODEL,
        contents=f"<conversation>\n{transcript.strip()}\n</conversation>\n\n<rubric>{rubric}</rubric>",
        config=types.GenerateContentConfig(
            system_instruction=JUDGE_PROMPT,
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    verdict = json.loads(response.text)
    return bool(verdict.get("pass")), verdict.get("reason", "")


def section_title(key: str) -> str:
    return next(s["title"] for s in policies.load()["sections"] if s["key"] == key)


def policy_hit(calls, expected_key: str) -> bool:
    """True if any policy tool call returned the expected section (or a chunk of it)."""
    title = section_title(expected_key)
    for call in calls:
        if call.name not in POLICY_TOOLS:
            continue
        out = json.loads(call.output)
        found = [out.get("secao", "")] + [t["secao"] for t in out.get("trechos", [])]
        if any(f.startswith(title) for f in found):
            return True
    return False


def run_case(mode: str, case: dict, model: str) -> dict:
    agent = Agent(policy_mode=mode, model=model)
    replies = [agent.ask(turn) for turn in case["turns"]]
    final = replies[-1]
    calls = [c for r in replies for c in r.tool_calls]
    called = {c.name for c in calls}
    answer = normalize(final.text)
    failures = []

    for tool in case.get("tools", []):
        if tool not in called:
            failures.append(f"did not call {tool}")
    if case.get("tools_any") and not called & set(case["tools_any"]):
        failures.append(f"called none of {case['tools_any']}")
    for tool in case.get("forbid_tools", []):
        if tool in called:
            failures.append(f"should not call {tool}")
    for fact in case.get("must_include", []):
        if normalize(fact) not in answer:
            failures.append(f"missing '{fact}'")
    for fact in case.get("must_not_include", []):
        if normalize(fact) in answer:
            failures.append(f"leaked '{fact}'")

    retrieval_ok = None
    if case.get("policy_section"):
        retrieval_ok = policy_hit(calls, case["policy_section"])
        if not retrieval_ok:
            failures.append(f"policy section '{case['policy_section']}' not retrieved")

    judge_reason = None
    if case.get("judge"):
        ok, judge_reason = judge(case["turns"], [r.text for r in replies], case["judge"])
        if not ok:
            failures.append(f"judge: {judge_reason}")

    return {
        "id": case["id"],
        "group": case["group"],
        "passed": not failures,
        "failures": failures,
        "retrieval_ok": retrieval_ok,
        "answer": final.text,
        "tool_calls": [{"name": c.name, "arguments": c.arguments} for c in calls],
        "seconds": sum(r.seconds for r in replies),
        "llm_calls": sum(r.llm_calls for r in replies),
        "input_tokens": sum(r.input_tokens for r in replies),
        "cached_tokens": sum(r.cached_tokens for r in replies),
        "output_tokens": sum(r.output_tokens for r in replies),
    }


def summarize(mode: str, results: list[dict]) -> dict:
    seconds = sorted(r["seconds"] for r in results)
    policy = [r for r in results if r["retrieval_ok"] is not None]
    return {
        "mode": mode,
        "passed": sum(r["passed"] for r in results),
        "total": len(results),
        "policy_passed": sum(r["passed"] for r in policy),
        "policy_total": len(policy),
        "retrieval_hits": sum(r["retrieval_ok"] for r in policy),
        "mean_seconds": statistics.mean(seconds),
        "p95_seconds": seconds[max(0, round(0.95 * len(seconds)) - 1)],
        "policy_mean_seconds": statistics.mean(r["seconds"] for r in policy) if policy else 0,
        "mean_input_tokens": statistics.mean(r["input_tokens"] for r in results),
        "cache_ratio": sum(r["cached_tokens"] for r in results) / max(1, sum(r["input_tokens"] for r in results)),
    }


def report(summaries: list[dict], all_results: dict[str, list[dict]], model: str) -> str:
    lines = [
        f"# Eval report\n\nModel `{model}`, judge `{JUDGE_MODEL}`, "
        f"clock pinned to {os.environ['EMPORIO_NOW']}, run on {datetime.now():%Y-%m-%d %H:%M}.\n",
        "| Policy mode | Cases passed | Policy cases passed | Right section retrieved | Mean latency | p95 latency | "
        "Mean latency on policy cases | Mean input tokens | Cached input |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        lines.append(
            f"| {s['mode']} | {s['passed']}/{s['total']} | {s['policy_passed']}/{s['policy_total']} | "
            f"{s['retrieval_hits']}/{s['policy_total']} | {s['mean_seconds']:.2f}s | {s['p95_seconds']:.2f}s | "
            f"{s['policy_mean_seconds']:.2f}s | {s['mean_input_tokens']:.0f} | {s['cache_ratio']:.0%} |"
        )
    for mode, results in all_results.items():
        failed = [r for r in results if not r["passed"]]
        lines.append(f"\n## Failures, {mode}\n")
        lines += [f"* `{r['id']}`: {'; '.join(r['failures'])}" for r in failed] or ["None."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modes", nargs="+", default=["sections", "rag"])
    parser.add_argument("--only", nargs="+", default=[""], help="run only cases whose id starts with one of these")
    parser.add_argument("--model", default=config.GEMINI_MODEL)
    parser.add_argument(
        "--all-cases-in-rag",
        action="store_true",
        help="by default rag runs only the policy cases: the other cases never touch the policy tool",
    )
    args = parser.parse_args()

    cases = [c for c in json.loads((EVALS_DIR / "cases.json").read_text()) if c["id"].startswith(tuple(args.only))]
    out_dir = EVALS_DIR / "results"
    out_dir.mkdir(exist_ok=True)

    summaries, all_results = [], {}
    for mode in args.modes:
        results = []
        mode_cases = cases if mode == "sections" or args.all_cases_in_rag else [c for c in cases if c["group"] == "policy"]
        for case in mode_cases:
            try:
                result = run_case(mode, case, args.model)
            except Exception as exc:  # one API failure should not throw away the whole run
                if "PerDay" in str(exc):
                    sys.exit(f"Daily API quota exhausted at case {case['id']}: {str(exc)[:200]}")
                result = {"id": case["id"], "group": case["group"], "passed": False, "seconds": 0.0,
                          "failures": [f"error: {str(exc)[:200]}"], "retrieval_ok": None, "answer": "",
                          "tool_calls": [], "llm_calls": 0, "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0}
            results.append(result)
            mark = "PASS" if result["passed"] else "FAIL"
            print(f"[{mode}] {mark} {case['id']} ({result['seconds']:.1f}s) {'; '.join(result['failures'])}", flush=True)
        all_results[mode] = results
        summaries.append(summarize(mode, results))
        (out_dir / f"{mode}.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))

    text = report(summaries, all_results, args.model)
    (out_dir / "report.md").write_text(text)
    print("\n" + text)
    sys.exit(0 if all(s["passed"] == s["total"] for s in summaries) else 1)


if __name__ == "__main__":
    main()
