export const API_BASE = window.location.origin;

export const STORAGE_KEYS = {
  history: "localgpt_history_v1",
  session: "localgpt_session_id",
  profileId: "localgpt_profile_id",
  chatSessionId: "localgpt_chat_session_id",
  whisperModel: "localgpt_whisper_model_v1",
  whisperPromptPreset: "localgpt_whisper_prompt_v1",
  llmModel: "localgpt_llm_model_v1",
  hrPrefix: "localgpt_hr_prefix_v1",
  role: "localgpt_role_v1",
  sidebar: "localgpt_sidebar_collapsed",
  theme: "localgpt_theme",
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

export function getSavedPromptPreset(defaultValue = "none") {
  const raw = safeGet(STORAGE_KEYS.whisperPromptPreset);
  return raw || defaultValue;
}

export function setSavedPromptPreset(preset) {
  safeSet(STORAGE_KEYS.whisperPromptPreset, preset);
}

export function getSavedLlmModel(defaultValue = "") {
  const raw = safeGet(STORAGE_KEYS.llmModel);
  return raw || defaultValue;
}

export function setSavedLlmModel(model) {
  safeSet(STORAGE_KEYS.llmModel, model);
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

export function getSavedRole(defaultValue = "free") {
  const raw = safeGet(STORAGE_KEYS.role);
  return raw || defaultValue;
}

export function setSavedRole(role) {
  safeSet(STORAGE_KEYS.role, role);
}

export function getSidebarPreference(defaultValue = false) {
  const raw = safeGet(STORAGE_KEYS.sidebar);
  if (raw === "1") return true;
  if (raw === "0") return false;
  return defaultValue;
}

export function setSidebarPreference(collapsed) {
  safeSet(STORAGE_KEYS.sidebar, collapsed ? "1" : "0");
}

export function getSavedTheme(defaultValue = "") {
  return safeGet(STORAGE_KEYS.theme) || defaultValue;
}

export function setSavedTheme(theme) {
  safeSet(STORAGE_KEYS.theme, theme);
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

export function getLastProfileId() {
  const raw = safeGet(STORAGE_KEYS.profileId);
  return raw ? Number(raw) : null;
}

export function setLastProfileId(profileId) {
  if (!profileId) {
    safeSet(STORAGE_KEYS.profileId, null);
    return;
  }
  safeSet(STORAGE_KEYS.profileId, String(profileId));
}

export function getLastChatSessionId() {
  return safeGet(STORAGE_KEYS.chatSessionId);
}

export function setLastChatSessionId(sessionId) {
  safeSet(STORAGE_KEYS.chatSessionId, sessionId || null);
}

export function deleteHistoryEntry(timestamp) {
  const items = loadHistory();
  const filtered = items.filter((item) => item.ts !== timestamp);
  saveHistory(filtered);
}
