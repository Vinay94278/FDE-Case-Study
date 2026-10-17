"""API contract: every endpoint, success or error, returns the same envelope."""
import asyncio

from fastapi.testclient import TestClient

from app.api.dependencies import get_question_answering_service
from app.core.application_container import ApplicationContainer
from app.main import create_app
from tests.helpers import build_test_settings

ENVELOPE_FIELDS = {"status", "status_code", "message", "technical_message", "error_code", "data", "request_id", "timestamp"}


class BrokenQuestionAnsweringService:
    async def answer_question(self, request_dto):
        raise RuntimeError("database exploded")


def provide_broken_service():
    return BrokenQuestionAnsweringService()


def build_client(tmp_path, raise_server_exceptions=True):
    settings = build_test_settings(query_log_store="jsonl", query_log_path=tmp_path / "queries.jsonl")
    container = asyncio.run(ApplicationContainer.create(settings))
    application = create_app(settings=settings, container=container)
    return application, TestClient(application, raise_server_exceptions=raise_server_exceptions)


def test_ask_success_uses_envelope(tmp_path):
    _, client = build_client(tmp_path)
    with client:
        response = client.post("/api/v1/ask", json={"question": "How do I set up SSO?"})
    body = response.json()
    assert response.status_code == 200
    assert set(body.keys()) == ENVELOPE_FIELDS
    assert body["status"] == "success"
    assert body["data"]["answer_status"] == "answered"
    assert response.headers["X-Request-ID"] == body["request_id"]


def test_incoming_request_id_is_reused(tmp_path):
    _, client = build_client(tmp_path)
    with client:
        response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-123"})
    assert response.json()["request_id"] == "trace-123"


def test_validation_error_lists_fields(tmp_path):
    _, client = build_client(tmp_path)
    with client:
        response = client.post("/api/v1/ask", json={"question": "x" * 600})
    body = response.json()
    assert response.status_code == 422
    assert body["status"] == "error"
    assert body["error_code"] == "VALIDATION_FAILED"
    assert body["data"][0]["field"] == "question"


def test_invalid_json_body_is_handled(tmp_path):
    _, client = build_client(tmp_path)
    with client:
        response = client.post("/api/v1/ask", content="not json", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_FAILED"


def test_unknown_route_and_wrong_method_use_envelope(tmp_path):
    _, client = build_client(tmp_path)
    with client:
        not_found_response = client.get("/api/v1/does-not-exist")
        wrong_method_response = client.get("/api/v1/ask")
    assert not_found_response.status_code == 404
    assert not_found_response.json()["error_code"] == "NOT_FOUND"
    assert wrong_method_response.status_code == 405
    assert wrong_method_response.json()["error_code"] == "METHOD_NOT_ALLOWED"


def test_unexpected_exception_returns_500_envelope(tmp_path):
    application, client = build_client(tmp_path, raise_server_exceptions=False)
    application.dependency_overrides[get_question_answering_service] = provide_broken_service
    with client:
        response = client.post("/api/v1/ask", json={"question": "How do I set up SSO?"})
    body = response.json()
    assert response.status_code == 500
    assert body["error_code"] == "INTERNAL_ERROR"
    assert body["message"] == "An unexpected error occurred. Please try again."
    assert "RuntimeError" in body["technical_message"]


def test_technical_message_hidden_when_disabled(tmp_path):
    settings = build_test_settings(expose_technical_messages=False)
    application = create_app(settings=settings, container=asyncio.run(ApplicationContainer.create(settings)))
    application.dependency_overrides[get_question_answering_service] = provide_broken_service
    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/ask", json={"question": "How do I set up SSO?"})
    assert response.json()["technical_message"] is None


def test_health_feedback_and_gap_report(tmp_path):
    _, client = build_client(tmp_path)
    with client:
        health_body = client.get("/api/v1/health").json()
        client.post("/api/v1/ask", json={"question": "Does Solstice have a mobile app?"})
        feedback_response = client.post(
            "/api/v1/feedback",
            json={"question": "Does Solstice have a mobile app?", "answer_status": "not_covered", "helpful": False},
        )
        gaps_body = client.get("/api/v1/insights/documentation-gaps").json()
    assert health_body["data"]["answer_mode"] == "extractive"
    assert health_body["data"]["document_count"] == 6
    assert feedback_response.status_code == 201
    assert gaps_body["data"]["gaps"][0]["question"] == "does solstice have a mobile app?"


def test_gap_report_limit_is_validated(tmp_path):
    _, client = build_client(tmp_path)
    with client:
        response = client.get("/api/v1/insights/documentation-gaps?limit=0")
    assert response.status_code == 422


def test_ui_is_served(tmp_path):
    _, client = build_client(tmp_path)
    with client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Solstice Help" in response.text
