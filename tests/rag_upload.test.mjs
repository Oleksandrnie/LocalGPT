import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { ragUploadReport, describeRagUploadError } from '../web_ui/js/rag_upload.mjs';

const source = fs.readFileSync(new URL('../web_ui/js/app.js', import.meta.url), 'utf8');
const upload = source.slice(source.indexOf('async function uploadRagFiles('), source.indexOf('\nasync function deleteRagFile'));
function harness(result, error) {
  const logs = [], toasts = [];
  const context = {
    state: { activeProfileId: 7 }, els: { ragFileInput: { value: 'selected' } },
    FormData: class { append() {} },
    console: { error: (...args) => logs.push(args) },
    request: async () => { if (error) throw error; return result; },
    renderRagPanel() {}, loadRagStatus: async () => {},
    setFooter: (...args) => toasts.push(args), ragUploadReport, describeRagUploadError,
  };
  vm.createContext(context);
  vm.runInContext(upload + '\nglobalThis.runUpload = uploadRagFiles;', context);
  return { context, logs, toasts };
}

test('zero saved files never invite indexing; per-file error details persist', async () => {
  const h = harness({ saved: [], errors: [{ file: 'synthetic.html', code: 'telegram_history_not_found', error: 'missing history' }] });
  await h.context.runUpload([{}]);
  assert.equal(h.logs.length, 1);
  assert.equal(h.logs[0][1].code, 'telegram_history_not_found');
  assert.equal(h.toasts[0][1], 'error');
  assert.doesNotMatch(h.toasts[0][0], /Теперь можно индексировать/);
  assert.match(h.context.state.ragUploadReport.details, /telegram_history_not_found/);
  assert.equal(h.context.els.ragFileInput.value, '');
  // Console gets only error metadata, never file name or content.
  assert.deepEqual(Object.keys(h.logs[0][1]).sort(), ['code', 'reason']);
});

test('HTTP failures are logged with safe fields', async () => {
  const h = harness(null, Object.assign(new Error('provider unavailable'), { code: 'telegram_requires_local_hash_embeddings', status: 409, payload: 'do-not-log' }));
  await h.context.runUpload([{}]);
  assert.equal(h.logs[0][1].status, 409);
  assert.equal(h.logs[0][1].code, 'telegram_requires_local_hash_embeddings');
  assert.doesNotMatch(JSON.stringify(h.logs), /do-not-log/);
});

test('success and mixed uploads distinguish outcomes', () => {
  assert.equal(ragUploadReport({saved:['a.md'],errors:[]}).tone, 'success');
  const mixed = ragUploadReport({saved:['a.md'],errors:[{error:'file_too_large'}]});
  assert.equal(mixed.tone, 'warning');
  assert.match(mixed.details, /5 MiB/);
  assert.equal(ragUploadReport({}).tone, 'warning');
});
