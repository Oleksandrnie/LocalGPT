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

Settings tab `Vision` не смешан с обычной chat library. Он показывает cards `qwen2.5vl:3b`, `qwen2.5vl:7b`, `gemma3:4b`, отдельно declared и runtime-confirmed capabilities, а также явные download/update/delete/primary actions. В этом tab находятся:

- enable image chat и primary model/auto;
- text-model fallback (`vision_context` или error);
- Vision context size в токенах (4096–131072, default 8192);
- Vision output tokens (128–8192, default/reset 1024); UI рекомендует не снижать лимит ниже 1024 из-за риска обрыва текста/таблицы, но сохраняет явно выбранные меньшие значения. Старое `0` отображается и сохраняется как 1024, без наследования обычного text budget; для больших таблиц может понадобиться больше;
- OCR assist/language;
- max images, file/total bytes, pixels и side;
- attachment cache statistics и cleanup.

После завершённого анализа действие Vision → RAG открывает dialog с редактируемым title/text. Export выполняется только после подтверждения пользователя и не переносит image binary.

Settings → Chat / LLM показывает отдельные `Output tokens` и `Thinking tokens`. Быстрый Thinking ON/OFF видим для thinking-capable модели (для Auto — по profile preference) и сохраняет оба budget override без сброса. Desktop/mobile header menu и slider в desktop/mobile model picker используют один save handler и после изменения синхронно рендерят общее effective состояние.

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
- Network address button: 0 адресов disabled, 1 копируется, 2+ открывают menu.
- ASR full analysis остаётся явно разрешаемым и предупреждает о нагрузке.
- Удаление ASR context должно синхронно обновлять RAG section.
- Image-only message, mixed text+image paste и multi-image drop используют один upload flow; отправка ждёт завершения uploads.
- Refresh восстанавливает history thumbnails и persisted vision task state без повторного user message.
- Attachment remove target и Vision tab controls проверяются с клавиатуры, в обеих темах и на mobile viewport.

Матрица проверок: [TESTING.md](../TESTING.md).
