import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app import db
from backend.apps.chat import tasks
from backend.apps.chat.service import ChatService
from backend.apps.chat.services import continuation, ollama_runtime, vision_runtime

Result = ollama_runtime.ChatCompletionResult
Event = ollama_runtime.ChatStreamEvent


class ChatContinuationTests(unittest.TestCase):
    def test_nonstream_preserves_prompt_and_options_and_removes_overlap(self):
        messages = [{"role": "system", "content": "policy"}, {"role": "user", "content": "original task"}]
        with patch.object(ollama_runtime, "chat_completion_result", side_effect=[
            Result("first part", done_reason="length"), Result("part finished", done_reason="stop"),
        ]) as provider:
            result = ChatService().chat_completion_result("model", messages, settings={"output_tokens": 64})
        self.assertEqual(result.content, "first part finished")
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(provider.call_args_list[0].kwargs["max_tokens"], 64)
        self.assertEqual(provider.call_args_list[1].kwargs["max_tokens"], 64)
        self.assertEqual(provider.call_args.kwargs["messages"][:2], messages)
        self.assertEqual(provider.call_args.kwargs["messages"][-2]["content"], "first part")
        self.assertEqual(messages[-1]["content"], "original task")

    def test_gate_empty_reasoning_stop_missing_reason_and_failure(self):
        for result in [Result("", done_reason="length"), Result("", reasoning="thinking", done_reason="length"),
                       Result("answer", done_reason="stop"), Result("answer")]:
            with self.subTest(result=result):
                provider = Mock(return_value=result)
                try:
                    continuation.complete([], provider)
                except HTTPException:
                    self.assertFalse(result.content)
                self.assertEqual(provider.call_count, 1)
        for exception in [RuntimeError("provider failure"), GeneratorExit("cancelled")]:
            provider = Mock(side_effect=exception)
            with self.assertRaises(type(exception)):
                continuation.complete([], provider)
            self.assertEqual(provider.call_count, 1)

    def test_four_additional_passes_maximum_and_stalled_overlap_is_incomplete(self):
        provider = Mock(side_effect=[Result(str(i), done_reason="length") for i in range(5)])
        result = continuation.complete([], provider)
        self.assertEqual(provider.call_count, 5)
        self.assertEqual(result.content, "01234")
        with self.assertRaises(HTTPException):
            ChatService.require_final_answer(result)
        provider = Mock(return_value=Result("repeated", done_reason="length"))
        result = continuation.complete([], provider)
        self.assertEqual(result.content, "repeated")
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(result.done_reason, "length")

    def test_stream_continuation_has_one_terminal_and_separate_reasoning(self):
        provider = Mock(side_effect=[
            iter([Event(content="first part"), Event(done=True, done_reason="length")]),
            iter([Event(reasoning="trace"), Event(content="part finished"), Event(done=True, done_reason="stop")]),
        ])
        with patch.object(ollama_runtime, "chat_completion_stream_events", provider):
            events = list(ChatService().chat_completion_stream_events("model", [], settings={"output_tokens": 64}))
        self.assertEqual("".join(e.content for e in events), "first part finished")
        self.assertEqual("".join(e.reasoning for e in events), "trace")
        self.assertEqual(sum(e.done for e in events), 1)
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(provider.call_args.kwargs["max_tokens"], 64)

    def test_stream_does_not_retry_empty_reasoning_stop_or_failure(self):
        for events in [
            [Event(done=True, done_reason="length")],
            [Event(reasoning="trace"), Event(done=True, done_reason="length")],
            [Event(content="answer"), Event(done=True, done_reason="stop")],
            [Event(content="answer"), Event(done=True)],
            [Event(content="disconnected")],
        ]:
            provider = Mock(return_value=iter(events))
            try:
                list(continuation.stream([], provider))
            except HTTPException:
                pass
            self.assertEqual(provider.call_count, 1)
        for exception in [RuntimeError("failed"), GeneratorExit("cancelled")]:
            provider = Mock(side_effect=exception)
            with self.assertRaises(type(exception)):
                list(continuation.stream([], provider))
            self.assertEqual(provider.call_count, 1)

    def test_direct_vision_privacy_guard_covers_pass_boundary(self):
        secret = "LOCALGPT_PRIVATE_CANARY_123456789"
        messages = [{"role": "system", "content": secret}, {"role": "user", "content": "task"}]
        for streaming in [False, True]:
            with self.subTest(streaming=streaming), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                outputs = [Result(secret[:18], done_reason="length"), Result(secret[18:], done_reason="stop")]
                if streaming:
                    outputs = [iter([Event(content=r.content), Event(done=True, done_reason=r.done_reason)]) for r in outputs]
                method = "chat_completion_stream_events" if streaming else "chat_completion_result"
                with patch.object(vision_runtime, method, side_effect=outputs):
                    tasks._chat_worker(
                        "model", messages, {"ocr_assist": "off"}, "", None, None, streaming,
                        *[str(root / name) for name in ["delta", "reasoning", "status", "result", "error"]],
                        [{"path": "/synthetic/image.png"}],
                        {"mode": "direct", "vision_model": "model", "response_model": "model"},
                    )
                self.assertEqual(json.loads((root / "error").read_text())["code"], "protected_prompt_literal_detected")
                self.assertFalse((root / "result").exists())
                if (root / "delta").exists():
                    text = "".join(json.loads(line)["text"] for line in (root / "delta").read_text().splitlines())
                    self.assertNotIn(secret, text)

    def test_privacy_guard_covers_pass_boundary_nonstream_and_stream(self):
        secret = "LOCALGPT_PRIVATE_CANARY_123456789"
        messages = [{"role": "system", "content": secret}]
        split = 18
        with patch.object(ollama_runtime, "chat_completion_result", side_effect=[
            Result(secret[:split], done_reason="length"), Result(secret[split:], done_reason="stop"),
        ]):
            with self.assertRaises(HTTPException) as caught:
                ChatService().chat_completion_result("model", messages, settings={})
            self.assertEqual(caught.exception.detail["code"], "protected_prompt_literal_detected")
        for field in ["content", "reasoning"]:
            outputs = []
            first = {field: secret[:split]}
            second = {field: secret[split:]}
            if field == "reasoning":
                first["content"] = "first"
                second["content"] = " last"
            with patch.object(ollama_runtime, "chat_completion_stream_events", side_effect=[
                iter([Event(**first), Event(done=True, done_reason="length")]),
                iter([Event(**second), Event(done=True, done_reason="stop")]),
            ]):
                with self.assertRaises(HTTPException):
                    for event in ChatService().chat_completion_stream_events("model", messages, settings={}):
                        outputs.append(getattr(event, field))
            self.assertNotIn(secret, "".join(outputs))

    def test_worker_text_and_direct_vision_stream_and_nonstream(self):
        for vision in [False, True]:
            for streaming in [False, True]:
                with self.subTest(vision=vision, streaming=streaming), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    original_db = db.DB_PATH
                    db.DB_PATH = root / "test.db"
                    try:
                        db.init_db()
                        profile = db.ensure_default_profile()
                        session = db.create_session(profile, "continued", "model")
                        db.add_message(session["id"], "user", "original task")
                        assistant = db.create_assistant_message(session["id"], model="model")
                        provider_module = vision_runtime if vision else ollama_runtime
                        method = "chat_completion_stream_events" if streaming else "chat_completion_result"
                        outputs = [Result("first part", done_reason="length"), Result("part finished", done_reason="stop")]
                        if streaming:
                            outputs = [iter([Event(content=r.content), Event(done=True, done_reason=r.done_reason)]) for r in outputs]
                        with patch.object(provider_module, method, side_effect=outputs) as provider:
                            tasks._chat_worker(
                                "model", [{"role": "user", "content": "original task"}],
                                {"ocr_assist": "off", "output_tokens": 64, "vision_output_tokens": 128},
                                session["id"], profile, assistant["id"], streaming,
                                *[str(root / name) for name in ["delta", "reasoning", "status", "result", "error"]],
                                [{"path": "/synthetic/image.png"}] if vision else None,
                                {"mode": "direct", "vision_model": "model", "response_model": "model"} if vision else None,
                            )
                        self.assertFalse((root / "error").exists())
                        self.assertEqual(json.loads((root / "result").read_text())["reply"], "first part finished")
                        self.assertEqual(db.get_message(assistant["id"])["status"], "completed")
                        self.assertEqual(provider.call_count, 2)
                        for call in provider.call_args_list:
                            self.assertEqual(call.args[0], "model")
                            self.assertEqual(call.kwargs["max_tokens"], 128 if vision else 64)
                        if vision:
                            self.assertEqual(provider.call_args.args[2], ["/synthetic/image.png"])
                            self.assertEqual(provider.call_args.kwargs["max_tokens"], 128)
                    finally:
                        db.DB_PATH = original_db

    def test_worker_cap_exhaustion_excludes_completed_history_and_memory(self):
        for streaming in [False, True]:
            with self.subTest(streaming=streaming), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                original_db = db.DB_PATH
                db.DB_PATH = root / "test.db"
                try:
                    db.init_db()
                    profile = db.ensure_default_profile()
                    session = db.create_session(profile, "cap", "model")
                    db.add_message(session["id"], "user", "task")
                    assistant = db.create_assistant_message(session["id"], model="model")
                    outputs = [Result(str(index), done_reason="length") for index in range(5)]
                    if streaming:
                        outputs = [iter([Event(content=r.content), Event(done=True, done_reason=r.done_reason)]) for r in outputs]
                    method = "chat_completion_stream_events" if streaming else "chat_completion_result"
                    with patch.object(ollama_runtime, method, side_effect=outputs) as provider, patch.object(tasks, "maybe_compress_session_history") as compress:
                        tasks._chat_worker(
                            "model", [{"role": "user", "content": "task"}], {"output_tokens": 64},
                            session["id"], profile, assistant["id"], streaming,
                            *[str(root / name) for name in ["delta", "reasoning", "status", "result", "error"]],
                        )
                    self.assertEqual(provider.call_count, 5)
                    self.assertEqual(json.loads((root / "error").read_text())["code"], "chat_final_answer_incomplete")
                    self.assertFalse((root / "result").exists())
                    self.assertEqual(db.get_message(assistant["id"])["status"], "failed")
                    self.assertEqual(db.get_message(assistant["id"])["content"], "")
                    self.assertEqual(db._completed_conversation_turns(session["id"]), [])
                    compress.assert_not_called()
                finally:
                    db.DB_PATH = original_db

    def test_rag_vision_analysis_and_response_continue_without_new_retrieval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            messages = [
                {"role": "system", "content": "original policy"},
                {"role": "user", "content": "Compare the image with RAG knowledge base documents"},
            ]
            with patch.object(vision_runtime, "chat_completion_result", side_effect=[
                Result("visual part", done_reason="length"), Result("part complete", done_reason="stop"),
            ]) as vision, patch.object(ollama_runtime, "chat_completion_result", side_effect=[
                Result("RAG part", done_reason="length"), Result("part complete", done_reason="stop"),
            ]) as text, patch("backend.apps.rag.service.search") as retrieval:
                tasks._chat_worker(
                    "text-model", messages, {"ocr_assist": "off", "output_tokens": 64, "vision_output_tokens": 128},
                    "", None, None, False,
                    *[str(root / name) for name in ["delta", "reasoning", "status", "result", "error"]],
                    [{"path": "/synthetic/image.png"}],
                    {"mode": "vision_context", "vision_model": "vision-model", "response_model": "text-model"},
                )
            self.assertFalse((root / "error").exists())
            result = json.loads((root / "result").read_text())
            self.assertEqual(result["reply"], "RAG part complete")
            self.assertEqual(result["vision_context"], "visual part complete")
            self.assertTrue(result["image_rag_included"])
            self.assertEqual(vision.call_count, 2)
            self.assertEqual(text.call_count, 2)
            retrieval.assert_not_called()
            for call in vision.call_args_list:
                self.assertEqual(call.args[2], ["/synthetic/image.png"])
                self.assertEqual(call.kwargs["max_tokens"], 128)
            self.assertEqual(vision.call_args.args[1][:len(vision.call_args_list[0].args[1])], vision.call_args_list[0].args[1])
            self.assertEqual(text.call_args.kwargs["messages"][:-2], text.call_args_list[0].kwargs["messages"])


if __name__ == "__main__":
    unittest.main()
