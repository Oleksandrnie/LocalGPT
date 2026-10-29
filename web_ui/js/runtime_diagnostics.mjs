// Explicit allowlist: never serialize request/response bodies, prompts or Error.message.
const tag = v => typeof v === 'string' && /^[a-zA-Z0-9_.:/-]{1,160}$/.test(v) ? v : null;
const count = v => typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v : null;
const mode = v => typeof v === 'boolean' ? v : tag(v);
export function runtimeDiagnostic(event, context = {}, data = {}) {
  const result = data.result || {};
  const task = data.task || {};
  const completion = task.result || task;
  const settings = task.used_settings || {};
  const planner = result.planner || {};
  const semantic = result.semantic || {};
  const error = data.error || {};
  const detail = error.payload?.detail;
  const code = tag(data.code || error.code || detail?.code || task.error_code);
  const safeBudgetMessages = new Map([
    ['Thinking budget exhausted before the model produced a final answer.', 'before_final_answer'],
    ['The model response reached its token limit before completion.', 'incomplete_answer'],
  ]);
  const budgetStage = code === 'chat_final_answer_incomplete' ? safeBudgetMessages.get(task.message || error.message) || null : null;
  const done = tag(detail?.done_reason || completion.done_reason) || (budgetStage ? 'length' : null);
  const limits = {};
  for (const key of ['top_k', 'max_context_chars', 'indexed_chunks', 'max_topics', 'max_candidates_per_query', 'max_retrieval_queries', 'retrieval_queries']) {
    limits[key] = count(result.limits?.[key]);
  }
  return {
    schema_version: 1, timestamp: new Date().toISOString(), event: tag(event),
    profile_id: count(context.profile_id), session_id: tag(context.session_id), task_id: tag(task.id || task.task_id || context.task_id),
    model: tag(task.model_name || context.model), requested_thinking: mode(context.thinking),
    effective_thinking: mode(settings.ollama_think), native_thinking: mode(data.native_thinking), reasoning_present: typeof data.reasoning_present === 'boolean' ? data.reasoning_present : null,
    configured_budgets: {output_tokens: count(settings.output_tokens ?? context.output_tokens), thinking_tokens: count(settings.thinking_tokens ?? context.thinking_tokens), provider_num_predict: count(settings.provider_num_predict)},
    completion: {state: tag(task.state), done_reason: done, eval_count: count(completion.eval_count), budget_failure_stage: budgetStage, token_budget_exhausted: done === 'length' ? true : done === 'stop' ? false : null},
    error: {code, type: tag(error.name), http_status: count(error.status)},
    planner: {status: tag(planner.status), model: tag(planner.model), reason: tag(planner.reason)},
    embedding: {status: tag(semantic.status || context.embedding_status), provider: tag(semantic.provider || context.embedding_provider), model: tag(semantic.model || context.embedding_model)},
    rag_context_enabled: typeof context.rag_context_enabled === 'boolean' ? context.rag_context_enabled : null,
    strategy: tag(result.limits?.strategy), result_count: Array.isArray(result.results) ? result.results.length : null,
    warning_count: Array.isArray(result.warnings) ? result.warnings.length : null, limits,
  };
}
export function emitRuntimeDiagnostic(event, context, data, level = 'info', logger = console) {
  const record = runtimeDiagnostic(event, context, data);
  logger[level](`[LocalGPT diagnostics] ${event}\n${JSON.stringify(record, null, 2)}`);
  return record;
}
