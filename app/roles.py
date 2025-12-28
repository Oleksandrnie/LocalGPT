from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from .config import PROMPTS_DIR


LANGUAGE_SUFFIX = "\n\nТребование: отвечай ТОЛЬКО на русском языке. Не используй другие языки."
BASE_PROMPT_PATH = PROMPTS_DIR / "system_base.md"
BASE_PROMPT_FALLBACK = (
    "Ты — локальный офлайн-ассистент LocalGPT. Отвечай только по фактам, коротко, без "
    "извинений и фантазий. Работай с данными из запроса и локальной сессии, не обращаясь "
    "к внешним источникам."
)


@dataclass(frozen=True)
class RoleDefinition:
    key: str
    label: str
    description: str
    prompt_file: Path
    fallback_prompt: str


ROLE_ORDER = [
    "free",
    "teacher",
    "business_strict",
    "explain",
    "calc",
    "hr",
]

ROLE_DEFINITIONS: dict[str, RoleDefinition] = {
    "free": RoleDefinition(
        key="free",
        label="Свободное общение",
        description="Дружелюбные, но лаконичные ответы без лишних формальностей.",
        prompt_file=PROMPTS_DIR / "system_free.md",
        fallback_prompt="Свободное общение: отвечай дружелюбно, по делу и кратко.",
    ),
    "teacher": RoleDefinition(
        key="teacher",
        label="Учитель",
        description="Объясняет шагами, с примерами и проверкой понимания.",
        prompt_file=PROMPTS_DIR / "system_teacher.md",
        fallback_prompt="Учитель: объясняй простыми словами, шагами и с примерами.",
    ),
    "business_strict": RoleDefinition(
        key="business_strict",
        label="Строгий деловой стиль",
        description="Формальные ответы без воды, только факты и действия.",
        prompt_file=PROMPTS_DIR / "system_business_strict.md",
        fallback_prompt="Строгий деловой стиль: формально, чётко, без эмоций и лишних слов.",
    ),
    "explain": RoleDefinition(
        key="explain",
        label="Режим объяснения",
        description="Короткие объяснения с аналогиями и главными шагами.",
        prompt_file=PROMPTS_DIR / "system_explain.md",
        fallback_prompt="Объясняй максимально понятно: определение, аналогия, ключевые шаги.",
    ),
    "calc": RoleDefinition(
        key="calc",
        label="Простые расчёты",
        description="Арифметика: +, -, *, /, %, скобки. Короткий числовой ответ.",
        prompt_file=PROMPTS_DIR / "system_calc.md",
        fallback_prompt="Считай арифметику точно. Верни только число и короткий шаг расчёта.",
    ),
    "hr": RoleDefinition(
        key="hr",
        label="HR",
        description="Исходный HR-промпт для анализа собеседований.",
        prompt_file=PROMPTS_DIR / "system_hr.md",
        fallback_prompt="Ты — локальный HR-аналитик. Отвечай кратко по фактам из транскрипта.",
    ),
}

DEFAULT_ROLE = "free"


def normalize_role(raw: str | None) -> str:
    key = (raw or DEFAULT_ROLE).strip().lower().replace("-", "_")
    return key if key in ROLE_DEFINITIONS else DEFAULT_ROLE


@lru_cache
def _load_prompt(path: Path, fallback: str) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        text = ""
    return text or fallback


def system_prompt_for(role_key: str | None) -> str:
    role = ROLE_DEFINITIONS.get(normalize_role(role_key), ROLE_DEFINITIONS[DEFAULT_ROLE])
    base = _load_prompt(BASE_PROMPT_PATH, BASE_PROMPT_FALLBACK)
    role_prompt = _load_prompt(role.prompt_file, role.fallback_prompt)
    return "\n\n".join(part for part in (base, role_prompt, LANGUAGE_SUFFIX) if part).strip()


def list_roles() -> list[dict]:
    roles: list[RoleDefinition] = []
    for key in ROLE_ORDER:
        if key in ROLE_DEFINITIONS:
            roles.append(ROLE_DEFINITIONS[key])
    for key, role in ROLE_DEFINITIONS.items():
        if role not in roles:
            roles.append(role)
    return [
        {
            "key": role.key,
            "label": role.label,
            "description": role.description,
        }
        for role in roles
    ]
