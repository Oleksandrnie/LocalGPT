from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config, db
from .routers import tts
from .routes import chat, criteria, meta, models, profiles, storage, transcripts, transcribe

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

db.init_db()
config.log_startup(LOGGER)

app = FastAPI(title="LocalGPT API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(meta.router)
app.include_router(models.router)
app.include_router(profiles.router)
app.include_router(criteria.router)
app.include_router(transcripts.router)
app.include_router(transcribe.router)
app.include_router(chat.router)
app.include_router(storage.router)
app.include_router(tts.router)

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
