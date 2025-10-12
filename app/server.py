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
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
MEM_TURNS = int(os.getenv("MEM_TURNS", "6"))  # сколько пар (user+assistant) храним в памяти на сессию
UI_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web_ui"))

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
app = FastAPI(title="LocalGPT HR API")

# Память чата по сессиям (in-memory)
SESSIONS: dict[str, list[dict]] = {}

class ChatReq(BaseModel):
    query: str
    context: str | None = None
    session_id: str | None = None

def _system_prompt() -> str:
    with open(os.path.join(os.path.dirname(__file__), "prompts", "system_hr.md"), "r") as f:
        base_prompt = f.read()
    return base_prompt + "\n\nТребование: отвечай ТОЛЬКО на русском языке. Не используй другие языки."

# Helper: удаляем повторы и случайные куски на других языках
def _sanitize(text: str) -> str:
    """Убираем явные повторы и случайные куски на других языках."""
    import re
    # удаляем явные китайские блоки/фразы
    text = re.sub(r"[\u4e00-\u9fff]{2,}.*?(?:[.!?。！？]|$)", "", text)
    # убираем подряд идущие идентичные строки
    lines, out = text.splitlines(), []
    for ln in lines:
        if not out or out[-1].strip() != ln.strip():
            out.append(ln)
    return "\n".join(out).strip()

@app.post("/chat")
def chat(req: ChatReq):
    try:
        # session memory
        sid = (req.session_id or "default").strip()
        history = SESSIONS.get(sid, [])

        messages = [{"role": "system", "content": _system_prompt()}]
        if req.context:
            messages.append({"role": "user", "content": f"Контекст:\n{req.context}"})
        # добавляем прошлые реплики (user/assistant) если есть
        if history:
            messages.extend(history)
        # текущий запрос
        messages.append({"role": "user", "content": req.query})

        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=TEMP,
            max_tokens=MAX_TOK,
            stop=["\n\n\n", "\n\n—", "\n\n1."],  # мягкие ограничители списков/абзацев
            presence_penalty=0.2,
            frequency_penalty=0.2,
        )
        text = resp.choices[0].message.content or ""
        text = _sanitize(text)

        # обновляем память для сессии: храним последние MEM_TURNS пар (user/assistant)
        new_history = history + [
            {"role": "user", "content": req.query},
            {"role": "assistant", "content": text},
        ]
        SESSIONS[sid] = new_history[-2 * MEM_TURNS:]

        return {"reply": text}
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
# Lightweight version endpoint to introspect config
@app.get("/version")
def version():
    return {"env": ENV, "model": MODEL, "base_url": BASE_URL}


# Reset session endpoint and request model
class ResetReq(BaseModel):
    session_id: str
    admin_token: str | None = None

@app.post("/session/reset")
def reset_session(req: ResetReq):
    if ADMIN_TOKEN and req.admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    SESSIONS.pop(req.session_id.strip(), None)
    return {"ok": True}


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
