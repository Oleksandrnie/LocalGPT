# LocalGPT Whisper Transcriber

LocalGPT теперь работает как локальный транскрибатор аудио/видео с историей текстов и записью голоса.

Хранение моделей и кэшей сделано project-local:
- модели Whisper берутся только из папок внутри текущего проекта;
- домашний `~/.cache/huggingface` и внешние import-пути не используются;
- обновление моделей тоже работает только внутри `models/...` текущего проекта.

## Что умеет
- Локальная транскрибация через `faster-whisper`.
- Выбор модели: `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`.
- Модель по умолчанию: `large-v3-turbo`.
- Язык интерфейса по умолчанию: English.
- Запись голоса в браузере (приоритет `M4A/AAC`, fallback `WebM/Opus`).
- Drag & drop загрузка аудио/видео в панели управления.
- История транскрибаций в файловом хранилище (`app/data/transcripts/*.json`).
- Единый тёмный интерфейс, адаптированный под desktop и phone.

## Запуск на Mac (локально)
1. Требования: Python 3.10+, ffmpeg.
2. Запуск из корня проекта:
   ```bash
   python3 run_localgpt.py
   ```
3. Ручной запуск:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r app/requirements.txt
   uvicorn app.server:app --host 127.0.0.1 --port 8000 --reload
   ```
4. UI: `http://127.0.0.1:8000/ui/gui_html.html`

## Запуск для обычного пользователя
Самый простой вариант без Terminal и без `Automator`:
- открыть в проекте `LTrnsrb.app`;
- или запустить `LTrnsrb.command`.

Как это работает:
- оба launcher-а лежат внутри самого проекта;
- они сами находят корень проекта относительно своего расположения;
- абсолютный путь вида `/Users/.../LocalGPT` вручную прописывать не нужно.

Важно:
- `LTrnsrb.app` лучше не выносить отдельно из папки проекта;
- если нужен запуск из Dock, откройте `LTrnsrb.app` один раз и выберите `Keep in Dock`.

## Быстрый запуск на Mac через Automator (LTrnsrb)
1. В проекте уже есть скрипт: `tools/LTrnsrb.sh`.
2. Рекомендуется сначала создать стабильный symlink:
   ```bash
   ln -s "/фактический/путь/к/LocalGPT" "$HOME/LocalGPT"
   ```
3. Что такое symlink:
   - это "ярлык" на папку или файл на уровне файловой системы;
   - `~/LocalGPT` будет указывать на реальную папку проекта, даже если она лежит на другом диске или в другом каталоге;
   - если проект переедет, достаточно обновить только symlink, а `Automator` менять не нужно.
4. Если symlink уже существует и его нужно перенаправить на новый путь:
   ```bash
   rm -f "$HOME/LocalGPT"
   ln -s "/новый/фактический/путь/к/LocalGPT" "$HOME/LocalGPT"
   ```
5. Откройте `Automator` -> `Application`.
6. Добавьте действие `Run Shell Script`.
7. Вставьте одну строку:
   ```bash
   /bin/zsh -lc "$HOME/LocalGPT/tools/LTrnsrb.sh"
   ```
8. Сохраните приложение как `LTrnsrb`.

Что делает `LTrnsrb`:
- проверяет, запущены ли backend и Caddy;
- при необходимости запускает их в фоне (`nohup`) без открытия Terminal;
- автоматически определяет актуальный LAN IP (с приоритетом Wi-Fi интерфейса, с учетом смены сети/VPN);
- при смене IP пересоздает Caddy-конфиг и перезапускает Caddy;
- открывает UI по актуальному LAN URL `https://<ваш-ip>:8443/ui/gui_html.html` (или fallback на localhost).

Логи launcher-а:
- backend: `${TMPDIR}LTrnsrb-<uid>/backend.log`
- caddy: `${TMPDIR}LTrnsrb-<uid>/caddy.log`

## LAN + iPhone (HTTPS через Caddy)
Для записи голоса на iPhone нужен HTTPS. Для этого используется локальный reverse proxy Caddy.

### 1) Установка Caddy (macOS)
```bash
brew install caddy
```

### 2) Конфиг Caddy
Для ручного запуска есть `Caddyfile.lan` (фиксированный вариант).
Для повседневного использования лучше запускать через `LTrnsrb`:
- он генерирует динамический конфиг в per-user runtime dir: `${TMPDIR}LTrnsrb-<uid>/Caddyfile.auto`;
- автоматически подставляет актуальный LAN IP;
- при смене IP (включая VPN/другую сеть) перезапускает Caddy с новым сертификатом.

Содержимое:
```caddy
https://Oleksandrs-MacBook-Pro.local:8443 {
    tls internal
    reverse_proxy 127.0.0.1:8000
}
```

### 3) Порядок запуска (важно)
1. В первом терминале запустить backend:
   ```bash
   cd /Users/oleksandrniemchenko/my_personal_files/LocalGPT
   python3 run_localgpt.py
   ```
2. Во втором терминале запустить Caddy:
   ```bash
   cd /Users/oleksandrniemchenko/my_personal_files/LocalGPT
   caddy run --config Caddyfile.lan
   ```
3. На Mac открыть:
   `https://Oleksandrs-MacBook-Pro.local:8443/ui/gui_html.html`
4. На iPhone открыть тот же URL (в той же Wi-Fi сети).

Подсказка в UI:
- под переключателем языков есть burger-меню `☰`;
- внутри меню: `Update model`, `Copy URL`, `Shut down app`;
- после `Shut down app` для нового старта нужно снова открыть `LTrnsrb`;
- `Choose file` и зона записи работают как drag & drop область для аудио/видео.

### 4) Сертификат Caddy для iPhone
При первом запуске `caddy run --config Caddyfile.lan` Caddy автоматически генерирует локальный CA сертификат.

Чтобы добавить этот CA в доверенные на самом Mac (через терминал), выполните:
```bash
caddy trust
```

Точный AppData путь можно проверить:
```bash
caddy environ | rg AppDataDir
```

Для текущей установки путь:
`/Users/oleksandrniemchenko/Library/Application Support/Caddy`

Root сертификат:
`/Users/oleksandrniemchenko/Library/Application Support/Caddy/pki/authorities/local/root.crt`

Скопировать сертификат на рабочий стол:
```bash
cp "/Users/oleksandrniemchenko/Library/Application Support/Caddy/pki/authorities/local/root.crt" "$HOME/Desktop/caddy-root.crt"
```

Далее на iPhone:
1. Передать `caddy-root.crt` через AirDrop.
2. Установить профиль сертификата.
3. Включить доверие: `Settings -> General -> About -> Certificate Trust Settings -> Full Trust for Root Certificates`.
4. Перезапустить Safari и открыть:
   `https://Oleksandrs-MacBook-Pro.local:8443/ui/gui_html.html`

### 5) Безопасность LAN
1. Не делайте port-forward на роутере (в интернет ничего не публикуем).
2. Mac и iPhone должны быть в одной сети.
3. Если в Wi-Fi включен client isolation, доступ между устройствами может не работать.

## API
- `GET /health`
- `GET /whisper/models`
- `POST /whisper/models/prepare`
- `GET /whisper/models/prepare/{task_id}`
- `GET /whisper/models/update-check/{model_name}`
- `POST /runtime/shutdown`
- `POST /transcribe` (multipart: `file`, `model`, `source_type`)
- `GET /transcripts`
- `GET /transcripts/{id}`
- `POST /transcripts`
- `PATCH /transcripts/{id}`
- `DELETE /transcripts/{id}`

## Хранилище
- Транскрибации: `app/data/transcripts/<id>.json`
- Формат записи включает:
  - `id`, `created_at`, `updated_at`
  - `source_type`, `source_name`
  - `model`, `language`, `duration_sec`
  - `preview`, `text`

## Конфигурация (`.env`)
Основные параметры смотрите в `.env.example`:
- `MODELS_DIR`
- `WHISPER_MODELS_DIR`
- `HF_CACHE_DIR`
- `CTRANSLATE2_CACHE_DIR`
- `TRANSCRIPTS_DIR`
- `WHISPER_MODEL_SIZE`
- `WHISPER_COMPUTE_TYPE`
- `WHISPER_DEVICE`
- `WHISPER_BEAM_SIZE`
- `WHISPER_FALLBACK_LANGUAGE`
- `HF_ENDPOINT` (по умолчанию `https://huggingface.co`)
- `HF_FALLBACK_ENDPOINT` (опциональный резервный endpoint)
- `HF_TRUST_ENV` (`1` если нужно использовать `HTTP_PROXY`/`HTTPS_PROXY`)
- `IOS_ACCESS_URL` (опционально фиксирует URL для iPhone-подсказки в UI)
- `IOS_HTTPS_PORT` (порт для генерации iPhone URL, если `IOS_ACCESS_URL` пуст)

## Smoke checklist
1. Выбрать аудио/видео файл -> транскрибация стартует автоматически.
2. Нажать `⏺`, записать >=3 сек -> запись сохраняется и автоматически транскрибируется.
3. Кнопки `copy | save | clear` работают с центральным полем.
4. История показывает дату/время и preview.
5. Клик по записи открывает модалку; `send` переносит текст в центральное поле.
