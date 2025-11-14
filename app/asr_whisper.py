import os
from pathlib import Path

# --- Whisper models root config ---
ROOT = Path(__file__).resolve().parents[1]
WHISPER_MODELS_DIR = os.getenv("WHISPER_MODELS_DIR", "ollama_models/whisper")
WHISPER_DOWNLOAD_ROOT = ROOT / WHISPER_MODELS_DIR
WHISPER_DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

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

def transcribe_with_fallback(
    audio_path: str,
    model_name: str,
    prompt_preset: str | None = None,
    compute_type: str | None = None,
    device: str | None = None,
    beam_size: int = 5,
) -> str:
    """Транскрибирует файл с двумя проходами:

    1) язык auto + VAD + initial_prompt (если есть),
    2) фолбэк: язык ru, без VAD и без промпта.

    Возвращает полученный текст (может быть пустой строкой при полной ошибке).
    """
    from faster_whisper import WhisperModel  # локальный импорт, чтобы не ломать существующие импорты

    path = Path(audio_path)

    # Значения по умолчанию из окружения, если явно не переданы
    if compute_type is None:
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    if device is None:
        device = os.getenv("WHISPER_DEVICE", "cpu")

    full_prompt = build_whisper_prompt(path, prompt_preset)

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

    def run_once(language: str | None, use_vad: bool, prompt: str | None) -> str:
        segments, info = model.transcribe(
            str(path),
            language=language,
            vad_filter=use_vad,
            beam_size=beam_size,
            initial_prompt=prompt,
        )
        return "".join(segment.text for segment in segments).strip()

    # 1) Умный прогон: автоопределение языка (language=None) + VAD + initial_prompt (если есть)
    text = run_once(language=None, use_vad=True, prompt=full_prompt)

    # 2) Фолбэк: язык ru, без VAD и без промпта
    if not text:
        text = run_once(language="ru", use_vad=False, prompt=None)

    return text
