# CLEANUP_REPORT — текущее состояние проекта

## Что изменено по сравнению со старой архитектурой

- Главный продуктовый сценарий переведён в chat-first формат.
- Основной UI больше не строится вокруг HR-анализа, ролей, карточек и старых многоэкранных панелей.
- Активный frontend теперь:
  - `web_ui/gui_html.html`
  - `web_ui/js/app.js`
  - `web_ui/css/style.css`

## Основные актуальные изменения

### 1. UI
- messenger-like layout;
- фиксированный sidebar;
- отдельный scroll для чата и списка диалогов;
- `+`-меню у поля ввода;
- кнопка микрофона в поле ввода;
- отключение `Отправить` при пустом input;
- удалён отдельный блок `Активный транскрипт`.

### 2. Голос
- voice input через `MediaRecorder`;
- распознавание через Whisper `large-v3-turbo`;
- непостоянный transcript для voice input (`store_result=false`);
- browser TTS через `speechSynthesis`.

### 3. Модели и настройки
- portable paths через `.env`;
- изменение базовой папки моделей из UI;
- model settings по профилю и модели;
- загрузки/обновления моделей Ollama из UI.

### 4. LAN
- `tools/LTrnsrb.sh`
- `LTrnsrb.command`
- health/meta маршрут знает LAN URL;
- runtime shutdown умеет завершать backend и Caddy.

### 5. Prompt layer
- prompts приведены к более естественному chat-style;
- prompt-файлы больше не кэшируются жёстко через `lru_cache`;
- убраны stop-токены, которые могли резать списки и ответы.

## Что осталось в репозитории как legacy/reference

- старые frontend-модули в `web_ui/js/`;
- backend role-system полностью не удалён, хотя в текущем UX он не в центре сценария.

## Итог

Проект сейчас следует документировать не как “локальный HR/ASR-бот”, а как:

**локальный chat-first ассистент с профилями, voice input, ASR, browser TTS, portable model storage и LAN-доступом через Caddy.**
