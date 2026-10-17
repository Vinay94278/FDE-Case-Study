"""FastAPI app. The API is the product; the HTML page is one thin client of it.
The same /api/ask endpoint could back an in-app help widget or a Slack bot.

Run:  uvicorn app.api:app --reload
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import load_settings
from .models import AskRequest, AskResponse, FeedbackRequest
from .qa import QAService
from .querylog import QueryLog

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.qa = QAService(settings)          # index is built once at startup
    app.state.log = QueryLog(settings.log_path)
    logging.getLogger("app").info("Ready: %s", app.state.qa.health())
    yield


app = FastAPI(title="Solstice Docs Q&A", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health(request: Request):
    return request.app.state.qa.health()


@app.post("/api/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request, debug: bool = False):
    result: AskResponse = request.app.state.qa.ask(body.question)
    request.app.state.log.write({
        "type": "ask", "question": body.question, "status": result.status,
        "mode": result.mode, "reason": result.reason, "latency_ms": result.latency_ms,
        "cited_docs": sorted({c.doc_id for c in result.citations}),
    })
    if not debug:
        result.debug = {}
    return result


@app.post("/api/feedback")
def feedback(body: FeedbackRequest, request: Request):
    request.app.state.log.write({"type": "feedback", **body.model_dump()})
    return {"ok": True}


@app.get("/api/gaps")
def gaps(request: Request, limit: int = 20):
    """Questions the docs could not answer, most frequent first."""
    return {"gaps": request.app.state.log.gaps(limit)}
