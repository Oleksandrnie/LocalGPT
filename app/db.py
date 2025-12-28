import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "db" / "localgpt.db"


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


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cursor = conn.execute(f"PRAGMA table_info({table});")
    columns = {row[1] for row in cursor.fetchall()}
    if column not in columns:
        conn.execute(ddl)


def init_db() -> None:
    with closing(_connect()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NULL,
                color TEXT NULL,
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
            """
        )
        _ensure_column(conn, "chat_sessions", "role", "ALTER TABLE chat_sessions ADD COLUMN role TEXT NOT NULL DEFAULT 'free';")
        conn.commit()
    ensure_default_profile()


def ensure_default_profile() -> int:
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT id FROM profiles WHERE is_active = 1 ORDER BY id LIMIT 1;")
        row = cur.fetchone()
        if row:
            return int(row["id"])
        now = _utcnow()
        cur = conn.execute(
            """
            INSERT INTO profiles (name, description, color, created_at, updated_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            ("Default", "Default profile", None, now, now),
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
    return [_row_dict(row) for row in rows if row]


def get_profile(profile_id: int) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return _row_dict(row)


def create_profile(name: str, description: str | None = None, color: str | None = None) -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("profile_name_required")
    now = _utcnow()
    with closing(_connect()) as conn:
        cur = conn.execute(
            """
            INSERT INTO profiles (name, description, color, created_at, updated_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (name.strip(), description, color, now, now),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
    return get_profile(new_id)  # type: ignore[return-value]


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
    messages = [{"role": row["role"], "content": row["content"]} for row in rows if row]
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
) -> dict[str, Any]:
    if not content.strip():
        raise ValueError("transcript_required")
    now = _utcnow()
    with closing(_connect()) as conn:
        cur = conn.execute(
            """
            INSERT INTO transcripts (
                profile_id, session_id, name, source_path, content, language,
                timeline_json, role_keywords_json, labels_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                session_id,
                name.strip(),
                source_path,
                content,
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


def list_transcripts(profile_id: int, session_id: str | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT id, profile_id, session_id, name, source_path, content, language,
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
        result.append(item)
    return result


def get_transcript(transcript_id: int) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            """
            SELECT id, profile_id, session_id, name, source_path, content, language,
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
                   created_at, updated_at
            FROM model_settings
            WHERE profile_id = ? AND model_name = ?
            """,
            (profile_id, model_name),
        ).fetchone()
    return _row_dict(row)


def upsert_model_settings(
    profile_id: int,
    model_name: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    num_ctx: int | None = None,
    mem_turns: int | None = None,
) -> dict[str, Any]:
    now = _utcnow()
    existing = get_model_settings(profile_id, model_name)
    with closing(_connect()) as conn:
        if existing:
            conn.execute(
                """
                UPDATE model_settings
                SET temperature = ?, max_tokens = ?, num_ctx = ?, mem_turns = ?, updated_at = ?
                WHERE profile_id = ? AND model_name = ?
                """,
                (temperature, max_tokens, num_ctx, mem_turns, now, profile_id, model_name),
            )
        else:
            conn.execute(
                """
                INSERT INTO model_settings (profile_id, model_name, temperature, max_tokens, num_ctx, mem_turns, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (profile_id, model_name, temperature, max_tokens, num_ctx, mem_turns, now, now),
            )
        conn.commit()
    return get_model_settings(profile_id, model_name)  # type: ignore[return-value]


def reset_model_settings(profile_id: int, model_name: str) -> None:
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM model_settings WHERE profile_id = ? AND model_name = ?", (profile_id, model_name))
        conn.commit()


def effective_settings(profile_id: int, model_name: str, defaults: dict[str, Any]) -> dict[str, Any]:
    overrides = get_model_settings(profile_id, model_name) or {}
    effective: dict[str, Any] = {}
    keys = ("temperature", "max_tokens", "num_ctx", "mem_turns")
    for key in keys:
        override_value = overrides.get(key)
        effective[key] = override_value if override_value is not None else defaults.get(key)
    return {
        "profile_id": profile_id,
        "model_name": model_name,
        "effective": effective,
        "overrides": {key: overrides.get(key) for key in keys},
        "defaults": {key: defaults.get(key) for key in keys},
    }
