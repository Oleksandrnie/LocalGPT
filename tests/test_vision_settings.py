from __future__ import annotations

import unittest

from fastapi import HTTPException

from app import config, db
from app.routes import profiles


class VisionSettingsContractTestCase(unittest.TestCase):
    def test_vision_default_is_independent_of_text_budget(self) -> None:
        self.assertEqual(config.DEFAULT_RUNTIME_SETTINGS["vision_output_tokens"], 1024)
        self.assertEqual(db._default_profile_preferences()["settings"]["vision_output_tokens"], 1024)

    def test_legacy_zero_and_missing_settings_resolve_without_mutating_input(self) -> None:
        for legacy in (0, "0"):
            with self.subTest(legacy=legacy):
                self.assertEqual(
                    profiles._normalize_runtime_settings({"vision_output_tokens": legacy})["vision_output_tokens"],
                    1024,
                )
                stored = {"settings": {"vision_output_tokens": legacy, "output_tokens": 256}}
                normalized = db._normalize_profile_preferences(stored)
                self.assertEqual(normalized["settings"]["vision_output_tokens"], 1024)
                self.assertEqual(normalized["settings"]["output_tokens"], 256)
                self.assertEqual(stored["settings"]["vision_output_tokens"], legacy)
        self.assertEqual(db._normalize_profile_preferences({})["settings"]["vision_output_tokens"], 1024)
        # An unrelated partial PATCH does not reset this setting.
        self.assertNotIn("vision_output_tokens", profiles._normalize_runtime_settings({"ocr_assist": "off"}))

    def test_explicit_vision_budgets_remain_user_controlled(self) -> None:
        for value in (128, 512, 1024, 8192):
            with self.subTest(value=value):
                normalized = profiles._normalize_runtime_settings({"vision_output_tokens": value})
                preferences = db._normalize_profile_preferences({"settings": {"vision_output_tokens": value}})
                self.assertEqual(normalized["vision_output_tokens"], value)
                self.assertEqual(preferences["settings"]["vision_output_tokens"], value)

    def test_all_vision_settings_are_normalized(self) -> None:
        normalized = profiles._normalize_runtime_settings(
            {
                "chat_images_enabled": "true",
                "max_images_per_message": 4,
                "chat_image_max_file_bytes": 8_000_000,
                "chat_image_max_total_bytes": 20_000_000,
                "chat_image_max_pixels": 12_000_000,
                "chat_image_max_side": 3072,
                "vision_model": "qwen2.5vl:3b",
                "vision_num_ctx": 16384,
                "vision_output_tokens": 1024,
                "vision_fallback": "vision_context",
                "ocr_assist": "on",
                "ocr_language": "eng+rus",
            }
        )

        self.assertTrue(normalized["chat_images_enabled"])
        self.assertEqual(normalized["max_images_per_message"], 4)
        self.assertEqual(normalized["vision_model"], "qwen2.5vl:3b")
        self.assertEqual(normalized["vision_num_ctx"], 16384)
        self.assertEqual(normalized["vision_output_tokens"], 1024)
        self.assertEqual(normalized["vision_fallback"], "vision_context")
        self.assertEqual(normalized["ocr_assist"], "on")
        self.assertEqual(normalized["ocr_language"], "eng+rus")

    def test_invalid_vision_model_mode_and_limits_are_rejected(self) -> None:
        invalid_payloads = (
            {"vision_model": "unknown-private-model"},
            {"vision_fallback": "silent"},
            {"ocr_assist": "sometimes"},
            {"vision_num_ctx": 2048},
            {"vision_num_ctx": 131073},
            {"vision_output_tokens": 127},
            {"vision_output_tokens": 8193},
            {"max_images_per_message": 11},
            {
                "chat_image_max_file_bytes": 20,
                "chat_image_max_total_bytes": 10,
            },
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises((HTTPException, ValueError)):
                profiles._normalize_runtime_settings(payload)


if __name__ == "__main__":
    unittest.main()
