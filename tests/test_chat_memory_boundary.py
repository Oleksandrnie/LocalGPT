from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import db
from app.schemas import ChatRequest
from backend.apps.chat.routes import _prepare_chat_request
from backend.apps.chat.service import current_session_summary_memory, maybe_compress_session_history


class ChatMemoryBoundaryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "chat-memory-boundary.db"
        db.init_db()
        self.profile_id = db.ensure_default_profile()
        self.session = db.create_session(self.profile_id, "Memory boundary", "qwen2.5:3b")
        self.other_session = db.create_session(self.profile_id, "Other session", "qwen2.5:3b")

    def tearDown(self) -> None:
        db.DB_PATH = self.previous_db_path
        self.tmpdir.cleanup()

    def _completed_turn(self, number: int) -> None:
        db.add_message(self.session["id"], "user", f"eligible-user-{number}", status="completed")
        db.add_message(
            self.session["id"],
            "assistant",
            f"eligible-assistant-{number}",
            reasoning=f"private-reasoning-{number}",
            status="completed",
        )

    @staticmethod
    def _contents(messages: list[dict]) -> list[str]:
        return [str(item["content"]) for item in messages]

    def _add_mixed_history(self) -> None:
        self._completed_turn(1)
        db.add_message(self.session["id"], "user", "failed-user", status="completed")
        db.add_message(self.session["id"], "assistant", "failed-assistant", status="failed", error="synthetic")
        self._completed_turn(2)
        db.add_message(self.session["id"], "user", "active-user", status="completed")
        db.add_message(self.session["id"], "assistant", "active-assistant", status="streaming")
        self._completed_turn(3)
        db.add_message(self.session["id"], "user", "partial-user", status="completed")
        db.add_message(
            self.session["id"],
            "assistant",
            "partial-assistant",
            status="completed",
            is_partial=True,
        )
        self._completed_turn(4)
        db.add_message(self.session["id"], "assistant", "orphan-assistant", status="completed")
        db.add_message(self.session["id"], "user", "superseded-orphan-user", status="completed")
        self._completed_turn(5)
        db.add_message(self.session["id"], "user", "cancelled-user", status="completed")
        db.add_message(self.session["id"], "assistant", "cancelled-assistant", status="cancelled")
        self._completed_turn(6)
        db.add_message(self.session["id"], "user", "latest-orphan-user", status="completed")

        db.add_message(self.other_session["id"], "user", "foreign-user", status="completed")
        db.add_message(self.other_session["id"], "assistant", "foreign-assistant", status="completed")

    def test_completed_turn_selection_splits_old_and_recent_history(self) -> None:
        self._add_mixed_history()

        recent = db.get_prompt_history(self.session["id"], limit_turns=2)
        old = db.get_messages_before_latest(self.session["id"], keep_pairs=2)
        all_eligible = db.get_messages_before_latest(self.session["id"], keep_pairs=0)

        expected_all = [
            value
            for number in range(1, 7)
            for value in (f"eligible-user-{number}", f"eligible-assistant-{number}")
        ]
        self.assertEqual(self._contents(old), expected_all[:8])
        self.assertEqual(self._contents(recent), expected_all[8:])
        self.assertEqual(self._contents(all_eligible), expected_all)
        self.assertEqual(self._contents(old) + self._contents(recent), expected_all)
        self.assertTrue(set(self._contents(old)).isdisjoint(self._contents(recent)))
        self.assertEqual(db.get_prompt_history(self.session["id"], limit_turns=0), [])
        self.assertEqual(
            self._contents(db.get_messages_before_latest(self.session["id"], keep_pairs=-4)),
            expected_all,
        )
        self.assertNotIn("private-reasoning", str(old) + str(recent))
        self.assertNotIn("foreign-", str(all_eligible))

    def test_compressor_receives_only_older_completed_turns(self) -> None:
        for number in range(1, 6):
            self._completed_turn(number)
            if number == 2:
                db.add_message(self.session["id"], "user", "excluded-failed-user", status="completed")
                db.add_message(self.session["id"], "assistant", "excluded-failed-assistant", status="failed")
            if number == 3:
                db.add_message(self.session["id"], "user", "excluded-active-user", status="completed")
                db.add_message(self.session["id"], "assistant", "excluded-partial-assistant", status="streaming")
        db.add_message(self.session["id"], "user", "excluded-orphan-user", status="completed")
        db.add_message(self.other_session["id"], "user", "excluded-foreign-user", status="completed")
        db.add_message(self.other_session["id"], "assistant", "excluded-foreign-assistant", status="completed")
        provider = Mock()
        provider.chat_completion.return_value = "safe summary"

        result = maybe_compress_session_history(
            service=provider,
            session_id=self.session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5:3b",
            settings={"summary_memory_enabled": True, "mem_turns": 1, "max_context_chars": 16000},
        )

        self.assertIsNotNone(result)
        provider.chat_completion.assert_called_once()
        prompt = provider.chat_completion.call_args.args[1]
        summary_request = "\n".join(str(item.get("content") or "") for item in prompt)
        for number in range(1, 5):
            self.assertIn(f"eligible-user-{number}", summary_request)
            self.assertIn(f"eligible-assistant-{number}", summary_request)
        self.assertNotIn("eligible-user-5", summary_request)
        self.assertNotIn("eligible-assistant-5", summary_request)
        for marker in ("excluded-failed", "excluded-active", "excluded-partial", "excluded-orphan", "excluded-foreign"):
            self.assertNotIn(marker, summary_request)
        self.assertNotIn("private-reasoning", summary_request)
        self.assertEqual(result["structured_json"]["message_count"], 8)
        self.assertEqual(result["structured_json"]["source_message_count"], 8)

    def test_chat_summary_identity_changes_when_source_content_is_edited(self) -> None:
        for number in range(1, 6):
            self._completed_turn(number)
        provider = Mock()
        provider.chat_completion.side_effect = ["first snapshot", "edited snapshot"]
        settings = {"summary_memory_enabled": True, "mem_turns": 1, "max_context_chars": 16000}

        first = maybe_compress_session_history(
            service=provider,
            session_id=self.session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5:3b",
            settings=settings,
        )
        oldest = db.get_messages_before_latest(self.session["id"], keep_pairs=1)[0]
        db.update_message(oldest["id"], content="edited-source-content")
        second = maybe_compress_session_history(
            service=provider,
            session_id=self.session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5:3b",
            settings=settings,
        )

        self.assertEqual(provider.chat_completion.call_count, 2)
        self.assertNotEqual(first["source_id"], second["source_id"])
        self.assertEqual(second["summary"], "edited snapshot")

    def test_prompt_uses_only_current_chat_summary_snapshot(self) -> None:
        for number in range(1, 7):
            self._completed_turn(number)
        provider = Mock()
        provider.chat_completion.side_effect = ["obsolete summary", "current summary"]
        settings = {"summary_memory_enabled": True, "mem_turns": 2, "max_context_chars": 16000}
        maybe_compress_session_history(
            service=provider,
            session_id=self.session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5:3b",
            settings=settings,
        )
        db.add_message(self.session["id"], "user", "eligible-user-7")
        db.add_message(self.session["id"], "assistant", "eligible-assistant-7")
        maybe_compress_session_history(
            service=provider,
            session_id=self.session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5:3b",
            settings=settings,
        )
        db.update_profile_preferences(
            self.profile_id,
            {"settings": {"mem_turns": 2, "summary_memory_enabled": True, "summary_memory_limit": 5}},
        )

        prepared = _prepare_chat_request(
            ChatRequest(
                query="continue",
                profile_id=self.profile_id,
                session_id=self.session["id"],
                model_name="qwen2.5:3b",
            )
        )
        memory_text = "\n".join(
            item["content"] for item in prepared["messages"] if "source=summary_memory" in item["content"]
        )
        self.assertIn("current summary", memory_text)
        self.assertNotIn("obsolete summary", memory_text)

        db.update_profile_preferences(self.profile_id, {"settings": {"mem_turns": 1}})
        changed_boundary = _prepare_chat_request(
            ChatRequest(
                query="continue after boundary change",
                profile_id=self.profile_id,
                session_id=self.session["id"],
                model_name="qwen2.5:3b",
            )
        )
        self.assertFalse(
            any("source=summary_memory" in item["content"] for item in changed_boundary["messages"])
        )

    def test_summary_truncation_keeps_complete_messages_and_records_snapshot_metadata(self) -> None:
        for number in range(1, 6):
            self._completed_turn(number)
        provider = Mock()
        provider.chat_completion.return_value = "bounded summary"

        result = maybe_compress_session_history(
            service=provider,
            session_id=self.session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5:3b",
            settings={"summary_memory_enabled": True, "mem_turns": 1, "max_context_chars": 80},
        )

        summary_request = provider.chat_completion.call_args.args[1][-1]["content"]
        self.assertNotIn("eligible-user-2", summary_request)
        self.assertIn("eligible-user-1", summary_request)
        self.assertIn("eligible-assistant-1", summary_request)
        self.assertEqual(result["structured_json"]["source_message_count"], 8)
        self.assertEqual(result["structured_json"]["summarized_message_count"], 2)
        self.assertTrue(result["structured_json"]["truncated"])

    def test_summary_snapshot_identity_changes_with_effective_context_budget(self) -> None:
        for number in range(1, 6):
            self._completed_turn(number)
        provider = Mock()
        provider.chat_completion.side_effect = ["bounded summary", "full summary"]

        bounded = maybe_compress_session_history(
            service=provider,
            session_id=self.session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5:3b",
            settings={"summary_memory_enabled": True, "mem_turns": 1, "max_context_chars": 80},
        )
        full = maybe_compress_session_history(
            service=provider,
            session_id=self.session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5:3b",
            settings={"summary_memory_enabled": True, "mem_turns": 1, "max_context_chars": 16000},
        )

        self.assertEqual(provider.chat_completion.call_count, 2)
        self.assertNotEqual(bounded["source_id"], full["source_id"])
        self.assertTrue(bounded["structured_json"]["truncated"])
        self.assertFalse(full["structured_json"]["truncated"])

    def test_current_summary_is_selected_even_when_more_than_100_rows_are_newer(self) -> None:
        for number in range(1, 6):
            self._completed_turn(number)
        provider = Mock()
        provider.chat_completion.return_value = "current chat snapshot"
        current = maybe_compress_session_history(
            service=provider,
            session_id=self.session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5:3b",
            settings={"summary_memory_enabled": True, "mem_turns": 1, "max_context_chars": 16000},
        )
        for index in range(105):
            db.create_session_summary(
                profile_id=self.profile_id,
                session_id=self.session["id"],
                source_type="asr",
                source_id=f"transcript-{index}",
                summary=f"newer summary {index}",
            )

        selected = current_session_summary_memory(
            self.session["id"],
            mem_turns=1,
            max_context_chars=16000,
            limit=5,
        )

        self.assertIn(current["source_id"], {item["source_id"] for item in selected})


if __name__ == "__main__":
    unittest.main()
