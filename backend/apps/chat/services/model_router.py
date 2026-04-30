from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from fastapi import HTTPException
from openai import OpenAI

from app import config

AUTO_MODEL_ID = "__auto_router__"
AUTO_MODEL_TITLE = "Auto / Smart Router"
ROUTER_MODEL_ID = "qwen3:0.6b"
LOCAL_CALCULATOR_TARGET = "__local_calculator__"
FALLBACK_TARGET_MODEL = "qwen2.5:7b-instruct"
LOW_CONFIDENCE_THRESHOLD = 0.6

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
    "quick_rag": "qwen2.5:3b-instruct",
    "default_chat": "qwen2.5:7b-instruct",
    "thinking": "qwen3:8b",
    "code": "qwen2.5-coder:7b",
    "code_compare": "deepseek-coder:6.7b",
    "calculation": LOCAL_CALCULATOR_TARGET,
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
- If the request is about exact arithmetic, classify it as calculation.
Supported intents:
- quick_rag: fast retrieval, short factual answer, local RAG lookup
- default_chat: normal writing, rewriting, explanation, general chat
- thinking: complex reasoning, planning, analysis, comparing options
- code: write, debug, explain, refactor code
- code_compare: compare two code solutions or verify another model's code
- calculation: exact arithmetic, hours/minutes, money, rates, percentages
- unknown: unclear request
Available target models:
- qwen2.5:3b-instruct for quick_rag
- qwen2.5:7b-instruct for default_chat and unknown
- qwen3:8b for thinking
- qwen2.5-coder:7b for code
- deepseek-coder:6.7b for code_compare
- __local_calculator__ for calculation
Rules:
1. Do not answer the user's request.
2. Do not perform calculations yourself.
3. For calculation, extract numbers and units into calculation_request.
4. If unsure, use unknown with qwen2.5:7b-instruct.
5. Return confidence from 0 to 1.
6. Return concise reason in Russian.
7. Return only JSON.
JSON schema:
{
  "intent": "quick_rag | default_chat | thinking | code | code_compare | calculation | unknown",
  "target_model": "qwen2.5:3b-instruct | qwen2.5:7b-instruct | qwen3:8b | qwen2.5-coder:7b | deepseek-coder:6.7b | __local_calculator__",
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
    raw_response: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload.get("calculation_request") is None:
            payload.pop("calculation_request", None)
        if not payload.get("fallback"):
            payload.pop("fallback_reason", None)
        if payload.get("raw_response") is None:
            payload.pop("raw_response", None)
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


def route_model(user_message: str, context: dict[str, Any] | None = None) -> RouterDecision:
    client = OpenAI(base_url=config.SETTINGS.base_url, api_key=config.SETTINGS.api_key)
    payload = {
        "user_message": user_message,
        "context": context or {},
    }
    try:
        response = client.chat.completions.create(
            model=ROUTER_MODEL_ID,
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0,
            max_tokens=700,
        )
    except Exception as exc:  # pragma: no cover - depends on Ollama runtime
        raise HTTPException(
            status_code=502,
            detail={
                "code": "router_failed",
                "message": f"Router-модель {ROUTER_MODEL_ID} не смогла обработать запрос: {exc}",
            },
        ) from exc

    content = response.choices[0].message.content if response.choices else ""
    return validate_router_decision(content or "")


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
    return payload

