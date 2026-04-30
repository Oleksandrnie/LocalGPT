from __future__ import annotations

from pathlib import Path

from .config import PROMPTS_DIR


LANGUAGE_SUFFIX = (
    "\n\nЯзыковое правило: отвечай на языке последнего сообщения пользователя. "
    "Если пользователь явно просит другой язык, переключись на него. "
    "Не закрепляй русский язык как единственный, если это не указано в профильном system prompt."
)
BASE_PROMPT_PATH = PROMPTS_DIR / "system_base.md"
BASE_PROMPT_FALLBACK = (
    "Ты — LocalGPT, естественный локальный ассистент. Отвечай по делу, живо и без "
    "канцелярита. Не выдумывай факты и не рассказывай о внутренних ограничениях системы, "
    "если пользователь не спросил об этом напрямую."
)
DEFAULT_ROLE = "chat"


def normalize_role(raw: str | None = None) -> str:
    return DEFAULT_ROLE


def _load_prompt(path: Path, fallback: str) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        text = ""
    return text or fallback


def system_prompt_for(role_key: str | None = None) -> str:
    base = _load_prompt(BASE_PROMPT_PATH, BASE_PROMPT_FALLBACK)
    return "\n\n".join(part for part in (base, LANGUAGE_SUFFIX) if part).strip()


def list_roles() -> list[dict]:
    return []
