export const API_BASE = "http://127.0.0.1:8000";

export const STORAGE_KEYS = {
  history: "localgpt_history_v1",
  session: "localgpt_session_id",
  whisperModel: "localgpt_whisper_model_v1",
  pinnedContext: "localgpt_pinned_context_v1",
  hrPrefix: "localgpt_hr_prefix_v1",
  criteria: "localgpt_criteria_list_v1",
};

function safeGet(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    console.warn("localStorage get error", error);
    return null;
  }
}

function safeSet(key, value) {
  try {
    if (value === null || value === undefined) {
      window.localStorage.removeItem(key);
      return;
    }
    window.localStorage.setItem(key, value);
  } catch (error) {
    console.warn("localStorage set error", error);
  }
}

export function ensureSessionId(key = STORAGE_KEYS.session) {
  let sessionId = safeGet(key);
  if (!sessionId) {
    sessionId = `sess_${Math.random().toString(36).slice(2)}`;
    safeSet(key, sessionId);
  }
  return sessionId;
}

export function getSavedModel(defaultValue = "medium") {
  const raw = safeGet(STORAGE_KEYS.whisperModel);
  return raw || defaultValue;
}

export function setSavedModel(model) {
  safeSet(STORAGE_KEYS.whisperModel, model);
}

export function getHrPrefix(defaultValue) {
  const raw = safeGet(STORAGE_KEYS.hrPrefix);
  if (!raw) return defaultValue;
  const trimmed = raw.trim();
  return trimmed || defaultValue;
}

export function setHrPrefix(value) {
  safeSet(STORAGE_KEYS.hrPrefix, value);
}

export function getPinnedContext() {
  return safeGet(STORAGE_KEYS.pinnedContext) || "";
}

export function setPinnedContext(value) {
  safeSet(STORAGE_KEYS.pinnedContext, value);
}

export function clearPinnedContext() {
  safeSet(STORAGE_KEYS.pinnedContext, null);
}

function parseJson(raw, fallback) {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw);
  } catch (error) {
    console.warn("JSON parse error", error);
    return fallback;
  }
}

export function loadHistory() {
  const raw = safeGet(STORAGE_KEYS.history);
  return parseJson(raw, []);
}

export function saveHistory(items) {
  safeSet(STORAGE_KEYS.history, JSON.stringify(items));
}

export function addHistoryEntry(question, answer) {
  const items = loadHistory();
  items.unshift({ ts: Date.now(), q: question, a: answer });
  saveHistory(items);
}

export function deleteHistoryEntry(timestamp) {
  const items = loadHistory();
  const filtered = items.filter((item) => item.ts !== timestamp);
  saveHistory(filtered);
}

export function loadCriteriaFromStorage() {
  const raw = safeGet(STORAGE_KEYS.criteria);
  return parseJson(raw, []);
}

export function saveCriteriaToStorage(criteriaList) {
  if (!Array.isArray(criteriaList) || !criteriaList.length) {
    safeSet(STORAGE_KEYS.criteria, null);
    return;
  }
  safeSet(STORAGE_KEYS.criteria, JSON.stringify(criteriaList));
}
