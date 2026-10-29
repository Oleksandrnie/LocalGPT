"""Resolve evidence links from indexed provenance, never from model suggestions."""
from __future__ import annotations

import re
from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException

from app import db
from backend.apps.telegram_search.links import telegram_permalink


def links_requested(query: str) -> bool:
    # A direct negative request wins; LLM expansions cannot turn links on.
    if re.search(r'без\s+ссыл\w*|не\s+(?:(?:добавляй|генерируй|выводи|показывай)\s+)?ссыл\w*|(?:without|no)\s+links?', query, re.I):
        return False
    return bool(re.search(
        r'(?:сгенерир\w*|добав\w*|покаж\w*|вывед\w*|дай|предостав\w*|найди|generate|include|show|give).{0,80}(?:ссыл\w*|\blinks?\b|\burls?\b)'
        r'|со\s+ссылками|ссылки\s+на\s+сообщения|with\s+(?:links?|urls?)', query, re.I))


def attach_links(evidence: list[dict], *, candidates: list[dict], query: str,
                 profile_id: int, session_id: str | None) -> bool:
    requested = links_requested(query)
    if not requested:
        return False
    by_id = {str(item.get('chunk_id')): item for item in candidates}
    for item in evidence:
        candidate = by_id.get(str(item.get('chunk_id')))
        item['links'] = []
        item.pop('telegram_link_unavailable', None)
        if not candidate:
            continue
        # These candidates must already have passed profile/session-scoped retrieval.
        chunk_meta = candidate.get('chunk_metadata') or {}
        direct = telegram_permalink(chunk_meta.get('message_url'))
        if direct:
            item['links'].append({'label': 'Открыть сообщение в Telegram', 'url': direct, 'kind': 'telegram'})
        chunk_id = item.get('chunk_id')
        if isinstance(chunk_id, int) and chunk_id > 0:
            params = {'profile_id': profile_id}
            if session_id:
                params['session_id'] = session_id
            item['links'].append({'label': 'Открыть исходный фрагмент локально',
                                  'url': f'/rag/evidence/{chunk_id}?' + urlencode(params), 'kind': 'local_evidence'})
        if chunk_meta.get('format') == 'telegram_html' and not direct:
            item['telegram_link_unavailable'] = True
    return True


def evidence_page(profile_id: int, chunk_id: int, session_id: str | None) -> str:
    if not db.get_profile(profile_id):
        raise HTTPException(404, 'profile_not_found')
    if session_id:
        session = db.get_session(session_id)
        if not session or session.get('profile_id') != profile_id:
            raise HTTPException(404, 'session_not_found')
    # Reuse the same document/session visibility rules as retrieval. No path or
    # URL from the caller is opened, and embedded source HTML is never served.
    chunks = db.list_rag_chunks(profile_id, session_id=session_id)
    selected = next((item for item in chunks if item['chunk_id'] == chunk_id), None)
    if not selected:
        raise HTTPException(404, 'evidence_not_found')
    meta = selected.get('chunk_metadata') or {}
    parts = [selected]
    if meta.get('format') == 'telegram_html' and meta.get('message_id'):
        parts = list({item['chunk_id']: item for item in chunks
                      if item['document_id'] == selected['document_id']
                      and (item.get('chunk_metadata') or {}).get('message_id') == meta['message_id']}.values())
        parts.sort(key=lambda item: item['chunk_index'])
    title = str(selected.get('source_id') or 'Источник')
    text = '\n\n'.join(item['content'] for item in parts)
    return ('<!doctype html><html lang="ru"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Исходный фрагмент</title><body><h1>' + escape(title) + '</h1>'
            '<p>Локальная копия индексированного источника. ID: ' + escape(str(meta.get('message_id') or chunk_id))
            + '</p><pre style="white-space:pre-wrap;overflow-wrap:anywhere">' + escape(text) + '</pre></body></html>')
