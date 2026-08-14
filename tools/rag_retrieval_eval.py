#!/usr/bin/env python3
"""Run the deterministic, metadata-only LocalGPT RAG retrieval baseline."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
import time
import tracemalloc
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import config, db
from backend.apps.rag import service as rag_service


DEFAULT_FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "rag_retrieval_eval"
REPORT_SCHEMA = "localgpt.rag_retrieval_eval_report.v1"


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _ndcg_at_k(ranks: list[int], *, expected_count: int, top_k: int) -> float:
    if expected_count <= 0 or top_k <= 0:
        return 0.0
    dcg = sum(1.0 / math.log2(rank + 1) for rank in ranks if rank <= top_k)
    ideal_count = min(expected_count, top_k)
    ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return round(dcg / ideal_dcg, 4) if ideal_dcg else 0.0


def _positive_metrics(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    return {
        "cases": len(rows),
        "recall_at_k": _mean([float(row["recall_at_k"]) for row in rows]),
        "mrr": _mean([float(row["reciprocal_rank"]) for row in rows]),
        "ndcg_at_k": _mean([float(row["ndcg_at_k"]) for row in rows]),
        "context_recall": _mean([float(row["context_recall"]) for row in rows]),
        "full_hit_rate": _mean([1.0 if row["full_hit"] else 0.0 for row in rows]),
        "grounded_hit_rate": _mean([1.0 if row["grounded_full_hit"] else 0.0 for row in rows]),
        "ideal_ranked_hit_rate": _mean([1.0 if row["ideal_ranked_hit"] else 0.0 for row in rows]),
    }


def _aggregate(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [row for row in case_rows if row["expected_source_count"] > 0]
    negatives = [row for row in case_rows if row["expect_no_results"]]
    status_cases = [row for row in case_rows if row["expected_status"] is not None]
    categories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in case_rows:
        categories[str(row["category"])].append(row)
    category_metrics: dict[str, Any] = {}
    for category, rows in sorted(categories.items()):
        category_positives = [row for row in rows if row["expected_source_count"] > 0]
        category_negatives = [row for row in rows if row["expect_no_results"]]
        entry: dict[str, Any] = {"cases": len(rows)}
        if category_positives:
            entry.update(_positive_metrics(category_positives))
        if category_negatives:
            entry["negative_rejection_rate"] = _mean(
                [1.0 if row["negative_rejected"] else 0.0 for row in category_negatives]
            )
        category_metrics[category] = entry
    summary: dict[str, Any] = {
        "total_cases": len(case_rows),
        "positive": _positive_metrics(positives),
        "negative_cases": len(negatives),
        "negative_rejection_rate": _mean([1.0 if row["negative_rejected"] else 0.0 for row in negatives]),
        "status_cases": len(status_cases),
        "status_accuracy": _mean([1.0 if row["status_match"] else 0.0 for row in status_cases]),
        "categories": category_metrics,
    }
    return summary


def evaluate_fixture(
    fixture_root: Path = DEFAULT_FIXTURE_ROOT,
    *,
    strategy: str | None = None,
) -> dict[str, Any]:
    fixture_root = fixture_root.resolve()
    manifest = json.loads((fixture_root / "cases.json").read_text(encoding="utf-8"))
    cases = list(manifest.get("cases") or [])
    top_k = int(manifest.get("top_k") or 5)
    max_context_chars = int(manifest.get("max_context_chars") or 3000)
    if not cases:
        raise ValueError("rag_eval_cases_required")

    previous_db_path = db.DB_PATH
    previous_rag_dir = config.RAG_SOURCE_DIR
    try:
        with tempfile.TemporaryDirectory(prefix="localgpt-rag-eval-") as temp_name:
            temp_root = Path(temp_name)
            db.DB_PATH = temp_root / "eval.db"
            config.RAG_SOURCE_DIR = temp_root / "rag"
            db.init_db()
            profile_id = db.ensure_default_profile()
            if strategy:
                db.set_app_setting(rag_service.RETRIEVAL_STRATEGY_SETTING, strategy)
            profile_source_dir = rag_service.ensure_profile_source_dir(profile_id)
            for source in sorted((fixture_root / "corpus").glob("*.md")):
                shutil.copy2(source, profile_source_dir / source.name)
            ingest = rag_service.ingest_sources(profile_id, force=True)

            rows: list[dict[str, Any]] = []
            tracemalloc.start()
            started = time.perf_counter()
            for case in cases:
                result = rag_service.search_with_diagnostics(profile_id, str(case.get("query") or ""), top_k=top_k)
                selected_sources = [str(item.get("source_id") or "") for item in result["results"]]
                expected_sources = [str(item) for item in (case.get("expected_sources") or [])]
                ranks = [selected_sources.index(source) + 1 for source in expected_sources if source in selected_sources]
                recall = len(ranks) / len(expected_sources) if expected_sources else 0.0
                reciprocal_rank = 1.0 / min(ranks) if ranks else 0.0
                ideal_ranks = list(range(1, min(len(expected_sources), top_k) + 1))
                context = rag_service.build_context(
                    result["results"],
                    max_chars=max_context_chars,
                    diagnostics=result["diagnostics"],
                )
                included_sources = [
                    source for source in expected_sources if f'"source_id":"{source}"' in context
                ]
                context_recall = len(included_sources) / len(expected_sources) if expected_sources else 0.0
                expected_status = case.get("expected_status")
                expect_no_results = bool(case.get("expect_no_results"))
                rows.append(
                    {
                        "case_id": str(case.get("id") or ""),
                        "category": str(case.get("category") or "unspecified"),
                        "expected_source_count": len(expected_sources),
                        "selected_count": len(selected_sources),
                        "matched_expected_count": len(ranks),
                        "recall_at_k": round(recall, 4),
                        "reciprocal_rank": round(reciprocal_rank, 4),
                        "ndcg_at_k": _ndcg_at_k(
                            ranks,
                            expected_count=len(expected_sources),
                            top_k=top_k,
                        ),
                        "ideal_ranked_hit": bool(expected_sources)
                        and sorted(ranks) == ideal_ranks,
                        "context_recall": round(context_recall, 4),
                        "full_hit": bool(expected_sources) and len(ranks) == len(expected_sources),
                        "grounded_full_hit": bool(expected_sources)
                        and len(ranks) == len(expected_sources)
                        and result["diagnostics"].get("overall_status") != "not_found",
                        "expect_no_results": expect_no_results,
                        "negative_rejected": expect_no_results and not selected_sources,
                        "evidence_status": result["diagnostics"].get("overall_status"),
                        "expected_status": expected_status,
                        "status_match": expected_status is not None
                        and result["diagnostics"].get("overall_status") == expected_status,
                    }
                )
            elapsed = time.perf_counter() - started
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            return {
                "schema": REPORT_SCHEMA,
                "fixture_schema": manifest.get("schema"),
                "preview_only": True,
                "metadata_only": True,
                "embedding_model": ingest.get("embedding_model") or rag_service.EMBEDDING_MODEL,
                "retrieval_strategy": rag_service.retrieval_strategy(),
                "top_k": top_k,
                "max_context_chars": max_context_chars,
                "corpus": {
                    "documents": int((ingest.get("stats") or {}).get("documents") or ingest.get("scanned") or 0),
                    "chunks": int((ingest.get("stats") or {}).get("chunks") or ingest.get("chunks_indexed") or 0),
                },
                "summary": _aggregate(rows),
                "cases": rows,
                "resources": {
                    "query_count": len(rows),
                    "elapsed_ms": round(elapsed * 1000, 3),
                    "mean_ms_per_query": round((elapsed * 1000) / max(1, len(rows)), 3),
                    "peak_bytes": int(peak_bytes),
                },
            }
    finally:
        db.DB_PATH = previous_db_path
        config.RAG_SOURCE_DIR = previous_rag_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--strategy", choices=("hybrid_v2", "lexical_v1", "legacy"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate_fixture(args.fixture_root, strategy=args.strategy)
    serialized = json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
