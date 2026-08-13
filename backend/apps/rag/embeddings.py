from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import error, request

from app import config


class EmbeddingError(RuntimeError):
    """Base error for embedding configuration and provider failures."""


class EmbeddingConfigurationError(EmbeddingError):
    pass


class EmbeddingProviderError(EmbeddingError):
    pass


@dataclass(frozen=True)
class EmbeddingDescriptor:
    provider: str
    model: str
    version: str
    dimensions: int
    storage_key: str

    def as_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "version": self.version,
            "dimensions": self.dimensions,
            "storage_key": self.storage_key,
        }


class EmbeddingProvider(Protocol):
    descriptor: EmbeddingDescriptor

    def embed(self, texts: list[str], *, release: bool = True) -> list[list[float]]: ...


class LocalHashEmbeddingProvider:
    def __init__(self, dimensions: int = 256) -> None:
        if dimensions != 256:
            raise EmbeddingConfigurationError("local_hash_requires_256_dimensions")
        self.descriptor = EmbeddingDescriptor(
            provider="local_hash",
            model="blake2b-token-hash",
            version="v1",
            dimensions=dimensions,
            storage_key="local-hash-v1",
        )

    def embed(self, texts: list[str], *, release: bool = True) -> list[list[float]]:
        del release
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.descriptor.dimensions
            for token in _tokens(text):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                value = int.from_bytes(digest, "big")
                index = value % self.descriptor.dimensions
                sign = 1.0 if (value >> 8) & 1 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(value * value for value in vector))
            vectors.append(vector if norm <= 0 else [round(value / norm, 6) for value in vector])
        return vectors


class OllamaEmbeddingProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        version: str,
        dimensions: int,
        timeout_seconds: float = 60.0,
        warm_keep_alive: str = "2m",
    ) -> None:
        if not model.strip() or not version.strip() or dimensions <= 0 or timeout_seconds <= 0:
            raise EmbeddingConfigurationError("ollama_embedding_config_invalid")
        self.base_url = _ollama_base_url(base_url)
        self.timeout_seconds = timeout_seconds
        self.warm_keep_alive = warm_keep_alive.strip() or "2m"
        self.descriptor = EmbeddingDescriptor(
            provider="ollama",
            model=model.strip(),
            version=version.strip(),
            dimensions=dimensions,
            storage_key=f"ollama/{model.strip()}/{version.strip()}/{dimensions}",
        )

    def embed(self, texts: list[str], *, release: bool = True) -> list[list[float]]:
        if not texts:
            return []
        payload = {
            "model": self.descriptor.model,
            "input": [str(text or "") for text in texts],
            "truncate": False,
            "dimensions": self.descriptor.dimensions,
            "keep_alive": "0" if release else self.warm_keep_alive,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/embed",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise EmbeddingProviderError(f"ollama_embedding_request_failed:{exc}") from exc
        vectors = parsed.get("embeddings") if isinstance(parsed, dict) else None
        return _validate_vectors(vectors, expected_count=len(texts), dimensions=self.descriptor.dimensions)


def provider_from_settings(settings: config.Settings | None = None) -> EmbeddingProvider:
    selected = settings or config.SETTINGS
    provider = str(selected.rag_embedding_provider or "").strip().lower().replace("-", "_")
    if provider == "local_hash":
        return LocalHashEmbeddingProvider()
    if provider == "ollama":
        return OllamaEmbeddingProvider(
            base_url=selected.base_url,
            model=selected.rag_embedding_model,
            version=selected.rag_embedding_version,
            dimensions=selected.rag_embedding_dimensions,
            timeout_seconds=selected.rag_embedding_timeout_seconds,
            warm_keep_alive=selected.rag_embedding_keep_alive,
        )
    raise EmbeddingConfigurationError(f"rag_embedding_provider_unknown:{provider or 'empty'}")


def _ollama_base_url(base_url: str) -> str:
    value = str(base_url or "http://localhost:11434").strip().rstrip("/")
    return value[:-3] if value.endswith("/v1") else value


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\wа-яА-ЯёЁ]{2,}", str(text or "").lower(), re.UNICODE)


def _validate_vectors(value: Any, *, expected_count: int, dimensions: int) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != expected_count:
        raise EmbeddingProviderError("ollama_embedding_count_mismatch")
    vectors: list[list[float]] = []
    for raw_vector in value:
        if not isinstance(raw_vector, list) or len(raw_vector) != dimensions:
            raise EmbeddingProviderError("ollama_embedding_dimension_mismatch")
        try:
            vector = [float(item) for item in raw_vector]
        except (TypeError, ValueError) as exc:
            raise EmbeddingProviderError("ollama_embedding_value_invalid") from exc
        if not all(math.isfinite(item) for item in vector):
            raise EmbeddingProviderError("ollama_embedding_value_invalid")
        vectors.append(vector)
    return vectors
