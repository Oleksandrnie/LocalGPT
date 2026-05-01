import json
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
from backend.apps.chat.services import local_calculator, model_residency, model_router, ollama_runtime


class ModelRouterTestCase(unittest.TestCase):
    def test_auto_model_aliases(self):
        self.assertTrue(model_router.is_auto_model("__auto_router__"))
        self.assertTrue(model_router.is_auto_model("Auto / Smart Router"))
        self.assertFalse(model_router.is_auto_model("qwen2.5:7b-instruct"))

    def test_ollama_keep_alive_defaults_by_model(self):
        self.assertEqual(ollama_runtime.resolve_keep_alive("qwen2.5:7b-instruct", {}), "4m")
        self.assertEqual(model_residency.resolve_model_keep_alive("qwen2.5:7b-instruct", {}, mode="auto"), "4m")
        self.assertEqual(model_residency.resolve_model_keep_alive("qwen2.5-coder:7b", {}, mode="auto"), "2m")
        self.assertEqual(ollama_runtime.resolve_keep_alive("mistral-nemo:12b", {}), "60s")
        self.assertEqual(ollama_runtime.resolve_keep_alive(model_router.ROUTER_MODEL_ID, {}, router=True), "2m")
        self.assertEqual(
            ollama_runtime.resolve_keep_alive("qwen2.5:7b-instruct", {"ollama_keep_alive": "45s"}),
            "45s",
        )

    def test_residency_limit_evicts_oldest_target_model(self):
        model_residency.reset_state()
        settings = {"max_resident_target_models": 2, "single_large_target_model": False}

        with patch.object(ollama_runtime, "unload_model", return_value=True) as unload_model:
            model_residency.apply_target_settings("qwen2.5:3b-instruct", settings, mode="auto")
            model_residency.apply_target_settings("qwen2.5:7b-instruct", settings, mode="auto")
            third = model_residency.apply_target_settings("qwen2.5-coder:7b", settings, mode="auto")

        self.assertEqual(
            model_residency.snapshot_state()["active_target_models"],
            ["qwen2.5:7b-instruct", "qwen2.5-coder:7b"],
        )
        unload_model.assert_called_once_with("qwen2.5:3b-instruct")
        self.assertEqual(third["evicted_model"], "qwen2.5:3b-instruct")
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
            ["qwen2.5:3b-instruct", "qwen2.5-coder:7b"],
        )
        unload_model.assert_called_once_with("qwen2.5:7b-instruct")
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
        self.assertEqual(heavy["target_keep_alive"], "60s")
        self.assertEqual(heavy["eviction_policy"], "heavy_policy")
        self.assertEqual(
            [call.args[0] for call in unload_model.call_args_list],
            ["qwen2.5:3b-instruct", "qwen2.5:7b-instruct"],
        )

    def test_chat_completion_passes_keep_alive_to_native_ollama_request(self):
        service = ChatService()
        messages = [{"role": "user", "content": "hello"}]

        with patch.object(ollama_runtime, "chat_completion", return_value="ok") as native_chat:
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
            with self.assertRaises(HTTPException) as ctx:
                start_chat_task(req)

        self.assertEqual(ctx.exception.status_code, 424)
        self.assertEqual(ctx.exception.detail["code"], "router_model_missing")
        self.assertEqual(ctx.exception.detail["model"], "qwen3:0.6b")

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
                "state": "running",
                "session_id": "s_test",
                "profile_id": self.profile_id,
                "model_name": "qwen2.5:7b-instruct",
                "used_settings": {},
            }
            task = start_chat_task(req)

        self.assertEqual(task["state"], "running")
        start_task.assert_called_once()
        self.assertEqual(start_task.call_args.kwargs["model_name"], "qwen2.5:7b-instruct")

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
            with self.assertRaises(HTTPException) as ctx:
                start_chat_task(req)

        self.assertEqual(ctx.exception.status_code, 424)
        self.assertEqual(ctx.exception.detail["code"], "chat_auto_target_model_missing")
        self.assertEqual(ctx.exception.detail["model"], "qwen2.5-coder:7b")

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

        self.assertEqual(prepared["effective_settings"]["target_keep_alive"], "60s")
        self.assertEqual(prepared["effective_settings"]["ollama_keep_alive_effective"], "60s")

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
        self.assertEqual(prepared["effective_settings"]["max_resident_target_models"], 2)

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
