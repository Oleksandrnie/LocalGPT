import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { ragUploadReport, describeRagUploadError, uploadRagBatches, splitRagUpload } from '../web_ui/js/rag_upload.mjs';

const source = fs.readFileSync(new URL('../web_ui/js/app.js', import.meta.url), 'utf8');
const upload = source.slice(source.indexOf('async function uploadRagFiles('), source.indexOf('\nasync function deleteRagFile'));
function harness(result, error) {
  const logs = [], toasts = [], requests = [];
  const context = {
    state: { activeProfileId: 7 }, els: { ragFileInput: { value: 'selected' } },
    FormData: class { files = []; append(_key, file) { this.files.push(file); } },
    console: { error: (...args) => logs.push(args) },
    request: async (path, options) => { requests.push({path,options}); if (error) throw error; return typeof result === "function" ? result(path, options) : result; },
    renderRagPanel() {}, loadRagStatus: async () => {},
    setFooter: (...args) => toasts.push(args), ragUploadReport, describeRagUploadError, uploadRagBatches,
  };
  vm.createContext(context);
  vm.runInContext(upload + '\nglobalThis.runUpload = uploadRagFiles;', context);
  return { context, logs, toasts, requests };
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


test('34 files totaling 69 MiB are sent in bounded sequential batches', async () => {
  const files = Array.from({ length: 34 }, (_, i) => ({ name: `synthetic-${i}.html`, size: Math.ceil(69 * 1024 * 1024 / 34) }));
  const batches = splitRagUpload(files);
  assert.equal(batches.flat().length, 34);
  assert.ok(batches.length > 1);
  let active = 0, peak = 0;
  const progress = [];
  const result = await uploadRagBatches(files, async batch => {
    active++; peak = Math.max(peak, active);
    assert.ok(batch.length <= 12);
    assert.ok(batch.reduce((n, f) => n + f.size, 0) <= 20 * 1024 * 1024);
    await Promise.resolve(); active--;
    return {saved: batch.map(f => f.name), errors: []};
  }, {onProgress: p => progress.push(p.processed)});
  assert.equal(peak, 1);
  assert.equal(result.saved.length, 34);
  assert.equal(result.processed, 34);
  assert.equal(result.not_processed, 0);
  assert.equal(progress.at(-1), 34);
});

test('a large HTML is sent alone without an artificial file-size rejection', () => {
  const batches = splitRagUpload([{size: 69 * 1024 * 1024}, {size: 1}]);
  assert.deepEqual(batches.map(b => b.length), [1, 1]);
});

test('per-file rejection does not discard successful files or stop following batches', async () => {
  const files = Array.from({length: 34}, (_, i) => ({name: `${i}.html`, size: 1}));
  let call = 0;
  const result = await uploadRagBatches(files, async batch => {
    call++;
    return {saved: batch.slice(call === 1 ? 1 : 0).map(f => f.name), errors: call === 1 ? [{code:'telegram_messages_not_found'}] : []};
  });
  assert.equal(call, 3);
  assert.equal(result.saved.length, 33);
  assert.equal(result.errors.length, 1);
  assert.equal(result.processed, 34);
});

test('network failure keeps earlier successes and reports unprocessed files', async () => {
  const files = Array.from({length:34}, () => ({size:1}));
  let call = 0;
  const result = await uploadRagBatches(files, async batch => {
    if (++call === 2) throw Object.assign(new Error('offline'), {code:'network_error'});
    return {saved:batch.map((_,i) => String(i)), errors:[]};
  });
  assert.equal(call, 2);
  assert.equal(result.saved.length, 12);
  assert.equal(result.not_processed, 22);
  assert.match(ragUploadReport(result).summary, /22/);
});


test('UI sends every batch to the captured profile even if selection changes', async () => {
  let h;
  h = harness((_path, options) => {
    h.context.state.activeProfileId = 9;
    return {saved:options.body.files.map(f => f.name), errors:[]};
  });
  await h.context.runUpload(Array.from({length:34}, (_,i) => ({name:`synthetic-${i}.html`,size:1})));
  assert.equal(h.requests.length, 3);
  assert.ok(h.requests.every(r => r.path.endsWith('profile_id=7')));
  assert.equal(h.context.state.ragUploadReport.profileId, 7);
  assert.match(h.context.state.ragUploadReport.details, /34/);
  assert.equal(h.toasts.length, 0);
  assert.equal(h.context.state.ragBusy, false);
});
