# LocalGPT Technical README

Технический документ для обсуждения с инженерами и/или ИИ-ассистентами.
Фокус: как формируется контекст, как работает «память» диалога и как управляются токены на входе/выходе.

## 1. Runtime-схема

- Backend: `FastAPI` (`backend.server:app`) с разделением на mini-app (`chat/asr/tts/ocr`).
- LLM gateway: `OpenAI`-совместимый клиент к локальному Ollama (`LOCAL_BASE_URL`, обычно `http://localhost:11434/v1`).
- Storage: `SQLite` (`app/db/localgpt.db`) + файловое хранилище артефактов.
- UI: статический web UI (`web_ui/`), который работает с backend API.

## 2. Поток chat-запроса (high-level)

1. UI отправляет `POST /chat` (или async-вариант `POST /chat/tasks`).
2. Backend:
   - валидирует/создаёт сессию;
   - вычисляет `effective_settings` (defaults + profile/model overrides);
   - подгружает историю (ограниченную `mem_turns`);
   - собирает финальный `messages[]` для LLM;
   - вызывает Ollama через OpenAI-совместимый API.
3. Ответ очищается `sanitize_reply()` и сохраняется в историю.
4. В ответ клиенту возвращаются `reply` и `used_settings`.

## 3. «Память» диалога

В проекте память реализована как **short-term window memory** на уровне базы сообщений:

- История хранится в `chat_messages` (SQLite).
- Для каждого запроса в prompt попадает не вся история, а последние `mem_turns` пар (`user+assistant`),
  то есть максимум `2 * mem_turns` сообщений.
- Это окно настраивается per profile + per model через `model_settings.mem_turns`.

Практически:

- больше `mem_turns` → лучше удерживается контекст, но больше токенов уходит на вход;
- меньше `mem_turns` → дешевле/быстрее, но чаще «забываются» детали раннего диалога.

## 4. Как формируется контекст (`messages[]`)

Порядок сборки важен и сейчас такой:

1. system prompt по роли (`system_prompt_for(role)`),
2. опциональный блок `Контекст` (если пришёл `req.context`),
3. опциональный блок `Транскрипт` (из `req.transcript` или из последнего transcript текущей сессии),
4. опциональный блок `Критерии оценки`,
5. дополнительный system guardrail «отвечай на последний вопрос без повторов»,
6. сообщения истории (окно `mem_turns`),
7. текущий пользовательский запрос.

Это означает, что transcript/criteria могут стабильно «подмешиваться» в prompt независимо от окна памяти.

## 5. Токены: вход/выход и лимиты

### 5.1 Что управляется сейчас

Через настройки доступны:

- `num_ctx` — желаемый размер контекстного окна модели,
- `max_tokens` — верхняя граница длины ответа,
- `temperature` — параметр выборки,
- `mem_turns` — размер окна истории.

`max_tokens` и `temperature` уже передаются прямо в `chat.completions.create(...)`.

### 5.2 Важный нюанс по `num_ctx`

`num_ctx` хранится и возвращается в `used_settings`, но в текущей реализации не прокидывается в сам вызов
`chat.completions.create(...)` (т.е. это скорее policy-level параметр для профиля/модели и UI, чем жёстко применяемый runtime-параметр на каждом запросе).

### 5.3 Практический budget-треугольник

Для планирования качества/стоимости удобно считать:

- `InputTokens ≈ tokens(system + context + transcript + criteria + history + user_query)`
- `OutputTokens ≤ max_tokens`
- `InputTokens + OutputTokens` должны укладываться в фактическое окно модели (model-dependent).

Влияние ручек:

- уменьшение `mem_turns` снижает `InputTokens`;
- сокращение transcript/context снижает `InputTokens`;
- уменьшение `max_tokens` ограничивает длину генерации и latency.

## 6. Где именно лежат настройки

Источники настроек:

1. `.env` / env-переменные → `app/config.py` (`SETTINGS` и `DEFAULT_SETTINGS`),
2. `model_settings` в SQLite (персональные overrides на `profile + model`),
3. итог через `db.effective_settings(...)`.

Приоритет: **override из БД > default из env/config**.

## 7. Минимальный справочник для техразбора

- Chat orchestration: `backend/apps/chat/routes.py`
- Prompt assembly + LLM call: `backend/apps/chat/service.py`
- Settings/env defaults: `app/config.py`
- DB schema + history/settings logic: `app/db.py`
- Runtime metadata (`/health`): `app/routes/meta.py`

## 8. Рекомендации для следующей итерации

1. Явно прокинуть `num_ctx` в runtime-параметры генерации (или задокументировать, почему это intentionally UI-level параметр).
2. Добавить наблюдаемость по токенам (input/output/total) в `chat.log`.
3. Ввести стратегию «summary memory» для длинных диалогов (summary + короткое окно raw-history).
4. Добавить hard-guards по размеру transcript/context (авто-усечение + предупреждение UI).
5. Добавить тех-эндпоинт `/chat/debug/prompt` (только для dev/admin), чтобы видеть итоговый assembled prompt.
