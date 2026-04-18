# 🧠 Память и контекст — текущее поведение

Этот файл описывает, как именно сейчас собирается контекст ответа.

## Что попадает в prompt

1. `system`
   Базовый системный prompt + роль из `app/roles.py`.

2. `context`
   Если передан явно в `/chat`.

3. `transcript`
   Либо из запроса, либо последний transcript для текущей сессии.

4. `criteria`
   Если переданы явно или сохранены для сессии.

5. История диалога
   Последние `MEM_TURNS` пар `user/assistant`.

6. Текущий запрос пользователя

## Что хранится постоянно

- профили
- сессии
- сообщения
- транскрипты
- настройки моделей

Всё это лежит в SQLite.

## Что временное / in-memory

- текущие runtime-статусы загрузок и launcher PID-состояние;
- активная voice-запись в браузере;
- non-persistent voice transcription (`store_result=false`);
- временные сообщения интерфейса и client-side UI state.

## История и память

- память режется по `MEM_TURNS`, а не по реальному token accounting;
- длинные transcript/criteria всё ещё могут выбивать модель из комфортного контекста;
- summarization контекста автоматически не делается.

## Транскрипты

### Файловый transcript
- создаётся через `/transcribe`
- сохраняется в БД
- может быть подтянут как контекст сессии

### Voice input transcript
- создаётся через `/transcribe` c `store_result=false`
- в БД не сохраняется
- просто вставляется в textarea до отправки

## Роли

Backend всё ещё знает роли:
- `free`
- `teacher`
- `business_strict`
- `explain`
- `calc`
- `hr`

Но в текущем chat-first UI пользовательский поток не строится вокруг role-switching.
Практически основной сценарий сейчас — свободное общение.

## Prompt-файлы

Файлы:
- `app/prompts/system_base.md`
- `app/prompts/system_free.md`
- `app/prompts/system_teacher.md`
- `app/prompts/system_business_strict.md`
- `app/prompts/system_explain.md`
- `app/prompts/system_calc.md`
- `app/prompts/system_hr.md`

Сейчас промпты читаются с диска без долгоживущего cache-слоя, поэтому их изменения проще проверять во время разработки.
