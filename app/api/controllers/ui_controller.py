"""Serves the single-page UI at /."""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

STATIC_DIRECTORY = Path(__file__).resolve().parent.parent.parent / "static"

router = APIRouter(include_in_schema=False)


@router.get("/")
async def serve_user_interface() -> FileResponse:
    return FileResponse(STATIC_DIRECTORY / "index.html")
