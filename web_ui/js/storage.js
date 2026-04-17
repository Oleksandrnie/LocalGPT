const STORAGE_KEYS = {
  voice: "localgpt_tts_voice_v1",
  speed: "localgpt_tts_speed_v1",
  theme: "localgpt_tts_theme_v1",
  language: "localgpt_tts_lang_v1",
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
    if (value === null || value === undefined || value === "") {
      window.localStorage.removeItem(key);
      return;
    }
    window.localStorage.setItem(key, String(value));
  } catch {
    // ignore storage errors
  }
}

export function getSavedVoice(defaultValue = "") {
  return safeGet(STORAGE_KEYS.voice) || defaultValue;
}

export function setSavedVoice(value) {
  safeSet(STORAGE_KEYS.voice, value);
}

export function getSavedSpeed(defaultValue = 1.25) {
  const raw = safeGet(STORAGE_KEYS.speed);
  if (!raw) return defaultValue;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : defaultValue;
}

export function setSavedSpeed(value) {
  safeSet(STORAGE_KEYS.speed, value);
}

export function getSavedTheme(defaultValue = "dark") {
  const raw = safeGet(STORAGE_KEYS.theme);
  return raw === "light" ? "light" : raw === "dark" ? "dark" : defaultValue;
}

export function setSavedTheme(value) {
  safeSet(STORAGE_KEYS.theme, value);
}

export function getSavedLanguage(defaultValue = "ru") {
  const raw = safeGet(STORAGE_KEYS.language);
  return raw === "en" || raw === "uk" || raw === "ru" ? raw : defaultValue;
}

export function setSavedLanguage(value) {
  safeSet(STORAGE_KEYS.language, value);
}
