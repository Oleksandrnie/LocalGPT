from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import config, db
from backend.apps.rag import embeddings
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


if __name__ == "__main__":
    unittest.main()
