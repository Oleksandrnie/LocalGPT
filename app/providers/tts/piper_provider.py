from __future__ import annotations

import json
import re
import wave
from pathlib import Path
from typing import Any

from ... import config
from .base import SynthesisResult, TTSProvider, VoiceDefinition

_LANGUAGE_RE = re.compile(r"^[a-z]{2}(?:_[A-Z]{2})?$")
_QUALITY_TOKENS = {"x_low", "low", "medium", "high"}


class PiperProvider(TTSProvider):
    name = "piper"

    def __init__(self) -> None:
        self._voice_runtime_cache: dict[str, Any] = {}

    def is_available(self) -> tuple[bool, str | None]:
        runtime_error = self._runtime_import_error()
        if runtime_error is not None:
            return False, "Пакет piper-tts недоступен в текущем окружении."

        if not config.PIPER_MODELS_DIR.exists():
            return False, f"Каталог моделей Piper не найден: {config.PIPER_MODELS_DIR}"

        voices = self.list_voices()
        if not voices:
            return (
                False,
                f"Голоса Piper не найдены в {config.PIPER_MODELS_DIR}. Ожидаются файлы *.onnx и *.onnx.json.",
            )

        return True, None

    def list_voices(self) -> list[VoiceDefinition]:
        voices: list[VoiceDefinition] = []
        for model_path in sorted(config.PIPER_MODELS_DIR.rglob("*.onnx")):
            if any(part.startswith(".") for part in model_path.relative_to(config.PIPER_MODELS_DIR).parts):
                continue
            voices.extend(self._discover_model_voices(model_path))
        return voices

    def get_voice(self, voice_id: str) -> VoiceDefinition | None:
        for voice in self.list_voices():
            if voice.id == voice_id:
                return voice
        return None

    def synthesize(self, text: str, voice_id: str, output_path: Path) -> SynthesisResult:
        voice = self.get_voice(voice_id)
        if not voice:
            raise ValueError("voice_not_found")

        PiperVoice, SynthesisConfig = self._runtime_classes()
        model = self._load_runtime_voice(voice, PiperVoice)
        synthesis_config = SynthesisConfig(speaker_id=voice.speaker_id)
        text_chunks = self._split_text_chunks(text)
        if not text_chunks:
            raise ValueError("text_required")

        sample_rate = voice.sample_rate or getattr(model.config, "sample_rate", None) or 22050
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output = output_path.with_suffix(f"{output_path.suffix}.tmp")
        total_frames = 0
        has_audio = False

        try:
            with wave.open(str(temp_output), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)

                for chunk_text in text_chunks:
                    for audio_chunk in model.synthesize(chunk_text, syn_config=synthesis_config):
                        if audio_chunk.sample_rate != sample_rate:
                            raise RuntimeError("tts_sample_rate_mismatch")
                        wav_file.writeframes(audio_chunk.audio_int16_bytes)
                        total_frames += len(audio_chunk.audio_int16_array)
                        has_audio = True

            if not has_audio or total_frames <= 0:
                raise RuntimeError("tts_empty_audio")

            temp_output.replace(output_path)
        except Exception:
            try:
                temp_output.unlink()
            except OSError:
                pass
            raise

        return SynthesisResult(
            output_path=str(output_path),
            duration_sec=round(total_frames / float(sample_rate), 3),
            sample_rate=sample_rate,
            voice=voice,
        )

    def _runtime_import_error(self) -> Exception | None:
        try:
            from piper.config import SynthesisConfig  # noqa: F401
            from piper.voice import PiperVoice  # noqa: F401
        except Exception as exc:  # pragma: no cover - depends on runtime env
            return exc
        return None

    def _runtime_classes(self):
        from piper.config import SynthesisConfig
        from piper.voice import PiperVoice

        return PiperVoice, SynthesisConfig

    def _load_runtime_voice(self, voice: VoiceDefinition, runtime_class):
        cache_key = voice.model_path
        cached = self._voice_runtime_cache.get(cache_key)
        if cached is not None:
            return cached

        runtime_voice = runtime_class.load(voice.model_file, config_path=voice.config_file)
        self._voice_runtime_cache[cache_key] = runtime_voice
        return runtime_voice

    def _discover_model_voices(self, model_path: Path) -> list[VoiceDefinition]:
        config_path = Path(f"{model_path}.json")
        if not config_path.exists():
            return []

        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        sample_rate = self._as_int(payload.get("audio", {}).get("sample_rate"))
        num_speakers = max(1, self._as_int(payload.get("num_speakers")) or 1)
        speaker_map = payload.get("speaker_id_map") or {}
        base_id = model_path.relative_to(config.PIPER_MODELS_DIR).with_suffix("").as_posix()
        base_name = self._derive_voice_name(model_path.stem)
        language = self._derive_language(model_path.stem, payload)
        quality = self._derive_quality(model_path.stem)
        base_voice = {
            "provider": self.name,
            "language": language,
            "quality": quality,
            "available": True,
            "model_path": str(model_path.resolve()),
            "config_path": str(config_path.resolve()),
            "sample_rate": sample_rate,
        }

        if speaker_map:
            items = sorted(
                ((speaker_name, self._as_int(speaker_id) or 0) for speaker_name, speaker_id in speaker_map.items()),
                key=lambda item: item[1],
            )
            return [
                VoiceDefinition(
                    id=self._voice_id(base_id, speaker_id),
                    name=f"{base_name} / {self._humanize(speaker_name)}",
                    speaker_id=speaker_id,
                    speaker_name=self._humanize(speaker_name),
                    **base_voice,
                )
                for speaker_name, speaker_id in items
            ]

        if num_speakers > 1:
            return [
                VoiceDefinition(
                    id=self._voice_id(base_id, speaker_id),
                    name=f"{base_name} / Speaker {speaker_id + 1}",
                    speaker_id=speaker_id,
                    speaker_name=f"Speaker {speaker_id + 1}",
                    **base_voice,
                )
                for speaker_id in range(num_speakers)
            ]

        return [
            VoiceDefinition(
                id=base_id,
                name=base_name,
                speaker_id=None,
                speaker_name=None,
                **base_voice,
            )
        ]

    def _derive_voice_name(self, stem: str) -> str:
        parts = [part for part in stem.split("-") if part]
        if len(parts) >= 3 and _LANGUAGE_RE.match(parts[0]) and parts[-1] in _QUALITY_TOKENS:
            parts = parts[1:-1]
        elif len(parts) >= 2 and parts[-1] in _QUALITY_TOKENS:
            parts = parts[:-1]

        name = " ".join(self._humanize(part) for part in parts)
        return name or self._humanize(stem)

    def _derive_language(self, stem: str, payload: dict[str, Any]) -> str | None:
        language = payload.get("language")
        if isinstance(language, dict):
            candidate = (language.get("code") or language.get("name") or "").strip()
            if candidate:
                return candidate
        elif isinstance(language, str) and language.strip():
            return language.strip()

        espeak = payload.get("espeak", {})
        candidate = (espeak.get("voice") or "").strip()
        if candidate:
            return candidate

        prefix = stem.split("-", 1)[0].strip()
        if prefix:
            return prefix
        return None

    def _derive_quality(self, stem: str) -> str | None:
        parts = [part for part in stem.split("-") if part]
        if parts and parts[-1] in _QUALITY_TOKENS:
            return parts[-1]
        return None

    def _split_text_chunks(self, text: str, max_chars: int = 2400) -> list[str]:
        clean = (text or "").replace("\r\n", "\n").strip()
        if not clean:
            return []

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", clean) if part.strip()]
        units = paragraphs or [clean]
        chunks: list[str] = []
        current = ""

        for unit in units:
            for piece in self._split_piece(unit, max_chars):
                candidate = piece if not current else f"{current}\n\n{piece}"
                if len(candidate) <= max_chars:
                    current = candidate
                    continue
                if current:
                    chunks.append(current.strip())
                current = piece

        if current:
            chunks.append(current.strip())

        return [chunk for chunk in chunks if chunk]

    def _split_piece(self, piece: str, max_chars: int) -> list[str]:
        piece = piece.strip()
        if len(piece) <= max_chars:
            return [piece]

        sentences = [item.strip() for item in re.split(r"(?<=[.!?…])\s+", piece) if item.strip()]
        if len(sentences) <= 1:
            return self._split_by_words(piece, max_chars)

        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            if len(sentence) > max_chars:
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.extend(self._split_by_words(sentence, max_chars))
                continue

            candidate = sentence if not current else f"{current} {sentence}"
            if len(candidate) <= max_chars:
                current = candidate
            else:
                chunks.append(current.strip())
                current = sentence

        if current:
            chunks.append(current.strip())

        return chunks

    def _split_by_words(self, text: str, max_chars: int) -> list[str]:
        words = text.split()
        if not words:
            return []

        chunks: list[str] = []
        current = ""
        for word in words:
            if len(word) > max_chars:
                if current:
                    chunks.append(current.strip())
                    current = ""
                for idx in range(0, len(word), max_chars):
                    chunks.append(word[idx : idx + max_chars])
                continue

            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= max_chars:
                current = candidate
            else:
                chunks.append(current.strip())
                current = word

        if current:
            chunks.append(current.strip())

        return chunks

    def _voice_id(self, base_id: str, speaker_id: int) -> str:
        return f"{base_id}::speaker:{speaker_id}"

    def _humanize(self, value: str) -> str:
        clean = re.sub(r"[_\-]+", " ", value.strip())
        return clean.title() if clean else value

    def _as_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
