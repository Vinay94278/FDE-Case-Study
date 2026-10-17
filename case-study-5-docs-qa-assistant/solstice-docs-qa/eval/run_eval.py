"""Run the evaluation set and print a results table.

  python -m eval.run_eval                     # uses .env (LLM mode if a key is set)
  python -m eval.run_eval --mode extractive   # force no-LLM mode
  python -m eval.run_eval --baseline          # the starter kit, for before/after

Writes eval/results_<mode>.md.
"""
import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import load_settings  # noqa: E402
from app.qa import QAService  # noqa: E402


def norm(text: str) -> str:
    return " ".join(text.lower().replace(",", "").split())


def judge(item: dict, status: str, answer: str, cited_docs: set[str]) -> tuple[bool, str]:
    if status not in item["expected_statuses"]:
        return False, f"expected {'/'.join(item['expected_statuses'])}"
    if status in {"answered", "partial"}:
        expected_docs = set(item["expected_doc_ids"])
        if expected_docs:
            ok = expected_docs <= cited_docs if status == "answered" else bool(expected_docs & cited_docs)
            if not ok:
                return False, f"cited {sorted(cited_docs)}, expected {sorted(expected_docs)}"
        needles = item["must_include_any"]
        if needles and not any(norm(n) in norm(answer) for n in needles):
            return False, f"answer missing key fact ({' / '.join(needles)})"
    return True, ""


def run_baseline(questions):
    """Starter kit: fixed 400-char chunks + keyword overlap, top-1 chunk, never refuses."""
    from baseline.docs_qa_utils import chunk_all_docs, find_best_chunks, load_docs
    chunks = chunk_all_docs(load_docs(ROOT / "data" / "docs.json"))
    for item in questions:
        t = time.perf_counter()
        score, chunk = find_best_chunks(item["question"], chunks, top_n=1)[0]
        status = "answered" if score > 0 else "not_covered"
        yield item, status, chunk["text"], {chunk["doc_id"]}, int((time.perf_counter() - t) * 1000)


def run_service(questions, service):
    for item in questions:
        r = service.ask(item["question"])
        yield item, r.status, r.answer, {c.doc_id for c in r.citations}, r.latency_ms, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto", "extractive"], default="auto")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--questions", default=str(ROOT / "data" / "eval_questions.json"))
    args = ap.parse_args()

    questions = json.load(open(args.questions, encoding="utf-8"))["questions"]

    if args.baseline:
        label, rows_iter = "baseline_starter_kit", run_baseline(questions)
    else:
        settings = load_settings()
        if args.mode == "extractive":
            settings = replace(settings, llm_provider="none")
        service = QAService(settings)
        label = service.mode if service.mode == "extractive" else f"llm_{service.llm.name.replace('/', '_').replace(':', '_')}"
        print("Health:", service.health())
        rows_iter = run_service(questions, service)

    rows, stats = [], {"pass": 0, "hallucinated": 0, "false_refusal": 0, "fallbacks": 0, "latency": []}
    for item, status, answer, cited, latency, *rest in rows_iter:
        ok, why = judge(item, status, answer, cited)
        answerable = "answered" in item["expected_statuses"]
        if ok:
            stats["pass"] += 1
        if not answerable and status == "answered":
            stats["hallucinated"] += 1
            why = "ANSWERED AN UNANSWERABLE QUESTION. " + why
        if answerable and status == "not_covered":
            stats["false_refusal"] += 1
        if rest and rest[0].mode == "extractive_fallback":
            stats["fallbacks"] += 1
        stats["latency"].append(latency)
        reason = rest[0].reason if rest else ""
        rows.append((item["id"], item["category"], item["question"], "/".join(item["expected_statuses"]),
                     status, "PASS" if ok else "FAIL", why or reason))
        print(f"{item['id']:5} {'PASS' if ok else 'FAIL'}  {status:12} {item['question'][:60]:60} {why}")

    n = len(rows)
    answerable_n = sum(1 for q in questions if "answered" in q["expected_statuses"])
    lat = sorted(stats["latency"])
    summary = [
        f"Mode: {label}",
        f"Overall pass: {stats['pass']}/{n}",
        f"Answered an unanswerable question (hallucination risk): {stats['hallucinated']}/{n - answerable_n}",
        f"Refused an answerable question (false refusal): {stats['false_refusal']}/{answerable_n}",
        f"LLM failures that fell back to extractive: {stats['fallbacks']}",
        f"Latency p50 / max: {lat[n // 2]} ms / {lat[-1]} ms",
    ]
    print("\n" + "\n".join(summary))

    out = ROOT / "eval" / f"results_{label}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# Eval results: {label}\n\n" + "\n".join(f"- {s}" for s in summary) + "\n\n")
        f.write("| ID | Category | Question | Expected | Got | Result | Notes |\n|---|---|---|---|---|---|---|\n")
        for r in rows:
            f.write("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |\n")
    print(f"\nWrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
