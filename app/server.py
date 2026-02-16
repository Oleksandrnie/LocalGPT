from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .routes import meta, transcribe, transcripts

app = FastAPI(title="LocalGPT Whisper API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(meta.router)
app.include_router(transcribe.router)
app.include_router(transcripts.router)

app.mount("/ui", StaticFiles(directory=config.UI_DIR, html=True), name="ui")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/gui_html.html")
