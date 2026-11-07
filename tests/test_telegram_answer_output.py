import unittest
from fastapi import HTTPException
from backend.apps.chat.service import enforce_protected_output, guard_stream_events
from backend.apps.chat.services.ollama_runtime import ChatStreamEvent
from backend.apps.rag.service import telegram_search_cards
from backend.apps.rag.retrieval import split_query_facets


class TelegramAnswerOutputTests(unittest.TestCase):
    def test_lookup_keeps_exact_evidence_and_locator(self):
        evidence = [{"source_id": "messages2.html", "content": "Установил Ollama и FastAPI. ```", "provenance": {"message_id": "message42", "timestamp": "2026-07-18 14:18:28", "author": "Тест"}, "truncated": True}]
        answer = telegram_search_cards("Найди сообщения про Ollama", evidence)
        for value in ["messages2.html", "message42", "2026-07-18 14:18:28", evidence[0]["content"], "сокращён", "Кандидаты"]:
            self.assertIn(value, answer)
        self.assertIn("````text", answer)
        self.assertIsNone(telegram_search_cards("Объясни этот стек", evidence))
        self.assertIsNone(telegram_search_cards("Найди сообщения", [{"content": "markdown"}]))
        self.assertIsNone(telegram_search_cards("Найди сообщения", []))

    def test_topics_split_without_requiring_their_joint_occurrence(self):
        facets = split_query_facets("MAX, силовики, ТЦК, война Россия-Украина")
        self.assertEqual(len(facets), 4)

    def test_transport_format_is_blocked_without_any_private_literals(self):
        with self.assertRaises(HTTPException) as error:
            enforce_protected_output([], '[LOCALGPT_DATA_ENVELOPE trust_class=L4]')
        self.assertEqual(error.exception.detail['code'], 'model_output_transport_envelope')

    def test_stream_never_exposes_split_envelope_marker(self):
        for size in [1, 3, 17, 100]:
            raw = 'Ответ: [LOCALGPT_DATA_ENVELOPE trust_class=L4] JSON'
            visible = []
            with self.assertRaises(HTTPException):
                for event in guard_stream_events([], [ChatStreamEvent(content=raw[i:i+size]) for i in range(0, len(raw), size)]):
                    visible.append(event.content)
            self.assertNotIn('[LOCALGPT_', ''.join(visible))

    def test_ordinary_stream_remains_exact(self):
        events = [ChatStreamEvent(content='Обычный ответ.'), ChatStreamEvent(done=True)]
        self.assertEqual(''.join(e.content for e in guard_stream_events([], events)), 'Обычный ответ.')
