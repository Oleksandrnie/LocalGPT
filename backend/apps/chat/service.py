from __future__ import annotations

import ast
import json
import logging
import math
import re
from datetime import datetime
from typing import Iterable

from fastapi import HTTPException
from openai import OpenAI

from app import config
from app.roles import normalize_role, system_prompt_for

LOGGER = logging.getLogger(__name__)

ALLOWED_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
ALLOWED_UNARY_OPS = (ast.UAdd, ast.USub)


TIME_TOKEN_PATTERN = re.compile(r"\d+:\d{1,2}|\d+(?:\.\d+)?|[+\-*/\(\)]")
TIME_HINT_PATTERN = re.compile(r"\b(?:час|ч\.?|hour|hrs?)", re.IGNORECASE)


def sanitize_reply(text: str) -> str:
    """Убирает повторы и случайные мусорные блоки из ответа модели."""
    import re

    text = re.sub(r"[\u4e00-\u9fff]{2,}.*?(?:[.!?。！？]|$)", "", text)

    def _drop_section(src: str, heading: str) -> str:
        pattern = re.compile(rf"(^##\s*{heading}.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
        return re.sub(pattern, "", src)

    for meta_heading in (
        "Минимальный набор фактов",
        "Чеклист перед отправкой",
        "Checklist before sending",
    ):
        text = _drop_section(text, meta_heading)

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


def _format_number(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("non_finite")
    rounded = round(value, 6)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    text = f"{rounded:.6f}".rstrip("0").rstrip(".")
    return text


def _extract_expression(raw: str) -> str | None:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", ".")
    candidates = re.findall(r"[0-9\.\+\-\*/%\(\)\s]+", cleaned)
    if not candidates:
        return None
    expr = max(candidates, key=len).strip()
    if not expr:
        return None
    if not re.fullmatch(r"[0-9\.\+\-\*/%\(\)\s]+", expr):
        return None
    return expr


def _extract_time_expression(raw: str) -> tuple[str | None, bool]:
    """Извлекает выражение, если в нём есть намёк на время (часы:минуты или текст)."""
    cleaned = (raw or "").strip()
    if not cleaned:
        return None, False
    hint = ":" in cleaned or bool(TIME_HINT_PATTERN.search(cleaned))
    cleaned = cleaned.replace(",", ".")
    candidates = re.findall(r"[0-9:\.\+\-\*/\(\)\s]+", cleaned)
    if not candidates:
        return None, hint
    expr = max(candidates, key=len).strip()
    return (expr or None), hint


def _safe_eval(expr: str) -> float:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise exc

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ALLOWED_BIN_OPS):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ValueError("division_by_zero")
                return left / right
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ALLOWED_UNARY_OPS):
            value = _eval(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("unsupported")

    return _eval(tree)


def _format_time_result(minutes_value: float) -> str:
    if not math.isfinite(minutes_value):
        raise ValueError("non_finite")
    sign = "-" if minutes_value < 0 else ""
    total_minutes = abs(minutes_value)
    hours = int(total_minutes // 60)
    minutes = total_minutes - (hours * 60)
    minutes_rounded = round(minutes, 2)
    if minutes_rounded >= 59.995:
        hours += 1
        minutes_rounded = 0.0
    if minutes_rounded.is_integer():
        minutes_text = f"{int(minutes_rounded):02d}"
    else:
        minutes_text = f"{minutes_rounded:05.2f}".rstrip("0").rstrip(".")
    hours_decimal = round(minutes_value / 60.0, 4)
    hours_decimal_text = f"{hours_decimal:.4f}".rstrip("0").rstrip(".")
    return f"{sign}{hours}:{minutes_text} (≈{hours_decimal_text} ч)"


def _evaluate_time_expression(expr: str, *, hinted: bool) -> str | None:
    tokens = TIME_TOKEN_PATTERN.findall(expr)
    if not tokens:
        return None
    sanitized = re.sub(r"\s+", "", expr)
    if "".join(tokens) != sanitized:
        return None
    has_time_token = any(":" in token for token in tokens)
    if not has_time_token and not hinted:
        return None

    converted: list[str] = []
    for token in tokens:
        if token in "+-*/()":
            converted.append(token)
            continue
        if ":" in token:
            hours_str, minutes_str = token.split(":")
            hours_val = int(hours_str)
            minutes_val = int(minutes_str)
            if minutes_val >= 60:
                hours_val += minutes_val // 60
                minutes_val = minutes_val % 60
            converted.append(str(hours_val * 60 + minutes_val))
            continue
        try:
            hours_float = float(token)
        except ValueError:
            return None
        converted.append(str(hours_float * 60.0))

    minutes_expr = "".join(converted)
    try:
        minutes_value = _safe_eval(minutes_expr)
        return _format_time_result(minutes_value)
    except (ValueError, OverflowError, SyntaxError):
        return None


def evaluate_math_expression(raw: str) -> str | None:
    time_expr, hinted = _extract_time_expression(raw)
    if time_expr:
        time_result = _evaluate_time_expression(time_expr, hinted=hinted)
        if time_result is not None:
            return time_result

    expr = _extract_expression(raw)
    if not expr:
        return None

    expr = re.sub(r"(\d+(?:\.\d+)?)%", lambda m: str(float(m.group(1)) / 100.0), expr)

    try:
        result = _safe_eval(expr)
        return _format_number(result)
    except (ValueError, OverflowError, SyntaxError):
        return None


def build_messages(
    *,
    role: str,
    user_query: str,
    context: str | None,
    transcript: str | None,
    criteria: Iterable[str],
    history: list[dict[str, str]],
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt_for(role)}]
    if context:
        messages.append({"role": "user", "content": f"Контекст:\n{context}"})
    if transcript:
        messages.append({"role": "user", "content": f"Транскрипт:\n{transcript}"})
    criteria_list = [c for c in criteria if c]
    if criteria_list:
        criteria_block = "\n".join(f"- {item}" for item in criteria_list)
        messages.append({"role": "user", "content": f"Критерии оценки:\n{criteria_block}"})
    messages.append(
        {
            "role": "system",
            "content": "Отвечай на последний вопрос пользователя, без повторения уже выданных ответов и без пересказа предыдущего анализа.",
        }
    )
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_query})
    return messages


class ChatService:
    def __init__(self) -> None:
        self.client = OpenAI(base_url=config.SETTINGS.base_url, api_key=config.SETTINGS.api_key)

    def log_chat_event(self, payload: dict[str, object]) -> None:
        try:
            config.LOG_DIR.mkdir(parents=True, exist_ok=True)
            with config.CHAT_LOG_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover - лог только для диагностики
            LOGGER.warning("Failed to write chat log: %s", exc)

    def chat_completion(self, model: str, messages: list[dict[str, str]], *, settings: dict) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=settings.get("temperature", config.SETTINGS.temperature),
                max_tokens=settings.get("max_tokens", config.SETTINGS.max_tokens),
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc
        text = resp.choices[0].message.content or ""
        return sanitize_reply(text)


def session_title_hint(raw_title: str | None, query: str | None) -> str:
    if raw_title and raw_title.strip():
        return raw_title.strip()
    prompt = (query or "").strip()
    if prompt:
        return (prompt[:60] + ("…" if len(prompt) > 60 else "")).strip()
    return "Новая сессия"


def normalize_model_name(model_name: str | None, fallback: str | None = None) -> str:
    base = fallback or config.SETTINGS.model
    return (model_name or base).strip() or base
