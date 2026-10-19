"""Answer the 5 questions provided with the brief and show each answer in full.

    python -m eval.answer_provided_questions                  # mode from .env
    python -m eval.answer_provided_questions --mode extractive

Prints every answer (or the honest refusal) with its sources, and writes
eval/provided_questions_<mode>.md for reviewers.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.application_container import ApplicationContainer  # noqa: E402
from app.core.logging_config import configure_logging  # noqa: E402
from app.core.settings import Settings  # noqa: E402
from app.dto.ask_dto import AskRequestDTO, AskResponseDTO  # noqa: E402

PROVIDED_QUESTIONS_PATH = PROJECT_ROOT / "data" / "example_questions.json"


def format_answer_block(provided_question: dict, response_dto: AskResponseDTO) -> List[str]:
    expected_doc_id = provided_question.get("expected_doc_id")
    if expected_doc_id is None:
        expected_doc_id = "none (docs do not cover it)"

    block_lines = [
        "### " + provided_question["question_id"] + ": " + provided_question["question"],
        "",
        "- Expected source: " + str(expected_doc_id),
        "- Outcome: **" + response_dto.answer_status + "** (" + response_dto.mode + ", " + response_dto.decision_reason + ")",
        "- Answer: " + response_dto.answer,
    ]
    if response_dto.missing_information:
        block_lines.append("- Not covered: " + response_dto.missing_information)
    for citation in response_dto.citations:
        block_lines.append("- Source " + citation.sentence_id + " (" + citation.title + "): \"" + citation.text + "\"")
    for related_document in response_dto.related_documents:
        block_lines.append("- Related article: " + related_document.title)
    block_lines.append("")
    return block_lines


async def main_async(arguments) -> None:
    settings_overrides = {"query_log_store": "none", "log_level": "WARNING"}
    if arguments.mode == "extractive":
        settings_overrides["llm_provider"] = "none"
    settings = Settings(**settings_overrides)
    configure_logging(settings.log_level, settings.log_format)
    container = await ApplicationContainer.create(settings)

    with open(PROVIDED_QUESTIONS_PATH, encoding="utf-8") as questions_file:
        provided_questions = json.load(questions_file)["example_questions"]

    mode_label = container.question_answering_service.get_answer_mode_name()
    report_lines = ["# Answers to the provided questions (" + mode_label + ")", ""]
    try:
        for provided_question in provided_questions:
            request_dto = AskRequestDTO(question=provided_question["question"])
            response_dto = await container.question_answering_service.answer_question(request_dto)
            report_lines.extend(format_answer_block(provided_question, response_dto))
    finally:
        await container.close()

    output_path = PROJECT_ROOT / "eval" / ("provided_questions_" + mode_label + ".md")
    with open(output_path, "w", encoding="utf-8") as report_file:
        report_file.write("\n".join(report_lines))
    print("\n".join(report_lines))
    print("Wrote " + str(output_path.relative_to(PROJECT_ROOT)))


def parse_arguments():
    argument_parser = argparse.ArgumentParser(description="Answer the 5 provided questions")
    argument_parser.add_argument("--mode", choices=["auto", "extractive"], default="auto")
    return argument_parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main_async(parse_arguments()))
