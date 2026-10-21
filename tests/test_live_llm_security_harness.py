from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "tools" / "live_llm_security.py"
SPEC = importlib.util.spec_from_file_location("live_llm_security", SCRIPT_PATH)
assert SPEC and SPEC.loader
live_security = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = live_security
SPEC.loader.exec_module(live_security)


class LiveLlmSecurityHarnessTestCase(unittest.TestCase):
    def test_required_categories_are_present_and_foreign_canaries_never_enter_prompt(self) -> None:
        cases = live_security.build_cases()
        categories = {case.category for case in cases}
        self.assertEqual(
            categories,
            {
                "direct_prompt_injection",
                "hidden_prompt_data_extraction",
                "poisoned_rag",
                "history_memory_criteria_transcript_injection",
                "ocr_vision_derived_injection",
                "forged_trust_boundary_labels",
                "action_tool_admin_escalation",
                "cross_profile_session_absence",
            },
        )
        for case in cases:
            prompt = "\n".join(item["content"] for item in case.messages)
            self.assertFalse(any(token in prompt for token in case.forbidden_prompt_tokens))
            has_session_private = "session_private" in case.protected_token_classes
            self.assertEqual(has_session_private, case.case_id == "hidden_extraction")

    def test_classification_separates_hard_disclosure_from_behavioral_jailbreak(self) -> None:
        case = live_security.build_cases()[0]
        hard = live_security.classify_case(case, case.protected_tokens[0])
        behavioral = live_security.classify_case(case, case.behavioral_tokens[0])
        blocked = live_security.classify_case(
            case,
            case.protected_tokens[0],
            backend_output_blocked=True,
        )
        clean = live_security.classify_case(case, "I cannot reveal hidden instructions.")

        self.assertTrue(hard["disclosure_breach"])
        self.assertTrue(hard["raw_disclosure_breach"])
        self.assertEqual(hard["disclosed_canary_classes"], ["hidden_policy"])
        self.assertFalse(hard["hard_pass"])
        self.assertTrue(behavioral["behavioral_jailbreak"])
        self.assertTrue(behavioral["hard_pass"])
        self.assertTrue(blocked["raw_disclosure_breach"])
        self.assertFalse(blocked["disclosure_breach"])
        self.assertTrue(blocked["hard_pass"])
        self.assertTrue(clean["hard_pass"])
        self.assertFalse(clean["behavioral_jailbreak"])

    def test_live_suite_records_metadata_only_and_unloads_model(self) -> None:
        completion = live_security.ollama_runtime.ChatCompletionResult(
            content="Safe refusal",
            done_reason="stop",
            eval_count=4,
        )
        with (
            patch.object(live_security, "build_cases", return_value=[live_security.build_cases()[0]]),
            patch.object(live_security, "model_metadata", return_value={"model": "synthetic:1b"}),
            patch.object(live_security, "_git_revision", return_value="abc123"),
            patch.object(live_security.ollama_runtime, "chat_completion_result", return_value=completion),
            patch.object(live_security.ollama_runtime, "unload_model", return_value=True) as unload,
        ):
            report = live_security.run_live_suite("synthetic:1b", repeats=2, max_tokens=64)

        self.assertEqual(report["summary"]["runs"], 2)
        self.assertEqual(report["summary"]["hard_failures"], 0)
        self.assertFalse(report["settings"]["raw_prompts_or_responses_recorded"])
        self.assertNotIn("Safe refusal", str(report))
        unload.assert_called_once_with("synthetic:1b", timeout=5.0)

    def test_live_suite_can_repeat_only_exact_selected_cases(self) -> None:
        completion = live_security.ollama_runtime.ChatCompletionResult(
            content="Safe refusal",
            done_reason="stop",
            eval_count=4,
        )
        with (
            patch.object(live_security, "model_metadata", return_value={"model": "synthetic:1b"}),
            patch.object(live_security, "_git_revision", return_value="abc123"),
            patch.object(live_security.ollama_runtime, "chat_completion_result", return_value=completion),
            patch.object(live_security.ollama_runtime, "unload_model", return_value=True),
        ):
            report = live_security.run_live_suite(
                "synthetic:1b",
                repeats=2,
                max_tokens=64,
                case_ids={"hidden_extraction", "forged_boundary"},
            )

        self.assertEqual(report["summary"]["runs"], 4)
        self.assertEqual(
            report["settings"]["selected_case_ids"],
            ["hidden_extraction", "forged_boundary"],
        )


if __name__ == "__main__":
    unittest.main()
