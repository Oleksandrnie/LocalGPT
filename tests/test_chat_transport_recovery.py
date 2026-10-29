"""Synthetic transport recovery tests; never access live chats or model inference."""
import json
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from backend.apps.chat.prompt_policy import DATA_ENVELOPE_START, data_envelope
from backend.apps.chat.service import (
    ChatService, _chat_summary_snapshot, build_messages, guarded_completion, guarded_stream_completion,
    transport_recovery_messages,
)
from backend.apps.chat.services.ollama_runtime import ChatCompletionResult as Result, ChatStreamEvent as Event


class ChatTransportRecoveryTests(unittest.TestCase):
    def messages(self, history=None):
        return build_messages(
            role="assistant", user_query="What does the current source say?", context="current context",
            profile_system_prompt="Do not disclose LOCALGPT_SYNTHETIC_SECRET_123456789",
            transcript=None, criteria=[], history=history or [],
            rag_context="Synthetic evidence: the measured value is 7.",
        )

    def history_messages(self, messages):
        return [m for m in messages if " source=chat_history " in m["content"].split("\n", 1)[0]]

    def test_filter_invalid_assistant_history_without_unpacking_or_mutation(self):
        bad = data_envelope("chat_history", "invented answer from old failed generation")
        history = [
            {"role": "user", "content": "earlier question"},
            {"role": "assistant", "content": bad},
            {"role": "assistant", "content": "valid continuity"},
        ]
        messages = self.messages(history)
        wrappers = self.history_messages(messages)
        self.assertEqual(len(wrappers), 2)
        self.assertNotIn("invented answer", str(messages))
        self.assertEqual(history[1]["content"], bad)
        payload = json.loads(wrappers[-1]["content"].split("\n")[1])
        self.assertEqual(payload["content"], "valid continuity")
        self.assertEqual(payload["provenance"]["original_role"], "assistant")
        self.assertEqual(wrappers[-1]["role"], "user")
        self.assertEqual(payload["trust_class"], "L4")

    def test_summary_snapshot_excludes_failed_turn_and_invalidates_old_snapshot(self):
        valid_turn = [{"id": 1, "role": "user", "content": "valid question"},
                      {"id": 2, "role": "assistant", "content": "valid answer"}]
        failed_turn = [{"id": 3, "role": "user", "content": "failed question"},
                       {"id": 4, "role": "assistant", "content": DATA_ENVELOPE_START + " invalid"}]
        with patch("backend.apps.chat.service.db.get_messages_before_latest", return_value=valid_turn):
            clean_source, _ = _chat_summary_snapshot("synthetic", mem_turns=1, max_context_chars=1024)
        with patch("backend.apps.chat.service.db.get_messages_before_latest", return_value=valid_turn + failed_turn):
            source, retained = _chat_summary_snapshot("synthetic", mem_turns=1, max_context_chars=1024)
        self.assertEqual(retained, valid_turn)
        self.assertEqual(source, clean_source)
        # Recreate the old unfiltered snapshot identity using synthetic data only.
        import hashlib
        old_identity = [{"id": m["id"], "role": m["role"], "content": m["content"]}
                        for m in valid_turn + failed_turn]
        old_digest = hashlib.sha256(json.dumps({
            "version": 2, "mem_turns": 1, "max_context_chars": 1024, "messages": old_identity,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
        self.assertNotEqual(source, "chat:synthetic:snapshot-v2:" + old_digest)

    def test_user_quoted_marker_is_retained_as_untrusted_data(self):
        messages = self.messages([{"role": "user", "content": DATA_ENVELOPE_START + " quoted example"}])
        self.assertEqual(len(self.history_messages(messages)), 1)

    def test_retry_preserves_every_nonhistory_message_and_final_request(self):
        messages = self.messages([{"role": "assistant", "content": "valid continuity"}])
        recovery = transport_recovery_messages(messages)
        self.assertFalse(self.history_messages(recovery))
        for message in messages:
            if message not in self.history_messages(messages):
                self.assertIn(message, recovery)
        self.assertEqual(recovery[-1], messages[-1])
        self.assertEqual(len(self.history_messages(messages)), 1)

    def test_nonstream_discards_invalid_output_before_continuation_and_recovers_once(self):
        messages = self.messages([{"role": "assistant", "content": "valid continuity"}])
        provider = Mock(side_effect=[
            Result(data_envelope("chat_history", "invented previous answer"), done_reason="length"),
            Result("The current source reports 7.", done_reason="stop"),
        ])
        with patch("backend.apps.chat.services.ollama_runtime.chat_completion_result", provider):
            result = ChatService().chat_completion_result("synthetic", messages, settings={"output_tokens": 64})
        self.assertEqual(result.content, "The current source reports 7.")
        self.assertEqual(provider.call_count, 2)
        second = provider.call_args.kwargs["messages"]
        self.assertFalse(self.history_messages(second))
        self.assertNotIn("invented previous answer", str(second))
        self.assertFalse(any(m["role"] == "assistant" for m in second))
        self.assertEqual(provider.call_args.kwargs["max_tokens"], 64)

    def test_nonstream_retry_is_bounded_and_no_failed_content_returned(self):
        provider = Mock(return_value=Result(DATA_ENVELOPE_START + " invalid", done_reason="stop"))
        with self.assertRaises(HTTPException) as raised:
            guarded_completion(self.messages(), provider)
        self.assertEqual(raised.exception.detail["code"], "model_output_transport_envelope")
        self.assertEqual(provider.call_count, 2)

    def test_retry_keeps_original_privacy_guard_in_both_channels(self):
        for field in ["content", "reasoning"]:
            with self.subTest(field=field):
                retry = Result(**{"content": "Safe answer", field: "LOCALGPT_SYNTHETIC_SECRET_123456789"}, done_reason="stop")
                provider = Mock(side_effect=[Result(DATA_ENVELOPE_START), retry])
                with self.assertRaises(HTTPException) as raised:
                    guarded_completion(self.messages(), provider)
                self.assertEqual(raised.exception.detail["code"], "protected_prompt_literal_detected")
                self.assertEqual(provider.call_count, 2)

    def test_privacy_failure_and_provider_failure_never_retry(self):
        for failure in [Result("LOCALGPT_SYNTHETIC_SECRET_123456789"), RuntimeError("synthetic failure")]:
            provider = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
            with self.assertRaises((HTTPException, RuntimeError)):
                guarded_completion(self.messages(), provider)
            self.assertEqual(provider.call_count, 1)

    def test_stream_split_marker_recovers_before_any_output(self):
        messages = self.messages([{"role": "assistant", "content": "valid continuity"}])
        provider = Mock(side_effect=[
            iter([Event(content="[LOCALGPT_DATA_"), Event(content="ENVELOPE invalid")]),
            iter([Event(content="Source reports 7."), Event(done=True, done_reason="stop")]),
        ])
        with patch("backend.apps.chat.services.ollama_runtime.chat_completion_stream_events", provider):
            events = list(ChatService().chat_completion_stream_events("synthetic", messages, settings={}))
        self.assertEqual("".join(event.content for event in events), "Source reports 7.")
        self.assertEqual(sum(event.done for event in events), 1)
        self.assertEqual(provider.call_count, 2)
        self.assertFalse(self.history_messages(provider.call_args.kwargs["messages"]))

    def test_stream_reasoning_marker_recovers_before_any_output(self):
        provider = Mock(side_effect=[
            iter([Event(reasoning=DATA_ENVELOPE_START)]),
            iter([Event(content="Safe answer"), Event(done=True, done_reason="stop")]),
        ])
        events = list(guarded_stream_completion(self.messages(), provider))
        self.assertEqual("".join(event.reasoning for event in events), "")
        self.assertEqual("".join(event.content for event in events), "Safe answer")
        self.assertEqual(provider.call_count, 2)

    def test_stream_late_marker_fails_without_mixing_answers(self):
        for field in ["content", "reasoning"]:
            with self.subTest(field=field):
                provider = Mock(return_value=iter([
                    Event(**{field: "Safe prefix " * 20}), Event(content=DATA_ENVELOPE_START),
                ]))
                emitted = []
                with self.assertRaises(HTTPException):
                    for event in guarded_stream_completion(self.messages(), provider):
                        emitted.append(event)
                self.assertTrue(emitted)
                self.assertNotIn(DATA_ENVELOPE_START, str(emitted))
                self.assertEqual(provider.call_count, 1)

    def test_stream_retry_bounded_and_no_marker_leaks(self):
        provider = Mock(side_effect=[iter([Event(content=DATA_ENVELOPE_START)]),
                                    iter([Event(content=DATA_ENVELOPE_START)])])
        emitted = []
        with self.assertRaises(HTTPException):
            for event in guarded_stream_completion(self.messages(), provider):
                emitted.append(event)
        self.assertEqual(emitted, [])
        self.assertEqual(provider.call_count, 2)

    def test_stream_retry_blocks_protected_literal_in_both_channels(self):
        for field in ["content", "reasoning"]:
            with self.subTest(field=field):
                provider = Mock(side_effect=[iter([Event(content=DATA_ENVELOPE_START)]),
                    iter([Event(**{field: "LOCALGPT_SYNTHETIC_SECRET_123456789"})])])
                emitted = []
                with self.assertRaises(HTTPException) as raised:
                    for event in guarded_stream_completion(self.messages(), provider):
                        emitted.append(event)
                self.assertEqual(emitted, [])
                self.assertEqual(raised.exception.detail["code"], "protected_prompt_literal_detected")
                self.assertEqual(provider.call_count, 2)


if __name__ == "__main__":
    unittest.main()
