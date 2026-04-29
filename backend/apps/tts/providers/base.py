from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoiceDefinition:
    id: str
    provider: str
    name: str
    language: str | None
    quality: str | None
    available: bool
    model_path: str
    config_path: str
    speaker_id: int | None = None
    speaker_name: str | None = None
    sample_rate: int | None = None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "provider": self.provider,
            "name": self.name,
            "language": self.language,
            "quality": self.quality,
            "available": self.available,
            "speaker_name": self.speaker_name,
            "sample_rate": self.sample_rate,
            "label": self.label,
        }

    @property
    def label(self) -> str:
        language = self.language or "unknown"
        if self.speaker_name:
            return f"{self.name} ({language}, {self.speaker_name})"
        return f"{self.name} ({language})"

    @property
    def model_file(self) -> Path:
        return Path(self.model_path)

    @property
    def config_file(self) -> Path:
        return Path(self.config_path)


@dataclass(frozen=True)
class SynthesisResult:
    output_path: str
    duration_sec: float
    sample_rate: int
    voice: VoiceDefinition


class TTSProvider(ABC):
    name: str

    @abstractmethod
    def is_available(self) -> tuple[bool, str | None]:
        raise NotImplementedError

    @abstractmethod
    def list_voices(self) -> list[VoiceDefinition]:
        raise NotImplementedError

    @abstractmethod
    def get_voice(self, voice_id: str) -> VoiceDefinition | None:
        raise NotImplementedError

    @abstractmethod
    def synthesize(self, text: str, voice_id: str, output_path: Path) -> SynthesisResult:
        raise NotImplementedError
