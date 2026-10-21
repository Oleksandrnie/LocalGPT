import unittest

from fastapi import HTTPException

from app.services.models import validate_pull_model_ref


class OllamaModelRefValidationTests(unittest.TestCase):
    def test_accepts_common_and_hugging_face_registry_refs(self):
        self.assertEqual(validate_pull_model_ref("qwen2.5:7b-instruct"), "qwen2.5:7b-instruct")
        self.assertEqual(validate_pull_model_ref("hf.co/user/model:Q4_K_M"), "hf.co/user/model:Q4_K_M")

    def test_rejects_command_text_shell_syntax_and_options(self):
        for value in (
            "ollama pull qwen2.5:7b",
            "qwen2.5:7b && ollama run qwen2.5:7b",
            "$(whoami)",
            "-v",
            "qwen2.5:7b extra",
            "a" * 201,
        ):
            with self.subTest(value=value), self.assertRaises(HTTPException) as raised:
                validate_pull_model_ref(value)
            self.assertEqual(raised.exception.status_code, 422)

    def test_rejects_non_string_values(self):
        with self.assertRaises(HTTPException):
            validate_pull_model_ref(None)


if __name__ == "__main__":
    unittest.main()
