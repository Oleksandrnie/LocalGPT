from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from fastapi import HTTPException

from app import config
from backend.apps.chat.services import model_residency, ollama_runtime

AUTO_MODEL_ID = "__auto_router__"
AUTO_MODEL_TITLE = "Auto / Smart Router"
ROUTER_MODEL_ID = "qwen3:0.6b"
LOCAL_CALCULATOR_TARGET = "__local_calculator__"
FALLBACK_TARGET_MODEL = "qwen2.5:7b-instruct"
LOW_CONFIDENCE_THRESHOLD = 0.6
EXPLICIT_CODE_LANGUAGE_RE = re.compile(
    r"(?i)(\bhtml\b|\bcss\b|\bjavascript\b|\bjs\b|\btypescript\b|\bts\b|\breact\b|\bvue\b|\bsvelte\b|"
    r"\bpython\b|\bfastapi\b|\bdocker\b|\bsql\b)"
)
EXPLICIT_CODE_ACTION_RE = re.compile(
    r"(?i)(напиши|сделай|создай|сгенерируй|верни|выведи|исправь|отлад|рефактор|реализуй|"
    r"сверстай|добавь|объясни|проверь|write|create|generate|return|fix|debug|refactor|implement)"
)
EXPLICIT_CODE_OBJECT_RE = re.compile(
    r"(?i)(код|скрипт|компонент|разметк|верстк|функци[яюи]|класс|endpoint|api|code|script|component|markup)"
)
QUICK_RAG_SOURCE_RE = re.compile(
    r"(?i)(\brag\b|раг\b|из\s+ра[гк]а?\b|из\s+баз[ыае]\b|по\s+баз[еы]\b|из\s+документ|"
    r"в\s+документ|из\s+контекст|из\s+файл|в\s+файл)"
)
QUICK_RAG_ACTION_RE = re.compile(
    r"(?i)(вытащ|достан|найд|покаж|перечисл|список|какие\s+есть|есть\s+ли|"
    r"в\s+одн[уо]?\s+строч|одной\s+строк|коротко|просто\s+данн|extract|list|find|show)"
)
QUICK_RAG_VERIFY_RE = re.compile(
    r"(?i)(точно|проверь|проверить|перепроверь|верно|правильно|самый\s+минимальн|"
    r"самый\s+деш[её]в|самый\s+маленьк|минимальн)"
)
QUICK_RAG_FACT_RE = re.compile(
    r"(?i)(тариф|цен[аыу]|стоимост|депозит|пакет|план|услови|минимальн|максимальн|"
    r"номер|дат[ауы]|срок|контакт|email|почт|телефон|адрес|реквизит|факт)"
)
QUICK_RAG_COMPLEX_RE = re.compile(
    r"(?i)(проанализ|сравн|выбери|лучше|оптимальн|стратег|план|рекоменд|объясни|"
    r"напиши\s+(?:сообщение|письмо|текст)|перепиш|сформулируй|summary|резюме)"
)

SUPPORTED_INTENTS = {
    "quick_rag",
    "default_chat",
    "thinking",
    "code",
    "code_compare",
    "calculation",
    "unknown",
}

ROUTER_MODEL_MAP = {
    "quick_rag": FALLBACK_TARGET_MODEL,
    "default_chat": "qwen2.5:7b-instruct",
    "thinking": "qwen3:8b",
    "code": "qwen2.5-coder:7b",
    "code_compare": "qwen2.5-coder:7b",
    "calculation": FALLBACK_TARGET_MODEL,
    "unknown": FALLBACK_TARGET_MODEL,
}

ROUTER_SYSTEM_PROMPT = """You are a local model router for LocalGPT.
Your task is to classify the user's chat request and select the best target model.
Return only valid JSON. No markdown. No explanations outside JSON.
Important:
- You are used only for chat flow.
- Do not route ASR Studio tasks.
- Do not route ASR pipeline stages.
- Do not select models for transcription, transcript pipeline, cleaner, segmenter, structurer, or summary stages.
- If the request is clearly about processing an already provided transcript inside normal chat, classify it as default_chat or thinking depending on complexity.
- If the request is about code, classify it as code or code_compare.
- Requests to create HTML, CSS, JavaScript, Python, API, component, markup, or script output are code,
  even if the content inside the code is marketing text, SEO, tariffs, a list, or another non-programming topic.
- If the request is about exact arithmetic, classify it as calculation, but route it to qwen2.5:7b-instruct.
  Local Calculator is used only when the user manually selects it in the model selector.
Supported intents:
- quick_rag: fast retrieval, short factual answer, local RAG lookup
- default_chat: normal writing, rewriting, explanation, general chat
- thinking: complex reasoning, planning, analysis, comparing options
- code: write, debug, explain, refactor code
- code_compare: compare two code solutions or verify another model's code
- calculation: exact arithmetic, hours/minutes, money, rates, percentages
- unknown: unclear request
Available target models:
- qwen2.5:7b-instruct for quick_rag, default_chat, calculation and unknown
- qwen3:8b for thinking
- qwen2.5-coder:7b for code and code_compare
- qwen2.5:3b-instruct, deepseek-coder:6.7b and mistral-nemo:12b are available for manual/pipeline usage,
  but Auto Router must not select them.
Rules:
1. Do not answer the user's request.
2. Do not perform calculations yourself.
3. For calculation, do not select __local_calculator__; select qwen2.5:7b-instruct.
4. If unsure, use unknown with qwen2.5:7b-instruct.
5. Return confidence from 0 to 1.
6. Return concise reason in Russian.
7. Return only JSON.
8. If RAG is enabled and the user asks to extract, list, or check short factual data, use quick_rag.
9. If the user asks to write, rewrite, explain, compare, or analyze retrieved facts, use default_chat or thinking.
JSON schema:
{
  "intent": "quick_rag | default_chat | thinking | code | code_compare | calculation | unknown",
  "target_model": "qwen2.5:7b-instruct | qwen3:8b | qwen2.5-coder:7b",
  "confidence": 0.0,
  "reason": "string",
  "calculation_request": {}
}"""


@dataclass
class RouterDecision:
    intent: str
    target_model: str
    confidence: float
    reason: str
    calculation_request: dict[str, Any] | None = None
    fallback: bool = False
    fallback_reason: str | None = None
    backend_override: bool = False
    backend_override_reason: str | None = None
    raw_response: str | None = None
    runtime_debug: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload.get("calculation_request") is None:
            payload.pop("calculation_request", None)
        if not payload.get("fallback"):
            payload.pop("fallback_reason", None)
        if not payload.get("backend_override"):
            payload.pop("backend_override_reason", None)
        if payload.get("raw_response") is None:
            payload.pop("raw_response", None)
        if payload.get("runtime_debug") is None:
            payload.pop("runtime_debug", None)
        return payload


def is_auto_model(selected_model: str | None) -> bool:
    value = str(selected_model or "").strip().lower()
    return value in {AUTO_MODEL_ID, "auto", "smart_router", "auto_router", "auto / smart router"}


def fallback_router_decision(reason: str, *, raw_response: str | None = None) -> RouterDecision:
    return RouterDecision(
        intent="unknown",
        target_model=FALLBACK_TARGET_MODEL,
        confidence=0.0,
        reason="Auto не смог уверенно определить тип задачи.",
        fallback=True,
        fallback_reason=reason,
        raw_response=raw_response,
    )


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def looks_like_explicit_code_request(user_message: str) -> bool:
    text = str(user_message or "").strip()
    if not text:
        return False
    has_language = bool(EXPLICIT_CODE_LANGUAGE_RE.search(text))
    has_action = bool(EXPLICIT_CODE_ACTION_RE.search(text))
    has_object = bool(EXPLICIT_CODE_OBJECT_RE.search(text))
    return (has_language and (has_action or has_object)) or (has_action and has_object)


def looks_like_simple_rag_lookup(user_message: str, context: dict[str, Any] | None = None) -> bool:
    text = str(user_message or "").strip()
    if not text:
        return False
    if QUICK_RAG_COMPLEX_RE.search(text):
        return False
    recent_text = "\n".join(
        str(item or "")
        for item in ((context or {}).get("recent_user_queries") or [])[-3:]
        if str(item or "").strip()
    )
    combined_text = "\n".join([recent_text, text]).strip()
    has_source = bool(QUICK_RAG_SOURCE_RE.search(text))
    has_action = bool(QUICK_RAG_ACTION_RE.search(text))
    has_verify = bool(QUICK_RAG_VERIFY_RE.search(text))
    has_fact = bool(QUICK_RAG_FACT_RE.search(text) or QUICK_RAG_FACT_RE.search(combined_text))
    rag_enabled = bool((context or {}).get("rag_enabled"))
    return (has_source and (has_action or has_verify or has_fact)) or (
        rag_enabled and (has_action or has_verify) and has_fact
    )


def correct_router_decision(
    user_message: str,
    decision: RouterDecision,
    context: dict[str, Any] | None = None,
) -> RouterDecision:
    if not looks_like_explicit_code_request(user_message):
        if decision.intent == "quick_rag":
            return decision
        if decision.intent not in {"code", "code_compare", "calculation"} and looks_like_simple_rag_lookup(user_message, context):
            return RouterDecision(
                intent="quick_rag",
                target_model=ROUTER_MODEL_MAP["quick_rag"],
                confidence=max(decision.confidence, 0.9),
                reason="Запрос просит быстро извлечь факты из RAG без анализа или переписывания.",
                calculation_request=None,
                fallback=False,
                backend_override=True,
                backend_override_reason="simple_rag_lookup",
                raw_response=decision.raw_response,
            )
        return decision
    if decision.intent in {"code", "code_compare"}:
        return decision
    return RouterDecision(
        intent="code",
        target_model=ROUTER_MODEL_MAP["code"],
        confidence=max(decision.confidence, 0.95),
        reason="Запрос явно просит написать или изменить программный код.",
        calculation_request=None,
        fallback=False,
        backend_override=True,
        backend_override_reason="explicit_code_request",
        raw_response=decision.raw_response,
    )


def validate_router_decision(raw_json: str) -> RouterDecision:
    raw = str(raw_json or "").strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return fallback_router_decision("invalid_json", raw_response=raw[:2000])

    if not isinstance(payload, dict):
        return fallback_router_decision("invalid_json", raw_response=raw[:2000])

    intent = str(payload.get("intent") or "unknown").strip()
    if intent not in SUPPORTED_INTENTS:
        intent = "unknown"

    expected_target = ROUTER_MODEL_MAP[intent]
    target_model = str(payload.get("target_model") or "").strip()
    if target_model != expected_target:
        target_model = expected_target

    confidence = _coerce_confidence(payload.get("confidence"))
    reason = str(payload.get("reason") or "").strip() or "Auto выбрал модель по типу запроса."
    calculation_request = payload.get("calculation_request") if isinstance(payload.get("calculation_request"), dict) else None

    decision = RouterDecision(
        intent=intent,
        target_model=target_model,
        confidence=confidence,
        reason=reason,
        calculation_request=calculation_request,
        raw_response=raw[:2000],
    )
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return fallback_router_decision("low_confidence", raw_response=raw[:2000])
    return decision


def route_model(
    user_message: str,
    context: dict[str, Any] | None = None,
    *,
    settings: dict[str, Any] | None = None,
) -> RouterDecision:
    payload = {
        "user_message": user_message,
        "context": context or {},
    }
    router_runtime = model_residency.prepare_router_for_request(settings or {})
    keep_alive = router_runtime.get("router_keep_alive")
    try:
        content = ollama_runtime.chat_completion(
            ROUTER_MODEL_ID,
            [
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0,
            max_tokens=700,
            keep_alive=keep_alive,
        )
    except Exception as exc:  # pragma: no cover - depends on Ollama runtime
        raise HTTPException(
            status_code=502,
            detail={
                "code": "router_failed",
                "message": f"Router-модель {ROUTER_MODEL_ID} не смогла обработать запрос.",
            },
        ) from exc

    decision = validate_router_decision(content or "")
    decision = correct_router_decision(user_message, decision, context)
    decision.runtime_debug = router_runtime
    return decision


def router_debug_settings(decision: RouterDecision) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model_selection_mode": "auto",
        "router_model": ROUTER_MODEL_ID,
        "router_intent": decision.intent,
        "router_target_model": decision.target_model,
        "router_confidence": decision.confidence,
        "router_reason": decision.reason,
    }
    if decision.fallback:
        payload["router_fallback"] = True
        payload["router_fallback_reason"] = decision.fallback_reason or "unknown"
    if decision.backend_override:
        payload["router_backend_override"] = True
        payload["router_backend_override_reason"] = decision.backend_override_reason or "unknown"
    if decision.runtime_debug:
        payload.update(decision.runtime_debug)
    return payload
