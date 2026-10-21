from __future__ import annotations

from io import BytesIO
from typing import BinaryIO


class UploadLimitExceeded(ValueError):
    """Raised when a stream contains more bytes than its caller permits."""


def copy_limited(source: BinaryIO, destination: BinaryIO, *, max_bytes: int, chunk_size: int = 1024 * 1024) -> int:
    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")
    copied = 0
    while True:
        chunk = source.read(min(chunk_size, max_bytes - copied + 1))
        if not chunk:
            return copied
        if len(chunk) > max_bytes - copied:
            raise UploadLimitExceeded
        destination.write(chunk)
        copied += len(chunk)


def read_limited(source: BinaryIO, *, max_bytes: int) -> bytes:
    buffer = BytesIO()
    copy_limited(source, buffer, max_bytes=max_bytes)
    return buffer.getvalue()
