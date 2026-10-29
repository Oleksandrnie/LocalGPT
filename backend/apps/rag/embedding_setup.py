"""Explicit model setup with per-profile activation after successful reindex."""
from __future__ import annotations

import json
from urllib.request import Request
from fastapi import HTTPException
from app import config, db
from app.services import models
from backend.apps.rag import embeddings, reindex_tasks, service


def _profile(profile_id):
    if not db.get_profile(profile_id):
        raise HTTPException(404, 'profile_not_found')
    if not embeddings.is_loopback_endpoint(config.SETTINGS.base_url):
        raise HTTPException(409, 'semantic_setup_requires_local_ollama')


def _model():
    model = models.validate_pull_model_ref(config.SETTINGS.rag_embedding_model)
    return model if ":" in model.rsplit("/", 1)[-1] else model + ":latest"


def _installed():
    base = embeddings._ollama_base_url(config.SETTINGS.base_url)
    try:
        with embeddings.open_local_request(Request(base+'/api/tags'), timeout=5) as response:
            payload = json.loads(response.read())
        if not isinstance(payload, dict) or not isinstance(payload.get('models'), list):
            raise ValueError('invalid model list')
        return next((m for m in payload['models'] if isinstance(m, dict) and m.get('name') == _model()), None)
    except (OSError, ValueError, embeddings.EmbeddingError) as exc:
        raise HTTPException(503, {'code':'local_ollama_unavailable','message':'Не удалось получить список моделей. Проверьте, что локальный Ollama запущен.'}) from exc


def status(profile_id):
    _profile(profile_id)
    installed = _installed()
    provider = service._embedding_provider(profile_id)
    generation = db.rag_embedding_generation_stats(profile_id, provider.descriptor.storage_key)
    configured = provider.descriptor.provider == 'ollama'
    fingerprint = str((installed or {}).get('digest') or '').removeprefix('sha256:')[:16]
    pinned = db.get_app_setting(f'rag_embedding_profile:{profile_id}')
    weights_match = bool(installed) and (not pinned or provider.descriptor.version.endswith('-' + fingerprint))
    downloads = models.pull_statuses().get('downloads', [])
    download = next((item for item in reversed(downloads) if item.get('model') == _model()), None)
    return {'profile_id': profile_id, 'model': _model(), 'installed': installed is not None,
            'active': configured and weights_match and generation['missing_chunks'] == 0,
            'configured': configured, 'generation': generation,
            'provider': provider.descriptor.as_metadata(), 'download': download,
            'operation': reindex_tasks.latest_reindex_task(profile_id)}


def install(profile_id):
    _profile(profile_id)
    if _installed():
        return {'installed': True, 'model': _model(), 'task': None}
    return {'installed': False, 'model': _model(), 'task': models.start_model_pull(_model())}


def activate(profile_id):
    _profile(profile_id)
    installed = _installed()
    if not installed:
        raise HTTPException(409, {'code':'embedding_model_not_installed','message':'Сначала установите embedding-модель через кнопку загрузки.'})
    # Pin the generation to the actual installed weights, not a mutable :latest tag.
    digest = str(installed.get('digest') or '').removeprefix('sha256:')[:16]
    if not digest or not all(c in '0123456789abcdef' for c in digest.lower()):
        raise HTTPException(409, 'embedding_model_digest_unavailable')
    version = config.SETTINGS.rag_embedding_version + '-' + digest
    provider = embeddings.OllamaEmbeddingProvider(base_url=config.SETTINGS.base_url, model=_model(),
        version=version, dimensions=config.SETTINGS.rag_embedding_dimensions,
        timeout_seconds=config.SETTINGS.rag_embedding_timeout_seconds,
        warm_keep_alive=config.SETTINGS.rag_embedding_keep_alive)
    provider.local_only = True
    # A synthetic probe verifies API compatibility/dimension before private data is processed.
    try:
        provider.embed(['LocalGPT semantic setup compatibility check'])
    except embeddings.EmbeddingError as exc:
        raise HTTPException(503, {'code':'embedding_model_probe_failed','message':'Модель не прошла проверку embeddings. Проверьте совместимость версии Ollama и размерность модели.'}) from exc
    def commit_provider():
        _profile(profile_id)
        # Avoid activating an index if the model was replaced during indexing.
        current = _installed()
        if not current or current.get('digest') != installed.get('digest'):
            raise HTTPException(409, 'embedding_model_changed_during_reindex')
        db.set_app_setting(f'rag_embedding_profile:{profile_id}', json.dumps({
            'provider': 'ollama', 'model': provider.descriptor.model, 'version': version,
            'dimensions': provider.descriptor.dimensions}))
    return reindex_tasks.start_reindex(profile_id, provider_override=provider, on_complete=commit_provider)


def use_lexical(profile_id):
    _profile(profile_id)
    operation = reindex_tasks.latest_reindex_task(profile_id)
    if operation and operation.get('status') in {'queued','running'}:
        raise HTTPException(409, 'semantic_setup_reindex_in_progress')
    service._current_generation_chunks(profile_id, embeddings.LocalHashEmbeddingProvider())
    db.set_app_setting(f'rag_embedding_profile:{profile_id}', json.dumps({'provider':'local_hash','dimensions':256}))
    return {'profile_id':profile_id,'provider':'local_hash'}
