import unittest

from tools.live_llm_evidence_eval import CASES, case_messages, score_response


class LiveLlmEvidenceEvalTests(unittest.TestCase):
    def test_suite_covers_multiple_domains_and_an_unanswerable_case(self):
        self.assertGreaterEqual(len({case.case_id.split("_")[0] for case in CASES}), 5)
        self.assertEqual(sum(case.abstention_expected for case in CASES), 1)
        self.assertTrue(all("Mars" not in " ".join(case.evidence_sources) for case in CASES))

    def test_messages_include_only_fixture_evidence_and_the_current_question(self):
        case = next(item for item in CASES if item.case_id == "warehouse_location_and_deadline")
        messages = case_messages(case)
        self.assertEqual([item["role"] for item in messages], ["system", "user"])
        self.assertIn("Q-17", messages[1]["content"])
        self.assertIn(case.query, messages[1]["content"])
        self.assertNotIn("rag_third_party", messages[1]["content"])

    def test_coverage_counts_each_expected_fact_marker(self):
        case = next(item for item in CASES if item.case_id == "warehouse_location_and_deadline")
        result = score_response(
            case,
            "Broken shipments go to quarantine zone Q-17, where an inspector checks them within six hours.",
        )
        self.assertEqual(result["matched_fact_markers"], 3)
        self.assertEqual(result["fact_marker_coverage"], 1.0)

    def test_negative_case_distinguishes_abstention_from_unsupported_color(self):
        case = next(item for item in CASES if item.abstention_expected)
        abstained = score_response(case, "The evidence does not state a spacesuit colour.")
        hallucinated = score_response(case, "The required suit is red.")
        self.assertTrue(abstained["abstention_marker_present"])
        self.assertFalse(abstained["unsupported_color_marker_present"])
        self.assertFalse(hallucinated["abstention_marker_present"])
        self.assertTrue(hallucinated["unsupported_color_marker_present"])

    def test_fact_markers_allow_equivalent_wording(self):
        greenhouse = next(item for item in CASES if item.case_id == "greenhouse_two_plants")
        greenhouse_result = score_response(
            greenhouse,
            "Орхидеи поливают каждый четвертый день, а суккуленты — один раз в двенадцать дней.",
        )
        microgrid = next(item for item in CASES if item.case_id == "microgrid_threshold_and_recovery")
        microgrid_result = score_response(
            microgrid,
            "When the main grid recovers, the battery returns to its charging state.",
        )
        museum = next(item for item in CASES if item.case_id == "museum_versioned_conflict")
        museum_result = score_response(
            museum,
            "In 2026 the choice depends on the condition of the fibres.",
        )
        markdown_museum_result = score_response(
            museum,
            "In 2022:\n- Textile exhibits must be stored at **45% relative humidity**.\n\n"
            "In 2026:\n- Textile exhibits may be stored at either **45%** or **50% relative humidity**.\n"
            "- The choice depends on the **fibre condition** of the textiles.",
        )
        self.assertEqual(greenhouse_result["fact_marker_coverage"], 1.0)
        self.assertEqual(microgrid_result["fact_marker_coverage"], 0.5)
        self.assertEqual(museum_result["matched_fact_markers"], 2)
        self.assertEqual(markdown_museum_result["fact_marker_coverage"], 1.0)


if __name__ == "__main__":
    unittest.main()
