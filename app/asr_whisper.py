import json
import os
from pathlib import Path
from typing import Any, Iterable

# --- Whisper models root config ---
ROOT = Path(__file__).resolve().parents[1]
WHISPER_MODELS_DIR = os.getenv("WHISPER_MODELS_DIR", "ollama_models/whisper")
WHISPER_DOWNLOAD_ROOT = ROOT / WHISPER_MODELS_DIR
WHISPER_DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

DEFAULT_FALLBACK_LANGUAGE = (
    os.getenv("WHISPER_FALLBACK_LANGUAGE", "ru").strip().lower() or "ru"
)
FALLBACK_USE_PROMPT = os.getenv("WHISPER_FALLBACK_USE_PROMPT", "true").strip().lower()
FALLBACK_USE_PROMPT = FALLBACK_USE_PROMPT not in {"0", "false", "no"}

DEFAULT_ROLE_KEYWORDS = {
    "hr": [
        "компания",
        "коллег",
        "зарплат",
        "ваканси",
        "обязанн",
        "тестовое",
        "условия",
        "расскажите",
        "задач",
        "офер",
    ],
    "candidate": [
        "меня зовут",
        "мой опыт",
        "работал",
        "учился",
        "занимался",
        "команда",
        "портфолио",
        "проживаю",
        "ищу",
        "готов",
    ],
}

RU_PRESET_PROMPT = (
    "корректная пунктуация, нормальная орфография, числа, даты, проценты, имена, "
    "названия компаний; не искажать слова; сохранять смысл речи"
)

EN_PRESET_PROMPT = (
    "use correct punctuation and spelling, numbers, dates, percentages, proper names; "
    "do not hallucinate; preserve meaning"
)

def build_whisper_prompt(audio_path: Path, prompt_preset: str | None) -> str | None:
    """Собирает initial_prompt из пресета (ru/en) и локального файла whisper_prompt.txt."""
    local_prompt_file = audio_path.parent / "whisper_prompt.txt"
    local_prompt = ""
    if local_prompt_file.exists():
        try:
            local_prompt = local_prompt_file.read_text(encoding="utf-8").strip()
        except Exception:
            # если не удалось прочитать подсказку — просто игнорируем
            local_prompt = ""

    user_prompt = ""
    if prompt_preset == "ru":
        user_prompt = RU_PRESET_PROMPT
    elif prompt_preset == "en":
        user_prompt = EN_PRESET_PROMPT

    parts: list[str] = []
    if user_prompt:
        parts.append(user_prompt)
    if local_prompt:
        parts.append(local_prompt)

    if not parts:
        return None
    return "; ".join(parts)

def _normalize_language(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in {"auto", "auto-detect", "detect"}:
        return None
    return normalized


def _normalize_role_keywords(data: dict[str, Iterable[str]] | None) -> dict[str, list[str]]:
    if not data:
        return {k: list(v) for k, v in DEFAULT_ROLE_KEYWORDS.items()}

    normalized: dict[str, list[str]] = {}
    for role, raw_keywords in data.items():
        if not isinstance(role, str):
            continue
        if isinstance(raw_keywords, str):
            candidates = [raw_keywords]
        elif isinstance(raw_keywords, Iterable):
            candidates = list(raw_keywords)
        else:
            continue
        cleaned: list[str] = []
        for item in candidates:
            if not isinstance(item, str):
                continue
            kw = item.strip().lower()
            if kw and kw not in cleaned:
                cleaned.append(kw)
        if cleaned:
            normalized[role.strip().lower() or role] = cleaned

    if not normalized:
        return {k: list(v) for k, v in DEFAULT_ROLE_KEYWORDS.items()}
    return normalized


def _load_role_keywords(audio_path: Path) -> dict[str, list[str]]:
    """Загружает словарь ключевых слов для определения ролей."""

    env_inline = os.getenv("WHISPER_ROLE_KEYWORDS")
    if env_inline:
        try:
            parsed = json.loads(env_inline)
            if isinstance(parsed, dict):
                return _normalize_role_keywords(parsed)
        except json.JSONDecodeError:
            pass

    env_path = os.getenv("WHISPER_ROLE_KEYWORDS_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    return _normalize_role_keywords(parsed)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass

    local_file = audio_path.parent / "role_keywords.json"
    if local_file.exists():
        try:
            parsed = json.loads(local_file.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                return _normalize_role_keywords(parsed)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass

    module_default = Path(__file__).with_name("role_keywords.json")
    if module_default.exists():
        try:
            parsed = json.loads(module_default.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                return _normalize_role_keywords(parsed)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass

    return {k: list(v) for k, v in DEFAULT_ROLE_KEYWORDS.items()}


def _annotate_speakers(
    segments: list[dict[str, Any]],
    role_keywords: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Присваивает каждому сегменту роль собеседника (HR/кандидат)."""

    if not segments:
        return []

    speakers = list(role_keywords.keys()) or list(DEFAULT_ROLE_KEYWORDS.keys())
    default_speaker = speakers[0] if speakers else "hr"
    annotated: list[dict[str, Any]] = []
    last_speaker = None

    for seg in segments:
        text = (seg.get("text") or "").lower()
        best_speaker = None
        best_score = 0

        for speaker, keywords in role_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword and keyword in text:
                    score += 1
            if score > best_score:
                best_score = score
                best_speaker = speaker
            elif score == best_score and score > 0:
                # Ничья по ключевым словам — не меняем говорящего
                best_speaker = last_speaker

        if not best_speaker:
            if last_speaker is None:
                best_speaker = default_speaker
            elif best_score == 0:
                # Без явных подсказок считаем, что говорит тот же собеседник.
                best_speaker = last_speaker
            else:
                best_speaker = last_speaker

        annotated_segment = {
            **seg,
            "speaker": best_speaker or default_speaker,
        }
        annotated.append(annotated_segment)
        last_speaker = annotated_segment["speaker"]

    return annotated


def transcribe_with_fallback(
    audio_path: str,
    model_name: str,
    prompt_preset: str | None = None,
    preferred_language: str | None = None,
    compute_type: str | None = None,
    device: str | None = None,
    beam_size: int = 5,
) -> dict[str, Any]:
    """Транскрибирует файл с двумя проходами и возвращает текст и сегменты.

    1) язык auto + VAD + initial_prompt (если есть),
    2) фолбэк: VAD выключен, язык берётся из preferred_language или системного
       значения, initial_prompt задаётся по настройкам.

    Возвращает словарь с итоговым текстом и списком сегментов вида
    {"start": float, "end": float, "text": str, "speaker": str}.
    """
    from faster_whisper import WhisperModel  # локальный импорт, чтобы не ломать существующие импорты

    path = Path(audio_path)

    # Значения по умолчанию из окружения, если явно не переданы
    if compute_type is None:
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    if device is None:
        device = os.getenv("WHISPER_DEVICE", "cpu")

    full_prompt = build_whisper_prompt(path, prompt_preset)

    fallback_language = _normalize_language(preferred_language) or _normalize_language(
        DEFAULT_FALLBACK_LANGUAGE
    )
    fallback_prompt = full_prompt if FALLBACK_USE_PROMPT else None

    try:
        model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            download_root=str(WHISPER_DOWNLOAD_ROOT),
        )
    except Exception as e:
        # Пробрасываем специальную ошибку, чтобы сервер и UI могли показать подсказку по скачиванию модели
        raise RuntimeError(f"WHISPER_MODEL_NOT_FOUND::{model_name}") from e

    role_keywords = _load_role_keywords(path)

    def run_once(
        language: str | None, use_vad: bool, prompt: str | None
    ) -> tuple[str, list[dict[str, Any]], Any]:
        segments, info = model.transcribe(
            str(path),
            language=language,
            vad_filter=use_vad,
            beam_size=beam_size,
            initial_prompt=prompt,
        )
        collected_segments: list[dict[str, Any]] = []
        text_parts: list[str] = []

        for segment in segments:
            segment_text = (segment.text or "").strip()
            if not segment_text:
                continue
            text_parts.append(segment.text)
            collected_segments.append(
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": segment_text,
                }
            )

        return "".join(text_parts).strip(), collected_segments, info

    # 1) Умный прогон: автоопределение языка (language=None) + VAD + initial_prompt (если есть)
    text, segments_data, info = run_once(language=None, use_vad=True, prompt=full_prompt)

    # 2) Фолбэк: управляемый язык (если задан) + отключённый VAD + контролируемый промпт
    if not text:
        text, segments_data, info = run_once(
            language=fallback_language,
            use_vad=False,
            prompt=fallback_prompt,
        )

    annotated_segments = _annotate_speakers(segments_data, role_keywords)

    result: dict[str, Any] = {
        "text": text,
        "segments": annotated_segments,
        "role_keywords": role_keywords,
    }
    language_result = getattr(info, "language", None)
    if language_result:
        result["language"] = language_result

    return result
