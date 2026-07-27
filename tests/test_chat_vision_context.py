from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.apps.chat.services import vision_context, vision_runtime


class VisionOcrAssistTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.first = Path(self.tmpdir.name) / "first.png"
        self.second = Path(self.tmpdir.name) / "second.webp"
        self.first.write_bytes(b"first")
        self.second.write_bytes(b"second")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_ocr_evidence_is_labeled_per_image_and_appended_as_auxiliary_context(self) -> None:
        with patch.object(
            vision_context,
            "extract_text_from_image",
            side_effect=[
                {"text": "Invoice 42", "engine": "tesseract", "language": "eng"},
                {"text": "Итого 900", "engine": "tesseract", "language": "rus"},
            ],
        ):
            evidence = vision_context.extract_ocr_evidence(
                [self.first, self.second],
                mode="on",
            )

        self.assertIn("[Изображение 1]\nInvoice 42", evidence.text)
        self.assertIn("[Изображение 2]\nИтого 900", evidence.text)
        messages = vision_context.append_ocr_evidence(
            [{"role": "user", "content": "Проверь сумму"}],
            evidence,
        )
        self.assertEqual(messages[0]["content"], "Проверь сумму")
        self.assertIn("вспомогательным evidence", messages[-1]["content"])

    def test_auto_mode_records_ocr_failure_without_blocking_vision(self) -> None:
        failure = HTTPException(
            status_code=503,
            detail={"code": "ocr_engine_missing", "message": "Tesseract missing"},
        )
        with patch.object(vision_context, "extract_text_from_image", side_effect=failure):
            evidence = vision_context.extract_ocr_evidence([self.first], mode="auto")

        self.assertEqual(evidence.text, "")
        self.assertEqual(evidence.warnings, ("image_1:ocr_engine_missing",))

    def test_required_and_ocr_only_modes_fail_explicitly(self) -> None:
        failure = HTTPException(
            status_code=422,
            detail={"code": "ocr_empty_result", "message": "No text"},
        )
        for mode in ("on", "ocr_only"):
            with self.subTest(mode=mode):
                with (
                    patch.object(vision_context, "extract_text_from_image", side_effect=failure),
                    self.assertRaises(vision_runtime.VisionRuntimeError) as raised,
                ):
                    vision_context.extract_ocr_evidence([self.first], mode=mode)
                self.assertEqual(raised.exception.code, "OCR_ASSIST_FAILED")

    def test_invalid_mode_is_rejected_instead_of_silent_fallback(self) -> None:
        with self.assertRaises(vision_runtime.VisionRuntimeError) as raised:
            vision_context.normalize_ocr_assist_mode("sometimes")
        self.assertEqual(raised.exception.code, "INVALID_OCR_ASSIST_MODE")


if __name__ == "__main__":
    unittest.main()
