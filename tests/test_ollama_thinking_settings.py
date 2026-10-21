from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from app import db
from app.routes import profiles
from app.schemas import ModelSettingsRequest
from app.services import models
from app.services.thinking import resolve_thinking
from backend.apps.asr.pipeline import _pipeline_ollama_think
from backend.apps.chat.service import ChatService, apply_generation_budget_policy
from backend.apps.chat.services import ollama_runtime


class ThinkingSettingsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_patch = patch.object(db, "DB_PATH", Path(self.tmp.name) / "settings.db")
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        db.init_db()
        self.profile = db.ensure_default_profile()
        self.metadata = patch.object(models, "_show_model_details", return_value={})
        self.show = self.metadata.start()
        self.addCleanup(self.metadata.stop)

    def save(self, value, model="custom-reasoner:latest"):
        return profiles.save_model_settings(ModelSettingsRequest(
            profile_id=self.profile, model_name=model, ollama_think=value,
            output_tokens=700, thinking_tokens=4096,
        ))

    def test_named_levels_round_trip_per_profile_and_model(self):
        self.show.return_value = {"thinking": {"values": ["low", "medium", "high", "Deep_Mode"], "default": "medium"}}
        for value in ("low", "medium", "high", "Deep_Mode"):
            with self.subTest(value=value):
                saved = self.save(value)
                loaded = profiles.get_model_settings(self.profile, "custom-reasoner:latest")
                self.assertEqual(saved["effective"]["ollama_think"], value)
                self.assertEqual(loaded["overrides"]["ollama_think"], value)
                self.assertEqual(loaded["effective"]["output_tokens"], 700)
                self.assertEqual(loaded["effective"]["thinking_tokens"], 4096)
        other = db.create_profile("Other profile")
        self.assertEqual(profiles.get_model_settings(other["id"], "custom-reasoner:latest")["effective"]["ollama_think"], "auto")
        self.assertEqual(profiles.get_model_settings(self.profile, "another:latest")["effective"]["ollama_think"], "auto")

    def test_booleans_use_legacy_storage_and_aliases_remain_compatible(self):
        self.show.return_value = {"thinking": {"values": [False, True], "default": True}}
        for value, expected in ((True, "on"), (False, "off"), ("auto", "auto"), ("ON", "on"), ("false", "off"), ("default", "auto")):
            with self.subTest(value=value):
                saved = self.save(value)
                self.assertEqual(saved["overrides"]["ollama_think"], expected)
                native = resolve_thinking(saved["effective"]["ollama_think"])
                self.assertIs(native, None if expected == "auto" else expected == "on")

    def test_unsupported_values_fail_before_persistence(self):
        for control, value in (
            ({"values": [False, True]}, "high"),
            ({"values": ["low", "high"]}, "medium"),
            ({"values": ["low", "high"]}, True),
            ({"values": [False]}, True),
            (None, "high"),
            ({"values": ["high"]}, "High"),
            ({"values": ["high"]}, " high "),
        ):
            with self.subTest(control=control, value=value):
                self.show.return_value = {"thinking": control}
                with self.assertRaises(HTTPException) as error:
                    self.save(value)
                self.assertEqual(error.exception.status_code, 422)
                self.assertEqual(error.exception.detail["code"], "invalid_ollama_think")
                self.assertIsNone(db.get_model_settings(self.profile, "custom-reasoner:latest"))

    def test_unknown_metadata_retains_boolean_legacy_support(self):
        for value in (True, False, "on", "off", "auto"):
            self.save(value)

    def test_schema_rejects_non_boolean_non_string_inputs(self):
        for value in (1, 0, [], {}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ModelSettingsRequest(profile_id=self.profile, model_name="custom", ollama_think=value)

    def test_named_levels_reach_native_payload_unchanged_in_both_paths(self):
        self.show.return_value = {"thinking": {"values": ["low", "medium", "high", "Deep_Mode"]}}
        service = ChatService()
        for level in ("low", "medium", "high", "Deep_Mode"):
            for stream in (False, True):
                with self.subTest(level=level, stream=stream):
                    settings = self.save(level)["effective"]
                    kwargs = service._runtime_kwargs("custom-reasoner:latest", settings)
                    self.assertEqual(kwargs["think"], level)
                    self.assertEqual(kwargs["max_tokens"], 4796)
                    payload = ollama_runtime._chat_payload(
                        "custom-reasoner:latest", [{"role": "user", "content": "Test"}],
                        stream=stream, temperature=0, max_tokens=kwargs["max_tokens"],
                        num_ctx=None, keep_alive=None, num_gpu=None, think=kwargs["think"],
                    )
                    self.assertEqual(json.loads(json.dumps(payload))["think"], level)
                    self.assertEqual(payload["messages"][0]["content"], "Test")

    def test_native_call_rejects_stale_per_model_named_value_before_http(self):
        self.show.return_value = {"thinking": {"values": [False, True]}}
        with patch.object(ollama_runtime, "_post_json_with_metal_recovery") as post:
            with self.assertRaises(HTTPException):
                ollama_runtime.chat_completion_result("bool-model", [], think="high")
            post.assert_not_called()
        with patch.object(ollama_runtime, "request") as request:
            with self.assertRaises(HTTPException):
                list(ollama_runtime.chat_completion_stream_events("bool-model", [], think="high"))
            request.Request.assert_not_called()

    def test_native_transports_receive_exact_named_and_boolean_values(self):
        messages = [{"role": "user", "content": "Test"}]
        for value in ("low", "medium", "high", False, True):
            with self.subTest(value=value):
                self.show.return_value = {"thinking": {"values": ["low", "medium", "high", False, True]}}
                with patch.object(ollama_runtime, "_post_json_with_metal_recovery", return_value={"message": {"content": "Answer"}}) as post:
                    ollama_runtime.chat_completion_result("custom", messages, think=value)
                    self.assertEqual(post.call_args.args[0], "/api/chat")
                    self.assertEqual(post.call_args.args[1]["think"], value)
                    self.assertIs(type(post.call_args.args[1]["think"]), type(value))
                with patch.object(ollama_runtime, "_post_json_stream", return_value=iter([{"done": True}])) as post:
                    list(ollama_runtime.chat_completion_stream_events("custom", messages, think=value))
                    self.assertEqual(post.call_args.args[0], "/api/chat")
                    self.assertEqual(post.call_args.args[1]["think"], value)
                    self.assertIs(type(post.call_args.args[1]["think"]), type(value))

    def test_boolean_false_survives_pipeline_and_budget_resolution(self):
        self.assertIs(_pipeline_ollama_think({"ollama_think": False}), False)
        self.assertEqual(_pipeline_ollama_think({"ollama_think": "high"}), "high")
        budget = apply_generation_budget_policy({"ollama_think": False, "output_tokens": 700})
        self.assertEqual(budget["provider_num_predict"], 700)
        self.assertFalse(budget["thinking_budget_applied"])

    def test_qwen_hybrid_off_and_named_controls_remain_distinct(self):
        messages = [{"role": "user", "content": "Test"}]
        off = ollama_runtime._chat_payload("qwen3:8b", messages, stream=False,
            temperature=None, max_tokens=700, num_ctx=None, keep_alive=None, num_gpu=None, think=False)
        self.assertNotIn("think", off)
        self.assertTrue(off["messages"][0]["content"].endswith("/no_think"))
        self.assertEqual(messages[0]["content"], "Test")
        self.show.return_value = {"thinking": {"values": ["low", "high"]}}
        named = ollama_runtime._chat_payload("qwen3:8b", messages, stream=False,
            temperature=None, max_tokens=700, num_ctx=None, keep_alive=None, num_gpu=None, think="low")
        self.assertEqual(named["think"], "low")
        self.assertEqual(named["messages"], messages)


if __name__ == "__main__":
    unittest.main()
