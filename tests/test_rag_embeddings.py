from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import config, db
from app.schemas import RagReindexRequest
from backend.apps.rag import embeddings
from backend.apps.rag import reindex_tasks
from backend.apps.rag import routes as rag_routes
from backend.apps.rag import service as rag_service


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class _StubProvider:
    descriptor = embeddings.EmbeddingDescriptor(
        provider="stub",
        model="multilingual-test",
        version="v2",
        dimensions=3,
        storage_key="stub/multilingual-test/v2/3",
    )

    def __init__(self) -> None:
        self.release_calls: list[bool] = []

    def embed(self, texts: list[str], *, release: bool = True) -> list[list[float]]:
        self.release_calls.append(release)
        return [[1.0, float(len(text) % 7), 0.5] for text in texts]


def _wait_for_task(task_id: str, profile_id: int, timeout: float = 2.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        task = reindex_tasks.get_reindex_task(task_id, profile_id)
        if task and task.get("status") in {"completed", "failed"}:
            return task
        time.sleep(0.01)
    raise AssertionError("reindex task did not reach a terminal state")


class RagEmbeddingProviderTestCase(unittest.TestCase):
    def test_local_hash_keeps_legacy_generation_contract(self) -> None:
        provider = embeddings.LocalHashEmbeddingProvider()

        first = provider.embed(["Пример multilingual text"])[0]
        second = provider.embed(["Пример multilingual text"])[0]

        self.assertEqual(provider.descriptor.storage_key, "local-hash-v1")
        self.assertEqual(provider.descriptor.dimensions, 256)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 256)

    def test_ollama_provider_sends_versioned_bounded_request_and_releases_model(self) -> None:
        provider = embeddings.OllamaEmbeddingProvider(
            base_url="http://localhost:11434/v1",
            model="embeddinggemma:latest",
            version="embeddinggemma-300m-v1",
            dimensions=3,
        )
        captured: dict[str, object] = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["timeout"] = timeout
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return _Response({"embeddings": [[0.1, 0.2, 0.3]]})

        with patch.object(embeddings.request, "urlopen", side_effect=fake_urlopen):
            vectors = provider.embed(["тест"])

        self.assertEqual(vectors, [[0.1, 0.2, 0.3]])
        self.assertEqual(captured["url"], "http://localhost:11434/api/embed")
        self.assertEqual(captured["payload"]["truncate"], False)
        self.assertEqual(captured["payload"]["dimensions"], 3)
        self.assertEqual(captured["payload"]["keep_alive"], "0")

    def test_ollama_provider_rejects_incompatible_vectors_without_fallback(self) -> None:
        provider = embeddings.OllamaEmbeddingProvider(
            base_url="http://localhost:11434",
            model="embeddinggemma:latest",
            version="v1",
            dimensions=3,
        )
        with patch.object(
            embeddings.request,
            "urlopen",
            return_value=_Response({"embeddings": [[0.1, 0.2]]}),
        ):
            with self.assertRaisesRegex(embeddings.EmbeddingProviderError, "dimension_mismatch"):
                provider.embed(["test"])


class RagEmbeddingGenerationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        reindex_tasks._reset_for_tests()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_db_path = db.DB_PATH
        self.previous_rag_dir = config.RAG_SOURCE_DIR
        db.DB_PATH = Path(self.tmpdir.name) / "localgpt-embeddings.db"
        config.RAG_SOURCE_DIR = Path(self.tmpdir.name) / "rag"
        db.init_db()
        self.profile_id = db.ensure_default_profile()
        source_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        (source_dir / "one.md").write_text("Семантический факт о северном сиянии.", encoding="utf-8")
        (source_dir / "two.md").write_text("Другая заметка о музейном архиве.", encoding="utf-8")
        self.hash_provider = embeddings.LocalHashEmbeddingProvider()
        with patch.object(rag_service, "_embedding_provider", return_value=self.hash_provider):
            rag_service.ingest_sources(self.profile_id, force=True)

    def tearDown(self) -> None:
        reindex_tasks._reset_for_tests()
        db.DB_PATH = self.previous_db_path
        config.RAG_SOURCE_DIR = self.previous_rag_dir
        self.tmpdir.cleanup()

    def test_new_generation_requires_explicit_reindex_and_preserves_rollback(self) -> None:
        provider = _StubProvider()
        with patch.object(rag_service, "_embedding_provider", return_value=provider):
            with self.assertRaises(HTTPException) as stale:
                rag_service.search(self.profile_id, "полярное свечение")
        self.assertEqual(stale.exception.status_code, 409)
        self.assertIn("rag_embedding_reindex_required", str(stale.exception.detail))
        provider.release_calls.clear()

        with patch.object(rag_service, "_embedding_provider", return_value=provider):
            ordinary_ingest = rag_service.ingest_sources(self.profile_id, force=True)
        self.assertEqual(ordinary_ingest["reindex_required"], 2)
        self.assertEqual(len(db.list_rag_chunks(self.profile_id, "local-hash-v1")), 2)
        self.assertEqual(db.list_rag_chunks(self.profile_id, provider.descriptor.storage_key), [])

        with patch.object(config.SETTINGS, "rag_embedding_batch_size", 1):
            result = rag_service.reindex_embeddings(self.profile_id, provider=provider)

        self.assertEqual(result["chunks_reindexed"], 2)
        self.assertEqual(provider.release_calls, [False, True])
        self.assertEqual(len(db.list_rag_chunks(self.profile_id, "local-hash-v1")), 2)
        self.assertEqual(len(db.list_rag_chunks(self.profile_id, provider.descriptor.storage_key)), 2)

        with patch.object(rag_service, "_embedding_provider", return_value=provider):
            semantic_results = rag_service.search(self.profile_id, "полярное свечение", strategy="legacy")
        self.assertTrue(semantic_results)

        with patch.object(rag_service, "_embedding_provider", return_value=self.hash_provider):
            rollback_results = rag_service.search(self.profile_id, "северном сиянии", strategy="legacy")
        self.assertTrue(rollback_results)

    def test_provider_failure_is_explicit_and_does_not_replace_generation(self) -> None:
        provider = _StubProvider()

        def fail(_texts: list[str], *, release: bool = True) -> list[list[float]]:
            del release
            raise embeddings.EmbeddingProviderError("model_unavailable")

        provider.embed = fail  # type: ignore[method-assign]
        with self.assertRaises(HTTPException) as failed:
            rag_service.reindex_embeddings(self.profile_id, provider=provider)

        self.assertEqual(failed.exception.status_code, 503)
        self.assertEqual(len(db.list_rag_chunks(self.profile_id, "local-hash-v1")), 2)
        self.assertEqual(db.list_rag_chunks(self.profile_id, provider.descriptor.storage_key), [])

    def test_status_distinguishes_source_ingest_and_generation_reindex(self) -> None:
        ready = rag_service.status(self.profile_id)
        self.assertEqual(ready["embedding_generation"]["status"], "ready")
        self.assertEqual(ready["embedding_generation"]["total_chunks"], 2)
        self.assertEqual(ready["embedding_generation"]["indexed_chunks"], 2)

        provider = _StubProvider()
        with patch.object(rag_service, "_embedding_provider", return_value=provider):
            stale_generation = rag_service.status(self.profile_id)
        self.assertEqual(stale_generation["embedding_generation"]["status"], "reindex_required")
        self.assertEqual(stale_generation["embedding_generation"]["missing_chunks"], 2)
        self.assertEqual(
            stale_generation["embedding_generation"]["available_generations"][0]["embedding_model"],
            "local-hash-v1",
        )

        source_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        (source_dir / "one.md").write_text("Изменённый факт без скрытой индексации.", encoding="utf-8")
        changed_source = rag_service.status(self.profile_id)
        self.assertEqual(changed_source["embedding_generation"]["status"], "ingest_required")
        self.assertEqual(changed_source["embedding_generation"]["pending_sources"], 1)

    def test_status_redacts_embedding_configuration_failure(self) -> None:
        with patch.object(
            rag_service,
            "_embedding_provider",
            side_effect=HTTPException(
                status_code=503,
                detail="rag_embedding_configuration_error:private-provider-marker",
            ),
        ):
            status = rag_service.status(self.profile_id)

        generation = status["embedding_generation"]
        self.assertEqual(generation["status"], "configuration_error")
        self.assertEqual(generation["error_code"], "rag_embedding_configuration_error")
        self.assertIsNone(status["embedding"])
        self.assertNotIn("private-provider-marker", json.dumps(status))

    def test_background_reindex_reports_progress_and_enforces_profile_ownership(self) -> None:
        provider = _StubProvider()
        other_profile = db.create_profile("Other")
        with patch.object(rag_service, "_embedding_provider", return_value=provider):
            started = reindex_tasks.start_reindex(self.profile_id)
        task = _wait_for_task(str(started["task_id"]), self.profile_id)

        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["processed_chunks"], 2)
        self.assertEqual(task["total_chunks"], 2)
        self.assertIsNone(reindex_tasks.get_reindex_task(str(started["task_id"]), int(other_profile["id"])))
        self.assertEqual(len(db.list_rag_chunks(self.profile_id, provider.descriptor.storage_key)), 2)

    def test_reindex_routes_expose_latest_profile_owned_operation(self) -> None:
        provider = _StubProvider()
        other_profile = db.create_profile("Route isolation")
        with patch.object(rag_service, "_embedding_provider", return_value=provider):
            started = rag_routes.rag_reindex(RagReindexRequest(profile_id=self.profile_id))
            task = _wait_for_task(str(started["task_id"]), self.profile_id)
            status = rag_routes.rag_status(profile_id=self.profile_id, session_id=None)

        self.assertEqual(task["status"], "completed")
        self.assertEqual(
            status["embedding_generation"]["operation"]["task_id"],
            started["task_id"],
        )
        with self.assertRaises(HTTPException) as hidden:
            rag_routes.rag_reindex_status(
                str(started["task_id"]),
                profile_id=int(other_profile["id"]),
            )
        self.assertEqual(hidden.exception.status_code, 404)

    def test_background_reindex_redacts_provider_failure_and_rejects_overlap(self) -> None:
        provider = _StubProvider()
        other_profile = db.create_profile("Global task guard")
        entered = threading.Event()
        release_gate = threading.Event()

        def blocked(_texts: list[str], *, release: bool = True) -> list[list[float]]:
            del release
            entered.set()
            if not release_gate.wait(timeout=2):
                raise embeddings.EmbeddingProviderError("timeout-sensitive-marker")
            raise embeddings.EmbeddingProviderError("private-provider-marker")

        provider.embed = blocked  # type: ignore[method-assign]
        with patch.object(rag_service, "_embedding_provider", return_value=provider):
            started = reindex_tasks.start_reindex(self.profile_id)
            self.assertTrue(entered.wait(timeout=1))
            with self.assertRaises(HTTPException) as overlap:
                reindex_tasks.start_reindex(int(other_profile["id"]))
        self.assertEqual(overlap.exception.status_code, 409)
        release_gate.set()
        task = _wait_for_task(str(started["task_id"]), self.profile_id)

        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error_code"], "rag_embedding_provider_unavailable")
        self.assertNotIn("private-provider-marker", json.dumps(task))
        self.assertEqual(len(db.list_rag_chunks(self.profile_id, "local-hash-v1")), 2)

    def test_atomic_generation_publish_rejects_changed_chunk_set(self) -> None:
        provider = _StubProvider()
        rag_service.reindex_embeddings(self.profile_id, provider=provider)
        existing = db.list_rag_chunks(self.profile_id, provider.descriptor.storage_key)
        document = db.create_source_document(
            profile_id=self.profile_id,
            session_id=None,
            source_type="manual_file",
            source_id="late.md",
            title="late.md",
            content=None,
            metadata={},
        )
        db.create_document_chunk(
            document_id=int(document["id"]),
            profile_id=self.profile_id,
            session_id=None,
            chunk_index=0,
            content="Поздно добавленный chunk.",
            metadata={},
        )
        rows = [
            {
                "chunk_id": int(item["chunk_id"]),
                "embedding": item["embedding"],
                "metadata": item["embedding_metadata"],
            }
            for item in existing
        ]

        with self.assertRaisesRegex(ValueError, "rag_embedding_source_changed"):
            db.replace_embedding_generation(self.profile_id, provider.descriptor.storage_key, rows)
        self.assertEqual(len(db.list_rag_chunks(self.profile_id, provider.descriptor.storage_key)), 2)


if __name__ == "__main__":
    unittest.main()
