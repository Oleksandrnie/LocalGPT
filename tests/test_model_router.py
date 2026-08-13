import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import config, db
from app.schemas import ChatRequest
from app.services import models as model_service
from backend.apps.chat.routes import _apply_auto_router, _prepare_chat_request, start_chat_task
from backend.apps.chat.service import ChatService
from backend.apps.chat.service import apply_generation_budget_policy
from backend.apps.chat.services import local_calculator, model_residency, model_router, ollama_runtime


class ModelRouterTestCase(unittest.TestCase):
    def test_auto_model_aliases(self):
        self.assertTrue(model_router.is_auto_model("__auto_router__"))
        self.assertTrue(model_router.is_auto_model("Auto / Smart Router"))
        self.assertFalse(model_router.is_auto_model("qwen2.5:7b-instruct"))

    def test_ollama_keep_alive_defaults_by_model(self):
        self.assertEqual(ollama_runtime.resolve_keep_alive("qwen2.5:7b-instruct", {}), "5m")
        self.assertEqual(model_residency.resolve_model_keep_alive("qwen2.5:7b-instruct", {}, mode="auto"), "4m")
        self.assertEqual(model_residency.resolve_model_keep_alive("qwen2.5:7b-instruct", {}, mode="manual"), "5m")
        self.assertEqual(
            model_residency.resolve_model_keep_alive("mistral-nemo:12b", {"ollama_keep_alive": "45s"}, mode="manual"),
            "5m",
        )
        self.assertEqual(model_residency.resolve_model_keep_alive("qwen2.5-coder:7b", {}, mode="auto"), "2m")
        self.assertEqual(ollama_runtime.resolve_keep_alive("mistral-nemo:12b", {}), "60s")
        self.assertEqual(ollama_runtime.resolve_keep_alive(model_router.ROUTER_MODEL_ID, {}, router=True), "2m")
        self.assertEqual(
            ollama_runtime.resolve_keep_alive("qwen2.5:7b-instruct", {"ollama_keep_alive": "45s"}),
            "45s",
        )

    def test_force_unload_models_terminates_stuck_runner_after_unload(self):
        with (
            patch.object(ollama_runtime, "unload_model", return_value=True) as unload_model,
            patch.object(ollama_runtime, "loaded_model_names", return_value={"qwen3:8b"}),
            patch.object(ollama_runtime, "_ollama_runner_pids", return_value=[12345]),
            patch.object(ollama_runtime.os, "kill") as kill,
        ):
            result = ollama_runtime.force_unload_models({"qwen3:8b"}, wait_timeout=0)

        self.assertEqual(result["unloaded_models"], ["qwen3:8b"])
        self.assertEqual(result["stuck_models"], ["qwen3:8b"])
        self.assertEqual(result["terminated_runner_pids"], [12345])
        unload_model.assert_called_once_with("qwen3:8b", timeout=1.0)
        kill.assert_called_once_with(12345, ollama_runtime.signal.SIGTERM)

    def test_force_unload_models_does_not_terminate_when_model_disappears(self):
        with (
            patch.object(ollama_runtime, "unload_model", return_value=True),
            patch.object(ollama_runtime, "loaded_model_names", return_value=set()),
            patch.object(ollama_runtime, "_ollama_runner_pids") as runner_pids,
            patch.object(ollama_runtime.os, "kill") as kill,
        ):
            result = ollama_runtime.force_unload_models({"qwen3:8b"}, wait_timeout=0)

        self.assertEqual(result["stuck_models"], [])
        self.assertEqual(result["terminated_runner_pids"], [])
        runner_pids.assert_not_called()
        kill.assert_not_called()

    def test_residency_limit_evicts_oldest_target_model(self):
        model_residency.reset_state()
        settings = {"max_resident_target_models": 2, "single_large_target_model": False}

        with patch.object(ollama_runtime, "unload_model", return_value=True) as unload_model:
            model_residency.apply_target_settings("qwen2.5:3b-instruct", settings, mode="auto")
            model_residency.apply_target_settings("qwen2.5:7b-instruct", settings, mode="auto")
            third = model_residency.apply_target_settings("qwen2.5-coder:7b", settings, mode="auto")

        self.assertEqual(
            model_residency.snapshot_state()["active_target_models"],
            ["qwen2.5-coder:7b"],
        )
        self.assertEqual(
            [call.args[0] for call in unload_model.call_args_list],
            ["qwen2.5:3b-instruct", "qwen2.5:7b-instruct"],
        )
        self.assertEqual(third["evicted_model"], "qwen2.5:7b-instruct")
        self.assertEqual(third["eviction_policy"], "lru")
        self.assertEqual(third["target_keep_alive"], "2m")

    def test_residency_single_large_policy_keeps_only_latest_medium_code_heavy_model(self):
        model_residency.reset_state()
        settings = {"max_resident_target_models": 3, "single_large_target_model": True}

        with patch.object(ollama_runtime, "unload_model", return_value=True) as unload_model:
            model_residency.apply_target_settings("qwen2.5:3b-instruct", settings, mode="auto")
            model_residency.apply_target_settings("qwen2.5:7b-instruct", settings, mode="auto")
            third = model_residency.apply_target_settings("qwen2.5-coder:7b", settings, mode="auto")

        self.assertEqual(
            model_residency.snapshot_state()["active_target_models"],
            ["qwen2.5-coder:7b"],
        )
        self.assertEqual(
            [call.args[0] for call in unload_model.call_args_list],
            ["qwen2.5:3b-instruct", "qwen2.5:7b-instruct"],
        )
        self.assertEqual(third["evicted_model"], "qwen2.5:7b-instruct")
        self.assertEqual(third["eviction_policy"], "single_large_target_model")
        self.assertTrue(third["single_large_target_model"])

    def test_residency_router_is_not_counted_as_target_model(self):
        model_residency.reset_state()

        with patch.object(ollama_runtime, "unload_model", return_value=True) as unload_model:
            router_debug = model_residency.prepare_router_for_request({})
            model_residency.apply_target_settings(
                "qwen2.5:3b-instruct",
                {"max_resident_target_models": 1},
                mode="auto",
            )
            model_residency.apply_target_settings(
                "qwen2.5:7b-instruct",
                {"max_resident_target_models": 1},
                mode="auto",
            )

        state = model_residency.snapshot_state()
        self.assertEqual(router_debug["router_keep_alive"], "2m")
        self.assertTrue(state["router_model_active"])
        self.assertEqual(state["active_target_models"], ["qwen2.5:7b-instruct"])
        unload_model.assert_called_once_with("qwen2.5:3b-instruct")

    def test_residency_heavy_policy_evicts_medium_and_light_by_default(self):
        model_residency.reset_state()

        with patch.object(ollama_runtime, "unload_model", return_value=True) as unload_model:
            model_residency.apply_target_settings("qwen2.5:3b-instruct", {"max_resident_target_models": 3}, mode="manual")
            model_residency.apply_target_settings("qwen2.5:7b-instruct", {"max_resident_target_models": 3}, mode="manual")
            heavy = model_residency.apply_target_settings(
                "mistral-nemo:12b",
                {"max_resident_target_models": 3, "allow_light_with_heavy": False},
                mode="manual",
            )

        self.assertEqual(model_residency.snapshot_state()["active_target_models"], ["mistral-nemo:12b"])
        self.assertEqual(heavy["target_keep_alive"], "5m")
        self.assertEqual(heavy["eviction_policy"], "heavy_policy")
        self.assertEqual(
            [call.args[0] for call in unload_model.call_args_list],
            ["qwen2.5:3b-instruct", "qwen2.5:7b-instruct"],
        )

    def test_chat_completion_passes_keep_alive_to_native_ollama_request(self):
        service = ChatService()
        messages = [{"role": "user", "content": "hello"}]

        with patch.object(
            ollama_runtime,
            "chat_completion_result",
            return_value=ollama_runtime.ChatCompletionResult(content="ok"),
        ) as native_chat:
            reply = service.chat_completion(
                "qwen2.5:7b-instruct",
                messages,
                settings={"temperature": 0.1, "max_tokens": 5, "ollama_keep_alive": "45s"},
            )

        self.assertEqual(reply, "ok")
        native_chat.assert_called_once_with(
            "qwen2.5:7b-instruct",
            messages=messages,
            temperature=0.1,
            max_tokens=5,
            keep_alive="45s",
        )

    def test_chat_completion_passes_num_ctx_to_native_ollama_request(self):
        service = ChatService()
        messages = [{"role": "user", "content": "hello"}]

        with patch.object(
            ollama_runtime,
            "chat_completion_result",
            return_value=ollama_runtime.ChatCompletionResult(content="ok"),
        ) as native_chat:
            reply = service.chat_completion(
                "qwen2.5vl:3b",
                messages,
                settings={"temperature": 0.1, "max_tokens": 5, "num_ctx": 8192},
            )

        self.assertEqual(reply, "ok")
        native_chat.assert_called_once_with(
            "qwen2.5vl:3b",
            messages=messages,
            temperature=0.1,
            max_tokens=5,
            num_ctx=8192,
            keep_alive="5m",
        )

    def test_vision_runtime_kwargs_use_vision_num_ctx(self):
        service = ChatService()

        kwargs = service._runtime_kwargs(
            "qwen2.5vl:3b",
            {"temperature": 0.1, "max_tokens": 5, "num_ctx": 32768, "vision_num_ctx": 16384},
            vision=True,
        )

        self.assertEqual(kwargs["num_ctx"], 16384)

    def test_chat_completion_passes_think_setting_to_native_ollama_request(self):
        service = ChatService()
        messages = [{"role": "user", "content": "hello"}]

        with patch.object(
            ollama_runtime,
            "chat_completion_result",
            return_value=ollama_runtime.ChatCompletionResult(content="ok"),
        ) as native_chat:
            reply = service.chat_completion(
                "qwen3:8b",
                messages,
                settings={"temperature": 0.1, "max_tokens": 5, "ollama_think": "off"},
            )

        self.assertEqual(reply, "ok")
        native_chat.assert_called_once_with(
            "qwen3:8b",
            messages=messages,
            temperature=0.1,
            max_tokens=2053,
            keep_alive="5m",
            think=False,
        )

    def test_chat_completion_rejects_reasoning_only_length_exhaustion(self):
        service = ChatService()
        result = ollama_runtime.ChatCompletionResult(
            content="",
            reasoning="unfinished reasoning",
            done_reason="length",
            eval_count=64,
        )

        with patch.object(ollama_runtime, "chat_completion_result", return_value=result):
            with self.assertRaises(HTTPException) as ctx:
                service.chat_completion(
                    "qwen3:8b",
                    [{"role": "user", "content": "hello"}],
                    settings={"max_tokens": 64, "ollama_think": "on"},
                )

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(ctx.exception.detail["code"], "chat_final_answer_incomplete")

    def test_chat_completion_stream_passes_keep_alive_to_native_ollama_request(self):
        service = ChatService()
        messages = [{"role": "user", "content": "hello"}]

        with patch.object(
            ollama_runtime,
            "chat_completion_stream_events",
            return_value=iter(
                [
                    ollama_runtime.ChatStreamEvent(content="при"),
                    ollama_runtime.ChatStreamEvent(content="вет", done=True, done_reason="stop"),
                ]
            ),
        ) as native_chat:
            chunks = list(
                service.chat_completion_stream(
                    "qwen2.5:7b-instruct",
                    messages,
                    settings={"temperature": 0.1, "max_tokens": 5, "ollama_keep_alive": "45s"},
                )
            )

        self.assertEqual(chunks, ["при", "вет"])
        native_chat.assert_called_once_with(
            "qwen2.5:7b-instruct",
            messages=messages,
            temperature=0.1,
            max_tokens=5,
            keep_alive="45s",
        )

    def test_ollama_chat_stream_parses_native_chat_chunks(self):
        messages = [{"role": "user", "content": "hello"}]

        with patch.object(
            ollama_runtime,
            "_post_json_stream",
            return_value=iter(
                [
                    {"message": {"thinking": "Сначала"}},
                    {"message": {"content": "При"}},
                    {"message": {"content": "вет"}},
                    {"done": True, "done_reason": "stop", "eval_count": 4},
                ]
            ),
        ) as post_stream:
            chunks = list(
                ollama_runtime.chat_completion_stream(
                    "qwen2.5:7b-instruct",
                    messages=messages,
                    temperature=0.1,
                    max_tokens=5,
                    num_ctx=8192,
                    keep_alive="45s",
                )
            )

        self.assertEqual(chunks, ["При", "вет"])
        payload = post_stream.call_args.args[1]
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["model"], "qwen2.5:7b-instruct")
        self.assertEqual(payload["messages"], messages)
        self.assertEqual(payload["options"]["temperature"], 0.1)
        self.assertEqual(payload["options"]["num_predict"], 5)
        self.assertEqual(payload["options"]["num_ctx"], 8192)
        self.assertEqual(payload["keep_alive"], "45s")

    def test_ollama_chat_keeps_qwen3_reasoning_parser_enabled_when_thinking_is_off(self):
        messages = [{"role": "user", "content": "hello"}]

        with patch.object(
            ollama_runtime,
            "_post_json",
            return_value={
                "message": {"content": "ok", "thinking": ""},
                "done_reason": "stop",
                "eval_count": 1,
            },
        ) as post_json:
            result = ollama_runtime.chat_completion_result(
                "qwen3:8b",
                messages=messages,
                temperature=0.1,
                max_tokens=5,
                think=False,
            )

        self.assertEqual(result.content, "ok")
        self.assertEqual(result.reasoning, "")
        self.assertEqual(result.done_reason, "stop")
        self.assertEqual(result.eval_count, 1)
        payload = post_json.call_args.args[1]
        self.assertNotIn("think", payload)
        self.assertEqual(payload["model"], "qwen3:8b")
        self.assertTrue(payload["messages"][-1]["content"].endswith("/no_think"))
        self.assertEqual(messages, [{"role": "user", "content": "hello"}])

    def test_ollama_chat_keeps_native_think_false_for_non_hybrid_model(self):
        payload = ollama_runtime._chat_payload(
            "qwen2.5:7b-instruct",
            [{"role": "user", "content": "hello"}],
            stream=False,
            temperature=None,
            max_tokens=None,
            num_ctx=None,
            keep_alive=None,
            num_gpu=None,
            think=False,
        )

        self.assertIs(payload["think"], False)
        self.assertEqual(payload["messages"][-1]["content"], "hello")

    def test_chat_completion_hides_structured_reasoning_when_thinking_is_off(self):
        service = ChatService()
        result = ollama_runtime.ChatCompletionResult(
            content="final",
            reasoning="internal trace",
            done_reason="stop",
        )

        with patch.object(ollama_runtime, "chat_completion_result", return_value=result):
            completed = service.chat_completion_result(
                "qwen3:8b",
                [{"role": "user", "content": "hello"}],
                settings={"max_tokens": 64, "ollama_think": "off"},
            )

        self.assertEqual(completed.content, "final")
        self.assertEqual(completed.reasoning, "")

    def test_chat_completion_rejects_content_truncated_at_token_limit(self):
        service = ChatService()
        result = ollama_runtime.ChatCompletionResult(
            content="unfinished visible answer",
            done_reason="length",
            eval_count=64,
        )

        with patch.object(ollama_runtime, "chat_completion_result", return_value=result):
            with self.assertRaises(HTTPException) as ctx:
                service.chat_completion_result(
                    "qwen3:8b",
                    [{"role": "user", "content": "hello"}],
                    settings={"max_tokens": 64, "ollama_think": "off"},
                )

        self.assertEqual(ctx.exception.detail["code"], "chat_final_answer_incomplete")

    def test_chat_completion_stream_hides_reasoning_when_thinking_is_off(self):
        service = ChatService()
        events = iter(
            [
                ollama_runtime.ChatStreamEvent(reasoning="internal trace"),
                ollama_runtime.ChatStreamEvent(content="final"),
                ollama_runtime.ChatStreamEvent(done=True, done_reason="stop"),
            ]
        )

        with patch.object(ollama_runtime, "chat_completion_stream_events", return_value=events):
            result = list(
                service.chat_completion_stream_events(
                    "qwen3:8b",
                    [{"role": "user", "content": "hello"}],
                    settings={"max_tokens": 64, "ollama_think": "off"},
                )
            )

        self.assertEqual("".join(item.content for item in result), "final")
        self.assertEqual("".join(item.reasoning for item in result), "")

    def test_ollama_chat_stream_events_keep_reasoning_out_of_content_wrapper(self):
        messages = [{"role": "user", "content": "hello"}]
        with patch.object(
            ollama_runtime,
            "_post_json_stream",
            return_value=iter(
                [
                    {"message": {"thinking": "reason ", "content": ""}},
                    {"message": {"thinking": "trace", "content": ""}},
                    {"message": {"content": "final"}},
                    {"done": True, "done_reason": "stop", "eval_count": 7},
                ]
            ),
        ):
            events = list(
                ollama_runtime.chat_completion_stream_events(
                    "qwen3:8b",
                    messages=messages,
                    think=True,
                )
            )

        self.assertEqual("".join(event.reasoning for event in events), "reason trace")
        self.assertEqual("".join(event.content for event in events), "final")
        self.assertTrue(events[-1].done)
        self.assertEqual(events[-1].done_reason, "stop")

    def test_ollama_chat_retries_metal_failure_with_cpu_fallback(self):
        messages = [{"role": "user", "content": "hello"}]
        metal_error = RuntimeError(
            "Ollama API error 500: ggml_metal_init: error: failed to initialize the Metal library; "
            "llama_init_from_model: failed to initialize Metal backend"
        )

        with (
            patch.object(
                ollama_runtime,
                "_post_json",
                side_effect=[metal_error, metal_error, {"message": {"content": "ok"}}],
            ) as post_json,
            patch.object(ollama_runtime, "unload_model", return_value=True) as unload_model,
            patch.object(ollama_runtime.time, "sleep"),
        ):
            reply = ollama_runtime.chat_completion(
                "qwen2.5:7b-instruct",
                messages=messages,
                temperature=0.1,
                max_tokens=5,
                keep_alive="45s",
            )

        self.assertEqual(reply, "ok")
        self.assertEqual(post_json.call_count, 3)
        cpu_payload = post_json.call_args_list[-1].args[1]
        self.assertEqual(cpu_payload["options"]["num_gpu"], 0)
        self.assertEqual(cpu_payload["keep_alive"], 0)
        self.assertEqual(unload_model.call_count, 2)
        unload_model.assert_called_with("qwen2.5:7b-instruct", timeout=1.5)

    def test_ollama_chat_can_disable_cpu_fallback(self):
        messages = [{"role": "user", "content": "hello"}]
        metal_error = RuntimeError(
            "Ollama API error 500: ggml_metal_init: error: failed to initialize the Metal library; "
            "llama_init_from_model: failed to initialize Metal backend"
        )

        with (
            patch.object(ollama_runtime, "_post_json", side_effect=[metal_error, metal_error]) as post_json,
            patch.object(ollama_runtime, "unload_model", return_value=True) as unload_model,
            patch.object(ollama_runtime.time, "sleep"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                ollama_runtime.chat_completion(
                    "qwen2.5:7b-instruct",
                    messages=messages,
                    temperature=0.1,
                    max_tokens=5,
                    keep_alive="45s",
                    allow_cpu_fallback=False,
                )

        self.assertIn("CPU fallback is disabled", str(ctx.exception))
        self.assertEqual(post_json.call_count, 2)
        unload_model.assert_called_once_with("qwen2.5:7b-instruct", timeout=1.5)

    def test_ollama_chat_stream_retries_metal_failure_with_cpu_fallback(self):
        messages = [{"role": "user", "content": "hello"}]
        metal_error = RuntimeError(
            "Ollama API error 500: ggml_metal_init: error: failed to initialize the Metal library; "
            "llama_init_from_model: failed to initialize Metal backend"
        )

        with (
            patch.object(
                ollama_runtime,
                "_post_json_stream",
                side_effect=[
                    metal_error,
                    metal_error,
                    iter([{"message": {"content": "ok"}}, {"done": True}]),
                ],
            ) as post_stream,
            patch.object(ollama_runtime, "unload_model", return_value=True) as unload_model,
            patch.object(ollama_runtime.time, "sleep"),
        ):
            chunks = list(
                ollama_runtime.chat_completion_stream(
                    "qwen2.5:7b-instruct",
                    messages=messages,
                    temperature=0.1,
                    max_tokens=5,
                    keep_alive="45s",
                )
            )

        self.assertEqual(chunks, ["ok"])
        self.assertEqual(post_stream.call_count, 3)
        cpu_payload = post_stream.call_args_list[-1].args[1]
        self.assertEqual(cpu_payload["options"]["num_gpu"], 0)
        self.assertEqual(cpu_payload["keep_alive"], 0)
        self.assertEqual(unload_model.call_count, 2)
        unload_model.assert_called_with("qwen2.5:7b-instruct", timeout=1.5)

    def test_ollama_chat_can_force_cpu_runner(self):
        messages = [{"role": "user", "content": "hello"}]

        with (
            patch.object(ollama_runtime, "_post_json", return_value={"message": {"content": "ok"}}) as post_json,
            patch.object(ollama_runtime, "unload_model", return_value=True) as unload_model,
        ):
            reply = ollama_runtime.chat_completion(
                "qwen2.5:7b-instruct",
                messages=messages,
                temperature=0.1,
                max_tokens=5,
                keep_alive="0",
                num_gpu=0,
            )

        self.assertEqual(reply, "ok")
        payload = post_json.call_args.args[1]
        self.assertEqual(payload["options"]["num_gpu"], 0)
        self.assertEqual(payload["keep_alive"], "0")
        unload_model.assert_called_once_with("qwen2.5:7b-instruct", timeout=1.5)

    def test_valid_router_decision_uses_intent_target(self):
        raw = json.dumps(
            {
                "intent": "code",
                "target_model": "qwen2.5-coder:7b",
                "confidence": 0.86,
                "reason": "Запрос связан с кодом.",
            },
            ensure_ascii=False,
        )

        decision = model_router.validate_router_decision(raw)

        self.assertFalse(decision.fallback)
        self.assertEqual(decision.intent, "code")
        self.assertEqual(decision.target_model, "qwen2.5-coder:7b")
        self.assertEqual(decision.confidence, 0.86)

    def test_router_decision_corrects_target_by_intent(self):
        raw = json.dumps(
            {
                "intent": "thinking",
                "target_model": "qwen2.5-coder:7b",
                "confidence": 0.9,
                "reason": "Нужен анализ.",
            },
            ensure_ascii=False,
        )

        decision = model_router.validate_router_decision(raw)

        self.assertFalse(decision.fallback)
        self.assertEqual(decision.intent, "thinking")
        self.assertEqual(decision.target_model, "qwen3:8b")

    def test_code_compare_uses_qwen_coder_in_auto_router(self):
        raw = json.dumps(
            {
                "intent": "code_compare",
                "target_model": "deepseek-coder:6.7b",
                "confidence": 0.9,
                "reason": "Нужно сравнить варианты кода.",
            },
            ensure_ascii=False,
        )

        decision = model_router.validate_router_decision(raw)

        self.assertFalse(decision.fallback)
        self.assertEqual(decision.intent, "code_compare")
        self.assertEqual(decision.target_model, "qwen2.5-coder:7b")

    def test_invalid_json_falls_back_to_default_chat(self):
        decision = model_router.validate_router_decision("```json\n{}\n```")

        self.assertTrue(decision.fallback)
        self.assertEqual(decision.fallback_reason, "invalid_json")
        self.assertEqual(decision.intent, "unknown")
        self.assertEqual(decision.target_model, "qwen2.5:7b-instruct")

    def test_low_confidence_falls_back_to_default_chat(self):
        raw = json.dumps(
            {
                "intent": "code",
                "target_model": "qwen2.5-coder:7b",
                "confidence": 0.59,
                "reason": "Не уверен.",
            },
            ensure_ascii=False,
        )

        decision = model_router.validate_router_decision(raw)

        self.assertTrue(decision.fallback)
        self.assertEqual(decision.fallback_reason, "low_confidence")
        self.assertEqual(decision.target_model, "qwen2.5:7b-instruct")

    def test_explicit_html_code_request_overrides_default_chat_decision(self):
        raw = json.dumps(
            {
                "intent": "default_chat",
                "target_model": "qwen2.5:7b-instruct",
                "confidence": 0.82,
                "reason": "Запрос про список SEO-тарифов.",
            },
            ensure_ascii=False,
        )
        decision = model_router.validate_router_decision(raw)

        corrected = model_router.correct_router_decision(
            "Круто, а теперь сделай мне HTML-код, который просто выведет на странице список только SEO-тарифов.",
            decision,
        )

        self.assertEqual(corrected.intent, "code")
        self.assertEqual(corrected.target_model, "qwen2.5-coder:7b")
        self.assertTrue(corrected.backend_override)
        self.assertEqual(corrected.backend_override_reason, "explicit_code_request")

    def test_code_request_override_applies_after_low_confidence_fallback(self):
        raw = json.dumps(
            {
                "intent": "code",
                "target_model": "qwen2.5-coder:7b",
                "confidence": 0.4,
                "reason": "Не уверен.",
            },
            ensure_ascii=False,
        )
        decision = model_router.validate_router_decision(raw)

        corrected = model_router.correct_router_decision("Напиши JS код для кнопки", decision)

        self.assertEqual(corrected.intent, "code")
        self.assertEqual(corrected.target_model, "qwen2.5-coder:7b")
        self.assertFalse(corrected.fallback)

    def test_simple_rag_lookup_overrides_default_chat_decision(self):
        raw = json.dumps(
            {
                "intent": "default_chat",
                "target_model": "qwen2.5:7b-instruct",
                "confidence": 0.78,
                "reason": "Обычный вопрос о тарифах.",
            },
            ensure_ascii=False,
        )
        decision = model_router.validate_router_decision(raw)

        corrected = model_router.correct_router_decision(
            "Ты мне можешь данные из РАК вытащить просто в одну строчку, какие есть тарифы, самые минимальные тарифы?",
            decision,
            {"rag_enabled": False},
        )

        self.assertEqual(corrected.intent, "quick_rag")
        self.assertEqual(corrected.target_model, "qwen2.5:7b-instruct")
        self.assertTrue(corrected.backend_override)
        self.assertEqual(corrected.backend_override_reason, "simple_rag_lookup")

    def test_rag_enabled_tariff_listing_uses_quick_rag(self):
        raw = json.dumps(
            {
                "intent": "default_chat",
                "target_model": "qwen2.5:7b-instruct",
                "confidence": 0.81,
                "reason": "Запрос требует обычного ответа.",
            },
            ensure_ascii=False,
        )
        decision = model_router.validate_router_decision(raw)

        corrected = model_router.correct_router_decision(
            "Мне нужно перечислить, какие есть вообще тарифы SEO, технической поддержки, есть ли депозит у компании.",
            decision,
            {"rag_enabled": True},
        )

        self.assertEqual(corrected.intent, "quick_rag")
        self.assertEqual(corrected.target_model, "qwen2.5:7b-instruct")

    def test_rag_pricing_followup_uses_recent_history_for_quick_rag(self):
        raw = json.dumps(
            {
                "intent": "default_chat",
                "target_model": "qwen2.5:7b-instruct",
                "confidence": 0.81,
                "reason": "Короткое уточнение.",
            },
            ensure_ascii=False,
        )
        decision = model_router.validate_router_decision(raw)

        corrected = model_router.correct_router_decision(
            "это точно самый минимальный? проверь хорошо",
            decision,
            {
                "rag_enabled": True,
                "recent_user_queries": [
                    "Выведи минимальный тариф технической поддержки и самый маленький тариф SEO.",
                ],
            },
        )

        self.assertEqual(corrected.intent, "quick_rag")
        self.assertEqual(corrected.target_model, "qwen2.5:7b-instruct")

    def test_rag_tariff_message_request_stays_default_chat(self):
        raw = json.dumps(
            {
                "intent": "default_chat",
                "target_model": "qwen2.5:7b-instruct",
                "confidence": 0.81,
                "reason": "Нужно написать текст.",
            },
            ensure_ascii=False,
        )
        decision = model_router.validate_router_decision(raw)

        corrected = model_router.correct_router_decision(
            "Напиши сообщение клиенту про тарифы SEO из RAG.",
            decision,
            {"rag_enabled": True},
        )

        self.assertEqual(corrected.intent, "default_chat")
        self.assertEqual(corrected.target_model, "qwen2.5:7b-instruct")

    def test_calculation_decision_routes_to_fallback_llm(self):
        raw = json.dumps(
            {
                "intent": "calculation",
                "target_model": "__local_calculator__",
                "confidence": 0.91,
                "reason": "Нужен точный расчёт.",
                "calculation_request": {
                    "operation": "sum_and_convert_to_minutes",
                    "items": [
                        {"value": 1.5, "unit": "hours"},
                        {"value": 35, "unit": "minutes"},
                    ],
                },
            },
            ensure_ascii=False,
        )

        decision = model_router.validate_router_decision(raw)

        self.assertFalse(decision.fallback)
        self.assertEqual(decision.target_model, "qwen2.5:7b-instruct")
        self.assertEqual(decision.calculation_request["operation"], "sum_and_convert_to_minutes")

    def test_local_calculator_sums_hours_and_minutes(self):
        result = local_calculator.calculate(
            {
                "operation": "sum_and_convert_to_minutes",
                "items": [
                    {"value": 1.5, "unit": "hours"},
                    {"value": 35, "unit": "minutes"},
                ],
            }
        )

        self.assertIn("125 минут", result["result"])
        self.assertIn("90 минут", result["details"])

    def test_local_calculator_multiplies_hours_by_rate(self):
        result = local_calculator.calculate({"operation": "multiply_hours_by_rate", "hours": 2.5, "rate": 1200})

        self.assertEqual(result["result"], "3000 ₽")
        self.assertIn("2.5 ч", result["details"])

    def test_local_calculator_sums_plain_numbers_from_text(self):
        result = local_calculator.calculate({"operation": "basic_arithmetic"}, "Сумма (7339.50 7339.50)")

        self.assertEqual(result["result"], "14679.00")
        self.assertIn("7339.50 + 7339.50 = 14679.00", result["details"])

    def test_local_calculator_supports_text_operations_and_fractions(self):
        cases = [
            ("3289141.59 минус 1", "3289140.59"),
            ("умножить 5 на 6", "30"),
            ("195923 умножить на 2", "391846"),
            ("разделить 10 на 2", "5"),
            ("195923 разделить на 2", "97961.5"),
            ("расстелить 10 на 2", "5"),
            ("391846.00 /2 и умножить на 3", "587769"),
            ("одна пятая плюс две пятых", "0.6"),
            ("одна пятая от 100", "20"),
        ]

        for query, expected in cases:
            with self.subTest(query=query):
                result = local_calculator.try_calculate_text(query, force=True)
                self.assertIsNotNone(result)
                self.assertEqual(result["result"], expected)

    def test_local_calculator_supports_text_average(self):
        result = local_calculator.try_calculate_text(
            "среднее значение суммы чисел 17940.00\n7339.50\n56810.00\n29900.00\n18837.00\n240030.00\n20989.50",
            force=True,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["result"], "55978.00")
        self.assertIn("/ 7 = 55978.00", result["details"])

    def test_local_calculator_does_not_auto_match_timezone_context(self):
        result = local_calculator.try_calculate_text("так, в москве +3, а в сеуле?")

        self.assertIsNone(result)

    def test_model_list_exposes_router_as_utility_not_recommended(self):
        installed = [{"name": "qwen3:0.6b"}, {"name": "qwen2.5:7b-instruct"}]
        with (
            patch.object(model_service, "_list_local_models", return_value=installed),
            patch.object(model_service, "_pull_statuses", return_value=[]),
        ):
            data = model_service.list_models()

        catalog_ids = [item["id"] for item in data["catalog"]]
        utility_ids = [item["id"] for item in data["utility"]]

        self.assertEqual(catalog_ids, [item["id"] for item in config.MODEL_CATALOG])
        self.assertEqual(len(catalog_ids), 7)
        self.assertEqual(utility_ids, ["qwen3:0.6b"])
        self.assertNotIn("qwen3:0.6b", catalog_ids)
        self.assertNotIn("qwen3:0.6b", [item["id"] for item in data["recommended"]])
        self.assertTrue(data["utility"][0]["installed"])


class AutoRouterChatFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.tmpdir.name) / "localgpt-test.db"
        db.init_db()
        self.profile_id = db.ensure_default_profile()
        model_residency.reset_state()

    def tearDown(self):
        model_residency.reset_state()
        self.tmpdir.cleanup()

    def test_auto_router_requires_router_model(self):
        req = ChatRequest(query="Объясни коротко", profile_id=self.profile_id, model_name=model_router.AUTO_MODEL_ID)

        with patch.object(model_service, "is_model_installed", return_value=False):
            task = start_chat_task(req)

        self.assertEqual(task["state"], "failed")
        self.assertEqual(task["error_code"], "router_model_missing")
        self.assertEqual(task["model_name"], "qwen3:0.6b")
        self.assertIsNotNone(task["user_message_id"])
        self.assertIsNotNone(task["assistant_message_id"])
        messages = db.get_messages(task["session_id"])
        self.assertEqual([item["role"] for item in messages], ["user", "assistant"])
        self.assertEqual(messages[0]["content"], "Объясни коротко")
        self.assertEqual(messages[1]["status"], "failed")
        self.assertEqual(messages[1]["task_id"], task["id"])
        self.assertIn("Router-модель", messages[1]["error"])

    def test_auto_router_calculation_uses_fallback_llm_not_local_calculator(self):
        req = ChatRequest(query="Сколько минут: 1.5 часа плюс 35 минут?", profile_id=self.profile_id, model_name=model_router.AUTO_MODEL_ID)
        decision = model_router.RouterDecision(
            intent="calculation",
            target_model="qwen2.5:7b-instruct",
            confidence=0.91,
            reason="Запрос требует точного арифметического расчёта.",
            calculation_request={
                "operation": "sum_and_convert_to_minutes",
                "items": [
                    {"value": 1.5, "unit": "hours"},
                    {"value": 35, "unit": "minutes"},
                ],
            },
        )

        with (
            patch.object(model_service, "is_model_installed", return_value=True),
            patch.object(model_router, "route_model", return_value=decision),
        ):
            prepared = _apply_auto_router(_prepare_chat_request(req))

        self.assertEqual(prepared["target_model"], "qwen2.5:7b-instruct")
        self.assertIsNone(prepared["calc_result"])
        self.assertEqual(prepared["effective_settings"]["model_selection_mode"], "auto")
        self.assertEqual(prepared["effective_settings"]["router_intent"], "calculation")

    def test_auto_router_explicit_sum_still_uses_router_model(self):
        req = ChatRequest(query="Сумма (7339.50 7339.50)", profile_id=self.profile_id, model_name=model_router.AUTO_MODEL_ID)
        decision = model_router.RouterDecision(
            intent="calculation",
            target_model="qwen2.5:7b-instruct",
            confidence=0.91,
            reason="Запрос требует точного арифметического расчёта.",
        )

        with (
            patch.object(model_service, "is_model_installed", return_value=True),
            patch.object(model_router, "route_model", return_value=decision) as route_model,
        ):
            prepared = _apply_auto_router(_prepare_chat_request(req))

        route_model.assert_called_once()
        self.assertEqual(prepared["target_model"], "qwen2.5:7b-instruct")
        self.assertIsNone(prepared["calc_result"])
        self.assertEqual(prepared["effective_settings"]["router_intent"], "calculation")

    def test_auto_router_defensively_falls_back_if_router_returns_local_calculator(self):
        req = ChatRequest(query="Сумма (7339.50 7339.50)", profile_id=self.profile_id, model_name=model_router.AUTO_MODEL_ID)
        decision = model_router.RouterDecision(
            intent="calculation",
            target_model=model_router.LOCAL_CALCULATOR_TARGET,
            confidence=0.91,
            reason="Запрос требует точного арифметического расчёта.",
        )

        with (
            patch.object(model_service, "is_model_installed", return_value=True),
            patch.object(model_router, "route_model", return_value=decision),
        ):
            prepared = _apply_auto_router(_prepare_chat_request(req))

        self.assertEqual(prepared["target_model"], "qwen2.5:7b-instruct")
        self.assertIsNone(prepared["calc_result"])
        self.assertTrue(prepared["effective_settings"]["router_fallback"])
        self.assertEqual(prepared["effective_settings"]["router_fallback_reason"], "calculator_manual_only")

    def test_auto_router_task_never_completes_with_local_calculator(self):
        req = ChatRequest(query="Сумма (7339.50 7339.50)", profile_id=self.profile_id, model_name=model_router.AUTO_MODEL_ID)
        decision = model_router.RouterDecision(
            intent="calculation",
            target_model=model_router.LOCAL_CALCULATOR_TARGET,
            confidence=0.91,
            reason="Запрос требует точного арифметического расчёта.",
        )

        with (
            patch.object(model_service, "is_model_installed", return_value=True),
            patch.object(model_router, "route_model", return_value=decision),
            patch("backend.apps.chat.routes.chat_tasks.start_chat_task") as start_task,
        ):
            start_task.return_value = {
                "id": "ct_test",
                "state": "generating",
                "session_id": "s_test",
                "profile_id": self.profile_id,
                "model_name": "qwen2.5:7b-instruct",
                "used_settings": {},
            }
            task = start_chat_task(req)

        self.assertEqual(task["state"], "generating")
        start_task.assert_called_once()
        self.assertEqual(start_task.call_args.kwargs["model_name"], "qwen2.5:7b-instruct")

    def test_auto_router_stream_true_only_applies_to_final_answer_task(self):
        req = ChatRequest(
            query="Напиши HTML код кнопки",
            profile_id=self.profile_id,
            model_name=model_router.AUTO_MODEL_ID,
            stream=True,
        )
        router_payload = json.dumps(
            {
                "intent": "code",
                "target_model": "qwen2.5-coder:7b",
                "confidence": 0.91,
                "reason": "Запрос связан с кодом.",
            },
            ensure_ascii=False,
        )

        def fake_start_task(**kwargs):
            return {
                "id": "ct_auto_stream",
                "task_id": "ct_auto_stream",
                "state": "generating",
                "session_id": kwargs["session_id"],
                "conversation_id": kwargs["session_id"],
                "profile_id": kwargs["profile_id"],
                "model_name": kwargs["model_name"],
                "role": kwargs["role"],
                "user_message_id": kwargs["user_message_id"],
                "assistant_message_id": kwargs["assistant_message_id"],
                "message": "Chat generation started.",
                "error_code": None,
                "pid": 123,
                "used_settings": kwargs["used_settings"],
                "router_notice": kwargs["router_notice"],
                "result": None,
                "stream": bool(kwargs.get("stream")),
                "streaming_enabled": bool(kwargs.get("stream")),
            }

        with (
            patch.object(model_service, "is_model_installed", return_value=True),
            patch.object(ollama_runtime, "chat_completion", return_value=router_payload) as router_chat,
            patch.object(ollama_runtime, "chat_completion_stream") as router_stream,
            patch("backend.apps.chat.routes.chat_tasks.start_chat_task", side_effect=fake_start_task) as start_task,
        ):
            task = start_chat_task(req)

        router_chat.assert_called_once()
        router_stream.assert_not_called()
        start_task.assert_called_once()
        self.assertEqual(start_task.call_args.kwargs["model_name"], "qwen2.5-coder:7b")
        self.assertTrue(start_task.call_args.kwargs["stream"])
        self.assertEqual(start_task.call_args.kwargs["used_settings"]["model_selection_mode"], "auto")
        self.assertTrue(task["stream"])

    def test_manual_local_calculator_model_uses_local_calculator(self):
        req = ChatRequest(query="Сумма (7339.50 7339.50)", profile_id=self.profile_id, model_name=model_router.LOCAL_CALCULATOR_TARGET)

        with patch.object(model_service, "is_model_installed") as installed:
            task = start_chat_task(req)

        installed.assert_not_called()
        self.assertEqual(task["state"], "completed")
        self.assertEqual(task["model_name"], model_router.LOCAL_CALCULATOR_TARGET)
        self.assertIn("14679.00", task["result"]["reply"])
        self.assertEqual(task["used_settings"]["model_selection_mode"], "calculator")

    def test_manual_explicit_sum_with_llm_does_not_use_local_calculator(self):
        req = ChatRequest(query="посчитай сумму 7339.50 7339.50", profile_id=self.profile_id, model_name="qwen2.5:7b-instruct")

        prepared = _apply_auto_router(_prepare_chat_request(req))

        self.assertEqual(prepared["target_model"], "qwen2.5:7b-instruct")
        self.assertIsNone(prepared["calc_result"])
        self.assertEqual(prepared["effective_settings"]["model_selection_mode"], "manual")
        self.assertNotIn("calculator_backend_override", prepared["effective_settings"])

    def test_auto_router_target_model_must_be_installed(self):
        req = ChatRequest(query="Исправь этот Python код", profile_id=self.profile_id, model_name=model_router.AUTO_MODEL_ID)
        decision = model_router.RouterDecision(
            intent="code",
            target_model="qwen2.5-coder:7b",
            confidence=0.86,
            reason="Запрос связан с кодом.",
        )

        def installed(model_name):
            return model_name == model_router.ROUTER_MODEL_ID

        with (
            patch.object(model_service, "is_model_installed", side_effect=installed),
            patch.object(model_router, "route_model", return_value=decision),
        ):
            task = start_chat_task(req)

        self.assertEqual(task["state"], "failed")
        self.assertEqual(task["error_code"], "chat_auto_target_model_missing")
        self.assertEqual(task["model_name"], "qwen2.5-coder:7b")
        messages = db.get_messages(task["session_id"])
        self.assertEqual([item["role"] for item in messages], ["user", "assistant"])
        self.assertEqual(messages[1]["status"], "failed")
        self.assertEqual(messages[1]["model"], "qwen2.5-coder:7b")
        self.assertIn("Auto выбрал модель", messages[1]["error"])

    def test_model_settings_persist_ollama_keep_alive(self):
        db.upsert_model_settings(
            self.profile_id,
            "qwen2.5:7b-instruct",
            temperature=0.25,
            max_tokens=1024,
            num_ctx=4096,
            mem_turns=6,
            ollama_keep_alive="45s",
        )

        settings = db.effective_settings(self.profile_id, "qwen2.5:7b-instruct", config.DEFAULT_SETTINGS)

        self.assertEqual(settings["effective"]["ollama_keep_alive"], "45s")
        self.assertEqual(settings["overrides"]["ollama_keep_alive"], "45s")

    def test_model_settings_persist_independent_token_budgets(self):
        db.upsert_model_settings(
            self.profile_id,
            "qwen3:8b",
            output_tokens=700,
            thinking_tokens=1300,
            ollama_think="on",
        )

        settings = db.effective_settings(self.profile_id, "qwen3:8b", config.DEFAULT_SETTINGS)

        self.assertEqual(settings["effective"]["output_tokens"], 700)
        self.assertEqual(settings["effective"]["max_tokens"], 700)
        self.assertEqual(settings["effective"]["thinking_tokens"], 1300)
        self.assertEqual(settings["overrides"]["output_tokens"], 700)
        self.assertEqual(settings["overrides"]["thinking_tokens"], 1300)

    def test_legacy_max_tokens_migrates_to_output_tokens(self):
        db.upsert_model_settings(self.profile_id, "qwen3:8b", max_tokens=777)
        with sqlite3.connect(db.DB_PATH) as conn:
            conn.execute(
                "UPDATE model_settings SET output_tokens = NULL WHERE profile_id = ? AND model_name = ?",
                (self.profile_id, "qwen3:8b"),
            )
            conn.commit()

        db.init_db()
        settings = db.effective_settings(self.profile_id, "qwen3:8b", config.DEFAULT_SETTINGS)

        self.assertEqual(settings["effective"]["output_tokens"], 777)
        self.assertEqual(settings["overrides"]["output_tokens"], 777)

    def test_generation_budget_policy_separates_on_and_off_semantics(self):
        enabled = apply_generation_budget_policy(
            {"output_tokens": 700, "thinking_tokens": 1300, "ollama_think": "on"}
        )
        disabled = apply_generation_budget_policy(
            {"output_tokens": 700, "thinking_tokens": 1300, "ollama_think": "off"}
        )

        self.assertEqual(enabled["provider_num_predict"], 2000)
        self.assertEqual(enabled["generation_budget_policy"], "combined_compatibility_cap")
        self.assertTrue(enabled["thinking_budget_applied"])
        self.assertFalse(enabled["native_reasoning_budget_supported"])
        self.assertEqual(disabled["provider_num_predict"], 700)
        self.assertEqual(disabled["generation_budget_policy"], "output_only")
        self.assertFalse(disabled["thinking_budget_applied"])

        qwen3_disabled = apply_generation_budget_policy(
            {"output_tokens": 700, "thinking_tokens": 1300, "ollama_think": "off"},
            model_name="qwen3:8b",
        )
        self.assertEqual(qwen3_disabled["provider_num_predict"], 2000)
        self.assertEqual(
            qwen3_disabled["generation_budget_policy"],
            "qwen3_off_structural_compatibility_cap",
        )
        self.assertTrue(qwen3_disabled["thinking_budget_applied"])

    def test_runtime_uses_combined_cap_for_thinking_on_and_qwen3_structural_off(self):
        service = ChatService()
        enabled = service._runtime_kwargs(
            "qwen3:8b",
            {"output_tokens": 700, "thinking_tokens": 1300, "ollama_think": "on"},
        )
        disabled = service._runtime_kwargs(
            "qwen3:8b",
            {"output_tokens": 700, "thinking_tokens": 1300, "ollama_think": "off"},
        )

        self.assertEqual(enabled["max_tokens"], 2000)
        self.assertTrue(enabled["think"])
        self.assertEqual(disabled["max_tokens"], 2000)
        self.assertFalse(disabled["think"])

        instruct_disabled = service._runtime_kwargs(
            "qwen2.5:7b-instruct",
            {"output_tokens": 700, "thinking_tokens": 1300, "ollama_think": "off"},
        )
        self.assertEqual(instruct_disabled["max_tokens"], 700)
        self.assertFalse(instruct_disabled["think"])

    def test_mem_turns_is_profile_setting_not_model_override(self):
        profile = db.update_profile_preferences(self.profile_id, {"settings": {"mem_turns": 10}})
        self.assertEqual(profile["preferences"]["settings"]["mem_turns"], 10)
        db.upsert_model_settings(
            self.profile_id,
            "qwen2.5:7b-instruct",
            temperature=0.25,
            max_tokens=1024,
            num_ctx=4096,
            mem_turns=3,
        )

        settings = db.effective_settings(self.profile_id, "qwen2.5:7b-instruct", config.DEFAULT_SETTINGS)

        self.assertEqual(settings["effective"]["mem_turns"], 10)
        self.assertEqual(settings["overrides"]["mem_turns"], 10)

    def test_manual_chat_preparation_applies_model_keep_alive_default(self):
        req = ChatRequest(query="hello", profile_id=self.profile_id, model_name="mistral-nemo:12b")

        prepared = _apply_auto_router(_prepare_chat_request(req))

        self.assertEqual(prepared["effective_settings"]["target_keep_alive"], "5m")
        self.assertEqual(prepared["effective_settings"]["ollama_keep_alive_effective"], "5m")

    def test_auto_router_target_model_uses_residency_policy(self):
        req = ChatRequest(query="Напиши HTML код кнопки", profile_id=self.profile_id, model_name=model_router.AUTO_MODEL_ID)
        decision = model_router.RouterDecision(
            intent="code",
            target_model="qwen2.5-coder:7b",
            confidence=0.86,
            reason="Запрос связан с кодом.",
            runtime_debug={"router_keep_alive": "2m"},
        )

        with (
            patch.object(model_service, "is_model_installed", return_value=True),
            patch.object(model_router, "route_model", return_value=decision),
            patch.object(ollama_runtime, "unload_model", return_value=True),
        ):
            prepared = _apply_auto_router(_prepare_chat_request(req))

        self.assertEqual(prepared["target_model"], "qwen2.5-coder:7b")
        self.assertEqual(prepared["effective_settings"]["model_selection_mode"], "auto")
        self.assertEqual(prepared["effective_settings"]["target_keep_alive"], "2m")
        self.assertEqual(prepared["effective_settings"]["max_resident_target_models"], 1)

    def test_mistral_nemo_code_request_gets_model_specific_hint(self):
        req = ChatRequest(query="напиши html + js для круга со свечением", profile_id=self.profile_id, model_name="mistral-nemo:12b")

        prepared = _prepare_chat_request(req)

        self.assertTrue(prepared["effective_settings"]["mistral_code_request_hint"])
        self.assertIn("пользователь просит обычный безопасный программный код", prepared["messages"][-1]["content"])
        self.assertIn("Исходный запрос пользователя", prepared["messages"][-1]["content"])

    def test_mistral_nemo_hint_does_not_apply_to_other_models(self):
        req = ChatRequest(query="напиши html + js для круга со свечением", profile_id=self.profile_id, model_name="qwen2.5-coder:7b")

        prepared = _prepare_chat_request(req)

        self.assertNotIn("mistral_code_request_hint", prepared["effective_settings"])
        self.assertNotIn("пользователь просит обычный безопасный программный код", prepared["messages"][-1]["content"])


if __name__ == "__main__":
    unittest.main()
