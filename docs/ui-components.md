# LocalGPT UI Components

Документ описывает базовый UI-layer static Web UI. Новые элементы интерфейса должны использовать эти классы и паттерны, чтобы не плодить разные визуальные версии одних и тех же контролов.

## Select

Всегда использовать кастомный `AppSelect`.

В текущей static UI-реализации `AppSelect` строится JavaScript-слоем поверх существующего `<select class="field__control">`. Нативный select остается только как скрытый backing-state для существующих обработчиков `change`, но пользователь не должен видеть и использовать системный браузерный select.

Правила:

- видимые нативные `<select>` запрещены;
- сторонние select-компоненты без стилизации под LocalGPT запрещены;
- все dropdown должны иметь единые состояния: default, hover, focus, open, disabled, active option;
- при программном изменении options/value нужно вызвать `queueSyncAppSelects()` или использовать существующие render-функции, где этот вызов уже добавлен.

Состояния:

- default: темный фон, тонкий border, стрелка справа;
- hover: фиолетовый border;
- focus/open: фиолетовый border и мягкий glow;
- dropdown: темный фон с blur, внутренний scroll для длинных списков;
- active option: фиолетовая подсветка.

## Button

Базовый класс: `.button`.

Варианты:

- `.button--primary` для основного действия;
- `.button--ghost` для вторичных действий;
- `.rag-status-button` для icon-only topbar-индикатора RAG с dot-состоянием.

Компактные topbar/composer-кнопки должны оставаться в диапазоне 36-44px по высоте. Новые действия не должны добавлять системные статусы в нижнюю область ввода.

## Input

Базовый класс: `.field__control`.

Правила:

- высота компактных single-line input: 40-46px;
- textarea в composer должна оставаться компактной и авторасширяться только по содержимому;
- системные статусы не размещаются в input area.

## Checkbox

Базовый паттерн: `.field.field--checkbox`.

Правила:

- checkbox должен использовать обычный `<input type="checkbox">` внутри label;
- для двухстрочного описания используется `.field__checkbox-copy`: `strong` для названия и `small` для пояснения;
- настройка `Стриминг ответов` находится первой карточкой в Settings → `Чат / LLM` как заметная `.generation-toggle-card`, сохраняется сразу при переключении в profile preferences как `streaming_enabled` и отправляется в chat request как `stream`;
- в пользовательском тексте не использовать внутренние названия флагов.

## Chat Messages

Текущий message runtime рендерится в `web_ui/js/app.js` через контейнеры `#messageList` и `.message-card`.

Текущий status rendering:

- сообщения в UI перечитываются из `GET /sessions/{session_id}/messages`;
- assistant-card рендерится по `message.status`, а не по локальному transient placeholder;
- `generating`: показать `Генерирую ответ...` и status badge;
- `streaming`: показывать partial content и animated continuation indicator;
- active assistant-card (`generating`/`streaming`) держит стабильную ширину и минимальную высоту, чтобы карточка не прыгала от маленькой к большой во время live-печати;
- `completed`: показывать обычный assistant-message;
- `failed`: показывать сохранённый `message.error` и кнопку `Повторить`;
- `cancelled`: показывать остановленное состояние;
- при включённой настройке `Стриминг ответов` UI подписывается на SSE и применяет `delta` к assistant-message через typewriter-buffer;
- плавность печати регулируется в `web_ui/js/app.js` константами `STREAM_TYPEWRITER_INTERVAL_MS`, `STREAM_TYPEWRITER_MIN_CHARS`, `STREAM_TYPEWRITER_MAX_CHARS`, `STREAM_TYPEWRITER_BACKLOG_STEP`, `STREAM_TYPEWRITER_FINAL_FLUSH_CHARS`;
- если SSE обрывается, UI возвращается к polling и перечитывает messages после финала;
- при открытии чата UI ищет active assistant-message с `task_id`, восстанавливает SSE/polling наблюдение и использует сохранённый partial content как replay-base, чтобы не продублировать старые чанки.

## SidebarToggle

Класс: `.sidebar-toggle-pill`.

Триггер находится на границе sidebar и контента, хранит состояние в `localStorage.sidebar_open` и использует стрелку `‹/›` для открытого/закрытого состояния.

## TopbarButton

Topbar-кнопки используют `.button.button--ghost`. Для кнопок со статусом используется отдельный modifier, например `.rag-status-button`.

RAG:

- кнопка icon-only, без видимой текстовой подписи;
- иконка: document + graph;
- OFF: нейтральный border, без dot и glow;
- ON: фиолетовый dot, фиолетовый border, мягкий glow;
- состояние должно соответствовать `rag_enabled` активного профиля.
- right-click открывает компактное popup-меню только для включения/отключения подмешивания RAG.

Settings:

- кнопка icon-only с классической шестерёнкой;
- без status dot.

ThemeToggle:

- класс `.theme-toggle-button`;
- располагается в topbar рядом с RAG и настройками;
- клик переключает `dark/light`;
- состояние хранится в `localStorage` через ключ `localgpt_simple_theme`;
- светлая тема использует `body.theme-light`, тёмная тема использует `body.theme-dark`;
- видимая иконка соответствует активной теме: солнце для light, луна для dark.

## Toast

Все системные уведомления идут через `setFooter(...)`, который теперь показывает toast под topbar и не пишет статус внизу интерфейса.

Обычный chat lifecycle не создаёт toast: старт генерации, переход в `streaming`, успешный `completed`, autorouter confidence и выбранная answer-модель отображаются только через состояние assistant-card или metadata. Toast остаётся для ошибок, отмены и degraded recovery, например обрыва SSE с переходом на polling.

Загрузка LLM-моделей тоже не создаёт progress/success toast. После подтверждения `/models/pull` пользователь видит состояние в `download-card`; повторный клик по уже активной загрузке остаётся тихим, а незагруженная модель не становится выбранной chat-моделью до появления в локальном списке.

Типы:

- `success`: зеленый marker;
- `info`: фиолетовый marker;
- `warning`: желтый marker;
- `error`: красный marker.

Поведение:

- появление через fade + slide;
- автозакрытие через 2-4 секунды;
- ручное закрытие кнопкой `×`;
- повтор одинакового уведомления подавляется на короткий промежуток времени.
