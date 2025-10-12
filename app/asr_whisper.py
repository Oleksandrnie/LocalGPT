# Copyright (c) 2025 Oleksandr Niemchenko. All Rights Reserved.
import os
from typing import Optional, Dict, List
from faster_whisper import WhisperModel

# ----------------------------
# Конфиг по умолчанию (можно переопределить через .env)
# ----------------------------
_DEFAULT_SIZE = os.getenv("WHISPER_MODEL_SIZE", "medium").strip()
_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8").strip()  # int8 | int8_float16 | float16 | float32
_DEVICE = os.getenv("WHISPER_DEVICE", "cpu").strip()               # "cpu" (для M1 — ок)
_VAD = os.getenv("WHISPER_VAD", "1").strip() == "1"                # VAD-фильтр сегментов
_LOG_ENABLED_ENV = os.getenv("WHISPER_LOG", "0").strip() == "1"

# Где искать уже скачанные модели
# 1) путь к конкретной модели (имеет приоритет)
_WHISPER_MODEL_PATH = os.getenv("WHISPER_MODEL_PATH")
# 2) корень, где лежат подпапки tiny/base/small/medium/large
_WHISPER_MODELS_DIR = os.getenv("WHISPER_MODELS_DIR")

# Кеш инстансов моделей
_MODELS: Dict[str, WhisperModel] = {}


# ----------------------------
# Вспомогательные функции
# ----------------------------
def _is_model_dir(path: str) -> bool:
    """Папка выглядит как директория модели (содержит model.bin и config.json)."""
    return os.path.isfile(os.path.join(path, "model.bin")) and os.path.isfile(os.path.join(path, "config.json"))


def _snapshots_leaf(path: str) -> str:
    """
    Если указан путь на HF-репозиторий (models--*/snapshots/<rev>),
    аккуратно «проваливаемся» до директории с model.bin/config.json.
    """
    # 1) Уже директория модели?
    if _is_model_dir(path):
        return path

    # 2) HF-структура: <path>/snapshots/<rev>/*
    snap_root = os.path.join(path, "snapshots")
    if os.path.isdir(snap_root):
        try:
            for rev in sorted(os.listdir(snap_root)):
                cand = os.path.join(snap_root, rev)
                if os.path.isdir(cand) and _is_model_dir(cand):
                    return cand
        except Exception:
            pass

    # 3) Возможно, нам уже дали путь «…/models--NAME/snapshots/<rev>»
    #    (на один уровень ниже)
    parent = os.path.dirname(path.rstrip("/"))
    if os.path.basename(parent) == "snapshots":
        if _is_model_dir(path):
            return path

    return path  # не нашли «листа» — вернём как есть (WhisperModel сам разрулит)


def _resolve_model_ref(size_or_path: str) -> str:
    """
    Возвращает ссылку для WhisperModel:
    - если задан WHISPER_MODEL_PATH — он приоритетный (с учётом snapshots);
    - если задан WHISPER_MODELS_DIR — ищем подпапку <dir>/<size>, поддерживаем HF-структуру;
    - если передан абсолютный путь — используем его (с учётом snapshots);
    - иначе возвращаем тэг размера (tiny/base/small/medium/large).
    """
    # 1) Жёсткий путь из окружения
    if _WHISPER_MODEL_PATH and os.path.isdir(_WHISPER_MODEL_PATH):
        return _snapshots_leaf(_WHISPER_MODEL_PATH)

    # 2) Корень со стандартными подпапками
    if _WHISPER_MODELS_DIR and os.path.isdir(_WHISPER_MODELS_DIR):
        candidate = os.path.join(_WHISPER_MODELS_DIR, size_or_path)
        if os.path.isdir(candidate):
            # Поддержка HF-структуры: внутри может быть models--*/snapshots/<rev>
            # Сценарий пользователя: .../whisper/medium/models--Systran--faster-whisper-medium/...
            # Пробуем «провалиться» до листа
            # 2.1 если внутри сразу «models--*», попробуем найти snapshots
            try:
                entries = os.listdir(candidate)
                models_like = [e for e in entries if e.startswith("models--")]
                if models_like:
                    # берём первую подходящую «models--*»
                    sub = os.path.join(candidate, models_like[0])
                    if os.path.isdir(sub):
                        leaf = _snapshots_leaf(sub)
                        if os.path.isdir(leaf):
                            return leaf
                # 2.2 иначе просто проверим сам candidate
            except Exception:
                pass
            return _snapshots_leaf(candidate)

    # 3) Абсолютный/относительный путь от пользователя
    if os.path.isdir(size_or_path):
        return _snapshots_leaf(size_or_path)

    # 4) Тэг модели
    return size_or_path


def list_local_models() -> List[str]:
    """
    Возвращает список доступных локальных моделей (имён подпапок) из WHISPER_MODELS_DIR.
    Полезно для UI.
    """
    result: List[str] = []
    root = _WHISPER_MODELS_DIR
    if not (root and os.path.isdir(root)):
        return result
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if os.path.isdir(p):
            result.append(name)
    return result


def get_whisper(model_size: Optional[str] = None) -> WhisperModel:
    """
    Возвращает/кеширует инстанс WhisperModel для указанного размера/пути.
    Пример значений: "tiny" | "base" | "small" | "medium" | "large" | "/abs/path/to/model"
    """
    key = (model_size or _DEFAULT_SIZE).strip()
    ref = _resolve_model_ref(key)

    # Ключ кеша — финальный ref (разные пути/разные размеры => разные инстансы)
    cache_key = f"{_DEVICE}:{_COMPUTE_TYPE}:{ref}"
    if cache_key in _MODELS:
        return _MODELS[cache_key]

    # На M1 Pro обычно device="cpu" + int8 -> ок
    model = WhisperModel(ref, device=_DEVICE, compute_type=_COMPUTE_TYPE)
    _MODELS[cache_key] = model
    return model


def _maybe_log(log_path: Optional[str], *lines: str) -> None:
    if not log_path:
        return
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            for ln in lines:
                f.write(str(ln) + "\n")
    except Exception:
        # не роняем процесс из-за логов
        pass


def transcribe_file(
    path: str,
    language: Optional[str] = None,
    model_size: Optional[str] = None,
    enable_log: Optional[bool] = None,
) -> str:
    """
    Транскрибирует аудио/видео.
    - path: путь к файлу
    - language: фиксированный язык (например, "ru") или None для авто
    - model_size: "tiny" | "base" | "small" | "medium" | "large" | путь к модели.
                  Если None — берём из WHISPER_MODEL_SIZE.
    - enable_log: если True или переменная окружения WHISPER_LOG=1 —
                  пишем лог в whisper_debug.log рядом с файлом.
    """
    # Подготовка лога (как в твоём bash-скрипте)
    do_log = (enable_log is True) or _LOG_ENABLED_ENV
    log_path = None
    if do_log:
        base_dir = os.path.dirname(os.path.abspath(path))
        log_path = os.path.join(base_dir, "whisper_debug.log")
        if os.path.exists(log_path):
            try:
                os.remove(log_path)
            except Exception:
                pass
        _maybe_log(
            log_path,
            f"Файл для транскрибации: {path}",
            f"Модель: {model_size or _DEFAULT_SIZE}",
            f"compute_type: {_COMPUTE_TYPE}",
            f"device: {_DEVICE}",
            f"language: {language or 'auto'}",
            f"vad_filter: {_VAD}",
        )

    model = get_whisper(model_size)
    segments, info = model.transcribe(
        path,
        language=language,
        vad_filter=_VAD,
    )

    # Склеиваем текст
    text_parts: List[str] = [seg.text for seg in segments]
    text = "".join(text_parts).strip()

    _maybe_log(
        log_path,
        f"Итоговая длительность: {getattr(info, 'duration', None)} сек",
        f"Символов в тексте: {len(text)}",
    )
    return text