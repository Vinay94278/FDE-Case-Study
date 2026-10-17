"""Run the evaluation set and write a results table.

    python -m eval.run_eval                          # mode from .env (LLM if a key is set)
    python -m eval.run_eval --mode extractive        # force no-LLM mode
    python -m eval.run_eval --baseline               # the starter kit, for before/after
    python -m eval.run_eval --runs 3                 # repeat to check LLM stability
    python -m eval.run_eval --split test             # only the held-out questions

Writes eval/results_<label>.md. The query log is switched off during evaluation so
test questions do not pollute the documentation gap report.
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.application_container import ApplicationContainer  # noqa: E402
from app.core.logging_config import configure_logging  # noqa: E402
from app.core.settings import Settings  # noqa: E402
from app.dto.ask_dto import AskRequestDTO, ConversationTurnDTO  # noqa: E402

ANSWERED = "answered"
PARTIAL = "partial"
NOT_COVERED = "not_covered"


@dataclass
class QuestionOutcome:
    question_id: str
    category: str
    split: str
    question: str
    expected_statuses: List[str]
    actual_status: str
    mode: str
    decision_reason: str
    passed: bool
    note: str
    latency_ms: int


# ---------------------------------------------------------------------- judging

def normalize_for_matching(text: str) -> str:
    return " ".join(text.lower().replace(",", "").split())


def judge_outcome(eval_item: dict, actual_status: str, answer_text: str, cited_doc_ids: Set[str]):
    """Return (passed, note). The same rules apply to every mode."""
    expected_statuses = eval_item["expected_statuses"]
    if actual_status not in expected_statuses:
        return False, "expected " + "/".join(expected_statuses)

    if actual_status == ANSWERED or actual_status == PARTIAL:
        expected_doc_ids = set(eval_item["expected_doc_ids"])
        if len(expected_doc_ids) > 0:
            if actual_status == ANSWERED:
                documents_ok = expected_doc_ids.issubset(cited_doc_ids)
            else:
                documents_ok = len(expected_doc_ids & cited_doc_ids) > 0
            if not documents_ok:
                return False, "cited " + str(sorted(cited_doc_ids)) + ", expected " + str(sorted(expected_doc_ids))

        required_phrases = eval_item["must_include_any"]
        if len(required_phrases) > 0:
            normalized_answer = normalize_for_matching(answer_text)
            phrase_found = False
            for required_phrase in required_phrases:
                if normalize_for_matching(required_phrase) in normalized_answer:
                    phrase_found = True
                    break
            if not phrase_found:
                return False, "key fact missing (" + " / ".join(required_phrases) + ")"

    return True, ""


# ---------------------------------------------------------------------- running

def build_request_dto(eval_item: dict) -> AskRequestDTO:
    history_dtos = []
    for turn in eval_item.get("conversation_history", []):
        history_dtos.append(ConversationTurnDTO(question=turn["question"], answer=turn.get("answer", "")))
    return AskRequestDTO(question=eval_item["question"], conversation_history=history_dtos)


def build_outcome(eval_item: dict, actual_status: str, mode: str, decision_reason: str,
                  passed: bool, note: str, latency_ms: int) -> QuestionOutcome:
    is_answerable = ANSWERED in eval_item["expected_statuses"]
    if not is_answerable and actual_status == ANSWERED:
        note = "ANSWERED AN UNANSWERABLE QUESTION. " + note
    return QuestionOutcome(
        question_id=eval_item["id"],
        category=eval_item["category"],
        split=eval_item.get("split", "dev"),
        question=eval_item["question"],
        expected_statuses=eval_item["expected_statuses"],
        actual_status=actual_status,
        mode=mode,
        decision_reason=decision_reason,
        passed=passed,
        note=note,
        latency_ms=latency_ms,
    )


async def run_service_once(container: ApplicationContainer, eval_items: List[dict]) -> List[QuestionOutcome]:
    outcomes = []
    for eval_item in eval_items:
        request_dto = build_request_dto(eval_item)
        response_dto = await container.question_answering_service.answer_question(request_dto)
        cited_doc_ids = set()
        for citation in response_dto.citations:
            cited_doc_ids.add(citation.doc_id)
        passed, note = judge_outcome(eval_item, response_dto.answer_status, response_dto.answer, cited_doc_ids)
        outcome = build_outcome(
            eval_item,
            response_dto.answer_status,
            response_dto.mode,
            response_dto.decision_reason,
            passed,
            note,
            response_dto.latency_ms,
        )
        outcomes.append(outcome)
    return outcomes


def run_baseline_once(eval_items: List[dict]) -> List[QuestionOutcome]:
    """Starter kit: fixed 400-character chunks, keyword overlap, top chunk, never refuses."""
    from baseline.docs_qa_utils import chunk_all_docs, find_best_chunks, load_docs

    starter_chunks = chunk_all_docs(load_docs(PROJECT_ROOT / "data" / "docs.json"))
    outcomes = []
    for eval_item in eval_items:
        started_at = time.perf_counter()
        best_score, best_chunk = find_best_chunks(eval_item["question"], starter_chunks, top_n=1)[0]
        actual_status = NOT_COVERED
        if best_score > 0:
            actual_status = ANSWERED
        passed, note = judge_outcome(eval_item, actual_status, best_chunk["text"], {best_chunk["doc_id"]})
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        outcome = build_outcome(eval_item, actual_status, "baseline", "top_keyword_chunk", passed, note, latency_ms)
        outcomes.append(outcome)
    return outcomes


# ---------------------------------------------------------------------- reporting

def summarize_outcomes(outcomes: List[QuestionOutcome]) -> Dict[str, int]:
    summary = {
        "total": len(outcomes),
        "passed": 0,
        "answerable": 0,
        "unanswerable": 0,
        "answered_unanswerable": 0,
        "false_refusals": 0,
        "llm_unavailable": 0,
    }
    for outcome in outcomes:
        is_answerable = ANSWERED in outcome.expected_statuses
        if outcome.passed:
            summary["passed"] += 1
        if is_answerable:
            summary["answerable"] += 1
            if outcome.actual_status == NOT_COVERED:
                summary["false_refusals"] += 1
        else:
            summary["unanswerable"] += 1
            if outcome.actual_status == ANSWERED:
                summary["answered_unanswerable"] += 1
        if outcome.mode == "llm_unavailable":
            summary["llm_unavailable"] += 1
    return summary


def filter_by_split(outcomes: List[QuestionOutcome], split_name: str) -> List[QuestionOutcome]:
    filtered_outcomes = []
    for outcome in outcomes:
        if outcome.split == split_name:
            filtered_outcomes.append(outcome)
    return filtered_outcomes


def format_summary_line(label: str, outcomes: List[QuestionOutcome]) -> str:
    summary = summarize_outcomes(outcomes)
    return (
        label + ": pass " + str(summary["passed"]) + "/" + str(summary["total"])
        + ", answered an unanswerable question " + str(summary["answered_unanswerable"])
        + "/" + str(summary["unanswerable"])
        + ", false refusals " + str(summary["false_refusals"]) + "/" + str(summary["answerable"])
        + ", LLM unavailable " + str(summary["llm_unavailable"])
    )


def build_summary_lines(mode_label: str, all_runs: List[List[QuestionOutcome]], skipped_ids: List[str]) -> List[str]:
    summary_lines = ["Mode: " + mode_label, "Runs: " + str(len(all_runs))]
    pass_counts = []
    for run_number, run_outcomes in enumerate(all_runs, start=1):
        pass_counts.append(summarize_outcomes(run_outcomes)["passed"])
        summary_lines.append(format_summary_line("Run " + str(run_number) + ", all", run_outcomes))
        for split_name in ("dev", "test"):
            split_outcomes = filter_by_split(run_outcomes, split_name)
            if len(split_outcomes) > 0:
                summary_lines.append(format_summary_line("Run " + str(run_number) + ", " + split_name, split_outcomes))

    if len(all_runs) > 1:
        summary_lines.append(
            "Pass count across runs: min " + str(min(pass_counts)) + ", max " + str(max(pass_counts))
            + ", mean " + str(round(statistics.mean(pass_counts), 1))
        )

    latencies = []
    for outcome in all_runs[-1]:
        latencies.append(outcome.latency_ms)
    latencies.sort()
    if len(latencies) > 0:
        summary_lines.append(
            "Latency p50 / max (last run): " + str(latencies[len(latencies) // 2])
            + " ms / " + str(latencies[-1]) + " ms"
        )
    if len(skipped_ids) > 0:
        summary_lines.append("Skipped in this mode (need an LLM): " + ", ".join(skipped_ids))
    return summary_lines


def build_table_lines(outcomes: List[QuestionOutcome]) -> List[str]:
    table_lines = [
        "| ID | Split | Category | Question | Expected | Got | Mode | Result | Reason / note |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for outcome in outcomes:
        result_text = "FAIL"
        if outcome.passed:
            result_text = "PASS"
        note_text = outcome.decision_reason
        if outcome.note != "":
            note_text = outcome.decision_reason + ": " + outcome.note
        row_values = [
            outcome.question_id,
            outcome.split,
            outcome.category,
            outcome.question,
            "/".join(outcome.expected_statuses),
            outcome.actual_status,
            outcome.mode,
            result_text,
            note_text,
        ]
        cleaned_values = []
        for row_value in row_values:
            cleaned_values.append(str(row_value).replace("|", "/"))
        table_lines.append("| " + " | ".join(cleaned_values) + " |")
    return table_lines


def write_results_file(output_path: Path, mode_label: str, summary_lines: List[str], table_lines: List[str]) -> None:
    with open(output_path, "w", encoding="utf-8") as results_file:
        results_file.write("# Eval results: " + mode_label + "\n\n")
        for summary_line in summary_lines:
            results_file.write("- " + summary_line + "\n")
        results_file.write("\n")
        results_file.write("\n".join(table_lines))
        results_file.write("\n")


def print_run(run_outcomes: List[QuestionOutcome], run_number: int) -> None:
    for outcome in run_outcomes:
        result_text = "FAIL"
        if outcome.passed:
            result_text = "PASS"
        print(
            outcome.question_id.ljust(5),
            result_text,
            outcome.actual_status.ljust(12),
            outcome.mode.ljust(16),
            outcome.question[:55].ljust(55),
            outcome.note,
        )
    print("---- end of run " + str(run_number))


# ---------------------------------------------------------------------- main

def select_items(all_items: List[dict], split_name: str) -> List[dict]:
    if split_name == "all":
        return list(all_items)
    selected_items = []
    for eval_item in all_items:
        if eval_item.get("split", "dev") == split_name:
            selected_items.append(eval_item)
    return selected_items


def remove_llm_only_items(eval_items: List[dict], skipped_ids: List[str]) -> List[dict]:
    runnable_items = []
    for eval_item in eval_items:
        if eval_item.get("requires_llm", False):
            skipped_ids.append(eval_item["id"])
        else:
            runnable_items.append(eval_item)
    return runnable_items


async def main_async(arguments) -> None:
    with open(arguments.questions, encoding="utf-8") as questions_file:
        all_items = json.load(questions_file)["questions"]
    eval_items = select_items(all_items, arguments.split)

    skipped_ids: List[str] = []
    container: Optional[ApplicationContainer] = None
    if arguments.baseline:
        mode_label = "baseline_starter_kit"
        eval_items = remove_llm_only_items(eval_items, skipped_ids)
    else:
        settings_overrides = {"query_log_store": "none", "log_level": "WARNING"}
        if arguments.mode == "extractive":
            settings_overrides["llm_provider"] = "none"
        settings = Settings(**settings_overrides)
        configure_logging(settings.log_level, settings.log_format)
        container = await ApplicationContainer.create(settings)
        if container.llm_client is not None:
            display_name = container.llm_client.get_display_name()
            mode_label = "llm_" + display_name.replace("/", "_").replace(":", "_")
        else:
            mode_label = "extractive"
            eval_items = remove_llm_only_items(eval_items, skipped_ids)

    all_runs: List[List[QuestionOutcome]] = []
    try:
        for run_number in range(1, arguments.runs + 1):
            if arguments.baseline:
                run_outcomes = run_baseline_once(eval_items)
            else:
                run_outcomes = await run_service_once(container, eval_items)
            all_runs.append(run_outcomes)
            print_run(run_outcomes, run_number)
    finally:
        if container is not None:
            await container.close()

    summary_lines = build_summary_lines(mode_label, all_runs, skipped_ids)
    table_lines = build_table_lines(all_runs[-1])
    output_path = PROJECT_ROOT / "eval" / ("results_" + mode_label + ".md")
    write_results_file(output_path, mode_label, summary_lines, table_lines)

    print("")
    for summary_line in summary_lines:
        print(summary_line)
    print("")
    print("Wrote " + str(output_path.relative_to(PROJECT_ROOT)))


def parse_arguments():
    argument_parser = argparse.ArgumentParser(description="Evaluate the docs Q&A service")
    argument_parser.add_argument("--mode", choices=["auto", "extractive"], default="auto")
    argument_parser.add_argument("--baseline", action="store_true")
    argument_parser.add_argument("--runs", type=int, default=1)
    argument_parser.add_argument("--split", choices=["all", "dev", "test"], default="all")
    argument_parser.add_argument("--questions", default=str(PROJECT_ROOT / "data" / "eval_questions.json"))
    return argument_parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main_async(parse_arguments()))
