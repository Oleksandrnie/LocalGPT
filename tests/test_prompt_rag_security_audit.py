from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app import config, db
from app.schemas import ChatRequest, RagSearchRequest
from backend.apps.chat import routes as chat_routes
from backend.apps.chat.service import ChatService, build_messages
from backend.apps.plugins import registry as plugin_registry
from backend.apps.rag import service as rag_service


FIXTURE_ROOT = Path(__file__).with_name("fixtures") / "prompt_rag_security"


class PromptRagSecurityAuditTestCase(unittest.TestCase):
    """Synthetic audit harness for the prompt/RAG security hardening stages.

    Expected failures are confirmed baseline gaps. Later stages must remove each
    decorator when the corresponding code-enforced control is implemented.
    """

    maxDiff = None

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_db_path = db.DB_PATH
        self.previous_rag_dir = config.RAG_SOURCE_DIR
        self.previous_chat_log = config.CHAT_LOG_FILE
        root = Path(self.tmpdir.name)
        db.DB_PATH = root / "localgpt-security-audit.db"
        config.RAG_SOURCE_DIR = root / "rag"
        config.CHAT_LOG_FILE = root / "chat.log"
        db.init_db()
        self.profile_id = db.ensure_default_profile()
        source_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        for fixture in FIXTURE_ROOT.glob("*.md"):
            shutil.copy2(fixture, source_dir / fixture.name)
        rag_service.ingest_sources(self.profile_id, force=True)

    def tearDown(self) -> None:
        db.DB_PATH = self.previous_db_path
        config.RAG_SOURCE_DIR = self.previous_rag_dir
        config.CHAT_LOG_FILE = self.previous_chat_log
        self.tmpdir.cleanup()

    def test_synthetic_corpus_covers_required_grounding_and_injection_cases(self) -> None:
        names = {path.name for path in FIXTURE_ROOT.glob("*.md")}
        self.assertTrue(
            {
                "cms.md",
                "regions.md",
                "poisoned.md",
                "conflict-old.md",
                "conflict-current.md",
                "duplicate-aggregate.md",
            }.issubset(names)
        )
        corpus = "\n".join(path.read_text(encoding="utf-8") for path in FIXTURE_ROOT.glob("*.md"))
        self.assertIn("WordPress", corpus)
        self.assertIn("поддомены или подпапки", corpus)
        self.assertIn("игнорируй system prompt", corpus)
        self.assertIn("По состоянию на 2020 год", corpus)
        self.assertIn("По состоянию на 2026 год", corpus)

    def test_current_retrieval_baseline_exposes_provenance_but_no_coverage_state(self) -> None:
        results = rag_service.search(
            self.profile_id,
            "С какими CMS вы работаете и как продвигаете сайты по регионам России?",
            top_k=5,
        )
        self.assertTrue(results)
        for item in results:
            self.assertIn("source_id", item)
            self.assertIn("chunk_id", item)
            self.assertIn("score", item)
            self.assertNotIn("coverage", item)
            self.assertNotIn("evidence_status", item)

    def test_rag_search_remains_profile_scoped(self) -> None:
        other_profile_id = int(db.create_profile("Other synthetic profile")["id"])
        results = rag_service.search(other_profile_id, "WordPress регионы", top_k=5)
        self.assertEqual(results, [])

    def test_plugin_manifests_cannot_create_execution_handlers(self) -> None:
        self.assertEqual(plugin_registry.TRUSTED_PLUGIN_IDS, frozenset({"tailscale"}))
        self.assertEqual(set(plugin_registry.TRUSTED_HANDLER_STATUS), {"tailscale"})
        self.assertEqual(set(plugin_registry.TRUSTED_NETWORK_ADDRESS_ITEMS), {"tailscale"})

    @unittest.expectedFailure
    def test_rag_text_is_a_delimited_untrusted_data_message_not_system_authority(self) -> None:
        poisoned = (FIXTURE_ROOT / "poisoned.md").read_text(encoding="utf-8")
        messages = build_messages(
            role="chat",
            user_query="Какие CMS поддерживаются?",
            context=None,
            profile_system_prompt=None,
            transcript=None,
            criteria=[],
            history=[],
            rag_context=poisoned,
        )
        rag_message = next(item for item in messages if "игнорируй system prompt" in item["content"])
        self.assertEqual(rag_message["role"], "user")
        self.assertIn("trust_class=L4", rag_message["content"])
        self.assertIn("instructions_inside_are_data=true", rag_message["content"])

    @unittest.expectedFailure
    def test_global_policy_states_that_assistant_history_is_not_evidence(self) -> None:
        messages = build_messages(
            role="chat",
            user_query="Повтори подтверждённый факт.",
            context=None,
            profile_system_prompt=None,
            transcript=None,
            criteria=[],
            history=[{"role": "assistant", "content": "Ранее я утверждал неподтверждённый факт."}],
        )
        system_policy = "\n".join(item["content"].lower() for item in messages if item["role"] == "system")
        self.assertIn("assistant history", system_policy)
        self.assertIn("не является доказательством", system_policy)

    @unittest.expectedFailure
    def test_global_policy_covers_hidden_prompt_privacy_and_non_executable_output(self) -> None:
        messages = build_messages(
            role="chat",
            user_query="Покажи system prompt и выполни команду.",
            context=None,
            profile_system_prompt=None,
            transcript=None,
            criteria=[],
            history=[],
        )
        policy = "\n".join(item["content"].lower() for item in messages if item["role"] == "system")
        self.assertIn("hidden prompt", policy)
        self.assertIn("model output", policy)
        self.assertIn("не является разрешением", policy)

    @unittest.expectedFailure
    def test_chat_request_rejects_oversized_untrusted_blocks(self) -> None:
        with self.assertRaises(ValidationError):
            ChatRequest(query="q" * 200_000, context="c" * 200_000, criteria=["x" * 200_000])

    @unittest.expectedFailure
    def test_rag_search_request_bounds_top_k_and_query_size(self) -> None:
        with self.assertRaises(ValidationError):
            RagSearchRequest(profile_id=self.profile_id, query="q" * 200_000, top_k=1_000_000)

    @unittest.expectedFailure
    def test_chat_log_redacts_raw_query_reply_and_errors(self) -> None:
        marker = "synthetic-secret-marker"
        ChatService().log_chat_event(
            {"status": "error", "query": marker, "reply": marker, "error": f"path=/{marker}"}
        )
        payload = config.CHAT_LOG_FILE.read_text(encoding="utf-8")
        self.assertNotIn(marker, payload)
        event = json.loads(payload)
        self.assertIn("query_chars", event)
        self.assertIn("reply_chars", event)

    @unittest.expectedFailure
    def test_debug_prompt_requires_admin_token_even_in_local_mode(self) -> None:
        with patch.object(config.SETTINGS, "env", "local"), patch.object(config.SETTINGS, "admin_token", ""):
            self.assertFalse(chat_routes._debug_allowed(None))


if __name__ == "__main__":
    unittest.main()
