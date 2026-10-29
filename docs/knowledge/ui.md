# Web UI

## Активный frontend

FastAPI отдаёт статические assets из `web_ui/`.

- HTML: `web_ui/gui_html.html`;
- CSS entry: `web_ui/css/style.css`;
- JavaScript entry: `web_ui/js/app.js`;
- Markdown renderer: `web_ui/js/markdown.mjs`;
- изображения/иконки: `web_ui/img/`, `favicon.svg`.

`gui_html.html` не подключает `js/main.js`; старый modular graph (`main.js`, `chat.js`, `sessions.js` и др.) не является активным runtime, пока entry point явно не мигрирован.

## Layout

Основные зоны:

- sidebar и chat/session navigation;
- floating topbar;
- message scroll/list и scroll-to-latest;
- composer с `+` actions, image picker и attachment strip;
- settings/modal surfaces;
- ASR, TTS и OCR tool docks;
- RAG и plugin/network panels;
- toast layer.

State частично хранится в profile preferences/backend, частично — в `localStorage` для чисто UI-настроек.

`ADMIN_TOKEN` не относится к обычному UI state: privileged action запрашивает его интерактивно, передаёт через `X-LocalGPT-Admin-Token` и хранит только в `sessionStorage`. Не переносите token в `localStorage`, URL или persisted profile preferences.

## Component conventions

### Buttons

- текстовое действие — обычная кнопка с понятным label;
- icon-only действие обязано иметь `aria-label` и `title`, если hover-help полезен;
- toggle синхронизирует `aria-pressed`, `aria-expanded`, `aria-selected` или `aria-checked`.

### Select

Видимый select использует `AppSelect`/custom picker. Native `<select>` может оставаться скрытым backing state, но не должен давать второй видимый control.

### Toast

Системные уведомления показываются под topbar. Normal chat lifecycle и download progress не должны спамить success/progress toast; ошибки, отмена и degraded recovery остаются заметными.

### Chat messages

Assistant card рендерится из persisted `message.status`. Optimistic placeholder не является источником истины. Markdown проходит через `markdown.mjs`; raw model HTML не вставляется напрямую.

После первого reasoning chunk у генерируемого assistant message появляется keyboard-accessible terminal icon `>_`. Read-only dialog сразу показывает накопленный reasoning и обновляется по SSE без повторного открытия; close/reopen сохраняет текущий live snapshot. После terminal state тот же dialog лениво загружает persisted reasoning. Escape/backdrop/close возвращают focus на исходную кнопку, а reasoning никогда не вставляется в body ответа.

Каждое непустое user message и completed assistant message имеет действие `Добавить в RAG`. Оно открывает общий editable title/text dialog; cancel ничего не индексирует, confirm отправляет только отредактированный текст. Vision export использует тот же dialog pattern.

Каждое непустое user и assistant message имеет действие `Скопировать`: общий clipboard path получает raw `message.content` выбранной карточки без Markdown-нормализации и показывает существующее подтверждение результата. User `Добавить в RAG` остаётся независимым действием.

RAG panel показывает безопасное состояние configured embedding generation: готовность, необходимость обычного ingest, необходимость semantic reindex, ошибку конфигурации или активную/failed operation. Переиндексация доступна только для `reindex_required`, требует отдельного подтверждения с названием модели и количеством chunks и блокирует конкурирующие source actions. Прогресс восстанавливается при повторном открытии/refresh, пока process-local task существует; после backend restart UI пересчитывает состояние через `/rag/status`, не показывает raw backend error и не запускает операцию автоматически.

Image composer принимает PNG/JPEG/WebP через picker, paste и multi-file drop. До отправки карточка показывает thumbnail, upload/error state и отдельную keyboard-accessible кнопку удаления. Обычная text paste не перехватывается, а backend settings остаются источником истины для count/byte/pixel/side limits. История загружает attachment metadata отдельно и рендерит ownership-checked thumbnail/media URLs, не binary data URI.

### Model state

Если chat-модель отсутствует, composer остаётся доступным для ввода, но отправка блокируется с понятным сообщением. Загрузка модели требует явного подтверждения.

В Settings → Chat / LLM `Thinking tokens` имеет default 4096, minimum 2048 и ручной диапазон до 32768; меньшие старые per-model overrides отображаются как минимум без изменения SQLite до сохранения. `Output tokens` остаётся независимым budget финального ответа.

Внизу Settings → Chat / LLM находится Ollama installer: достаточно указать модель или вставить команду `ollama pull <model>`; `ollama run` добавлять не нужно. Если в двухстрочном блоке есть точная matching `ollama run <model>`, она распознаётся, но игнорируется и не запускается. Другие команды, аргументы, shell chaining/substitution и лишние строки отклоняются до запроса к backend. Pull progress, состояние и остановка показываются рядом с installer; после завершения списка моделей перечитывается, и установленная chat-модель вне встроенного каталога тоже появляется в выборе. Модель не выбирается и не запускается автоматически — её нужно выбрать отдельно. Подтверждённые embedding-only модели не попадают в chat-выбор; это не интерфейс установки Vision/ASR/TTS/embedding runtime.

`Библиотека загрузки LLM` группирует модели по состоянию: установленные в Ollama и доступные для установки. Каждая модель показана компактной строкой с кратким статусом и одной основной кнопкой выбора/загрузки; обновление, удаление и сведения находятся в отдельном раскрываемом меню действий.

Settings tab `Vision` не смешан с обычной chat library. Он показывает cards `qwen2.5vl:3b`, `qwen2.5vl:7b`, `gemma3:4b`, отдельно declared и runtime-confirmed capabilities, а также явные download/update/delete/primary actions. В этом tab находятся:

- enable image chat и primary model/auto;
- text-model fallback (`vision_context` или error);
- Vision context size в токенах (4096–131072, default 8192);
- Vision output tokens (128–8192, default/reset 1024); UI рекомендует не снижать лимит ниже 1024 из-за риска обрыва текста/таблицы, но сохраняет явно выбранные меньшие значения. Старое `0` отображается и сохраняется как 1024, без наследования обычного text budget; для больших таблиц может понадобиться больше;
- OCR assist/language;
- max images, file/total bytes, pixels и side;
- attachment cache statistics и cleanup.

После завершённого анализа действие Vision → RAG открывает dialog с редактируемым title/text. Export выполняется только после подтверждения пользователя и не переносит image binary.

Settings → Chat / LLM показывает отдельные `Output tokens`, `Thinking tokens` и динамический `Thinking — режим / уровень`. Последний строится только по фактическому Ollama metadata выбранной установленной модели: named levels показываются без переименования, boolean-only модели сохраняют ON/OFF, `Auto` использует Ollama default, а отсутствующая/явно unsupported metadata не порождает выдуманный control. Кастомные installed Ollama-модели используют ту же схему. Desktop/mobile header menu синхронизируется с Settings; quick model picker используется только для выбора модели. Управление размышлением находится в кнопке Thinking рядом с моделью: она показывает Auto / On / Off или точное имя уровня и на desktop, и на mobile. Auto использует настройку модели по умолчанию и не получает подсветку включённого режима. Сохранение thinking choice не сбрасывает output/thinking budget overrides. Для Auto-router остаётся отдельная profile preference. Выбор reasoning effort не меняет видимость trace: её можно просматривать отдельно у ответа через `>_`.

Там же `История чата, пар сообщений` задаёт profile default 6 в диапазоне 0–100. Один turn — завершённая пара `user + assistant` только текущего chat; `0` отключает short history. Setting сохраняется в profile preferences и применяется ко всем chat-моделям, но не смешивает sessions.

## Themes

Dark/light theme переключается topbar control и сохраняется в `localStorage`. Новые компоненты должны использовать существующие CSS tokens и проверяться в обеих темах, включая hover, focus, disabled, warning и overlay states.

## Responsive strategy

CSS содержит отдельные ranges для узких телефонов, 391–430, 431–480, tablet/mobile до 768, landscape-height и более широких layout transitions. Не добавляйте breakpoint только под один screenshot; сначала используйте общие mobile constraints.

В mobile/short-landscape media range session open/delete и message `Добавить в RAG`/`Скопировать` имеют минимум 44 px по высоте; круглые session actions также 44×44 px.

Проверять:

- composer и клавиатуру;
- safe-area/viewport height;
- sidebar/drawers;
- settings forms;
- tool docks/history;
- menus у краёв экрана;
- длинные сообщения и streaming;
- touch targets.

## Model transfer

Settings → System содержит компактные соседние действия `Экспорт моделей` и `Импорт моделей`. Экспорт открывает отдельную модалку со списком complete units, выбором всех/отдельных моделей, количеством выбранных и unique size полного набора; только подтверждение в этой модалке запускает задачу, отображающую progress и скачивающую `.localgpt-models`. Import использует file picker, checksum preview и отдельный confirmation dialog; success report разделяет опубликованные и уже идентичные файлы. Успешный импорт автоматически удаляет его временный upload-archive. Рядом System показывает число и размер оставшихся временных архивов и предлагает подтверждённую очистку, которая не затрагивает установленные модели или экспортированные пользователем файлы.

## Navigation и state

- sidebar open state — `sidebar_open`;
- theme, active profile/session, tool panels и selected settings сохраняются под `localgpt_simple_*` keys;
- backend остаётся source of truth для profiles, sessions, messages, model settings и task states;
- refresh должен восстановить active assistant task по persisted `task_id`.

## Accessibility

Текущий UI использует aria labels/states, menu roles и keyboard-friendly buttons, но изменения требуют ручной проверки:

- focus visibility и order;
- Escape/close behavior;
- dialog/menu expanded states;
- icon labels;
- color contrast в обеих темах;
- keyboard-only navigation;
- reduced motion и streaming readability.

Не скрывайте интерактивный элемент только визуально без корректного `hidden`, focus или aria state.

## Regression considerations

- SSE `delta` дедуплицируется по sequence; pagehide/close переходит к polling fallback.
- task status/events/cancel URL всегда несёт active `profile_id` и `session_id`; 429 на SSE connection limit должен перейти в существующий polling/error recovery без reconnect storm.
- Scroll-to-latest не должен ломать auto-scroll пользователя, который читает историю.
- RAG indicator отражает active profile.
- ASR full analysis остаётся явно разрешаемым и предупреждает о нагрузке.
- Удаление ASR context должно синхронно обновлять RAG section.
- Image-only message, mixed text+image paste и multi-image drop используют один upload flow; отправка ждёт завершения uploads.
- Refresh восстанавливает history thumbnails и persisted vision task state без повторного user message.
- Attachment remove target и Vision tab controls проверяются с клавиатуры, в обеих темах и на mobile viewport.

Матрица проверок: [TESTING.md](../TESTING.md).


### Адаптивный переключатель Thinking и загрузка истории

Quick Thinking использует единый сегментный ряд: Auto / On / Off для boolean-моделей или Auto плюс все объявленные именованные уровни, например low/medium/high. Auto — полноценная первая позиция индикатора; поддерживаемые runtime-значения и их регистр не изменяются. Индикатор сдвигается между положениями; точный регистр и число named values сохраняются. ArrowLeft/ArrowRight меняют выбранный сегмент, обычное меню сохраняет управление Up/Down/Home/End. Предусмотрены focus state, reduced motion, размер touch target44px и ограничение popup границами viewport. Сегментный выбор не перекрывается success toast; ошибки сохранения продолжают показываться.

История запрашивается независимо от необязательных вложений/транскриптов. Сбой вспомогательного endpoint не скрывает успешно полученные сообщения. Запоздалые ответы другого session/profile не изменяют активную историю. При подготовке chat task UI сразу показывает временное сообщение пользователя; после подтверждения оно заменяется серверной записью без дубля. При ошибке отправки очищенный composer восстанавливается. Загрузка истории при старте не ждёт необязательных ASR/TTS/storage сервисов. Временное сообщение до принятия backend не считается сохранённой записью; данные уже принятого запроса остаются в SQLite.


### Прокрутка во время генерации

Перерисовка сообщений сохраняет scrollTop, если пользователь читает выше конца чата. При закреплении у низа список следует за увеличением ответа без smooth-анимации на каждом токене; кнопка перехода вниз включает следование снова. Отложенная автоматическая прокрутка повторно проверяет закрепление перед выполнением. Обновление уже открытой сессии и завершение восстановленной задачи не должны принудительно возвращать читателя вниз. Browser scroll anchoring для контейнера отключён, позицию сохраняет приложение.

Если в сохранённом или поступающем assistant-ответе обнаружен LOCALGPT_DATA_ENVELOPE, вместо содержимого показывается ошибка служебного формата с возможностью повторить запрос. Копирование и экспорт этого ответа недоступны; сама запись в базе не переписывается. Backend отдельно блокирует такой формат в новых генерациях. После frontend-изменений страницу необходимо обновить; перезапуск backend не заменяет загрузку нового JavaScript браузером.

### Smart search controls

The right-click RAG menu contains independent switches for RAG context and knowledge search. A compact question mark offers hover/focus help. The former large composer button/status is removed; status remains in an aria-live region and in the input indicator tooltip. Only when search is active, a small search indicator appears to the right of the dictation microphone; clicking it opens the RAG menu. Input padding and mobile hit targets prevent icon/text overlap.

The UI labels the path as plan, search, then citations. It reports when semantic embeddings or the local planner are unavailable instead of claiming a full smart search. Results use the author label `База знаний`; requested links are clickable, safe HTTPS or scoped local evidence links, while URLs inside quoted source code remain inert. Available search does not require a loaded answer-generation model; the selected local chat model improves planning when installed. The existing cancellation/session race guards remain in force.


### Waiting dots and long-search confirmation

Three CSS-animated dots appear immediately after submission, before a slow start request returns. The temporary assistant row is render-only: it is never placed into stored messages, copied or exported. When the exact assistant/task placeholder appears, the dots move into that card without duplication. Actual answer content, available reasoning, completion, failure or cancellation hide the dots; On/Off/Auto settings alone do not decide visibility. Existing reasoning access remains available through the answer button. Recovery uses the same indicator. The scope includes profile, chat and request mode, so old answers or stale operations cannot suppress/reveal another request's loader.

A stable screen-reader status announces the operation once; the animated dots are aria-hidden and respect reduced motion. The renderer preserves the existing reading position and bottom-follow behavior. Search mode shows the same waiting indicator while planning/retrieval run, plus a Continue/Cancel dialog after30seconds. Background progress remains independent of the dialog, and the dialog is closed automatically on completion. Client start obtains the task ID even after an early cancellation so the server job can still be cancelled.

### Manual scroll intent during streaming

Upward wheel/touch/keyboard input pauses following before the native scroll event, including small movements within the former96px proximity threshold. Repaint/programmatic events no longer infer following from proximity alone. Scrollbar movement is detected before DOM replacement; only actual bottom position or a deliberate downward input reaching the end resumes following. Queued jumps carry a revision token so upward input can invalidate them. End and the latest-message button intentionally jump to the current growing end.

Completion, cancellation and same-session refresh preserve the reading position. Navigating to a different session/profile or a new empty chat resets following, so a paused old chat does not affect the next conversation. No backend behavior or stored message content changes.


### Guided semantic setup

The Knowledge panel contains an embedding-model setup card with metadata availability, download progress/cancel, refresh, activation and lexical rollback. Installation is offered once on startup or after an unconfigured search warning, with a Later choice. Activation explains that only the selected profile is reindexed, sources stay local and the old index remains active until success. Profile/session changes cannot apply late setup responses to another screen. The .env instructions are replaced by UI actions; model-install readiness is distinct from LLM planner JSON availability.


### User message compositing

User message cards no longer apply backdrop-filter blur inside the masked scrolling container. Their purple gradient, shadow, theme colors and the scroll fade remain. This avoids the blur/mask compositing combination implicated by a reported transient vertical tint split. The exact hardware artifact was not reproduced in headless Chrome; validation covered computed styles and synthetic screenshots in dark/light themes at multiple scroll positions and mobile width. Assistant card styling remains unchanged.

В «Система» доступен тайм-аут ожидания поиска в базе: целое число секунд от1 до86400, по умолчанию30. Сохраняется автоматически в localStorage браузера и применяется при следующем поиске. Это интервал подтверждения продолжения, а не автоматической отмены: открытое окно не останавливает поиск.
