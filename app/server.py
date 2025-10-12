# Copyright (c) 2025 Oleksandr Niemchenko. All Rights Reserved.
import os
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from .asr_whisper import transcribe_file  # ← фиксированный импорт

load_dotenv()

ENV = os.getenv("ENV", "local")
BASE_URL = os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1")
API_KEY  = os.getenv("LOCAL_API_KEY", "LOCAL-KEY")
MODEL    = os.getenv("LOCAL_MODEL", "qwen2.5:7b-instruct")
TEMP     = float(os.getenv("TEMP", "0.25"))
MAX_TOK  = int(os.getenv("MAX_TOKENS", "512"))
UI_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web_ui"))

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
app = FastAPI(title="LocalGPT HR API")

class ChatReq(BaseModel):
    query: str
    context: str | None = None

def _system_prompt() -> str:
    with open(os.path.join(os.path.dirname(__file__), "prompts", "system_hr.md"), "r") as f:
        base_prompt = f.read()
    return base_prompt + "\n\nТребование: отвечай ТОЛЬКО на русском языке. Не используй другие языки."

@app.post("/chat")
def chat(req: ChatReq):
    try:
        messages = [{"role":"system","content":_system_prompt()}]
        if req.context:
            messages.append({"role":"user","content":f"Контекст:\n{req.context}"})
        messages.append({"role":"user","content":req.query})
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, temperature=TEMP, max_tokens=MAX_TOK
        )
        return {"reply": resp.choices[0].message.content}
    except Exception as e:
        # Возвращаем понятную ошибку, если Ollama/LLM недоступны
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")

@app.post("/transcribe")
def transcribe(
    file: UploadFile = File(...),
    model: str | None = Form(default=None),
    language: str = Form(default="ru")
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or '')[-1]) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        text = transcribe_file(path=tmp_path, language=language, model_size=model)
        return {"text": text, "model": model, "language": language}
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

@app.get("/health")
def health():
    return {"status": "ok", "env": ENV, "model": MODEL}


# Lightweight version endpoint to introspect config
@app.get("/version")
def version():
    return {"env": ENV, "model": MODEL, "base_url": BASE_URL}


from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/ui/gui_html.html")