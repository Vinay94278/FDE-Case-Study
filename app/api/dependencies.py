"""FastAPI dependencies that hand controllers their service (controllers never build services)."""
from fastapi import Depends, Request

from app.core.application_container import ApplicationContainer
from app.core.exceptions import ServiceUnavailableException
from app.services.feedback_service import FeedbackService
from app.services.health_service import HealthService
from app.services.insights_service import InsightsService
from app.services.question_answering_service import QuestionAnsweringService


def get_application_container(request: Request) -> ApplicationContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise ServiceUnavailableException(technical_message="Application container is not initialised")
    return container


def get_question_answering_service(
    container: ApplicationContainer = Depends(get_application_container),
) -> QuestionAnsweringService:
    return container.question_answering_service


def get_feedback_service(container: ApplicationContainer = Depends(get_application_container)) -> FeedbackService:
    return container.feedback_service


def get_insights_service(container: ApplicationContainer = Depends(get_application_container)) -> InsightsService:
    return container.insights_service


def get_health_service(container: ApplicationContainer = Depends(get_application_container)) -> HealthService:
    return container.health_service
