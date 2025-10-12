# Copyright (c) 2025 Oleksandr Niemchenko. All Rights Reserved.
#!/usr/bin/env bash
set -euo pipefail

PROJ="$HOME/my_personal_files/LocalGPT"

 # 1) Запустить/убедиться, что жив Ollama
echo "[*] Checking if Ollama is running..."
if ! pgrep -x "ollama" >/dev/null; then
  echo "[*] Starting Ollama locally (not as a service)..."
  nohup ollama serve >/tmp/ollama_local.log 2>&1 &
  sleep 2
else
  echo "[i] Ollama already running."
fi

# Подождать, пока поднимется порт 11434 (до ~15 сек)
for i in {1..30}; do
  if curl -s http://127.0.0.1:11434/v1/models >/dev/null; then
    break
  fi
  sleep 0.5
done

# 2) Убедиться, что модель на месте
if ! ollama list | grep -q "qwen2.5:7b-instruct"; then
  echo "[*] Pulling model qwen2.5:7b-instruct..."
  ollama pull qwen2.5:7b-instruct
fi

# 3) Запуск FastAPI с --reload
echo "[*] Starting FastAPI (dev mode)..."
cd "$PROJ"
source venv/bin/activate
export PYTHONPATH="$(pwd)"

# Открыть UI в браузере (macOS)
open "http://127.0.0.1:8000/"

# Если порт занят — убьём старый uvicorn
if lsof -i :8000 >/dev/null 2>&1; then
  echo "[i] Port 8000 is busy, killing old uvicorn..."
  pkill -f "uvicorn.*app.server:app" || true
fi

exec uvicorn app.server:app \
  --host 127.0.0.1 \
  --port 8000 \
  --log-level info \
  --reload \
  --reload-dir app \
  --reload-exclude 'venv/*' \
  --reload-exclude '*.pyc'
