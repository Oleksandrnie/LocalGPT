/** Ask periodically while the independent search/polling operation keeps running.
 * askContinue resolves true to keep waiting, false to cancel, or null to defer
 * when another dialog owns the UI. stop() invalidates any pending answer.
 */
export function createSearchWaitMonitor({
  askContinue,
  onCancel,
  intervalMs = 30000,
  setTimeoutFn = setTimeout,
  clearTimeoutFn = clearTimeout,
}) {
  let stopped = false;
  let timer = null;

  const schedule = () => {
    if (!stopped) timer = setTimeoutFn(tick, intervalMs);
  };
  const stop = () => {
    stopped = true;
    if (timer !== null) clearTimeoutFn(timer);
    timer = null;
  };
  async function tick() {
    timer = null;
    if (stopped) return;
    let answer;
    try {
      answer = await askContinue();
    } catch {
      // A dismissed/unavailable dialog never implies user cancellation.
      answer = null;
    }
    if (stopped) return;
    if (answer === false) {
      stop();
      await onCancel();
      return;
    }
    schedule();
  }
  schedule();
  return { stop };
}
