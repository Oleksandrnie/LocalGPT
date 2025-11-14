# Copyright (c) 2025 Oleksandr Niemchenko. All Rights Reserved.
import logging
import os
import tempfile
import re
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from .asr_whisper import transcribe_with_fallback

LOGGER = logging.getLogger(__name__)
PROMPT_PATH = Path(__file__).with_name("prompts") / "system_hr.md"
FALLBACK_SYSTEM_PROMPT = (
    "Ты — локальный HR-ассистент. Работай строго по фактам, не выдумывай данные и"
    " отвечай кратко на русском языке. Если информации не хватает, прямо укажи на"
    " это и предложи следующий шаг."
)
PROMPT_LANGUAGE_SUFFIX = (
    "\n\nТребование: отвечай ТОЛЬКО на русском языке. Не используй другие языки."
)

load_dotenv()

ENV = os.getenv("ENV", "local")
BASE_URL = os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1")
API_KEY  = os.getenv("LOCAL_API_KEY", "LOCAL-KEY")
MODEL    = os.getenv("LOCAL_MODEL", "qwen2.5:7b-instruct")
TEMP     = float(os.getenv("TEMP", "0.25"))
MAX_TOK  = int(os.getenv("MAX_TOKENS", "512"))
NUM_CTX = int(os.getenv("NUM_CTX", "32768"))
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
    try:
        with PROMPT_PATH.open("r", encoding="utf-8") as f:
            base_prompt = f.read()
    except (OSError, UnicodeDecodeError) as exc:
        LOGGER.warning("Failed to read system prompt from %s: %s", PROMPT_PATH, exc)
        base_prompt = FALLBACK_SYSTEM_PROMPT
    return base_prompt + PROMPT_LANGUAGE_SUFFIX

# Helper: удаляем повторы и случайные куски на других языках
def _sanitize(text: str) -> str:
    """Убираем явные повторы и случайные куски на других языках."""
    import re

    # удаляем явные китайские блоки/фразы
    text = re.sub(r"[\u4e00-\u9fff]{2,}.*?(?:[.!?。！？]|$)", "", text)

    # вырезаем служебные секции-инструкции, которые модель иногда копирует в ответ
    def _drop_section(src: str, heading: str) -> str:
        pattern = re.compile(rf"(^##\s*{heading}.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
        return re.sub(pattern, "", src)

    for meta_heading in (
        "Минимальный набор фактов",
        "Чеклист перед отправкой",
        "Checklist before sending",
    ):
        text = _drop_section(text, meta_heading)

    # удаляем строки с типовыми подсказками вроде «Теперь вы можете…»
    text = re.sub(r"^.*Теперь вы можете.*$", "", text, flags=re.MULTILINE)

    lines: list[str] = []
    seen_headings: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            if lines and lines[-1] == "":
                continue
            lines.append("")
            continue

        if stripped.startswith("### "):
            key = stripped.lower()
            if key in seen_headings:
                continue
            seen_headings.add(key)

        if lines and lines[-1].strip() == stripped:
            continue

        lines.append(line)

    return "\n".join(lines).strip()


def _build_timeline(segments: list[dict]) -> list[dict]:
    """Объединяет соседние сегменты одного говорящего в таймлайн."""

    timeline: list[dict] = []
    if not segments:
        return timeline

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start))
        speaker = (segment.get("speaker") or "unknown").strip().lower() or "unknown"

        if timeline and timeline[-1]["speaker"] == speaker and start <= timeline[-1]["end"] + 0.6:
            timeline[-1]["end"] = max(timeline[-1]["end"], end)
            timeline[-1]["text"] = (timeline[-1]["text"] + " " + text).strip()
        else:
            timeline.append(
                {
                    "speaker": speaker,
                    "start": start,
                    "end": end,
                    "text": text,
                }
            )

    return timeline

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

LANGUAGE_RE = re.compile(r"^[a-z0-9]{2,8}(?:-[a-z0-9]{2,8})?$")


@app.post("/transcribe")
def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default="small"),
    prompt_preset: str = Form(default="none"),
    language: str = Form(default="auto"),
):
    """Транскрибация аудио/видео через faster-whisper.

    - model — размер модели whisper (tiny/base/small/medium/large).
    - prompt_preset — режим промпта: none / ru / en.
    - language — `auto` (по умолчанию) или BCP-47 код (`ru`, `en`, `pt-br`...), влияет на второй проход Whisper.
    """
    # сохраняем файл во временный путь
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=os.path.splitext(file.filename or "")[-1],
    ) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    # модель по умолчанию, если в форме пришло пусто
    model_name = (model or os.getenv("WHISPER_MODEL_SIZE", "medium")).strip()

    preset = (prompt_preset or "none").strip().lower()
    if not preset:
        preset = "none"
    if preset not in {"none", "ru", "en"}:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_prompt_preset",
                "message": "prompt_preset must be one of: none, ru, en.",
            },
        )
    preset_value = None if preset == "none" else preset

    language_raw = (language or "auto").strip().lower()
    if language_raw == "":
        language_raw = "auto"
    if language_raw != "auto" and not LANGUAGE_RE.fullmatch(language_raw):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_language",
                "message": "language must be 'auto' или BCP-47 код (например, 'ru', 'en', 'pt-br').",
            },
        )
    preferred_language = None if language_raw == "auto" else language_raw

    try:
        transcription = transcribe_with_fallback(
            audio_path=tmp_path,
            model_name=model_name,
            prompt_preset=preset_value,
            preferred_language=preferred_language,
        )
        text = transcription.get("text", "") if isinstance(transcription, dict) else str(transcription)
        segments = []
        if isinstance(transcription, dict):
            segments = list(transcription.get("segments") or [])
        if not text:
            raise RuntimeError("empty_transcription")
        timeline = _build_timeline(segments)
        detected_language = None
        if isinstance(transcription, dict):
            detected_language = transcription.get("language")
        role_keywords = {}
        if isinstance(transcription, dict):
            role_keywords = transcription.get("role_keywords") or {}
        return {
            "text": text,
            "model": model_name,
            "prompt_preset": preset,
            "language": language_raw,
            "detected_language": detected_language,
            "segments": segments,
            "timeline": timeline,
            "role_keywords": role_keywords,
        }
    except RuntimeError as e:
        msg = str(e)
        if msg.startswith("WHISPER_MODEL_NOT_FOUND::"):
            missing_model = msg.split("::", 1)[1] if "::" in msg else model_name
            raise HTTPException(
                status_code=424,
                detail={
                    "code": "whisper_model_missing",
                    "model": missing_model,
                    "message": f'Whisper model "{missing_model}" is not available locally.',
                },
            )
        if msg == "empty_transcription":
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "empty_transcription",
                    "message": "Whisper вернул пустую транскрипцию.",
                },
            )
        # остальные ошибки пробрасываем дальше как 500
        raise
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

@app.get("/health")
def health():
    return {
        "status": "ok",
        "env": ENV,
        "model": MODEL,
        "num_ctx": NUM_CTX,
        "max_tokens": MAX_TOK,
    }


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
