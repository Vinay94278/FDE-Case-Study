"""Application entry point.

    uvicorn app.main:app --reload

create_app() wires settings, logging, middleware, exception handlers and routes.
The heavy work (loading docs, building the index, connecting the LLM) happens in
the lifespan startup hook, so a broken configuration fails fast with a clear log.
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.controllers import (
    ask_controller,
    feedback_controller,
    health_controller,
    insights_controller,
    ui_controller,
)
from app.core.application_container import ApplicationContainer
from app.core.exception_handlers import register_exception_handlers
from app.core.exceptions import AppException
from app.core.logging_config import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.settings import Settings

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None, container: Optional[ApplicationContainer] = None) -> FastAPI:
    """Build the FastAPI app. Tests pass their own settings or a prebuilt container."""
    if settings is None:
        settings = Settings()
    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(fastapi_app: FastAPI):
        logger.info("Starting %s %s (env=%s)", settings.app_name, settings.app_version, settings.app_env)
        if container is not None:
            fastapi_app.state.container = container
        else:
            try:
                fastapi_app.state.container = await ApplicationContainer.create(settings)
            except AppException as error:
                logger.critical("Startup failed: %s (%s)", error.message, error.technical_message)
                raise
        yield
        await fastapi_app.state.container.close()
        logger.info("Shutdown complete")

    fastapi_app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Answers admin questions using only the Solstice documentation.",
        lifespan=lifespan,
    )
    fastapi_app.state.settings = settings

    fastapi_app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(fastapi_app)

    fastapi_app.include_router(ask_controller.router)
    fastapi_app.include_router(feedback_controller.router)
    fastapi_app.include_router(insights_controller.router)
    fastapi_app.include_router(health_controller.router)
    fastapi_app.include_router(ui_controller.router)
    fastapi_app.mount("/static", StaticFiles(directory=str(ui_controller.STATIC_DIRECTORY)), name="static")
    return fastapi_app


app = create_app()
