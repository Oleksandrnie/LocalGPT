from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config, db
from .routes import chat, criteria, meta, models, profiles, storage, transcripts, transcribe

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

db.init_db()
config.log_startup(LOGGER)

app = FastAPI(title="LocalGPT HR API")

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

app.mount("/ui", StaticFiles(directory=config.UI_DIR, html=True), name="ui")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/ui/gui_html.html")
