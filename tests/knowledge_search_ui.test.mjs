import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../web_ui/js/app.js', import.meta.url), 'utf8');
function install(context, name, async = false) {
  const start = source.indexOf(`${async ? 'async ' : ''}function ${name}(`);
  assert.ok(start >= 0, name);
  const end = source.indexOf('\n}', start) + 2;
  vm.runInContext(source.slice(start, end), context);
}
function harness(request = async () => ({status: 'matches', session_id: 's1', user_message_id: 1})) {
  const state = {activeProfileId: 7, currentSessionId: 's1', messages: [], chatAttachments: [],
    knowledgeSearchMode: true, knowledgeSearchRequest: null, isSending: false, installedModels: [], selectedLlmModel: ''};
  const notices = [], loads = [], paths = [];
  const button = {disabled: false, textContent: '', classList: {toggle() {}}, setAttribute() {}};
  const context = vm.createContext({state, AbortController, Date,
    LOCAL_CALCULATOR_MODEL_ID: 'calculator', AUTO_MODEL_ID: 'auto',
    els: {promptInput: {value: 'quartz'}, knowledgeSearchStatus: {}, sendButton: button},
    request: (path, options) => {paths.push(path); return request(path, options)},
    waitForKnowledgeSearch: ({request, body, signal}) => request('/chat/knowledge-search/tasks', {method:'POST',body,signal}),
    setFooter: (...args) => notices.push(args), renderMessages() {}, autoResizePrompt() {},
    renderChatAttachments() {}, renderChatModelNotice() {},
    ensureModelInstalled: () => {throw new Error('Search must not check model availability')},
    loadSessions: async ({preferredSessionId}) => {loads.push(preferredSessionId); state.currentSessionId = preferredSessionId},
  });
  for (const name of ['closeKnowledgeSearchWaitDialog', 'cancelKnowledgeSearch', 'syncKnowledgeSearchControl', 'updateSendButtonState']) install(context, name);
  for (const name of ['sendKnowledgeSearch', 'sendPromptText', 'cancelCurrentChatGeneration']) install(context, name, true);
  return {context, state, notices, loads, paths, button};
}
function pending() {
  let resolve, reject;
  const promise = new Promise((yes, no) => {resolve = yes; reject = no});
  return {promise, resolve, reject};
}

test('search branches before model checks and never submits chat generation', async () => {
  const h = harness();
  await h.context.sendPromptText('quartz', {clearInput: true});
  assert.deepEqual(h.paths, ['/chat/knowledge-search/tasks']);
  assert.deepEqual(h.loads, ['s1']);
  assert.equal(h.state.isSending, false);
  assert.equal(h.context.els.promptInput.value, '');
  assert.match(h.context.els.knowledgeSearchStatus.textContent, /найдены/);
});

test('search is usable without installed or selected chat model', () => {
  const h = harness();
  h.context.updateSendButtonState();
  assert.equal(h.button.disabled, false);
  assert.equal(h.button.textContent, 'Найти');
});

test('loading, no matches, empty index and errors have distinct visible states', async () => {
  const deferred = pending();
  const h = harness(() => deferred.promise);
  const send = h.context.sendPromptText('quartz');
  assert.equal(h.state.isSending, true);
  assert.equal(h.context.els.knowledgeSearchStatus.textContent, 'Планирую запрос и ищу в базе…');
  deferred.resolve({status: 'no_matches', session_id: 's1'});
  await send;
  assert.equal(h.context.els.knowledgeSearchStatus.textContent, 'Совпадений не найдено');
  const empty = harness(async () => ({status: 'empty_index', session_id: 's1'}));
  await empty.context.sendPromptText('quartz');
  assert.match(empty.context.els.knowledgeSearchStatus.textContent, /Индекс пуст/);
  const broken = harness(async () => {throw new Error('synthetic error')});
  await broken.context.sendPromptText('quartz', {clearInput: true});
  assert.match(broken.context.els.knowledgeSearchStatus.textContent, /Ошибка поиска/);
  assert.equal(broken.context.els.promptInput.value, 'quartz');
  assert.deepEqual(broken.loads, []);
  assert.deepEqual(broken.paths, ['/chat/knowledge-search/tasks']);
});

for (const switchContext of ['profile', 'session', 'mode']) {
  test(`late search response after ${switchContext} switch cannot replace chat`, async () => {
    const deferred = pending();
    const h = harness(() => deferred.promise);
    const send = h.context.sendPromptText('quartz');
    if (switchContext === 'profile') h.state.activeProfileId = 9;
    if (switchContext === 'session') h.state.currentSessionId = 's2';
    if (switchContext === 'mode') h.state.knowledgeSearchMode = false;
    deferred.resolve({status: 'matches', session_id: 'old-session'});
    await send;
    assert.deepEqual(h.loads, []);
    assert.equal(h.notices.length, 0);
  });
}

test('Stop aborts search without calling task cancellation, stale result cannot clear newer request', async () => {
  const first = pending(), second = pending();
  let count = 0, signal;
  const h = harness((_path, options) => {
    count += 1;
    if (count === 1) signal = options.signal;
    return count === 1 ? first.promise : second.promise;
  });
  const old = h.context.sendPromptText('old');
  await h.context.cancelCurrentChatGeneration();
  assert.equal(signal.aborted, true);
  assert.equal(h.state.isSending, false);
  const fresh = h.context.sendPromptText('fresh');
  const active = h.state.knowledgeSearchRequest;
  first.resolve({status: 'matches', session_id: 'stale'});
  await old;
  assert.equal(h.state.knowledgeSearchRequest, active);
  assert.equal(h.state.isSending, true);
  assert.deepEqual(h.loads, []);
  second.resolve({status: 'matches', session_id: 's1'});
  await fresh;
  assert.deepEqual(h.paths, ['/chat/knowledge-search/tasks', '/chat/knowledge-search/tasks']);
});

test('mode toggle cancels pending search and enables normal mode', async () => {
  const deferred = pending();
  const h = harness(() => deferred.promise);
  let toggle;
  h.context.els.knowledgeSearchToggle = {checked: false, addEventListener: (_type, callback) => {toggle = callback}, setAttribute() {}};
  const start = source.indexOf('  els.knowledgeSearchToggle?.addEventListener("change", () => {');
  const end = source.indexOf('\n  });', start) + '\n  });'.length;
  vm.runInContext(source.slice(start, end), h.context);
  const old = h.context.sendPromptText('quartz');
  h.context.els.knowledgeSearchToggle.checked = false;
  toggle();
  assert.equal(h.state.knowledgeSearchMode, false);
  assert.equal(h.state.knowledgeSearchRequest, null);
  assert.equal(h.state.isSending, false);
  deferred.resolve({status: 'matches', session_id: 'old'});
  await old;
  assert.deepEqual(h.loads, []);
});

test('new chat cancels pending search even when both sessions have no ID yet', async () => {
  const deferred = pending();
  const h = harness(() => deferred.promise);
  h.state.currentSessionId = null;
  let newChat;
  h.context.els.newChatButton = {addEventListener: (_type, callback) => {newChat = callback}};
  h.context.STORAGE_KEYS = {activeSessionId: 'session'};
  h.context.writeStored = () => {};
  h.context.openSession = async () => {};
  h.context.closeSidebar = () => {};
  const start = source.indexOf('  els.newChatButton?.addEventListener("click", async () => {');
  const end = source.indexOf('\n  });', start) + '\n  });'.length;
  vm.runInContext(source.slice(start, end), h.context);
  const old = h.context.sendPromptText('quartz');
  await newChat();
  assert.equal(h.state.knowledgeSearchRequest, null);
  deferred.resolve({status: 'matches', session_id: 'old'});
  await old;
  assert.deepEqual(h.loads, []);
});

test('first search opens its newly created session through real session-list loading', async () => {
  const h = harness(path => path === '/chat/knowledge-search/tasks'
    ? Promise.resolve({status: 'matches', session_id: 'created-session', user_message_id: 1})
    : Promise.resolve({sessions: [{id: 'created-session'}]}));
  h.state.currentSessionId = null;
  h.context.STORAGE_KEYS = {activeSessionId: 'session'};
  h.context.renderSessionList = () => {};
  h.context.readStored = () => '';
  h.context.openSession = async id => {
    assert.equal(h.state.knowledgeSearchRequest.initialSessionId, null);
    assert.equal(h.state.knowledgeSearchRequest.sessionId, 'created-session');
    assert.equal(h.state.pendingChatMessage.acceptedSessionId, 'created-session');
    h.loads.push(id);
    h.state.currentSessionId = id;
  };
  install(h.context, 'loadSessions', true);
  await h.context.sendPromptText('quartz', {clearInput: true});
  assert.equal(h.state.currentSessionId, 'created-session');
  assert.deepEqual(h.loads, ['created-session']);
  assert.deepEqual(h.paths, ['/chat/knowledge-search/tasks', '/sessions?profile_id=7']);
  assert.equal(h.state.knowledgeSearchRequest, null);
  assert.equal(h.state.isSending, false);
  assert.match(h.notices.at(-1)[0], /Фрагменты найдены/);
});

for (const initialSessionId of ['s1', null]) {
test(`session-list refresh after search from ${initialSessionId ?? 'new chat'} cannot reopen old chat after a switch`, async () => {
  const deferred = pending();
  const h = harness(path => path === '/chat/knowledge-search/tasks'
    ? Promise.resolve({status: 'matches', session_id: 's1'}) : deferred.promise);
  h.state.currentSessionId = initialSessionId;
  h.context.STORAGE_KEYS = {activeSessionId: 'session'};
  h.context.renderSessionList = () => {};
  h.context.readStored = () => '';
  h.context.openSession = async id => {h.loads.push(id); h.state.currentSessionId = id};
  install(h.context, 'loadSessions', true);
  const send = h.context.sendPromptText('quartz');
  await new Promise(resolve => setImmediate(resolve));
  h.state.currentSessionId = 's2';
  deferred.resolve({sessions: [{id: 's1'}, {id: 's2'}]});
  await send;
  assert.equal(h.state.currentSessionId, 's2');
  assert.deepEqual(h.loads, []);
});
}

test('images are explicitly rejected and long query is rejected without sending', async () => {
  const h = harness();
  h.state.chatAttachments.push({status: 'ready', server: {id: 'image'}});
  await h.context.sendPromptText('quartz', {attachmentIds: ['image']});
  assert.match(h.notices[0][0], /Уберите изображения/);
  h.state.chatAttachments = [];
  await h.context.sendPromptText('x'.repeat(4001));
  assert.match(h.notices[1][0], /4000/);
  assert.deepEqual(h.paths, []);
});

test('RAG menu search switch has accessible help and compact input indicator', () => {
  const html = fs.readFileSync(new URL('../web_ui/gui_html.html', import.meta.url), 'utf8');
  const css = fs.readFileSync(new URL('../web_ui/css/style.css', import.meta.url), 'utf8');
  assert.match(html, /id="knowledgeSearchToggle" type="checkbox"/);
  assert.match(html, /id="knowledgeSearchIndicator"/);
  assert.doesNotMatch(html, /class="knowledge-search-control"/);
  assert.match(html, /class="knowledge-search-info" type="button"/);
  assert.match(css, /\.knowledge-search-info:hover \+ \.knowledge-search-help/);
  assert.match(css, /\.knowledge-search-info:focus(?:-visible)? \+ \.knowledge-search-help/);
  assert.match(css, /\.knowledge-search-indicator\[hidden\]/);
});

test('search checkbox and input indicator reflect mode and compact status', () => {
  const h = harness();
  h.context.els.knowledgeSearchToggle = {};
  h.context.els.knowledgeSearchIndicator = {setAttribute(name, value) {this[name] = value;}};
  h.context.els.knowledgeSearchStatus.textContent = 'Found candidates';
  h.context.syncKnowledgeSearchControl();
  assert.equal(h.context.els.knowledgeSearchToggle.checked, true);
  assert.equal(h.context.els.knowledgeSearchIndicator.hidden, false);
  assert.match(h.context.els.knowledgeSearchIndicator.title, /Found candidates/);
  h.state.knowledgeSearchMode = false;
  h.context.syncKnowledgeSearchControl();
  assert.equal(h.context.els.knowledgeSearchIndicator.hidden, true);
  assert.equal(h.context.els.knowledgeSearchToggle.checked, false);
});

test('declining long-search confirmation cancels wait and restores submitted input', async () => {
  const h = harness();
  h.context.waitForKnowledgeSearch = async ({onCancel}) => {
    await onCancel();
    const error = new Error('cancelled'); error.name = 'AbortError'; throw error;
  };
  await h.context.sendPromptText('synthetic original prompt', {clearInput:true});
  assert.equal(h.context.els.promptInput.value, 'synthetic original prompt');
  assert.equal(h.state.isSending,false);
  assert.equal(h.state.pendingChatMessage,null);
  assert.deepEqual(h.loads,[]);
});
