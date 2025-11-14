# Copyright (c) 2025 Oleksandr Niemchenko. All Rights Reserved.
import csv
import io
import logging
import os
import re
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable

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
# Кэш критериев, загруженных пользователем (по session_id)
SESSION_CRITERIA: dict[str, list[str]] = {}
# Последний транскрипт на сессию (можно использовать при повторном анализе)
SESSION_TRANSCRIPTS: dict[str, str] = {}

class ChatReq(BaseModel):
    query: str
    context: str | None = None
    session_id: str | None = None
    transcript: str | None = None
    criteria: list[str] | None = None

def _system_prompt() -> str:
    try:
        with PROMPT_PATH.open("r", encoding="utf-8") as f:
            base_prompt = f.read()
    except (OSError, UnicodeDecodeError) as exc:
        LOGGER.warning("Failed to read system prompt from %s: %s", PROMPT_PATH, exc)
        base_prompt = FALLBACK_SYSTEM_PROMPT
    return base_prompt + PROMPT_LANGUAGE_SUFFIX

# --- Критерии и источники данных -------------------------------------------------

MAX_CRITERIA = 200

def _normalize_criterion(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"[\u200b\u200c\u200d]", "", raw)
    text = text.strip()
    text = re.sub(r"^[-•*\d\)\].\s]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _criteria_from_lines(lines: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for line in lines:
        cleaned = _normalize_criterion(line)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= MAX_CRITERIA:
            break
    return result

def _decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")

def _parse_csv(text: str) -> list[str]:
    stream = io.StringIO(text)
    reader = csv.reader(stream)
    lines: list[str] = []
    for row in reader:
        if not row:
            continue
        for cell in row:
            if cell and cell.strip():
                lines.append(cell)
                break
    return _criteria_from_lines(lines)

def _parse_xlsx(data: bytes) -> list[str]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - зависит от окружения
        raise RuntimeError("openpyxl_not_available") from exc

    workbook = load_workbook(filename=io.BytesIO(data), read_only=True, data_only=True)
    sheet = workbook.active
    lines: list[str] = []
    for row in sheet.iter_rows(values_only=True):
        if not row:
            continue
        for cell in row:
            if isinstance(cell, str) and cell.strip():
                lines.append(cell)
                break
            if isinstance(cell, (int, float)):
                lines.append(str(cell))
                break
        if len(lines) >= MAX_CRITERIA:
            break
    return _criteria_from_lines(lines)

def _parse_text_block(text: str) -> list[str]:
    if not text:
        return []
    raw_lines = re.split(r"[\r\n]+", text)
    return _criteria_from_lines(raw_lines)

def _extract_sheet_id(raw: str) -> tuple[str, str | None]:
    value = (raw or "").strip()
    if not value:
        raise ValueError("google_sheet_id_required")
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", value)
    gid = None
    if match:
        sheet_id = match.group(1)
        gid_match = re.search(r"gid=([0-9]+)", value)
        if gid_match:
            gid = gid_match.group(1)
        return sheet_id, gid
    return value, None

def _load_google_sheet_csv(sheet_id: str, gid: str | None = None) -> str:
    if not sheet_id:
        raise ValueError("google_sheet_id_required")
    params = {"format": "csv"}
    if gid:
        params["gid"] = gid
    query = urllib.parse.urlencode(params)
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?{query}"
    with urllib.request.urlopen(url, timeout=15) as response:  # type: ignore[call-arg]
        data = response.read()
    return _decode_bytes(data)

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


@app.post("/criteria/parse")
def parse_criteria(
    session_id: str = Form(default=""),
    google_sheet_id: str = Form(default=""),
    google_gid: str = Form(default=""),
    raw_text: str = Form(default=""),
    file: UploadFile | None = File(default=None),
):
    sid = (session_id or "default").strip() or "default"
    criteria: list[str] | None = None
    source = None
    try:
        if file is not None:
            content = file.file.read()
            if not content:
                raise ValueError("empty_file")
            suffix = Path(file.filename or "").suffix.lower()
            if suffix == ".csv":
                criteria = _parse_csv(_decode_bytes(content))
                source = "file:csv"
            elif suffix in {".xlsx", ".xlsm"}:
                criteria = _parse_xlsx(content)
                source = "file:xlsx"
            else:
                raise ValueError("unsupported_file")
        elif google_sheet_id.strip():
            sheet_id, gid = _extract_sheet_id(google_sheet_id)
            csv_text = _load_google_sheet_csv(sheet_id, gid or (google_gid.strip() or None))
            criteria = _parse_csv(csv_text)
            source = "google_sheets"
        elif raw_text.strip():
            criteria = _parse_text_block(raw_text)
            source = "text"
        else:
            raise ValueError("no_source")
    except ValueError as exc:
        code = str(exc)
        if code == "unsupported_file":
            raise HTTPException(
                status_code=422,
                detail={"code": "unsupported_file", "message": "Разрешены только CSV и XLSX"},
            ) from exc
        if code == "empty_file":
            raise HTTPException(
                status_code=422,
                detail={"code": "empty_file", "message": "Файл критериев пустой"},
            ) from exc
        if code == "google_sheet_id_required":
            raise HTTPException(
                status_code=422,
                detail={"code": "google_sheet_id_required", "message": "Укажите ID таблицы Google Sheets"},
            ) from exc
        raise HTTPException(
            status_code=400,
            detail={"code": "criteria_source_missing", "message": "Не указан источник критериев"},
        ) from exc
    except RuntimeError as exc:
        if str(exc) == "openpyxl_not_available":
            raise HTTPException(
                status_code=500,
                detail={"code": "openpyxl_missing", "message": "Установите зависимость openpyxl для чтения XLSX"},
            ) from exc
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "criteria_fetch_failed", "message": str(exc)},
        ) from exc
    if not criteria:
        raise HTTPException(
            status_code=422,
            detail={"code": "criteria_not_found", "message": "Не удалось выделить критерии"},
        )
    SESSION_CRITERIA[sid] = criteria
    return {"criteria": criteria, "count": len(criteria), "session_id": sid, "source": source}

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

        request_criteria = [c for c in (req.criteria or []) if isinstance(c, str)]
        cleaned_criteria = _criteria_from_lines(request_criteria) if request_criteria else []
        if cleaned_criteria:
            SESSION_CRITERIA[sid] = cleaned_criteria
        active_criteria = cleaned_criteria or SESSION_CRITERIA.get(sid, []) or []

        transcript_text = (req.transcript or "").strip()
        if transcript_text:
            SESSION_TRANSCRIPTS[sid] = transcript_text
        else:
            transcript_text = (SESSION_TRANSCRIPTS.get(sid) or "").strip()

        messages = [{"role": "system", "content": _system_prompt()}]
        if req.context:
            messages.append({"role": "user", "content": f"Контекст:\n{req.context}"})
        if transcript_text:
            label = "Транскрипт из запроса" if (req.transcript or "").strip() else "Транскрипт из памяти сессии"
            messages.append({"role": "user", "content": f"{label}:\n{transcript_text}"})
        if active_criteria:
            criteria_block = "\n".join(f"- {item}" for item in active_criteria)
            messages.append({"role": "user", "content": f"Критерии оценки:\n{criteria_block}"})
        # добавляем прошлые реплики (user/assistant) если есть
        if history:
            messages.extend(history)
        # текущий запрос
        user_query = (req.query or "").strip() or "проанализируй"
        messages.append({"role": "user", "content": user_query})

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
            {"role": "user", "content": user_query},
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
    session_id: str = Form(default=""),
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

    sid = (session_id or "").strip()

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
        if sid:
            SESSION_TRANSCRIPTS[sid] = text

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
    sid = req.session_id.strip()
    SESSIONS.pop(sid, None)
    SESSION_CRITERIA.pop(sid, None)
    SESSION_TRANSCRIPTS.pop(sid, None)
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
