const STORAGE_KEYS = {
  model: "whisper_only_model_v1",
  language: "whisper_only_lang_v1",
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

export function getSavedModel(defaultValue = "large-v3-turbo") {
  return safeGet(STORAGE_KEYS.model) || defaultValue;
}

export function setSavedModel(value) {
  safeSet(STORAGE_KEYS.model, value);
}

export function getSavedLanguage(defaultValue = "en") {
  return safeGet(STORAGE_KEYS.language) || defaultValue;
}

export function setSavedLanguage(value) {
  safeSet(STORAGE_KEYS.language, value);
}
