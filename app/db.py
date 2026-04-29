import json
import os
import sqlite3
import uuid
from copy import deepcopy
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from . import config

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("LOCALGPT_DB_PATH", str(PROJECT_ROOT / "db" / "localgpt.db"))).expanduser()
if not DB_PATH.is_absolute():
    DB_PATH = (PROJECT_ROOT.parent / DB_PATH).resolve()


def _utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _merge_dict(target: dict[str, Any], updates: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(updates, dict):
        return target
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_dict(target[key], value)
        elif value is not None:
            target[key] = value
    return target


def _clone_jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _default_runtime_preferences() -> dict[str, Any]:
    return _clone_jsonable(config.DEFAULT_RUNTIME_SETTINGS)


def _to_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _from_json(raw: str | None, fallback: Any = None) -> Any:
    if raw is None:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _default_profile_preferences() -> dict[str, Any]:
    whisper_model = config.SETTINGS.whisper_default_model
    preferences = {
        "chat": {
            "dictation_model": whisper_model,
            "system_prompt": "",
        },
        "asr": {
            "studio_model": config.ASR_STUDIO_DEFAULT_MODEL,
            "prompt_preset": "none",
        },
        "tts": {
            "provider": config.SETTINGS.tts_default_provider,
            "voice_id": "",
            "speed": "1",
        },
        "ocr": {},
    }
    preferences["settings"] = _default_runtime_preferences()
    return preferences


def _normalize_profile_preferences(value: Any) -> dict[str, Any]:
    normalized = deepcopy(_default_profile_preferences())
    if isinstance(value, dict):
        _merge_dict(normalized, value)
    return normalized


def _profile_row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    data = _row_dict(row)
    if not data:
        return None
    data["preferences"] = _normalize_profile_preferences(_from_json(data.pop("preferences_json", None), {}))
    return data


def _migrate_asr_studio_default(conn: sqlite3.Connection) -> None:
    migration_key = "migration_asr_studio_default_large_v3_turbo"
    existing = conn.execute("SELECT value FROM app_settings WHERE key = ?", (migration_key,)).fetchone()
    if existing:
        return

    legacy_default = config.SETTINGS.whisper_default_model
    studio_default = config.ASR_STUDIO_DEFAULT_MODEL
    rows = conn.execute("SELECT id, preferences_json FROM profiles").fetchall()
    now = _utcnow()
    for row in rows:
        raw_preferences = _from_json(row["preferences_json"], {})
        raw_preferences = raw_preferences if isinstance(raw_preferences, dict) else {}
        raw_asr = raw_preferences.get("asr") if isinstance(raw_preferences.get("asr"), dict) else {}
        raw_chat = raw_preferences.get("chat") if isinstance(raw_preferences.get("chat"), dict) else {}
        current_studio_model = str(raw_asr.get("studio_model") or "").strip()
        current_dictation_model = str(raw_chat.get("dictation_model") or "").strip()

        should_update = not current_studio_model or (
            current_studio_model == legacy_default and current_dictation_model == legacy_default
        )
        if not should_update:
            continue

        preferences = _normalize_profile_preferences(raw_preferences)
        preferences.setdefault("asr", {})["studio_model"] = studio_default
        conn.execute(
            "UPDATE profiles SET preferences_json = ?, updated_at = ? WHERE id = ?",
            (_to_json(preferences), now, row["id"]),
        )

    conn.execute(
        "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
        (migration_key, "1", now),
    )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cursor = conn.execute(f"PRAGMA table_info({table});")
    columns = {row[1] for row in cursor.fetchall()}
    if column not in columns:
        conn.execute(ddl)


def init_db() -> None:
    default_preferences = _to_json(_default_profile_preferences()) or "{}"
    with closing(_connect()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NULL,
                color TEXT NULL,
                preferences_json TEXT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                profile_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                model_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'free',
                criteria_json TEXT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
            ON chat_messages (session_id, created_at);

            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                session_id TEXT NULL,
                name TEXT NOT NULL,
                source_path TEXT NULL,
                content TEXT NOT NULL,
                summary TEXT NULL,
                structured_json TEXT NULL,
                latest_pipeline_run_id INTEGER NULL,
                language TEXT NULL,
                timeline_json TEXT NULL,
                role_keywords_json TEXT NULL,
                labels_json TEXT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS model_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                model_name TEXT NOT NULL,
                temperature REAL NULL,
                max_tokens INTEGER NULL,
                num_ctx INTEGER NULL,
                mem_turns INTEGER NULL,
                pipeline_enabled INTEGER NULL,
                summary_memory_enabled INTEGER NULL,
                rag_enabled INTEGER NULL,
                default_pipeline_preset TEXT NULL,
                max_transcript_chars INTEGER NULL,
                max_context_chars INTEGER NULL,
                summary_memory_limit INTEGER NULL,
                rag_top_k INTEGER NULL,
                rag_max_context_chars INTEGER NULL,
                pipeline_json TEXT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                UNIQUE(profile_id, model_name),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transcript_pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transcript_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                session_id TEXT NULL,
                preset TEXT NOT NULL,
                action TEXT NOT NULL,
                raw_transcript TEXT NOT NULL,
                cleaned_transcript TEXT NULL,
                segments_json TEXT NULL,
                speaker_mapping_json TEXT NULL,
                speaker_overrides_json TEXT NULL,
                structured_json TEXT NULL,
                summary TEXT NULL,
                stage_timings_json TEXT NULL,
                warnings_json TEXT NULL,
                used_settings_json TEXT NULL,
                debug_json TEXT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_transcript_created
            ON transcript_pipeline_runs (transcript_id, created_at);

            CREATE TABLE IF NOT EXISTS session_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                session_id TEXT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NULL,
                summary TEXT NOT NULL,
                structured_json TEXT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_session_summaries_session_created
            ON session_summaries (session_id, created_at);

            CREATE TABLE IF NOT EXISTS source_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                session_id TEXT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NULL,
                title TEXT NULL,
                content TEXT NULL,
                metadata_json TEXT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS document_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                session_id TEXT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS document_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding_json TEXT NULL,
                metadata_json TEXT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (chunk_id) REFERENCES document_chunks(id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_source_documents_profile_source
            ON source_documents (profile_id, source_type, source_id);

            CREATE INDEX IF NOT EXISTS idx_document_chunks_profile
            ON document_chunks (profile_id, document_id, chunk_index);

            CREATE INDEX IF NOT EXISTS idx_document_embeddings_profile_model
            ON document_embeddings (profile_id, embedding_model);
            """
        )
        _ensure_column(conn, "chat_sessions", "role", "ALTER TABLE chat_sessions ADD COLUMN role TEXT NOT NULL DEFAULT 'free';")
        _ensure_column(conn, "profiles", "preferences_json", "ALTER TABLE profiles ADD COLUMN preferences_json TEXT NULL;")
        _ensure_column(conn, "model_settings", "pipeline_enabled", "ALTER TABLE model_settings ADD COLUMN pipeline_enabled INTEGER NULL;")
        _ensure_column(conn, "model_settings", "summary_memory_enabled", "ALTER TABLE model_settings ADD COLUMN summary_memory_enabled INTEGER NULL;")
        _ensure_column(conn, "model_settings", "rag_enabled", "ALTER TABLE model_settings ADD COLUMN rag_enabled INTEGER NULL;")
        _ensure_column(conn, "model_settings", "default_pipeline_preset", "ALTER TABLE model_settings ADD COLUMN default_pipeline_preset TEXT NULL;")
        _ensure_column(conn, "model_settings", "max_transcript_chars", "ALTER TABLE model_settings ADD COLUMN max_transcript_chars INTEGER NULL;")
        _ensure_column(conn, "model_settings", "max_context_chars", "ALTER TABLE model_settings ADD COLUMN max_context_chars INTEGER NULL;")
        _ensure_column(conn, "model_settings", "summary_memory_limit", "ALTER TABLE model_settings ADD COLUMN summary_memory_limit INTEGER NULL;")
        _ensure_column(conn, "model_settings", "rag_top_k", "ALTER TABLE model_settings ADD COLUMN rag_top_k INTEGER NULL;")
        _ensure_column(conn, "model_settings", "rag_max_context_chars", "ALTER TABLE model_settings ADD COLUMN rag_max_context_chars INTEGER NULL;")
        _ensure_column(conn, "model_settings", "pipeline_json", "ALTER TABLE model_settings ADD COLUMN pipeline_json TEXT NULL;")
        _ensure_column(conn, "transcripts", "summary", "ALTER TABLE transcripts ADD COLUMN summary TEXT NULL;")
        _ensure_column(conn, "transcripts", "structured_json", "ALTER TABLE transcripts ADD COLUMN structured_json TEXT NULL;")
        _ensure_column(conn, "transcripts", "latest_pipeline_run_id", "ALTER TABLE transcripts ADD COLUMN latest_pipeline_run_id INTEGER NULL;")
        conn.execute(
            "UPDATE profiles SET preferences_json = COALESCE(preferences_json, ?)",
            (default_preferences,),
        )
        _migrate_asr_studio_default(conn)
        conn.commit()
    ensure_default_profile()


def ensure_default_profile() -> int:
    default_preferences = _to_json(_default_profile_preferences()) or "{}"
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT id FROM profiles WHERE is_active = 1 ORDER BY id LIMIT 1;")
        row = cur.fetchone()
        if row:
            return int(row["id"])
        now = _utcnow()
        cur = conn.execute(
            """
            INSERT INTO profiles (name, description, color, preferences_json, created_at, updated_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            ("Default", "Default profile", None, default_preferences, now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_profiles(include_inactive: bool = False) -> list[dict[str, Any]]:
    ensure_default_profile()
    query = "SELECT * FROM profiles"
    params: list[Any] = []
    if not include_inactive:
        query += " WHERE is_active = 1"
    query += " ORDER BY created_at ASC"
    with closing(_connect()) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_profile_row_dict(row) for row in rows if row]


def get_profile(profile_id: int) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return _profile_row_dict(row)


def create_profile(name: str, description: str | None = None, color: str | None = None) -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("profile_name_required")
    now = _utcnow()
    default_preferences = _to_json(_default_profile_preferences()) or "{}"
    clean_description = description.strip() if isinstance(description, str) and description.strip() else None
    with closing(_connect()) as conn:
        cur = conn.execute(
            """
            INSERT INTO profiles (name, description, color, preferences_json, created_at, updated_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (name.strip(), clean_description, color, default_preferences, now, now),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
    return get_profile(new_id)  # type: ignore[return-value]


_PROFILE_UNSET = object()


def update_profile(
    profile_id: int,
    *,
    name: Any = _PROFILE_UNSET,
    description: Any = _PROFILE_UNSET,
    color: Any = _PROFILE_UNSET,
) -> dict[str, Any] | None:
    profile = get_profile(profile_id)
    if not profile:
        return None

    updates: list[str] = []
    params: list[Any] = []

    if name is not _PROFILE_UNSET:
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValueError("profile_name_required")
        updates.append("name = ?")
        params.append(clean_name)

    if description is not _PROFILE_UNSET:
        clean_description = description.strip() if isinstance(description, str) and description.strip() else None
        updates.append("description = ?")
        params.append(clean_description)

    if color is not _PROFILE_UNSET:
        clean_color = color.strip() if isinstance(color, str) and color.strip() else None
        updates.append("color = ?")
        params.append(clean_color)

    if not updates:
        return profile

    updates.append("updated_at = ?")
    params.append(_utcnow())
    params.append(profile_id)

    with closing(_connect()) as conn:
        conn.execute(f"UPDATE profiles SET {', '.join(updates)} WHERE id = ?", tuple(params))
        conn.commit()
    return get_profile(profile_id)


def update_profile_preferences(profile_id: int, updates: dict[str, Any]) -> dict[str, Any] | None:
    profile = get_profile(profile_id)
    if not profile:
        return None
    current_preferences = _normalize_profile_preferences(profile.get("preferences"))
    merged_preferences = _merge_dict(current_preferences, updates or {})
    with closing(_connect()) as conn:
        conn.execute(
            "UPDATE profiles SET preferences_json = ?, updated_at = ? WHERE id = ?",
            (_to_json(merged_preferences), _utcnow(), profile_id),
        )
        conn.commit()
    return get_profile(profile_id)


def delete_profile(profile_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        conn.commit()


def list_sessions(profile_id: int) -> list[dict[str, Any]]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            """
            SELECT id, profile_id, title, model_name, role, created_at, updated_at
            FROM chat_sessions
            WHERE profile_id = ?
            ORDER BY updated_at DESC
            """,
            (profile_id,),
        ).fetchall()
    return [_row_dict(row) for row in rows if row]


def get_session(session_id: str) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            """
            SELECT id, profile_id, title, model_name, role, created_at, updated_at, criteria_json
            FROM chat_sessions WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
    data = _row_dict(row)
    if data and data.get("criteria_json") is not None:
        data["criteria"] = _from_json(data["criteria_json"], [])
    return data


def create_session(
    profile_id: int, title: str, model_name: str, session_id: str | None = None, role: str = "free"
) -> dict[str, Any]:
    if not title.strip():
        raise ValueError("session_title_required")
    sid = session_id or str(uuid.uuid4())
    now = _utcnow()
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO chat_sessions (id, profile_id, title, model_name, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (sid, profile_id, title.strip(), model_name.strip(), role.strip() or "free", now, now),
        )
        conn.commit()
    return get_session(sid)  # type: ignore[return-value]


def delete_session(session_id: str) -> None:
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        conn.commit()


def reset_session(session_id: str) -> None:
    now = _utcnow()
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        conn.execute("UPDATE chat_sessions SET criteria_json = NULL, updated_at = ? WHERE id = ?", (now, session_id))
        conn.commit()


def update_session(
    session_id: str, *, title: str | None = None, model_name: str | None = None, role: str | None = None
) -> dict[str, Any] | None:
    fields: list[str] = []
    params: list[Any] = []
    if title is not None:
        fields.append("title = ?")
        params.append(title.strip())
    if model_name is not None:
        fields.append("model_name = ?")
        params.append(model_name.strip())
    if role is not None:
        fields.append("role = ?")
        params.append(role.strip())
    if not fields:
        return get_session(session_id)
    params.extend([_utcnow(), session_id])
    with closing(_connect()) as conn:
        conn.execute(
            f"UPDATE chat_sessions SET {', '.join(fields)}, updated_at = ? WHERE id = ?",
            params,
        )
        conn.commit()
    return get_session(session_id)  # type: ignore[return-value]


def add_message(session_id: str, role: str, content: str) -> None:
    now = _utcnow()
    with closing(_connect()) as conn:
        conn.execute(
            "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now),
        )
        conn.execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, session_id))
        conn.commit()


def get_messages(session_id: str, limit_pairs: int | None = None) -> list[dict[str, Any]]:
    limit = limit_pairs * 2 if limit_pairs else None
    query = """
        SELECT role, content, created_at
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY created_at DESC
    """
    params: list[Any] = [session_id]
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    with closing(_connect()) as conn:
        rows = conn.execute(query, params).fetchall()
    messages = [
        {"role": row["role"], "content": row["content"], "created_at": row["created_at"]}
        for row in rows
        if row
    ]
    messages.reverse()
    return messages


def save_session_criteria(session_id: str, criteria: list[str]) -> None:
    now = _utcnow()
    with closing(_connect()) as conn:
        conn.execute(
            "UPDATE chat_sessions SET criteria_json = ?, updated_at = ? WHERE id = ?",
            (_to_json(criteria or []), now, session_id),
        )
        conn.commit()


def get_session_criteria(session_id: str) -> list[str]:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT criteria_json FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return []
    return _from_json(row["criteria_json"], [])  # type: ignore[arg-type]


def create_transcript(
    profile_id: int,
    name: str,
    content: str,
    *,
    session_id: str | None = None,
    source_path: str | None = None,
    language: str | None = None,
    timeline: Iterable[dict[str, Any]] | None = None,
    role_keywords: dict[str, Any] | None = None,
    labels: dict[str, Any] | None = None,
    summary: str | None = None,
    structured_json: dict[str, Any] | list[Any] | None = None,
    latest_pipeline_run_id: int | None = None,
) -> dict[str, Any]:
    if not content.strip():
        raise ValueError("transcript_required")
    now = _utcnow()
    with closing(_connect()) as conn:
        cur = conn.execute(
            """
            INSERT INTO transcripts (
                profile_id, session_id, name, source_path, content, summary, structured_json, latest_pipeline_run_id, language,
                timeline_json, role_keywords_json, labels_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                session_id,
                name.strip(),
                source_path,
                content,
                summary,
                _to_json(structured_json),
                latest_pipeline_run_id,
                language,
                _to_json(list(timeline) if timeline is not None else None),
                _to_json(role_keywords),
                _to_json(labels),
                now,
                now,
            ),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
    return get_transcript(new_id)  # type: ignore[return-value]


def list_transcripts(
    profile_id: int,
    session_id: str | None = None,
    *,
    origin: str | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT id, profile_id, session_id, name, source_path, content,
               summary, structured_json, latest_pipeline_run_id, language,
               timeline_json, role_keywords_json, labels_json, created_at, updated_at
        FROM transcripts
        WHERE profile_id = ?
    """
    params: list[Any] = [profile_id]
    if session_id:
        query += " AND session_id = ?"
        params.append(session_id)
    query += " ORDER BY updated_at DESC"
    with closing(_connect()) as conn:
        rows = conn.execute(query, params).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = _row_dict(row)
        if not item:
            continue
        item["timeline"] = _from_json(item.pop("timeline_json", None), [])
        item["role_keywords"] = _from_json(item.pop("role_keywords_json", None), {})
        item["labels"] = _from_json(item.pop("labels_json", None), {})
        item["structured_json"] = _from_json(item.get("structured_json"), None)
        result.append(item)
    if origin is None:
        return result

    expected_origin = str(origin).strip()
    if not expected_origin:
        return result

    return [
        item
        for item in result
        if str((item.get("labels") or {}).get("origin") or "").strip() == expected_origin
    ]


def get_transcript(transcript_id: int) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            """
            SELECT id, profile_id, session_id, name, source_path, content,
                   summary, structured_json, latest_pipeline_run_id, language,
                   timeline_json, role_keywords_json, labels_json, created_at, updated_at
            FROM transcripts WHERE id = ?
            """,
            (transcript_id,),
        ).fetchone()
    item = _row_dict(row)
    if not item:
        return None
    item["timeline"] = _from_json(item.pop("timeline_json", None), [])
    item["role_keywords"] = _from_json(item.pop("role_keywords_json", None), {})
    item["labels"] = _from_json(item.pop("labels_json", None), {})
    item["structured_json"] = _from_json(item.get("structured_json"), None)
    return item


def update_transcript(
    transcript_id: int,
    *,
    name: str | None = None,
    content: str | None = None,
    language: str | None = None,
    timeline: Iterable[dict[str, Any]] | None = None,
    role_keywords: dict[str, Any] | None = None,
    labels: dict[str, Any] | None = None,
    summary: str | None = None,
    structured_json: dict[str, Any] | list[Any] | None = None,
    latest_pipeline_run_id: int | None = None,
) -> dict[str, Any] | None:
    now = _utcnow()
    fields: list[str] = []
    params: list[Any] = []
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if content is not None:
        fields.append("content = ?")
        params.append(content)
    if language is not None:
        fields.append("language = ?")
        params.append(language)
    if timeline is not None:
        fields.append("timeline_json = ?")
        params.append(_to_json(list(timeline)))
    if role_keywords is not None:
        fields.append("role_keywords_json = ?")
        params.append(_to_json(role_keywords))
    if labels is not None:
        fields.append("labels_json = ?")
        params.append(_to_json(labels))
    if summary is not None:
        fields.append("summary = ?")
        params.append(summary)
    if structured_json is not None:
        fields.append("structured_json = ?")
        params.append(_to_json(structured_json))
    if latest_pipeline_run_id is not None:
        fields.append("latest_pipeline_run_id = ?")
        params.append(latest_pipeline_run_id)
    if not fields:
        return get_transcript(transcript_id)
    params.extend([now, transcript_id])
    with closing(_connect()) as conn:
        conn.execute(f"UPDATE transcripts SET {', '.join(fields)}, updated_at = ? WHERE id = ?", params)
        conn.commit()
    return get_transcript(transcript_id)


def delete_transcript(transcript_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM transcripts WHERE id = ?", (transcript_id,))
        conn.commit()


def delete_transcripts(
    profile_id: int,
    session_id: str | None = None,
    *,
    origin: str | None = None,
) -> int:
    items = list_transcripts(profile_id, session_id=session_id, origin=origin)
    ids = [int(item["id"]) for item in items if item.get("id") is not None]
    if not ids:
        return 0

    placeholders = ", ".join("?" for _ in ids)
    with closing(_connect()) as conn:
        conn.execute(f"DELETE FROM transcripts WHERE id IN ({placeholders})", ids)
        conn.commit()
    return len(ids)


def get_latest_transcript_for_session(session_id: str) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            """
            SELECT id, content, language, timeline_json, role_keywords_json, labels_json
            FROM transcripts
            WHERE session_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
    item = _row_dict(row)
    if not item:
        return None
    item["timeline"] = _from_json(item.pop("timeline_json", None), [])
    item["role_keywords"] = _from_json(item.pop("role_keywords_json", None), {})
    item["labels"] = _from_json(item.pop("labels_json", None), {})
    return item


def get_model_settings(profile_id: int, model_name: str) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            """
            SELECT id, profile_id, model_name, temperature, max_tokens, num_ctx, mem_turns,
                   pipeline_enabled, summary_memory_enabled, rag_enabled,
                   default_pipeline_preset, max_transcript_chars, max_context_chars,
                   summary_memory_limit, rag_top_k, rag_max_context_chars, pipeline_json,
                   created_at, updated_at
            FROM model_settings
            WHERE profile_id = ? AND model_name = ?
            """,
            (profile_id, model_name),
        ).fetchone()
    data = _row_dict(row)
    if data and data.get("pipeline_json") is not None:
        data["pipeline"] = _from_json(data.get("pipeline_json"), {})
    return data


def upsert_model_settings(
    profile_id: int,
    model_name: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    num_ctx: int | None = None,
    mem_turns: int | None = None,
    pipeline_enabled: bool | None = None,
    summary_memory_enabled: bool | None = None,
    rag_enabled: bool | None = None,
    default_pipeline_preset: str | None = None,
    max_transcript_chars: int | None = None,
    max_context_chars: int | None = None,
    summary_memory_limit: int | None = None,
    rag_top_k: int | None = None,
    rag_max_context_chars: int | None = None,
    pipeline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _utcnow()
    existing = get_model_settings(profile_id, model_name)
    pipeline_enabled_db = None if pipeline_enabled is None else int(bool(pipeline_enabled))
    summary_memory_enabled_db = None if summary_memory_enabled is None else int(bool(summary_memory_enabled))
    rag_enabled_db = None if rag_enabled is None else int(bool(rag_enabled))
    pipeline_json = _to_json(pipeline) if pipeline is not None else None
    with closing(_connect()) as conn:
        if existing:
            conn.execute(
                """
                UPDATE model_settings
                SET temperature = ?, max_tokens = ?, num_ctx = ?, mem_turns = ?,
                    pipeline_enabled = ?, summary_memory_enabled = ?, rag_enabled = ?,
                    default_pipeline_preset = ?, max_transcript_chars = ?, max_context_chars = ?,
                    summary_memory_limit = ?, rag_top_k = ?, rag_max_context_chars = ?,
                    pipeline_json = ?, updated_at = ?
                WHERE profile_id = ? AND model_name = ?
                """,
                (
                    temperature,
                    max_tokens,
                    num_ctx,
                    mem_turns,
                    pipeline_enabled_db,
                    summary_memory_enabled_db,
                    rag_enabled_db,
                    default_pipeline_preset,
                    max_transcript_chars,
                    max_context_chars,
                    summary_memory_limit,
                    rag_top_k,
                    rag_max_context_chars,
                    pipeline_json,
                    now,
                    profile_id,
                    model_name,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO model_settings (
                    profile_id, model_name, temperature, max_tokens, num_ctx, mem_turns,
                    pipeline_enabled, summary_memory_enabled, rag_enabled,
                    default_pipeline_preset, max_transcript_chars, max_context_chars,
                    summary_memory_limit, rag_top_k, rag_max_context_chars,
                    pipeline_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    model_name,
                    temperature,
                    max_tokens,
                    num_ctx,
                    mem_turns,
                    pipeline_enabled_db,
                    summary_memory_enabled_db,
                    rag_enabled_db,
                    default_pipeline_preset,
                    max_transcript_chars,
                    max_context_chars,
                    summary_memory_limit,
                    rag_top_k,
                    rag_max_context_chars,
                    pipeline_json,
                    now,
                    now,
                ),
            )
        conn.commit()
    return get_model_settings(profile_id, model_name)  # type: ignore[return-value]


def reset_model_settings(profile_id: int, model_name: str) -> None:
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM model_settings WHERE profile_id = ? AND model_name = ?", (profile_id, model_name))
        conn.commit()


def effective_settings(profile_id: int, model_name: str, defaults: dict[str, Any]) -> dict[str, Any]:
    overrides = get_model_settings(profile_id, model_name) or {}
    profile = get_profile(profile_id) or {}
    profile_settings = ((profile.get("preferences") or {}).get("settings") or {}) if isinstance(profile, dict) else {}
    effective: dict[str, Any] = _clone_jsonable(defaults)
    if isinstance(profile_settings, dict):
        _merge_dict(effective, profile_settings)
    keys = (
        "temperature",
        "max_tokens",
        "num_ctx",
        "mem_turns",
        "pipeline_enabled",
        "summary_memory_enabled",
        "rag_enabled",
        "default_pipeline_preset",
        "max_transcript_chars",
        "max_context_chars",
        "summary_memory_limit",
        "rag_top_k",
        "rag_max_context_chars",
    )
    for key in keys:
        override_value = overrides.get(key)
        if override_value is not None:
            if key in {"pipeline_enabled", "summary_memory_enabled", "rag_enabled"}:
                effective[key] = bool(override_value)
            else:
                effective[key] = override_value
    if isinstance(overrides.get("pipeline"), dict):
        pipeline = _clone_jsonable(effective.get("pipeline") or {})
        _merge_dict(pipeline, overrides["pipeline"])
        effective["pipeline"] = pipeline
    effective["num_ctx_requested"] = effective.get("num_ctx")
    effective["num_ctx_applied"] = False
    effective["num_ctx_apply_method"] = "openai_compatible_not_supported"
    settings_keys = tuple([*keys, "pipeline"])
    return {
        "profile_id": profile_id,
        "model_name": model_name,
        "effective": effective,
        "overrides": {key: overrides.get(key) for key in settings_keys},
        "defaults": {key: defaults.get(key) for key in settings_keys},
    }


def count_messages(session_id: str) -> int:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM chat_messages WHERE session_id = ?", (session_id,)).fetchone()
    return int(row["count"] if row else 0)


def get_messages_before_latest(session_id: str, keep_pairs: int) -> list[dict[str, Any]]:
    keep_count = max(0, int(keep_pairs or 0) * 2)
    query = """
        SELECT role, content, created_at
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY created_at ASC
    """
    with closing(_connect()) as conn:
        rows = conn.execute(query, (session_id,)).fetchall()
    messages = [
        {"role": row["role"], "content": row["content"], "created_at": row["created_at"]}
        for row in rows
        if row
    ]
    if keep_count <= 0:
        return messages
    return messages[:-keep_count]


def create_session_summary(
    *,
    profile_id: int,
    session_id: str | None,
    source_type: str,
    source_id: str | None,
    summary: str,
    structured_json: dict[str, Any] | list[Any] | None = None,
) -> dict[str, Any]:
    now = _utcnow()
    with closing(_connect()) as conn:
        cur = conn.execute(
            """
            INSERT INTO session_summaries (
                profile_id, session_id, source_type, source_id, summary, structured_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (profile_id, session_id, source_type, source_id, summary, _to_json(structured_json), now, now),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
    return get_session_summary(new_id) or {}


def get_session_summary(summary_id: int) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM session_summaries WHERE id = ?", (summary_id,)).fetchone()
    data = _row_dict(row)
    if data:
        data["structured_json"] = _from_json(data.get("structured_json"), None)
    return data


def get_session_summary_by_source(session_id: str, source_type: str, source_id: str | None) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            """
            SELECT * FROM session_summaries
            WHERE session_id = ? AND source_type = ? AND COALESCE(source_id, '') = COALESCE(?, '')
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (session_id, source_type, source_id),
        ).fetchone()
    data = _row_dict(row)
    if data:
        data["structured_json"] = _from_json(data.get("structured_json"), None)
    return data


def list_session_summaries(session_id: str, *, limit: int = 5, source_type: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM session_summaries WHERE session_id = ?"
    params: list[Any] = [session_id]
    if source_type:
        query += " AND source_type = ?"
        params.append(source_type)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(max(1, int(limit or 5)))
    with closing(_connect()) as conn:
        rows = conn.execute(query, params).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = _row_dict(row)
        if not item:
            continue
        item["structured_json"] = _from_json(item.get("structured_json"), None)
        result.append(item)
    result.reverse()
    return result


def create_pipeline_run(
    *,
    transcript_id: int,
    profile_id: int,
    session_id: str | None,
    preset: str,
    action: str,
    raw_transcript: str,
    cleaned_transcript: str | None,
    segments: list[dict[str, Any]] | None,
    speaker_mapping: list[dict[str, Any]] | None,
    speaker_overrides: dict[str, Any] | None,
    structured_json: dict[str, Any] | list[Any] | None,
    summary: str | None,
    stage_timings: dict[str, Any] | None,
    warnings: list[str] | None,
    used_settings: dict[str, Any] | None,
    debug: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _utcnow()
    with closing(_connect()) as conn:
        cur = conn.execute(
            """
            INSERT INTO transcript_pipeline_runs (
                transcript_id, profile_id, session_id, preset, action, raw_transcript,
                cleaned_transcript, segments_json, speaker_mapping_json, speaker_overrides_json,
                structured_json, summary, stage_timings_json, warnings_json, used_settings_json,
                debug_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transcript_id,
                profile_id,
                session_id,
                preset,
                action,
                raw_transcript,
                cleaned_transcript,
                _to_json(segments),
                _to_json(speaker_mapping),
                _to_json(speaker_overrides),
                _to_json(structured_json),
                summary,
                _to_json(stage_timings),
                _to_json(warnings),
                _to_json(used_settings),
                _to_json(debug),
                now,
                now,
            ),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
    return get_pipeline_run(new_id) or {}


def _pipeline_row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    data = _row_dict(row)
    if not data:
        return None
    data["segments"] = _from_json(data.pop("segments_json", None), [])
    data["speaker_mapping"] = _from_json(data.pop("speaker_mapping_json", None), [])
    data["speaker_overrides"] = _from_json(data.pop("speaker_overrides_json", None), {})
    data["structured_json"] = _from_json(data.pop("structured_json", None), None)
    data["stage_timings"] = _from_json(data.pop("stage_timings_json", None), {})
    data["warnings"] = _from_json(data.pop("warnings_json", None), [])
    data["used_settings"] = _from_json(data.pop("used_settings_json", None), {})
    data["debug"] = _from_json(data.pop("debug_json", None), {})
    return data


def get_pipeline_run(run_id: int) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM transcript_pipeline_runs WHERE id = ?", (run_id,)).fetchone()
    return _pipeline_row_dict(row)


def get_latest_pipeline_run(transcript_id: int) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            """
            SELECT * FROM transcript_pipeline_runs
            WHERE transcript_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (transcript_id,),
        ).fetchone()
    return _pipeline_row_dict(row)


def update_pipeline_run(
    run_id: int,
    *,
    cleaned_transcript: str | None = None,
    segments: list[dict[str, Any]] | None = None,
    speaker_mapping: list[dict[str, Any]] | None = None,
    speaker_overrides: dict[str, Any] | None = None,
    structured_json: dict[str, Any] | list[Any] | None = None,
    summary: str | None = None,
    stage_timings: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    used_settings: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    fields: list[str] = []
    params: list[Any] = []
    mapping = {
        "cleaned_transcript": cleaned_transcript,
        "segments_json": _to_json(segments) if segments is not None else None,
        "speaker_mapping_json": _to_json(speaker_mapping) if speaker_mapping is not None else None,
        "speaker_overrides_json": _to_json(speaker_overrides) if speaker_overrides is not None else None,
        "structured_json": _to_json(structured_json) if structured_json is not None else None,
        "summary": summary,
        "stage_timings_json": _to_json(stage_timings) if stage_timings is not None else None,
        "warnings_json": _to_json(warnings) if warnings is not None else None,
        "used_settings_json": _to_json(used_settings) if used_settings is not None else None,
        "debug_json": _to_json(debug) if debug is not None else None,
    }
    for column, value in mapping.items():
        if value is None:
            continue
        fields.append(f"{column} = ?")
        params.append(value)
    if not fields:
        return get_pipeline_run(run_id)
    fields.append("updated_at = ?")
    params.extend([_utcnow(), run_id])
    with closing(_connect()) as conn:
        conn.execute(f"UPDATE transcript_pipeline_runs SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
    return get_pipeline_run(run_id)


def create_source_document(
    *,
    profile_id: int,
    session_id: str | None,
    source_type: str,
    source_id: str | None,
    title: str | None,
    content: str | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    now = _utcnow()
    with closing(_connect()) as conn:
        cur = conn.execute(
            """
            INSERT INTO source_documents (
                profile_id, session_id, source_type, source_id, title, content,
                metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (profile_id, session_id, source_type, source_id, title, content, _to_json(metadata), now, now),
        )
        conn.commit()
        doc_id = int(cur.lastrowid)
    return get_source_document(doc_id) or {}


def delete_source_document(profile_id: int, source_type: str, source_id: str | None) -> int:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "DELETE FROM source_documents WHERE profile_id = ? AND source_type = ? AND source_id = ?",
            (profile_id, source_type, source_id),
        )
        conn.commit()
        return int(cur.rowcount or 0)


def _source_document_row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    data = _row_dict(row)
    if not data:
        return None
    data["metadata"] = _from_json(data.pop("metadata_json", None), {})
    return data


def get_source_document(document_id: int) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM source_documents WHERE id = ?", (document_id,)).fetchone()
    return _source_document_row_dict(row)


def list_source_documents(profile_id: int | None = None, source_type: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM source_documents"
    clauses: list[str] = []
    params: list[Any] = []
    if profile_id is not None:
        clauses.append("profile_id = ?")
        params.append(profile_id)
    if source_type:
        clauses.append("source_type = ?")
        params.append(source_type)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY updated_at DESC, id DESC"
    with closing(_connect()) as conn:
        rows = conn.execute(query, params).fetchall()
    return [item for row in rows if (item := _source_document_row_dict(row))]


def create_document_chunk(
    *,
    document_id: int,
    profile_id: int,
    session_id: str | None,
    chunk_index: int,
    content: str,
    metadata: dict[str, Any] | None,
) -> int:
    now = _utcnow()
    with closing(_connect()) as conn:
        cur = conn.execute(
            """
            INSERT INTO document_chunks (
                document_id, profile_id, session_id, chunk_index, content,
                metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (document_id, profile_id, session_id, chunk_index, content, _to_json(metadata), now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def create_document_embedding(
    *,
    chunk_id: int,
    profile_id: int,
    embedding_model: str,
    embedding: list[float],
    metadata: dict[str, Any] | None,
) -> int:
    now = _utcnow()
    with closing(_connect()) as conn:
        cur = conn.execute(
            """
            INSERT INTO document_embeddings (
                chunk_id, profile_id, embedding_model, embedding_json,
                metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (chunk_id, profile_id, embedding_model, _to_json(embedding), _to_json(metadata), now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_rag_chunks(profile_id: int, embedding_model: str | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.profile_id,
            c.session_id,
            c.chunk_index,
            c.content,
            c.metadata_json AS chunk_metadata_json,
            d.source_type,
            d.source_id,
            d.title,
            d.metadata_json AS document_metadata_json,
            e.embedding_model,
            e.embedding_json,
            e.metadata_json AS embedding_metadata_json
        FROM document_chunks c
        JOIN source_documents d ON d.id = c.document_id
        JOIN document_embeddings e ON e.chunk_id = c.id
        WHERE c.profile_id = ?
    """
    params: list[Any] = [profile_id]
    if embedding_model:
        query += " AND e.embedding_model = ?"
        params.append(embedding_model)
    query += " ORDER BY d.updated_at DESC, c.chunk_index ASC"
    with closing(_connect()) as conn:
        rows = conn.execute(query, params).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = _row_dict(row) or {}
        item["chunk_metadata"] = _from_json(item.pop("chunk_metadata_json", None), {})
        item["document_metadata"] = _from_json(item.pop("document_metadata_json", None), {})
        item["embedding"] = _from_json(item.pop("embedding_json", None), [])
        item["embedding_metadata"] = _from_json(item.pop("embedding_metadata_json", None), {})
        result.append(item)
    return result


def rag_stats(profile_id: int | None = None) -> dict[str, Any]:
    params: list[Any] = []
    profile_clause = ""
    if profile_id is not None:
        profile_clause = " WHERE profile_id = ?"
        params.append(profile_id)
    with closing(_connect()) as conn:
        doc_count = conn.execute(f"SELECT COUNT(*) AS n FROM source_documents{profile_clause}", params).fetchone()["n"]
        chunk_count = conn.execute(f"SELECT COUNT(*) AS n FROM document_chunks{profile_clause}", params).fetchone()["n"]
        embedding_count = conn.execute(f"SELECT COUNT(*) AS n FROM document_embeddings{profile_clause}", params).fetchone()["n"]
    return {
        "documents": int(doc_count or 0),
        "chunks": int(chunk_count or 0),
        "embeddings": int(embedding_count or 0),
    }


_MAINTENANCE_TABLES = (
    "transcripts",
    "transcript_pipeline_runs",
    "session_summaries",
    "source_documents",
    "document_chunks",
    "document_embeddings",
)

_RESET_TABLES = (
    "profiles",
    "chat_sessions",
    "chat_messages",
    "transcripts",
    "transcript_pipeline_runs",
    "session_summaries",
    "source_documents",
    "document_chunks",
    "document_embeddings",
    "model_settings",
)


def _table_counts(conn: sqlite3.Connection, tables: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in tables:
        row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
        counts[table] = int(row["count"] if row else 0)
    return counts


def _vacuum_database() -> None:
    with closing(_connect()) as conn:
        conn.execute("VACUUM")


def cleanup_database_garbage(*, vacuum: bool = True) -> dict[str, Any]:
    with closing(_connect()) as conn:
        before = _table_counts(conn, _MAINTENANCE_TABLES)

        transcript_rows = conn.execute(
            """
            SELECT id, labels_json
            FROM transcripts
            WHERE session_id IS NULL
            """
        ).fetchall()
        transcript_ids: list[int] = []
        for row in transcript_rows:
            labels = _from_json(row["labels_json"], {}) or {}
            origin = str(labels.get("origin") or "").strip()
            if origin in {"", "asr_context"}:
                transcript_ids.append(int(row["id"]))

        if transcript_ids:
            placeholders = ", ".join("?" for _ in transcript_ids)
            conn.execute(f"DELETE FROM transcripts WHERE id IN ({placeholders})", transcript_ids)

        conn.execute(
            """
            DELETE FROM session_summaries
            WHERE session_id IS NULL
              AND (
                source_type = 'chat'
                OR (
                  source_type = 'asr'
                  AND (
                    source_id IS NULL
                    OR NOT EXISTS (
                      SELECT 1
                      FROM transcripts
                      WHERE transcripts.id = CAST(session_summaries.source_id AS INTEGER)
                    )
                  )
                )
              )
            """
        )
        conn.execute(
            """
            DELETE FROM source_documents
            WHERE session_id IS NULL
              AND source_type != 'manual_file'
            """
        )

        conn.commit()
        after = _table_counts(conn, _MAINTENANCE_TABLES)

    if vacuum:
        _vacuum_database()

    return {
        "status": "ok",
        "vacuum": bool(vacuum),
        "deleted": {table: max(0, before[table] - after[table]) for table in _MAINTENANCE_TABLES},
        "remaining": after,
    }


def reset_database(*, vacuum: bool = True) -> dict[str, Any]:
    with closing(_connect()) as conn:
        before = _table_counts(conn, _RESET_TABLES)
        conn.execute("DELETE FROM profiles")
        conn.commit()

    default_profile_id = ensure_default_profile()

    if vacuum:
        _vacuum_database()

    with closing(_connect()) as conn:
        after = _table_counts(conn, _RESET_TABLES)

    return {
        "status": "ok",
        "vacuum": bool(vacuum),
        "default_profile_id": default_profile_id,
        "deleted": {table: max(0, before[table] - after[table]) for table in _RESET_TABLES},
        "remaining": after,
    }
