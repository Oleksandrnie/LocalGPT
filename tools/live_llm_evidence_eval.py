#!/usr/bin/env python3
"""Sequential evidence-use smoke for installed local Ollama chat models.

Uses synthetic evidence only and reports lexical fact-marker coverage, not a
semantic truth score. Response bodies are omitted unless explicitly requested.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import config  # noqa: E402
from backend.apps.chat.services import ollama_runtime  # noqa: E402

DEFAULT_MODELS = (
    "qwen2.5:3b-instruct",
    "qwen2.5:7b-instruct",
    "qwen3:4b",
    "qwen2.5-coder:7b",
    "mistral-nemo:12b",
)
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "rag_retrieval_eval" / "corpus"
REPORT_SCHEMA = "localgpt.live_llm_evidence_eval.v1"
SYSTEM_PROMPT = (
    "Answer using only the supplied evidence. Include every relevant fact needed by the question, "
    "preserve dates/version distinctions, and do not merge conflicting rules. If the evidence does "
    "not contain the requested information, say that it is not stated. Be concise."
)


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    query: str
    evidence_sources: tuple[str, ...]
    fact_patterns: tuple[str, ...]
    abstention_expected: bool = False
    forbidden_patterns: tuple[str, ...] = ()


CASES = (
    EvalCase(
        "greenhouse_two_plants",
        "Как часто поливать орхидеи и суккуленты?",
        ("greenhouse-irrigation.md",),
        (
            r"(?:орхиде\w*.{0,60}(?:четыре|4|четв[её]рт\w*).{0,20}д(?:ень|н\w*)|orchid\w*.{0,35}(?:four|4).{0,20}days?)",
            r"(?:суккулент\w*.{0,60}(?:один раз в|каждые|через).{0,25}(?:двенадцать|12).{0,20}д(?:ень|н\w*)|succulent\w*.{0,35}(?:every|each|once every).{0,15}(?:twelve|12).{0,15}days?)",
        ),
    ),
    EvalCase(
        "warehouse_location_and_deadline",
        "Where are broken shipments isolated, and how soon are they examined?",
        ("warehouse-damage.md",),
        (r"q-17", r"quarantine", r"(?:within|in no more than)\s+(?:six|6)\s+hours"),
    ),
    EvalCase(
        "microgrid_threshold_and_recovery",
        "At what charge level does the backup battery start supplying power, and what happens after the main grid recovers?",
        ("microgrid-storage.md",),
        (r"(?:below|under|less than)\s+(?:thirty|30)\s*(?:percent|%)", r"(?:returns?|switches?).{0,30}charg|recharg"),
    ),
    EvalCase(
        "observatory_interval_method_and_signoff",
        "How often and with what reference is the optical spectrometer calibrated, and who signs the record?",
        ("observatory-calibration.md",),
        (r"(?:every|each)\s+(?:fourteen|14)\s+days", r"argon\s+reference\s+lamp", r"night\s+technician", r"sign(?:ed|s)?"),
    ),
    EvalCase(
        "museum_versioned_conflict",
        "Compare the 2022 and 2026 humidity rules for textile exhibits, including what determines the 2026 choice.",
        ("museum-climate-old.md", "museum-climate-current.md"),
        (r"2022", r"2022.{0,100}45\s*(?:percent|%)", r"2026", r"2026.{0,240}(?:45|50)\s*%?.{0,20}\b(?:or|and)\b.{0,20}(?:45|50)\s*%?", r"(?:fibre|fiber).{0,20}condition|condition.{0,20}(?:fibre|fiber)"),
    ),
    EvalCase(
        "negative_unsupported_color",
        "What colour spacesuit is required for a Mars landing?",
        (),
        (),
        abstention_expected=True,
        forbidden_patterns=(r"\b(?:red|blue|green|yellow|black|white|orange|purple|pink)\b", r"\b(?:красн\w*|син\w*|голуб\w*|зелен\w*|ж[её]лт\w*|ч[её]рн\w*|бел\w*)\b"),
    ),
)

ABSTENTION_PATTERN = re.compile(
    r"(?:not stated|(?:does|do) not state|not provided|not specified|no information|not in the evidence|"
    r"cannot determine|can't determine|unknown|"
    r"нет данных|не указано|не сказано|недостаточно информации|не могу определить)",
    re.IGNORECASE,
)


def case_messages(case: EvalCase) -> list[dict[str, str]]:
    evidence = "\n\n".join(
        (FIXTURE_ROOT / source).read_text(encoding="utf-8").strip()
        for source in case.evidence_sources
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Evidence:\n<evidence>\n{evidence}\n</evidence>\n\nQuestion: {case.query}",
        },
    ]


def score_response(case: EvalCase, response: str) -> dict[str, Any]:
    text = str(response or "")
    matched = [bool(re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)) for pattern in case.fact_patterns]
    forbidden = [bool(re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)) for pattern in case.forbidden_patterns]
    abstained = bool(ABSTENTION_PATTERN.search(text))
    return {
        "case_id": case.case_id,
        "expected_fact_markers": len(matched),
        "matched_fact_markers": sum(matched),
        "fact_marker_coverage": round(sum(matched) / len(matched), 3) if matched else None,
        "abstention_expected": case.abstention_expected,
        "abstention_marker_present": abstained,
        "unsupported_color_marker_present": any(forbidden),
        "response_chars": len(text),
    }


def _installed_models() -> list[str]:
    payload = ollama_runtime._get_json("/api/tags", timeout=4.0)
    models = payload.get("models") if isinstance(payload.get("models"), list) else []
    return [
        str(item.get("name") or item.get("model") or "").strip()
        for item in models
        if isinstance(item, dict) and str(item.get("name") or item.get("model") or "").strip()
    ]


def _system_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    try:
        pressure = subprocess.run(["memory_pressure", "-Q"], capture_output=True, text=True, timeout=4, check=False)
        match = re.search(r"System-wide memory free percentage:\s*(\d+)%", pressure.stdout)
        if match:
            snapshot["memory_free_percent"] = int(match.group(1))
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=4, check=False)
        for key in ("Swapins", "Swapouts"):
            match = re.search(rf"^{key}:\s+(\d+)", vm.stdout, re.MULTILINE)
            if match:
                snapshot[f"{key.lower()}_pages"] = int(match.group(1))
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        thermal = subprocess.run(["pmset", "-g", "therm"], capture_output=True, text=True, timeout=4, check=False)
        output = thermal.stdout
        if re.search(r"no thermal warning level has been recorded", output, re.IGNORECASE):
            snapshot["thermal_warning"] = False
            snapshot["thermal_warning_status"] = "none_recorded"
        else:
            level = re.search(r"thermal warning level:\s*(\d+)", output, re.IGNORECASE)
            if level:
                snapshot["thermal_warning"] = int(level.group(1)) > 0
                snapshot["thermal_warning_status"] = int(level.group(1))
            else:
                snapshot["thermal_warning"] = None
                snapshot["thermal_warning_status"] = "not_exposed"
        snapshot["thermal_signal_available"] = bool(output.strip())
    except (OSError, subprocess.SubprocessError):
        snapshot["thermal_signal_available"] = False
    return snapshot


def _ollama_runner_rss_mb() -> tuple[float, int]:
    try:
        result = subprocess.run(["ps", "-axo", "rss=,command="], capture_output=True, text=True, timeout=4, check=False)
    except (OSError, subprocess.SubprocessError):
        return 0.0, 0
    rss_kb = 0
    count = 0
    for line in result.stdout.splitlines():
        if "llama-server" not in line and "ollama runner" not in line:
            continue
        match = re.match(r"\s*(\d+)\s+", line)
        if match:
            rss_kb += int(match.group(1))
            count += 1
    return round(rss_kb / 1024, 1), count


class ResourceSampler:
    def __init__(self, interval_seconds: float = 1.0) -> None:
        self.interval_seconds = interval_seconds
        self.stop_event = threading.Event()
        self.samples: list[float] = []
        self.memory_free_samples: list[int] = []
        self.thread = threading.Thread(target=self._run, name="ollama-rss-sampler", daemon=True)

    def _run(self) -> None:
        while not self.stop_event.is_set():
            rss_mb, count = _ollama_runner_rss_mb()
            if count:
                self.samples.append(rss_mb)
            try:
                pressure = subprocess.run(["memory_pressure", "-Q"], capture_output=True, text=True, timeout=4, check=False)
                match = re.search(r"System-wide memory free percentage:\s*(\d+)%", pressure.stdout)
                if match:
                    self.memory_free_samples.append(int(match.group(1)))
            except (OSError, subprocess.SubprocessError):
                pass
            self.stop_event.wait(self.interval_seconds)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> dict[str, Any]:
        self.stop_event.set()
        self.thread.join(timeout=5)
        return {
            "ollama_runner_peak_rss_mb_sampled": max(self.samples, default=None),
            "ollama_runner_rss_samples": len(self.samples),
            "minimum_memory_free_percent_sampled": min(self.memory_free_samples, default=None),
            "memory_pressure_samples": len(self.memory_free_samples),
            "rss_sampling_interval_seconds": self.interval_seconds,
        }


def _model_metadata(model: str) -> dict[str, Any]:
    version = ollama_runtime._get_json("/api/version", timeout=4.0)
    shown = ollama_runtime._post_json("/api/show", {"model": model}, timeout=10.0)
    details = shown.get("details") if isinstance(shown.get("details"), dict) else {}
    return {
        "model": model,
        "family": details.get("family"),
        "parameter_size": details.get("parameter_size"),
        "quantization_level": details.get("quantization_level"),
        "ollama_version": version.get("version"),
    }


def evaluate_model(model: str, *, max_tokens: int = 1024, include_responses: bool = False) -> dict[str, Any]:
    before = _system_snapshot()
    sampler = ResourceSampler()
    sampler.start()
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    try:
        for case in CASES:
            try:
                case_started = time.perf_counter()
                completion = ollama_runtime.chat_completion_result(
                    model,
                    case_messages(case),
                    temperature=0,
                    max_tokens=max_tokens,
                    num_ctx=4096,
                    keep_alive="5m",
                    think=False,
                    allow_cpu_fallback=False,
                )
                row = score_response(case, completion.content)
                row.update({
                    "done_reason": completion.done_reason,
                    "eval_count": completion.eval_count,
                    "elapsed_ms": round((time.perf_counter() - case_started) * 1000, 1),
                    "reasoning_chars": len(completion.reasoning or ""),
                })
                if include_responses:
                    row["response"] = completion.content
                results.append(row)
            except Exception as exc:  # One model/case error must not skip unload or conceal other cases.
                results.append({"case_id": case.case_id, "error_type": type(exc).__name__, "error": str(exc)[:240]})
    finally:
        sampled = sampler.stop()
        unloaded = ollama_runtime.unload_model(model, timeout=5.0)
    after = _system_snapshot()
    expected = [row for row in results if "expected_fact_markers" in row]
    positive = [row for row in expected if row["expected_fact_markers"] > 0]
    negative = [row for row in expected if row["abstention_expected"]]
    return {
        "model": _model_metadata(model),
        "settings": {"temperature": 0, "num_ctx": 4096, "max_tokens": max_tokens, "think": False},
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "summary": {
            "case_count": len(CASES),
            "answered_cases": len(expected),
            "nonempty_final_answers": sum(row["response_chars"] > 0 for row in expected),
            "positive_fact_marker_coverage": round(
                sum(row["matched_fact_markers"] for row in positive)
                / max(1, sum(row["expected_fact_markers"] for row in positive)),
                3,
            ),
            "positive_cases_full_marker_coverage": sum(
                row["matched_fact_markers"] == row["expected_fact_markers"] for row in positive
            ),
            "negative_abstention_marker_present": bool(negative) and all(row["abstention_marker_present"] for row in negative),
            "negative_unsupported_color_markers": sum(row["unsupported_color_marker_present"] for row in negative),
            "provider_errors": sum("error_type" in row for row in results),
            "explicit_length_stops": sum(row.get("done_reason") == "length" for row in results),
        },
        "resources": {
            "before": before,
            "after": after,
            "swapins_page_delta": after.get("swapins_pages", 0) - before.get("swapins_pages", 0),
            "swapouts_page_delta": after.get("swapouts_pages", 0) - before.get("swapouts_pages", 0),
            "runner": sampled,
            "explicit_unload_succeeded": unloaded,
        },
        "cases": results,
    }


def run(models: list[str] | None = None, *, max_tokens: int = 1024, include_responses: bool = False) -> dict[str, Any]:
    installed = _installed_models()
    selected = models or [model for model in DEFAULT_MODELS if model in installed]
    missing = [model for model in selected if model not in installed]
    if missing:
        raise ValueError(f"Requested model(s) not installed: {', '.join(missing)}")
    results: list[dict[str, Any]] = []
    for model in selected:
        results.append(evaluate_model(model, max_tokens=max_tokens, include_responses=include_responses))
    return {
        "schema": REPORT_SCHEMA,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "revision": subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=False).stdout.strip() or None,
        "synthetic_only": True,
        "direct_model_evidence_use_not_full_chat_rag": True,
        "raw_prompts_recorded": False,
        "raw_responses_recorded": include_responses,
        "models": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", help="Exact installed Ollama model tag; repeat for sequential comparisons.")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--include-responses", action="store_true", help="Include synthetic model responses for manual review.")
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    args = parser.parse_args()
    if args.max_tokens < 128 or args.max_tokens > 8192:
        parser.error("--max-tokens must be between 128 and 8192")
    try:
        report = run(args.model, max_tokens=args.max_tokens, include_responses=args.include_responses)
    except Exception as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__, "message": str(exc)}, ensure_ascii=False))
        return 3
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if all(item["summary"]["provider_errors"] == 0 for item in report["models"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
