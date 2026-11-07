import tempfile
import unittest
import threading
import time
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import config, db
from backend.apps.rag import service, routes, embeddings, embedding_setup as setup, reindex_tasks


class EmbeddingSetupTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        for target, name, value in [(db,'DB_PATH',Path(tmp.name)/'test.sqlite'),
                                   (config,'RAG_SOURCE_DIR',Path(tmp.name)/'sources'),
                                   (config,'SETTINGS',replace(config.SETTINGS,base_url='http://127.0.0.1:11434',rag_embedding_provider='local_hash',rag_embedding_dimensions=256))]:
            p=patch.object(target,name,value);p.start();self.addCleanup(p.stop)
        db.init_db();self.profile=db.ensure_default_profile();self.other=db.create_profile('Other')['id']
        (service.source_dir(self.profile)/'sample.md').write_text('synthetic source')
        service.ingest_sources(self.profile)
        self.model={'name':config.SETTINGS.rag_embedding_model,'digest':'sha256:'+'a'*64}
        p=patch.object(setup,'_installed',return_value=self.model);p.start();self.addCleanup(p.stop)
        p=patch.object(setup.models,'pull_statuses',return_value={'downloads':[]});p.start();self.addCleanup(p.stop)
        app=FastAPI();app.include_router(routes.router);self.client=TestClient(app);self.addCleanup(self.client.close)

    def post(self, action, profile=None):
        return self.client.post('/rag/embedding-setup/'+action,params={'profile_id':profile or self.profile})

    def test_missing_model_install_uses_existing_manager_and_changes_no_provider(self):
        with patch.object(setup,'_installed',return_value=None),patch.object(setup.models,'start_model_pull',return_value={'task_id':'synthetic','state':'pending'}) as pull:
            result=self.post('install')
        self.assertEqual(result.status_code,200);pull.assert_called_once_with(config.SETTINGS.rag_embedding_model)
        self.assertEqual(service._embedding_provider(self.profile).descriptor.provider,'local_hash')
        self.assertEqual(service._embedding_provider(self.other).descriptor.provider,'local_hash')

    def test_activation_is_profile_scoped_and_deferred_until_success(self):
        with patch.object(embeddings.OllamaEmbeddingProvider,'embed',return_value=[[0.1]*256]),patch.object(reindex_tasks,'start_reindex',return_value={'task_id':'synthetic'}) as start:
            response=self.post('activate')
        self.assertEqual(response.status_code,202)
        self.assertEqual(service._embedding_provider(self.profile).descriptor.provider,'local_hash')
        provider=start.call_args.kwargs['provider_override'];self.assertTrue(provider.local_only)
        start.call_args.kwargs['on_complete']()
        self.assertEqual(service._embedding_provider(self.profile).descriptor.storage_key,provider.descriptor.storage_key)
        self.assertEqual(service._embedding_provider(self.other).descriptor.provider,'local_hash')

    def test_probe_failure_and_model_replacement_never_activate(self):
        with patch.object(embeddings.OllamaEmbeddingProvider,'embed',side_effect=embeddings.EmbeddingProviderError('synthetic')):
            self.assertEqual(self.post('activate').status_code,503)
        self.assertEqual(service._embedding_provider(self.profile).descriptor.provider,'local_hash')
        with patch.object(embeddings.OllamaEmbeddingProvider,'embed',return_value=[[0.1]*256]),patch.object(reindex_tasks,'start_reindex') as start:
            self.post('activate')
        with patch.object(setup,'_installed',return_value={**self.model,'digest':'sha256:'+'b'*64}):
            with self.assertRaises(Exception):start.call_args.kwargs['on_complete']()
        self.assertEqual(service._embedding_provider(self.profile).descriptor.provider,'local_hash')

    def test_remote_endpoint_or_missing_profile_never_downloads(self):
        with patch.object(setup.models,'start_model_pull') as pull:
            self.assertEqual(self.post('install',999).status_code,404)
            with patch.object(config,'SETTINGS',replace(config.SETTINGS,base_url='https://remote.invalid')):
                self.assertEqual(self.post('install').status_code,409)
            pull.assert_not_called()

    def test_status_does_not_probe_documents_and_missing_model_blocks_activation(self):
        with patch.object(setup,'_installed',return_value=None),patch.object(embeddings.OllamaEmbeddingProvider,'embed') as embed:
            status=self.client.get('/rag/embedding-setup',params={'profile_id':self.profile}).json()
            self.assertFalse(status['installed']);self.assertFalse(status['active'])
            self.assertEqual(self.post('activate').status_code,409);embed.assert_not_called()

    def test_real_worker_keeps_old_index_until_atomic_profile_activation(self):
        event=threading.Event();calls=[]
        def embed(provider,texts,**kwargs):
            calls.append(texts)
            if len(calls)>1:event.wait(3)
            return [[0.1]*256 for _ in texts]
        with patch.object(embeddings.OllamaEmbeddingProvider,'embed',new=embed):
            response=self.post('activate');self.assertEqual(response.status_code,202)
            task_id=response.json()['task_id']
            try:
                self.assertEqual(service._embedding_provider(self.profile).descriptor.provider,'local_hash')
                self.assertTrue(service.search(self.profile,'synthetic'))
            finally:
                event.set()
                until=time.monotonic()+5
                while time.monotonic()<until:
                    task=reindex_tasks.get_reindex_task(task_id,self.profile)
                    if task['status'] in {'failed','completed'}:break
                    time.sleep(.01)
            self.assertEqual(task['status'],'completed',task)
        self.assertEqual(service._embedding_provider(self.profile).descriptor.provider,'ollama')
        self.assertEqual(service._embedding_provider(self.other).descriptor.provider,'local_hash')
        with patch.object(embeddings.OllamaEmbeddingProvider,'embed',new=embed):
            self.assertTrue(service.search(self.profile,'synthetic'))
        self.assertEqual(self.post('lexical').status_code,200)
        self.assertTrue(service.search(self.profile,'synthetic'))

    def test_worker_failure_preserves_provider_and_existing_search(self):
        calls=[]
        def embed(provider,texts,**kwargs):
            calls.append(texts)
            if len(calls)>1:raise embeddings.EmbeddingProviderError('synthetic reindex failure')
            return [[0.1]*256]
        with patch.object(embeddings.OllamaEmbeddingProvider,'embed',new=embed):
            response=self.post('activate');self.assertEqual(response.status_code,202)
            task_id=response.json()['task_id'];until=time.monotonic()+5
            while time.monotonic()<until:
                task=reindex_tasks.get_reindex_task(task_id,self.profile)
                if task['status'] in {'failed','completed'}:break
                time.sleep(.01)
            self.assertEqual(task['status'],'failed')
        self.assertEqual(service._embedding_provider(self.profile).descriptor.provider,'local_hash')
        self.assertTrue(service.search(self.profile,'synthetic'))
