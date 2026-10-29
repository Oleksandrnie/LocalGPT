import { createSearchWaitMonitor } from './knowledge_search_wait.mjs';

function aborted() {
  const error = new Error('Поиск остановлен.');
  error.name = 'AbortError';
  return error;
}

// Starting a job is intentionally not aborted: its reply gives us the ID needed
// to cancel a server job even if the user stops during the initial HTTP request.
export async function waitForKnowledgeSearch({request, body, signal, onTask = () => {},
  askContinue, onCancel, onMonitorStop = () => {}, pollMs = 1000, intervalMs = 30000,
  sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms)),
  monitorFactory = createSearchWaitMonitor}) {
  if (signal?.aborted) throw aborted();
  let task = null, cancelPromise = null;
  const query = new URLSearchParams({profile_id: String(body.profile_id)});
  if (body.session_id) query.set('session_id', body.session_id);
  const scoped = (suffix = '') => `/chat/knowledge-search/tasks/${encodeURIComponent(task.task_id)}${suffix}?${query}`;
  const cancel = () => {
    if (task && !['completed', 'failed', 'cancelled'].includes(task.state) && !cancelPromise) {
      cancelPromise = request(scoped('/cancel'), {method:'POST', body:{}, signal: AbortSignal.timeout(5000)}).catch(() => null);
    }
    return cancelPromise;
  };
  signal?.addEventListener('abort', cancel);
  const monitor = monitorFactory({askContinue, onCancel, intervalMs});
  try {
    task = await request('/chat/knowledge-search/tasks', {method:'POST', body});
    onTask(task);
    for (;;) {
      if (signal?.aborted) { await cancel(); throw aborted(); }
      if (task.state === 'completed') return task.result;
      if (task.state === 'cancelled') throw aborted();
      if (task.state === 'failed') {
        const detail = task.error?.detail;
        const error = new Error(typeof detail === 'string' ? detail : detail?.message || 'Ошибка поиска в базе.');
        error.status = task.error?.status_code || 500;
        throw error;
      }
      await sleep(pollMs);
      if (signal?.aborted) { await cancel(); throw aborted(); }
      task = await request(scoped(), {signal});
    }
  } catch (error) {
    await cancel();
    throw error;
  } finally {
    monitor.stop();
    signal?.removeEventListener('abort', cancel);
    onMonitorStop();
  }
}
