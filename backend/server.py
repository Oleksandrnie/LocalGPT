from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import config, db
from app.routes import criteria, meta, models, profiles, storage
from backend.apps.asr import models_routes as asr_models
from backend.apps.asr import pipeline_routes as asr_pipeline
from backend.apps.asr import routes as transcribe
from backend.apps.asr import transcripts
from backend.apps.chat import routes as chat
from backend.apps.chat import attachments as chat_attachments
from backend.apps.ocr import routes as ocr
from backend.apps.plugins import routes as plugins
from backend.apps.rag import routes as rag
from backend.apps.model_transfer import router as model_transfer
from backend.apps.tts import router as tts

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

db.init_db()
config.log_startup(LOGGER)

app = FastAPI(title="LocalGPT API")

cors_allow_origins = list(config.SETTINGS.cors_allow_origins)
cors_allow_origin_regex = config.SETTINGS.cors_allow_origin_regex or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_origin_regex=cors_allow_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(meta.router)
app.include_router(models.router)
app.include_router(asr_models.router)
app.include_router(profiles.router)
app.include_router(criteria.router)
app.include_router(transcripts.router)
app.include_router(asr_pipeline.router)
app.include_router(transcribe.router)
app.include_router(ocr.router)
app.include_router(rag.router)
app.include_router(chat_attachments.router)
app.include_router(chat.router)
app.include_router(storage.router)
app.include_router(tts.router)
app.include_router(plugins.router)
app.include_router(model_transfer.router)

app.mount("/ui", StaticFiles(directory=config.UI_DIR, html=True), name="ui")


@app.middleware("http")
async def disable_ui_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/ui/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/ui/gui_html.html")
