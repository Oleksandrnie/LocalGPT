from __future__ import annotations

import unittest

from fastapi import HTTPException

from app.routes import profiles


class VisionSettingsContractTestCase(unittest.TestCase):
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
                "vision_fallback": "vision_context",
                "ocr_assist": "on",
                "ocr_language": "eng+rus",
            }
        )

        self.assertTrue(normalized["chat_images_enabled"])
        self.assertEqual(normalized["max_images_per_message"], 4)
        self.assertEqual(normalized["vision_model"], "qwen2.5vl:3b")
        self.assertEqual(normalized["vision_fallback"], "vision_context")
        self.assertEqual(normalized["ocr_assist"], "on")
        self.assertEqual(normalized["ocr_language"], "eng+rus")

    def test_invalid_vision_model_mode_and_limits_are_rejected(self) -> None:
        invalid_payloads = (
            {"vision_model": "unknown-private-model"},
            {"vision_fallback": "silent"},
            {"ocr_assist": "sometimes"},
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
