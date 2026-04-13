# TTS Branch Notes

Текущая ветка перестроена под локальный TTS-продукт.

Что зафиксировано:
- основной runtime теперь работает только с `Piper` и `WAV`;
- backend отдаёт `/tts/*` API и не содержит старого speech-to-text runtime;
- WebUI перестроен под сценарий `text -> voice -> generate -> speed -> save`;
- история и аудиофайлы сохраняются в `app/data/tts/*`;
- локальные модели ожидаются в `models/tts/piper/*`.

Что не входит в эту ветку:
- speech-to-text runtime
- запись голоса
- диктовка
- voice cloning
- MP3
- облачные API
