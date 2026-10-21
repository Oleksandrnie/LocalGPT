from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import config, db
from app.schemas import ChatRequest
from backend.apps.chat import routes as chat_routes
from backend.apps.chat.service import assess_rag_answer
from backend.apps.chat.services.ollama_runtime import ChatCompletionResult
from backend.apps.rag import service as rag_service


class ChatRagAnswerQualityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_db_path = db.DB_PATH
        self.previous_rag_dir = config.RAG_SOURCE_DIR
        root = Path(self.tmpdir.name)
        db.DB_PATH = root / "rag-answer-quality.db"
        config.RAG_SOURCE_DIR = root / "rag"
        db.init_db()
        self.profile_id = db.ensure_default_profile()
        db.update_profile_preferences(
            self.profile_id,
            {
                "chat": {"system_prompt": "Use concise bullet points when listing sourced facts."},
                "settings": {"rag_enabled": True, "mem_turns": 2},
            },
        )

    def tearDown(self) -> None:
        db.DB_PATH = self.previous_db_path
        config.RAG_SOURCE_DIR = self.previous_rag_dir
        self.tmpdir.cleanup()

    def _ingest(self, name: str, content: str) -> None:
        source_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        (source_dir / name).write_text(content, encoding="utf-8")
        rag_service.ingest_sources(self.profile_id, force=True)

    def test_retrieved_cross_domain_evidence_reaches_actual_completion_messages(self) -> None:
        cases = (
            ("library.md", "The North Library closes at 19:40 on Thursday.", "When does North Library close Thursday?", "19:40"),
            ("microgrid.md", "Battery inspection code is MG-4821 and occurs each Tuesday.", "What is the battery inspection code?", "MG-4821"),
        )
        for source_name, source_text, query, marker in cases:
            with self.subTest(source=source_name):
                self._ingest(source_name, source_text)
                captured: list[dict[str, str]] = []

                def complete(_model: str, messages: list[dict[str, str]], *, settings: dict) -> ChatCompletionResult:
                    captured.extend(messages)
                    return ChatCompletionResult(content=f"- {marker}")

                with (
                    patch.object(chat_routes, "_ensure_chat_model_available"),
                    patch.object(chat_routes.chat_service, "chat_completion_result", side_effect=complete),
                ):
                    response = chat_routes.chat(
                        ChatRequest(query=query, profile_id=self.profile_id, model_name="qwen2.5:3b")
                    )

                rag_message = next(item for item in captured if "source=rag_context" in item["content"])
                self.assertIn(marker, rag_message["content"])
                self.assertIn("Use concise bullet points", str(captured))
                self.assertEqual(response["rag_answer_diagnostics"]["retrieval_status"], "supported")
                self.assertEqual(response["rag_answer_diagnostics"]["answer_status"], "evidence_traceable")

    def test_not_found_is_distinct_from_found_but_untraceable_answer(self) -> None:
        missing = assess_rag_answer(
            "The answer is unavailable.",
            [],
            {"overall_status": "not_found", "facet_coverage": []},
        )
        ignored = assess_rag_answer(
            "I prefer not to discuss maintenance schedules.",
            [{"source_id": "maintenance.md", "chunk_id": 7, "content": "Turbine inspection occurs every 17 days."}],
            {"overall_status": "supported", "facet_coverage": []},
        )

        self.assertEqual(missing["answer_status"], "evidence_not_found")
        self.assertEqual(ignored["answer_status"], "evidence_found_answer_not_traceable")
        self.assertEqual(ignored["source_ids"], ["maintenance.md"])
        self.assertEqual(ignored["chunk_ids"], [7])

    def test_answer_trace_uses_included_evidence_even_when_facet_diagnostic_is_not_found(self) -> None:
        manifest = [
            {
                "source_id": "greenhouse-irrigation.md",
                "chunk_id": 19,
                "content": "Orchids are watered every four days.",
            }
        ]
        diagnostics = {"overall_status": "not_found", "facet_coverage": []}

        traceable = assess_rag_answer("Orchids need water every four days.", manifest, diagnostics)
        unrelated = assess_rag_answer("I cannot answer that question.", manifest, diagnostics)

        self.assertEqual(traceable["retrieval_status"], "not_found")
        self.assertEqual(traceable["answer_status"], "evidence_traceable")
        self.assertEqual(unrelated["retrieval_status"], "not_found")
        self.assertEqual(unrelated["answer_status"], "evidence_found_answer_not_traceable")

    def test_source_filename_does_not_make_unrelated_answer_traceable(self) -> None:
        chunks = [
            {
                "source_id": "maintenance.md",
                "chunk_id": 7,
                "chunk_index": 0,
                "score": 1.0,
                "evidence_status": "supported",
                "content": "Turbine inspection occurs every 17 days.",
                "document_metadata": {},
                "provenance": {"source_id": "maintenance.md", "chunk_id": 7, "chunk_index": 0},
            }
        ]
        diagnostics = {"overall_status": "supported", "facet_coverage": [], "selected_chunks": 1}

        with (
            patch.object(
                chat_routes.rag_service,
                "search_with_diagnostics",
                return_value={"results": chunks, "diagnostics": diagnostics},
            ),
            patch.object(chat_routes, "_ensure_chat_model_available"),
            patch.object(
                chat_routes.chat_service,
                "chat_completion_result",
                return_value=ChatCompletionResult(content="Maintenance schedules are unavailable."),
            ),
        ):
            response = chat_routes.chat(
                ChatRequest(
                    query="What is the inspection interval?",
                    profile_id=self.profile_id,
                    model_name="qwen2.5:3b",
                )
            )

        trace = response["rag_answer_diagnostics"]
        self.assertEqual(trace["answer_status"], "evidence_found_answer_not_traceable")
        self.assertEqual(trace["source_ids"], ["maintenance.md"])
        self.assertEqual(trace["chunk_ids"], [7])

    def test_no_evidence_phrase_does_not_match_service_rules(self) -> None:
        chunks = [
            {
                "source_id": "oversized.md",
                "chunk_id": 9,
                "chunk_index": 0,
                "score": 1.0,
                "evidence_status": "supported",
                "content": "A source fact that cannot fit behind its oversized provenance header.",
                "document_metadata": {},
                "provenance": {
                    "source_id": "oversized.md",
                    "chunk_id": 9,
                    "chunk_index": 0,
                    "note": "z" * 5000,
                },
            }
        ]
        diagnostics = {"overall_status": "supported", "facet_coverage": [], "selected_chunks": 1}
        db.update_profile_preferences(self.profile_id, {"settings": {"rag_max_context_chars": 500}})

        with (
            patch.object(
                chat_routes.rag_service,
                "search_with_diagnostics",
                return_value={"results": chunks, "diagnostics": diagnostics},
            ),
            patch.object(chat_routes, "_ensure_chat_model_available"),
            patch.object(
                chat_routes.chat_service,
                "chat_completion_result",
                return_value=ChatCompletionResult(content="No evidence was found."),
            ),
        ):
            response = chat_routes.chat(
                ChatRequest(
                    query="Can you find the source fact?",
                    profile_id=self.profile_id,
                    model_name="qwen2.5:3b",
                )
            )

        trace = response["rag_answer_diagnostics"]
        self.assertEqual(trace["retrieval_status"], "supported")
        self.assertEqual(trace["answer_status"], "evidence_not_found")
        self.assertEqual(trace["source_ids"], [])
        self.assertEqual(trace["chunk_ids"], [])
        self.assertEqual(trace["matched_term_count"], 0)

    def test_manifest_excludes_omitted_chunk_with_the_same_source_id(self) -> None:
        omitted_marker = "OMITTED-CHUNK-99117"
        chunks = [
            {
                "source_id": "shared.md",
                "chunk_id": 1,
                "chunk_index": 0,
                "score": 1.0,
                "evidence_status": "supported",
                "content": "Included turbine interval is 17 days. " + ("x" * 400),
                "document_metadata": {},
                "provenance": {"source_id": "shared.md", "chunk_id": 1, "chunk_index": 0},
            },
            {
                "source_id": "shared.md",
                "chunk_id": 2,
                "chunk_index": 1,
                "score": 0.9,
                "evidence_status": "supported",
                "content": f"This second chunk contains {omitted_marker}.",
                "document_metadata": {},
                "provenance": {
                    "source_id": "shared.md",
                    "chunk_id": 2,
                    "chunk_index": 1,
                    "note": "z" * 1000,
                },
            },
        ]
        diagnostics = {"overall_status": "supported", "facet_coverage": [], "selected_chunks": 2}

        snapshot = rag_service.build_context_snapshot(chunks, max_chars=1000, diagnostics=diagnostics)
        manifest = snapshot["evidence_manifest"]
        trace = assess_rag_answer(omitted_marker, manifest, diagnostics)

        self.assertNotIn(omitted_marker, snapshot["context"])
        self.assertEqual([item["chunk_id"] for item in manifest], [1])
        self.assertEqual(trace["answer_status"], "evidence_found_answer_not_traceable")
        self.assertEqual(trace["source_ids"], ["shared.md"])
        self.assertEqual(trace["chunk_ids"], [1])

    def test_answer_trace_excludes_retrieved_tail_that_was_not_sent_to_model(self) -> None:
        tail_marker = "UNSENT-TAIL-MARKER-99117"
        chunks = [
            {
                "source_id": "bounded.md",
                "chunk_id": 17,
                "chunk_index": 0,
                "score": 1.0,
                "evidence_status": "supported",
                "content": "visible evidence " + ("x" * 1800) + " " + tail_marker,
                "document_metadata": {},
                "provenance": {"source_id": "bounded.md", "chunk_id": 17, "chunk_index": 0},
            }
        ]
        diagnostics = {"overall_status": "supported", "facet_coverage": [], "selected_chunks": 1}
        db.update_profile_preferences(self.profile_id, {"settings": {"rag_max_context_chars": 1000}})
        captured: list[dict[str, str]] = []

        def complete(_model: str, messages: list[dict[str, str]], *, settings: dict) -> ChatCompletionResult:
            captured.extend(messages)
            return ChatCompletionResult(content=tail_marker)

        with (
            patch.object(
                chat_routes.rag_service,
                "search_with_diagnostics",
                return_value={"results": chunks, "diagnostics": diagnostics},
            ),
            patch.object(chat_routes, "_ensure_chat_model_available"),
            patch.object(chat_routes.chat_service, "chat_completion_result", side_effect=complete),
        ):
            response = chat_routes.chat(
                ChatRequest(query="What is the bounded marker?", profile_id=self.profile_id, model_name="qwen2.5:3b")
            )

        self.assertNotIn(tail_marker, "\n".join(item["content"] for item in captured))
        self.assertEqual(
            response["rag_answer_diagnostics"]["answer_status"],
            "evidence_found_answer_not_traceable",
        )

    def test_task_worker_receives_the_same_evidence_snapshot_for_post_answer_trace(self) -> None:
        self._ingest("warehouse.md", "Warehouse seal identifier is WH-7719.")
        captured: dict = {}

        def start(**kwargs):
            captured.update(kwargs)
            return {"id": "synthetic-task", "state": "generating"}

        with (
            patch.object(chat_routes, "_ensure_chat_model_available"),
            patch.object(chat_routes.chat_tasks, "start_chat_task", side_effect=start),
        ):
            response = chat_routes.start_chat_task(
                ChatRequest(
                    query="What is the warehouse seal identifier?",
                    profile_id=self.profile_id,
                    model_name="qwen2.5:3b",
                )
            )

        self.assertEqual(response["id"], "synthetic-task")
        self.assertTrue(captured["rag_evidence_manifest"])
        self.assertEqual(captured["rag_diagnostics"]["overall_status"], "supported")
        self.assertTrue(any("WH-7719" in item["content"] for item in captured["rag_evidence_manifest"]))
        self.assertTrue(any("WH-7719" in item["content"] for item in captured["messages"]))

    def test_followup_keeps_completed_turn_and_retrieves_prior_topic_evidence(self) -> None:
        self._ingest(
            "observatory.md",
            "The observatory calibrates the spectrograph every 17 days. The calibration owner is Mira Chen.",
        )
        session = db.create_session(self.profile_id, "Observatory", "qwen2.5:3b")
        db.add_message(session["id"], "user", "How often is the spectrograph calibrated?")
        db.add_message(session["id"], "assistant", "It is calibrated every 17 days.")

        prepared = chat_routes._prepare_chat_request(
            ChatRequest(
                query="And who owns it?",
                profile_id=self.profile_id,
                session_id=session["id"],
                model_name="qwen2.5:3b",
            )
        )

        self.assertIn("Mira Chen", prepared["rag_context"])
        self.assertEqual(prepared["recent_user_queries"], ["How often is the spectrograph calibrated?"])
        self.assertTrue(any("source=chat_history" in item["content"] for item in prepared["messages"]))
        self.assertTrue(any("Use concise bullet points" in item["content"] for item in prepared["messages"]))


if __name__ == "__main__":
    unittest.main()
