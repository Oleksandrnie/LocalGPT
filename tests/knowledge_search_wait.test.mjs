import test from 'node:test';
import assert from 'node:assert/strict';
import { createSearchWaitMonitor } from '../web_ui/js/knowledge_search_wait.mjs';

function clock() {
  const timers = new Map();
  let now = 0;
  let next = 0;
  return {
    setTimeoutFn(fn, ms) { const id = ++next; timers.set(id, { at: now + ms, fn }); return id; },
    clearTimeoutFn(id) { timers.delete(id); },
    async advance(ms) {
      now += ms;
      for (const [id, timer] of [...timers]) {
        if (timer.at <= now) { timers.delete(id); timer.fn(); }
      }
      await Promise.resolve();
      await Promise.resolve();
    },
    get size() { return timers.size; },
  };
}

test('asks at 30 seconds and repeats 30 seconds after continue without cancelling', async () => {
  const time = clock();
  let asks = 0;
  let cancels = 0;
  const monitor = createSearchWaitMonitor({ ...time, askContinue: async () => { asks++; return true; }, onCancel() { cancels++; } });
  await time.advance(29999);
  assert.equal(asks, 0);
  await time.advance(1);
  assert.equal(asks, 1);
  await time.advance(30000);
  assert.equal(asks, 2);
  assert.equal(cancels, 0);
  monitor.stop();
  assert.equal(time.size, 0);
});

test('keeps a single pending dialog and cancel fires once', async () => {
  const time = clock();
  let resolve;
  let asks = 0;
  let cancels = 0;
  createSearchWaitMonitor({ ...time, askContinue() { asks++; return new Promise(r => { resolve = r; }); }, onCancel() { cancels++; } });
  await time.advance(30000);
  await time.advance(120000);
  assert.equal(asks, 1);
  assert.equal(cancels, 0);
  resolve(false);
  await Promise.resolve();
  assert.equal(cancels, 1);
  assert.equal(time.size, 0);
});

test('completion stops future prompts and invalidates an already open dialog', async () => {
  const time = clock();
  let resolve;
  let cancels = 0;
  const monitor = createSearchWaitMonitor({ ...time, askContinue: () => new Promise(r => { resolve = r; }), onCancel() { cancels++; } });
  await time.advance(30000);
  monitor.stop();
  resolve(false);
  await Promise.resolve();
  await time.advance(60000);
  assert.equal(cancels, 0);
  assert.equal(time.size, 0);
});

test('another dialog defers the question without cancelling the search', async () => {
  const time = clock();
  let asks = 0;
  createSearchWaitMonitor({ ...time, askContinue: async () => { asks++; return null; }, onCancel: () => assert.fail('must not cancel') });
  await time.advance(30000);
  await time.advance(30000);
  assert.equal(asks, 2);
});
