import asyncio, logging, secrets
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import ROOT, VERSION
from app.database import database as db
from app.llm.ollama import OllamaProvider
from app.llm.base import LLMError
from app.tools.registry import ToolRegistry
from app.agent.orchestrator import Agent
from app.voice.providers import LocalSTT, WindowsSpeech
from app.api.routes import router
from app.personal import router as personal_router, init_personal
from app.tools.desktop import router as desktop_router

logger = logging.getLogger("laila")


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    init_personal()
    db.run(
        "UPDATE documents SET status='error',error='Indexing was interrupted. Retry indexing.' WHERE status='processing'"
    )
    db.run("UPDATE tool_logs SET status='error',result='{}' WHERE status='running'")
    app.state.token = secrets.token_urlsafe(32)
    app.state.provider = OllamaProvider()
    app.state.registry = ToolRegistry(app.state.provider)
    app.state.agent = Agent(app.state.provider, app.state.registry)
    app.state.stt = LocalSTT()
    app.state.tts = WindowsSpeech()
    app.state.tts_lock = asyncio.Lock()
    app.state.active = {}
    app.state.indexing = set()
    yield
    for entry in list(app.state.active.values()):
        if entry.get("task"):
            entry["task"].cancel()


app = FastAPI(
    title="Laila AI",
    version=VERSION,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.middleware("http")
async def local_guard(request: Request, call_next):
    host = request.url.hostname
    if host not in {"127.0.0.1", "localhost", "::1", "testserver"}:
        return JSONResponse({"detail": "Local host required."}, status_code=403)
    if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        return JSONResponse({"detail": "Loopback access only."}, status_code=403)
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
        return JSONResponse(
            {"detail": "Cross-origin request blocked."}, status_code=403
        )
    if request.headers.get("sec-fetch-site") == "cross-site":
        return JSONResponse({"detail": "Cross-site request blocked."}, status_code=403)
    try:
        length = int(request.headers.get("content-length", "0"))
    except ValueError:
        return JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)
    if length > 20_000_000:
        return JSONResponse({"detail": "Request too large."}, status_code=413)
    if request.method not in {"GET", "HEAD"}:
        token = request.headers.get("x-laila-token", "")
        if not secrets.compare_digest(token, getattr(app.state, "token", "!")):
            return JSONResponse(
                {"detail": "Refresh Laila to start a local session."}, status_code=403
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    return response


@app.exception_handler(LLMError)
async def llm_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=503)


@app.exception_handler(ValueError)
async def value_error(request, exc):
    return JSONResponse({"detail": str(exc)[:600]}, status_code=400)


@app.exception_handler(Exception)
async def error(request, exc):
    logger.error(
        "Request failed: %s", type(exc).__name__
    )  # no prompts, file contents or secrets
    return JSONResponse(
        {
            "detail": "Operation failed. Check file format, model setup and available memory."
        },
        status_code=500,
    )


app.include_router(router)
app.include_router(personal_router)
app.include_router(desktop_router)


@app.get("/")
async def index():
    return FileResponse(ROOT / "frontend/index.html")


app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")
