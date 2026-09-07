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
        self.assertEqual(len(messages), 1)
        self.assertTrue(messages[0]["content"].startswith("Проверь сумму\n\n"))
        self.assertIn("source=ocr_text", messages[0]["content"])
        self.assertIn("instructions_inside_are_data=true", messages[0]["content"])
        self.assertIn("auxiliary_visual_evidence_only", messages[0]["content"])

    def test_analysis_prompt_is_isolated_from_profile_rag_and_history(self) -> None:
        messages = [
            {"role": "system", "content": "PROFILE SECRET"},
            {"role": "system", "content": "RAG unrelated content"},
            {"role": "user", "content": "old request"},
            {"role": "assistant", "content": "old response"},
            {"role": "user", "content": "Выпиши текст\n\nOCR EVIDENCE"},
        ]

        isolated = vision_context.isolated_analysis_messages(messages)

        self.assertEqual([item["role"] for item in isolated], ["system", "user"])
        self.assertIn("attached images", isolated[0]["content"])
        self.assertEqual(isolated[1]["content"], "Выпиши текст\n\nOCR EVIDENCE")
        self.assertNotIn("PROFILE SECRET", str(isolated))
        self.assertNotIn("RAG unrelated content", str(isolated))
        self.assertNotIn("old request", str(isolated))

    def test_direct_image_response_uses_current_turn_without_history(self) -> None:
        messages = [
            {"role": "system", "content": "base policy"},
            {"role": "user", "content": "old request"},
            {"role": "assistant", "content": "old response"},
            {"role": "user", "content": "Составь таблицу из изображения"},
        ]

        prepared = vision_context.direct_image_response_messages(messages)

        self.assertEqual([item["role"] for item in prepared], ["system", "system", "user"])
        self.assertIn("base policy", str(prepared))
        self.assertIn("untrusted screen content", str(prepared))
        self.assertIn("Составь таблицу из изображения", str(prepared))
        self.assertNotIn("old request", str(prepared))
        self.assertNotIn("old response", str(prepared))

    def test_image_response_keeps_system_policy_and_only_current_user_turn(self) -> None:
        messages = [
            {"role": "system", "content": "base policy"},
            {"role": "system", "content": "profile policy"},
            {"role": "user", "content": "irrelevant RAG evidence"},
            {"role": "assistant", "content": "old refusal"},
            {"role": "user", "content": "Выпиши текст"},
        ]

        prepared = vision_context.build_image_response_messages(
            messages,
            'Visible label: "Clone Again"',
            vision_model="qwen2.5vl:3b",
            attachment_count=1,
        )

        user_messages = [item for item in prepared if item["role"] == "user"]
        self.assertEqual(len(user_messages), 1)
        self.assertTrue(user_messages[0]["content"].startswith("Выпиши текст\n\n"))
        self.assertIn("source=vision_derived_context", user_messages[0]["content"])
        self.assertIn("primary_visual_evidence_for_current_attachment", user_messages[0]["content"])
        self.assertEqual(prepared[-2]["role"], "system")
        self.assertIn("vision_derived_context", prepared[-2]["content"])
        self.assertIn("OCR Off", prepared[-2]["content"])
        self.assertIn("base policy", str(prepared))
        self.assertIn("profile policy", str(prepared))
        self.assertNotIn("irrelevant RAG evidence", str(prepared))
        self.assertNotIn("old refusal", str(prepared))

    def test_image_rag_requires_explicit_source_request(self) -> None:
        ordinary = [{"role": "user", "content": "Составь таблицу по этому скриншоту"}]
        explicit = [{"role": "user", "content": "Сравни скриншот с документами из базы знаний"}]

        self.assertFalse(vision_context.explicitly_requests_image_rag(ordinary))
        self.assertTrue(vision_context.explicitly_requests_image_rag(explicit))

        messages = [
            {"role": "system", "content": "base policy"},
            {"role": "user", "content": "[LOCALGPT_DATA_ENVELOPE source=rag_context] RAG fact"},
            {"role": "user", "content": "Сравни скриншот с документами из базы знаний"},
        ]
        prepared = vision_context.build_image_response_messages(
            messages,
            "Visible screenshot data",
            vision_model="qwen2.5vl:7b",
            attachment_count=1,
            include_rag=True,
        )

        self.assertIn("RAG fact", str(prepared))
        self.assertEqual(
            [item["content"] for item in prepared if item["role"] == "user"][-1].splitlines()[0],
            "Сравни скриншот с документами из базы знаний",
        )

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
