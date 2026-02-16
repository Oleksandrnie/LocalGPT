export const API_BASE = "http://127.0.0.1:8000";

const STORAGE_KEYS = {
  model: "whisper_only_model_v1",
};

function safeGet(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
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
  } catch {
    // ignore storage errors
  }
}

export function getSavedModel(defaultValue = "small") {
  return safeGet(STORAGE_KEYS.model) || defaultValue;
}

export function setSavedModel(value) {
  safeSet(STORAGE_KEYS.model, value);
}
