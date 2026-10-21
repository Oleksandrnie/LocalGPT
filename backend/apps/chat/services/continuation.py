"""Bounded continuation orchestration; provider calls retain their original options."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Iterable, Iterator

from fastapi import HTTPException

from backend.apps.chat.services.ollama_runtime import ChatCompletionResult, ChatStreamEvent

MAX_CONTINUATIONS = 4
CONTINUE_INSTRUCTION = (
    "Continue the same answer exactly where it was cut off. Do not repeat any existing "
    "text or restart the answer. Preserve the original request, language, format, and "
    "evidence restrictions; do not introduce new sources or change the task."
)


def _require_content(content: str, reasoning: str, done_reason: str | None) -> None:
    if content.strip():
        return
    message = (
        "Thinking budget exhausted before the model produced a final answer."
        if reasoning.strip() and done_reason == "length"
        else "The model completed without a final answer."
    )
    raise HTTPException(status_code=502, detail={
        "code": "chat_final_answer_incomplete", "message": message, "done_reason": done_reason,
    })


def continuation_messages(messages: list[dict[str, Any]], content: str) -> list[dict[str, Any]]:
    return [dict(message) for message in messages] + [
        {"role": "assistant", "content": content},
        {"role": "user", "content": CONTINUE_INSTRUCTION},
    ]


def without_overlap(previous: str, content: str) -> str:
    # Remove only an exact suffix/prefix match, never fuzzy or interior matches.
    if not content or not previous:
        return content
    prefix = [0] * len(content)
    size = 0
    for index in range(1, len(content)):
        while size and content[index] != content[size]:
            size = prefix[size - 1]
        if content[index] == content[size]:
            size += 1
        prefix[index] = size
    size = 0
    for char in previous[-len(content):]:
        while size and (size == len(content) or char != content[size]):
            size = prefix[size - 1]
        if char == content[size]:
            size += 1
    return content[size:]


def complete(messages: list[dict[str, Any]], call: Callable[..., ChatCompletionResult]) -> ChatCompletionResult:
    content = reasoning = ""
    current_messages = messages
    for attempt in range(MAX_CONTINUATIONS + 1):
        result = call(current_messages)
        _require_content(result.content, result.reasoning, result.done_reason)
        addition = without_overlap(content, result.content) if attempt else result.content
        content += addition
        reasoning += result.reasoning
        if result.done_reason != "length" or not result.content.strip() or not addition.strip():
            break
        if attempt < MAX_CONTINUATIONS:
            current_messages = continuation_messages(messages, content)
    return replace(result, content=content, reasoning=reasoning)


def stream(messages: list[dict[str, Any]], call: Callable[..., Iterable[ChatStreamEvent]]) -> Iterator[ChatStreamEvent]:
    content = ""
    current_messages = messages
    for attempt in range(MAX_CONTINUATIONS + 1):
        pass_content = pass_reasoning = ""
        terminal = None
        for event in call(current_messages):
            pass_content += event.content
            pass_reasoning += event.reasoning
            if event.done:
                terminal = event
            # The initial pass streams normally. Later bounded passes are held
            # until exact overlap can be resolved without retracting SSE deltas.
            if not attempt and (event.content or event.reasoning):
                yield replace(event, done=False, done_reason=None, eval_count=None)
        addition = without_overlap(content, pass_content) if attempt else pass_content
        content += addition
        if attempt and (addition or pass_reasoning):
            yield ChatStreamEvent(content=addition, reasoning=pass_reasoning)
        if terminal is None:
            # A dropped/incomplete provider stream is never a successful stop.
            raise HTTPException(status_code=502, detail={
                "code": "chat_final_answer_incomplete",
                "message": "The model completed without a final answer.",
            })
        _require_content(pass_content, pass_reasoning, terminal.done_reason)
        if (terminal.done_reason != "length" or not pass_content.strip()
                or not addition.strip() or attempt == MAX_CONTINUATIONS):
            yield replace(terminal, content="", reasoning="")
            return
        current_messages = continuation_messages(messages, content)
