from __future__ import annotations

import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.apps.rag import embeddings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "tools" / "rag_retrieval_eval.py"
SPEC = importlib.util.spec_from_file_location("rag_retrieval_eval", SCRIPT_PATH)
assert SPEC and SPEC.loader
rag_eval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rag_eval)


class _FixtureSemanticProvider:
    descriptor = embeddings.EmbeddingDescriptor(
        provider="fixture_semantic",
        model="cross-domain-contract",
        version="v1",
        dimensions=6,
        storage_key="fixture-semantic/cross-domain-contract/v1/6",
    )
    concepts = (
        ("borrow", "collection books", "calendar days", "checked out"),
        ("spectr", "analyser", "analyzer", "calibrat", "reference gas", "argon"),
        ("damaged", "broken shipment", "parcels", "quarantine", "inspection", "examination", "q-17"),
        ("основн", "резервн", "батаре", "аккумулятор", "тридцат", "уровн"),
        ("орх", "поить", "воду", "орошен"),
        ("textile", "humidity", "fibre", "2022", "2026"),
    )

    def embed(self, texts: list[str], *, release: bool = True) -> list[list[float]]:
        del release
        vectors: list[list[float]] = []
        for text in texts:
            lowered = str(text or "").lower()
            vector = [1.0 if any(marker in lowered for marker in markers) else 0.0 for markers in self.concepts]
            norm = math.sqrt(sum(value * value for value in vector))
            vectors.append(vector if norm == 0 else [value / norm for value in vector])
        return vectors


class RagRetrievalEvalTestCase(unittest.TestCase):
    def test_report_is_metadata_only_and_exposes_current_baseline_gaps(self) -> None:
        report = rag_eval.evaluate_fixture()

        self.assertEqual(report["schema"], "localgpt.rag_retrieval_eval_report.v1")
        self.assertTrue(report["preview_only"])
        self.assertTrue(report["metadata_only"])
        self.assertEqual(report["embedding_model"], "local-hash-v1")
        self.assertEqual(report["summary"]["total_cases"], 10)
        self.assertGreater(report["summary"]["positive"]["recall_at_k"], 0.0)
        self.assertLess(report["summary"]["positive"]["recall_at_k"], 1.0)
        self.assertIn("ndcg_at_k", report["summary"]["positive"])
        self.assertIn("ideal_ranked_hit_rate", report["summary"]["positive"])
        self.assertLess(
            report["summary"]["positive"]["grounded_hit_rate"],
            report["summary"]["positive"]["full_hit_rate"],
        )
        self.assertGreaterEqual(report["summary"]["negative_rejection_rate"], 0.5)
        serialized = json.dumps(report, ensure_ascii=False).lower()
        self.assertNotIn("spacesuit", serialized.lower())
        self.assertNotIn("borrowed", serialized.lower())
        self.assertTrue(all("query" not in row and "content" not in row for row in report["cases"]))

    def test_eval_is_deterministic_except_for_resource_observation(self) -> None:
        first = rag_eval.evaluate_fixture()
        second = rag_eval.evaluate_fixture()

        first.pop("resources")
        second.pop("resources")
        self.assertEqual(first, second)

    def test_semantic_fusion_improves_grounded_paraphrases_without_regressing_controls(self) -> None:
        baseline = rag_eval.evaluate_fixture()
        provider = _FixtureSemanticProvider()
        with patch.object(rag_eval.rag_service, "_embedding_provider", return_value=provider):
            semantic = rag_eval.evaluate_fixture()
            lexical_rollback = rag_eval.evaluate_fixture(strategy="lexical_v1")

        self.assertEqual(semantic["retrieval_strategy"], "hybrid_v2")
        self.assertEqual(lexical_rollback["retrieval_strategy"], "lexical_v1")
        self.assertGreater(
            semantic["summary"]["positive"]["grounded_hit_rate"],
            baseline["summary"]["positive"]["grounded_hit_rate"],
        )
        self.assertGreater(
            semantic["summary"]["categories"]["paraphrase"]["grounded_hit_rate"],
            lexical_rollback["summary"]["categories"]["paraphrase"]["grounded_hit_rate"],
        )
        self.assertEqual(semantic["summary"]["positive"]["ndcg_at_k"], 1.0)
        self.assertEqual(semantic["summary"]["positive"]["ideal_ranked_hit_rate"], 1.0)
        self.assertGreater(
            semantic["summary"]["positive"]["ndcg_at_k"],
            lexical_rollback["summary"]["positive"]["ndcg_at_k"],
        )
        self.assertEqual(semantic["summary"]["categories"]["exact_identifier"]["recall_at_k"], 1.0)
        self.assertEqual(semantic["summary"]["negative_rejection_rate"], 1.0)
        self.assertEqual(semantic["summary"]["status_accuracy"], 1.0)

    def test_ndcg_requires_all_expected_sources_in_the_ideal_prefix(self) -> None:
        self.assertEqual(rag_eval._ndcg_at_k([1, 2], expected_count=2, top_k=5), 1.0)
        self.assertLess(rag_eval._ndcg_at_k([1, 5], expected_count=2, top_k=5), 1.0)
        self.assertEqual(rag_eval._ndcg_at_k([], expected_count=0, top_k=5), 0.0)

    def test_cli_writes_metadata_only_report_and_creates_output_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "nested" / "report.json"
            with patch.object(sys, "argv", [str(SCRIPT_PATH), "--output", str(output)]):
                self.assertEqual(rag_eval.main(), 0)
            loaded = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(loaded["schema"], "localgpt.rag_retrieval_eval_report.v1")


if __name__ == "__main__":
    unittest.main()
