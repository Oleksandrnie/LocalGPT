from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "tools" / "rag_retrieval_eval.py"
SPEC = importlib.util.spec_from_file_location("rag_retrieval_eval", SCRIPT_PATH)
assert SPEC and SPEC.loader
rag_eval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rag_eval)


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

    def test_cli_writes_metadata_only_report_and_creates_output_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "nested" / "report.json"
            with patch.object(sys, "argv", [str(SCRIPT_PATH), "--output", str(output)]):
                self.assertEqual(rag_eval.main(), 0)
            loaded = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(loaded["schema"], "localgpt.rag_retrieval_eval_report.v1")


if __name__ == "__main__":
    unittest.main()
