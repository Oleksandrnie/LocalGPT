from __future__ import annotations

import base64
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import config
from app.services import models as model_service
from backend.apps.chat.service import ChatService
from backend.apps.chat.services import ollama_runtime, vision_runtime
from backend.apps.chat.tasks import _vision_runtime_kwargs


def _runtime_model(
    name: str,
    *,
    capabilities: list[str],
    confirmed: bool = True,
    installed: bool = True,
) -> dict:
    return {
        "name": name,
        "installed": installed,
        "runtime_installed": installed,
        "capabilities": capabilities,
        "capabilities_confirmed": confirmed,
    }


class VisionTaskSettingsTestCase(unittest.TestCase):
    def test_separate_vision_model_does_not_inherit_response_thinking_toggle(self) -> None:
        kwargs = _vision_runtime_kwargs(
            ChatService(),
            "qwen2.5vl:3b",
            "qwen3:4b",
            {
                "ollama_think": "on",
                "output_tokens": 512,
                "thinking_tokens": 2048,
                "vision_num_ctx": 8192,
            },
        )

        self.assertNotIn("think", kwargs)
        self.assertEqual(kwargs["num_ctx"], 8192)
        self.assertEqual(kwargs["keep_alive"], "0")

    def test_direct_vision_model_keeps_its_own_thinking_setting(self) -> None:
        kwargs = _vision_runtime_kwargs(
            ChatService(),
            "qwen3-vl:4b",
            "qwen3-vl:4b",
            {"ollama_think": "on", "output_tokens": 512, "vision_num_ctx": 8192},
        )

        self.assertIs(kwargs["think"], True)


class VisionModelMetadataTestCase(unittest.TestCase):
    def test_show_json_exposes_confirmed_capabilities_without_raw_template(self) -> None:
        payload = (
            '{"details":{"family":"qwen2vl","families":["qwen2vl"],'
            '"parameter_size":"3.8B","quantization_level":"Q4_K_M"},'
            '"model_info":{"qwen2vl.context_length":125000},'
            '"capabilities":["completion","vision"]}'
        )
        completed = subprocess.CompletedProcess(
            ["ollama", "show", "qwen2.5vl:3b", "--json"],
            0,
            stdout=payload,
            stderr="",
        )

        with patch.object(model_service.subprocess, "run", return_value=completed) as run:
            details = model_service._show_model_details("qwen2.5vl:3b")

        self.assertEqual(details["architecture"], "qwen2vl")
        self.assertEqual(details["parameters"], "3.8B")
        self.assertEqual(details["quantization"], "Q4_K_M")
        self.assertEqual(details["context_length"], "125000")
        self.assertEqual(details["capabilities"], ["completion", "vision"])
        self.assertTrue(details["capabilities_confirmed"])
        self.assertNotIn("template", details)
        run.assert_called_once()

    def test_show_plain_fallback_parses_capability_section(self) -> None:
        unsupported_json = subprocess.CompletedProcess(
            ["ollama", "show", "legacy", "--json"],
            1,
            stdout="",
            stderr="Error: unknown flag: --json",
        )
        plain = subprocess.CompletedProcess(
            ["ollama", "show", "legacy"],
            0,
            stdout=(
                "  Model\n"
                "    architecture qwen2vl\n"
                "    parameters 3.8B\n"
                "    quantization Q4_K_M\n\n"
                "  Capabilities\n"
                "    completion\n"
                "    vision\n"
            ),
            stderr="",
        )

        with patch.object(model_service.subprocess, "run", side_effect=[unsupported_json, plain]):
            details = model_service._show_model_details("legacy")

        self.assertEqual(details["capabilities"], ["completion", "vision"])
        self.assertTrue(details["capabilities_confirmed"])

    def test_vision_catalog_is_separate_from_normal_chat_catalog(self) -> None:
        vision_ids = {item["id"] for item in config.VISION_MODEL_CATALOG}
        normal_ids = {item["id"] for item in config.MODEL_CATALOG}

        self.assertEqual(vision_ids, {"qwen2.5vl:3b", "qwen2.5vl:7b", "gemma3:4b"})
        self.assertTrue(vision_ids.isdisjoint(normal_ids))

    def test_models_response_exposes_dedicated_vision_catalog(self) -> None:
        with (
            patch.object(model_service, "_list_local_models", return_value=[]),
            patch.object(model_service, "_list_active_models", return_value=[]),
            patch.object(model_service, "_pull_statuses", return_value=[]),
            patch.object(model_service, "_inspect_storage_manifests", return_value=({}, {})),
            patch.object(model_service, "_list_partial_blobs", return_value=[]),
        ):
            response = model_service.list_models()

        vision_ids = {item["id"] for item in response["vision_catalog"]}
        normal_ids = {item["id"] for item in response["catalog"]}
        self.assertEqual(vision_ids, {"qwen2.5vl:3b", "qwen2.5vl:7b", "gemma3:4b"})
        self.assertTrue(vision_ids.isdisjoint(normal_ids))
        self.assertTrue(all(item["declared_capabilities"] == ["text", "vision"] for item in response["vision_catalog"]))
        self.assertTrue(all(not item["capabilities_confirmed"] for item in response["vision_catalog"]))


class VisionRouteResolverTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vision_3b = _runtime_model(
            "qwen2.5vl:3b",
            capabilities=["completion", "vision"],
        )
        self.vision_7b = _runtime_model(
            "qwen2.5vl:7b",
            capabilities=["completion", "vision"],
        )
        self.text_model = _runtime_model(
            "qwen2.5:7b-instruct",
            capabilities=["completion"],
        )

    def test_selected_confirmed_vision_model_uses_direct_route(self) -> None:
        plan = vision_runtime.resolve_vision_route(
            selected_model="qwen2.5vl:7b",
            configured_vision_model="auto",
            installed_models=[self.vision_3b, self.vision_7b],
        )

        self.assertEqual(plan.mode, "direct")
        self.assertEqual(plan.vision_model, "qwen2.5vl:7b")
        self.assertEqual(plan.response_model, "qwen2.5vl:7b")

    def test_auto_prefers_catalog_order_and_bypasses_text_router(self) -> None:
        plan = vision_runtime.resolve_vision_route(
            selected_model=vision_runtime.AUTO_ROUTER_MODEL_ID,
            configured_vision_model="auto",
            installed_models=[self.vision_7b, self.vision_3b],
        )

        self.assertEqual(plan.mode, "direct")
        self.assertEqual(plan.vision_model, "qwen2.5vl:3b")
        self.assertEqual(plan.reason, "image_bypasses_text_intent_router")

    def test_text_model_uses_separate_vision_context_route(self) -> None:
        plan = vision_runtime.resolve_vision_route(
            selected_model="qwen2.5:7b-instruct",
            configured_vision_model="auto",
            installed_models=[self.text_model, self.vision_3b],
        )

        self.assertEqual(plan.mode, "vision_context")
        self.assertEqual(plan.vision_model, "qwen2.5vl:3b")
        self.assertEqual(plan.response_model, "qwen2.5:7b-instruct")

    def test_unconfirmed_declared_vision_is_not_used(self) -> None:
        unconfirmed = _runtime_model(
            "qwen2.5vl:3b",
            capabilities=["completion", "vision"],
            confirmed=False,
        )

        with self.assertRaises(vision_runtime.VisionRuntimeError) as raised:
            vision_runtime.resolve_vision_route(
                selected_model=vision_runtime.AUTO_ROUTER_MODEL_ID,
                configured_vision_model="auto",
                installed_models=[unconfirmed],
            )

        self.assertEqual(raised.exception.code, "VISION_MODEL_MISSING")

    def test_explicit_missing_vision_model_has_actionable_error(self) -> None:
        with self.assertRaises(vision_runtime.VisionRuntimeError) as raised:
            vision_runtime.resolve_vision_route(
                selected_model="qwen2.5:7b-instruct",
                configured_vision_model="qwen2.5vl:7b",
                installed_models=[self.text_model],
            )

        self.assertEqual(raised.exception.code, "VISION_MODEL_NOT_INSTALLED")
        self.assertEqual(raised.exception.details["vision_model"], "qwen2.5vl:7b")


class VisionOllamaPayloadTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.first_path = Path(self.tmpdir.name) / "first.png"
        self.second_path = Path(self.tmpdir.name) / "second.webp"
        self.first_path.write_bytes(b"\x89PNG\r\nlocalgpt-first")
        self.second_path.write_bytes(b"RIFF-localgpt-second-WEBP")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_multimodal_builder_copies_messages_and_attaches_images_to_last_user(self) -> None:
        original = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "analyze"},
        ]

        messages = vision_runtime.build_multimodal_messages(
            original,
            [self.first_path, self.second_path],
        )

        self.assertNotIn("images", original[-1])
        self.assertNotIn("images", messages[1])
        self.assertEqual(messages[-1]["content"], "analyze")
        self.assertEqual(base64.b64decode(messages[-1]["images"][0]), self.first_path.read_bytes())
        self.assertEqual(base64.b64decode(messages[-1]["images"][1]), self.second_path.read_bytes())

    def test_multimodal_builder_enforces_total_byte_limit(self) -> None:
        with self.assertRaises(vision_runtime.VisionRuntimeError) as raised:
            vision_runtime.build_multimodal_messages(
                [{"role": "user", "content": "analyze"}],
                [self.first_path],
                max_total_bytes=4,
            )

        self.assertEqual(raised.exception.code, "IMAGES_TOTAL_TOO_LARGE")
        self.assertNotIn(str(self.first_path), raised.exception.message)
        self.assertNotIn(str(self.first_path), str(raised.exception.details))

    def test_runtime_passes_base64_only_in_transient_ollama_messages(self) -> None:
        original = [{"role": "user", "content": "what is shown?"}]

        with patch.object(ollama_runtime, "chat_completion", return_value="vision answer") as native_chat:
            reply = vision_runtime.chat_completion(
                "qwen2.5vl:3b",
                original,
                [self.first_path],
                temperature=0.1,
                max_tokens=120,
            )

        self.assertEqual(reply, "vision answer")
        self.assertNotIn("images", original[0])
        sent_messages = native_chat.call_args.kwargs["messages"]
        self.assertEqual(base64.b64decode(sent_messages[0]["images"][0]), self.first_path.read_bytes())
        native_chat.assert_called_once()

    def test_native_ollama_payload_contains_images_on_user_message(self) -> None:
        original = [{"role": "user", "content": "what is shown?"}]

        with patch.object(
            ollama_runtime,
            "_post_json",
            return_value={"message": {"content": "native answer"}},
        ) as post_json:
            reply = vision_runtime.chat_completion(
                "qwen2.5vl:3b",
                original,
                [self.first_path],
                allow_cpu_fallback=False,
            )

        self.assertEqual(reply, "native answer")
        payload = post_json.call_args.args[1]
        self.assertEqual(payload["model"], "qwen2.5vl:3b")
        self.assertFalse(payload["stream"])
        self.assertEqual(base64.b64decode(payload["messages"][0]["images"][0]), self.first_path.read_bytes())
        self.assertNotIn("images", original[0])

    def test_native_ollama_payload_contains_requested_context_size(self) -> None:
        original = [{"role": "user", "content": "what is shown?"}]

        with patch.object(
            ollama_runtime,
            "_post_json",
            return_value={"message": {"content": "native answer"}},
        ) as post_json:
            vision_runtime.chat_completion(
                "qwen2.5vl:3b",
                original,
                [self.first_path],
                num_ctx=16384,
                allow_cpu_fallback=False,
            )

        payload = post_json.call_args.args[1]
        self.assertEqual(payload["options"]["num_ctx"], 16384)


if __name__ == "__main__":
    unittest.main()
