import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import server


def test_system_prompt_returns_file_content():
    prompt = server._system_prompt()
    assert "Требование: отвечай ТОЛЬКО на русском языке" in prompt
    assert "Ты — локальный HR" in prompt


def test_system_prompt_fallback(monkeypatch, caplog, tmp_path):
    broken_prompt = tmp_path / "system_hr.md"
    broken_prompt.write_bytes(b"\xff\xfe")
    monkeypatch.setattr(server, "PROMPT_PATH", broken_prompt)

    with caplog.at_level(logging.WARNING):
        prompt = server._system_prompt()

    assert server.FALLBACK_SYSTEM_PROMPT in prompt
    assert "Failed to read system prompt" in caplog.text
    assert prompt.endswith(server.PROMPT_LANGUAGE_SUFFIX)
