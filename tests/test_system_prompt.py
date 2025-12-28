from pathlib import Path

from app import roles


def test_hr_prompt_includes_language_suffix():
    prompt = roles.system_prompt_for("hr")
    assert roles.LANGUAGE_SUFFIX.strip() in prompt
    assert "локальный HR" in prompt


def test_fallback_used_when_file_missing(monkeypatch):
    missing_path = Path("/tmp/system_missing.md")
    monkeypatch.setattr(roles, "BASE_PROMPT_PATH", missing_path)
    prompt = roles.system_prompt_for("hr")
    assert roles.BASE_PROMPT_FALLBACK in prompt
