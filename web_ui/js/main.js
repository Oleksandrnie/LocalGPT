import {
  deleteVoice,
  deleteHistoryItem,
  downloadVoice,
  fetchHealth,
  fetchVoiceDownloadTask,
  generateSpeech,
  getHistoryItem,
  listHistory,
  listVoiceLibrary,
  listVoices,
  previewVoice,
  processSpeed,
} from "./api.js";
import { renderHistoryList } from "./history.js";
import {
  getSavedLanguage,
  getSavedSpeed,
  getSavedTheme,
  getSavedVoice,
  setSavedLanguage,
  setSavedSpeed,
  setSavedTheme,
  setSavedVoice,
} from "./storage.js";
import { formatDateTime, formatDuration, setStatus } from "./ui.js";

const PREVIEW_TEXT_LIMIT = 240;
const LANGUAGE_LOCALES = {
  en: "en-US",
  uk: "uk-UA",
  ru: "ru-RU",
};

const VOICE_LANGUAGE_LABELS = {
  en: { en: "English", uk: "Англійська", ru: "Английский" },
  en_US: { en: "English (US)", uk: "Англійська (США)", ru: "Английский (США)" },
  uk: { en: "Ukrainian", uk: "Українська", ru: "Украинский" },
  uk_UA: { en: "Ukrainian", uk: "Українська", ru: "Украинский" },
  ru: { en: "Russian", uk: "Російська", ru: "Русский" },
  ru_RU: { en: "Russian", uk: "Російська", ru: "Русский" },
};

const I18N = {
  en: {
    documentTitle: "LocalGPT TTS / Voice",
    appTitle: "LocalGPT TTS / Voice",
    appSubtitle: "Local voice generation without external APIs or cloud.",
    themeDark: "Dark",
    themeLight: "Light",
    healthChecking: "Checking local TTS...",
    voiceLoading: "Loading voices...",
    step1: "Step 1",
    step2: "Step 2",
    step4: "Step 4",
    textTitle: "Text",
    settings: "Settings",
    clear: "Clear",
    textLabel: "Text",
    textPlaceholder: "Enter text for local speech synthesis...",
    textHint: "Long text will be split into chunks and stitched into one WAV.",
    currentVoice: "Current voice",
    voiceSummaryHint: "Voice selection, download, preview, and deletion live in settings.",
    voiceNone: "No matching local voices yet.",
    generate: "Generate",
    apply: "Застосувати",
    idle: "Idle",
    generateIdleStatus: "Waiting for action.",
    settingsTitle: "Voices",
    localVoiceLabel: "Local voice",
    preview: "Preview",
    refresh: "Refresh",
    previewHint: "Preview uses a locally installed voice.",
    library: "Library",
    librarySearchPlaceholder: "Search by language, name, or quality...",
    libraryLoading: "Loading Piper voice catalog...",
    step2Title: "Result and speed",
    recordMetaEmpty: "History and player appear after generation.",
    resultEyebrow: "Result WAV",
    resultTitle: "Result",
    downloadWav: "Download WAV",
    resultEmpty: "WAV has not been generated yet.",
    speedEyebrow: "Speed",
    speedTitle: "Speed",
    speedInitialStatus: "Select a speed. The player previews it live; Apply saves a separate WAV.",
    step4Title: "History",
    historyRefresh: "Refresh",
    historyEmpty: "History is empty.",
    historyDelete: "Delete record",
    historyBase: "base",
    historyProcessed: "processed",
    emptyPreview: "(empty)",
    unknown: "unknown",
    healthOk: "Local TTS: {status} • provider: {provider}",
    healthFail: "Failed to fetch health: {message}",
    voiceCount: "Voices available: {count}",
    voicesUnavailable: "Voices are not available yet.",
    voiceRefreshFail: "Failed to load voices: {message}",
    libraryLoaded: "Piper catalog: {count} voices.",
    libraryLoadedBadge: "{count} voices",
    libraryError: "Voice catalog error: {message}",
    loading: "Loading",
    error: "Error",
    downloading: "Downloading",
    deleting: "Deleting...",
    use: "Use",
    download: "Download",
    delete: "Delete",
    installed: "Installed",
    remote: "Remote",
    notFound: "Nothing found.",
    localIds: "local IDs: {count}",
    notDownloaded: "not downloaded yet",
    speakerOne: "1 speaker",
    speakerMany: "{count} speakers",
    generating: "Generating",
    generateStarted: "Generation started in background...",
    generateDone: "Ready: {voice} • {duration}",
    generateReady: "Ready",
    generateError: "Generation error.",
    ttsReady: "Speech is ready.",
    enterText: "Enter text for speech synthesis.",
    textTooLong: "Text exceeds the {limit}-character limit.",
    chooseVoice: "Choose a voice first.",
    baseMissing: "Generate the base WAV first.",
    speedCreate: "Creating a separate WAV at {speed}...",
    speedDone: "Saved: {speed} • {duration}",
    speedError: "Post-processing error.",
    speedSaved: "Processed WAV is ready.",
    speedOriginal: "1x uses the original WAV. No extra file is needed.",
    speedPreviewOnly: "Previewing {speed} live from the original WAV. Apply to save.",
    speedSavedStatus: "Saved {speed} WAV is active.",
    recordDeleted: "Record deleted.",
    recordDeleteConfirm: "Delete this history item and related WAV files?",
    previewCreating: "Generating local preview...",
    previewReady: "Preview ready: {label}.",
    previewError: "Could not create preview.",
    voiceDownloading: "Downloading voice {voiceKey}...",
    voiceDownloadedStatus: "Voice {voiceKey} is installed locally.",
    voiceDownloadedToast: "Voice {voiceKey} downloaded.",
    voiceDeleteConfirm: "Delete local voice {label}?",
    voiceDeletedStatus: "Voice {label} removed locally.",
    voiceDeletedToast: "Voice {label} deleted.",
    voiceDownloadError: "Could not download voice.",
    voiceDeleteError: "Could not delete voice.",
    voicePreviewNeedsSelection: "Choose a local voice first.",
    voiceNotDownloaded: "This voice is not installed locally yet.",
    voiceSelectedToast: "Selected voice {label}.",
    historyLoadError: "Could not load history: {message}",
    recordOpenError: "Could not open record.",
    backgroundTimeout: "Background task timed out.",
    downloadTimeout: "Voice download timed out.",
    clearToast: "Text cleared.",
    resultBaseMeta: "{voice} • WAV • {duration}",
    resultProcessedMeta: "{voice} • saved {speed} • {duration} • WAV",
    recordMetaLine: "{voice} • {time} • {status}",
    voiceLabelFallback: "Voice",
    closeSettingsAria: "Close settings",
    voiceSettingsAria: "Voice settings",
    languageSwitchAria: "Language",
    themeSwitchAria: "Theme switch",
    speedOptionsAria: "Speed options",
  },
  uk: {
    documentTitle: "LocalGPT TTS / Voice",
    appTitle: "LocalGPT TTS / Voice",
    appSubtitle: "Локальна генерація озвучення без зовнішніх API та хмари.",
    themeDark: "Темна",
    themeLight: "Світла",
    healthChecking: "Перевірка локального TTS...",
    voiceLoading: "Завантаження голосів...",
    step1: "Крок 1",
    step2: "Крок 2",
    step4: "Крок 4",
    textTitle: "Текст",
    settings: "Налаштування",
    clear: "Очистити",
    textLabel: "Текст",
    textPlaceholder: "Введіть текст для локального синтезу мовлення...",
    textHint: "Довгий текст буде розбитий на частини й склеєний в один WAV.",
    currentVoice: "Поточний голос",
    voiceSummaryHint: "Вибір, завантаження, прев’ю та видалення голосів знаходяться в налаштуваннях.",
    voiceNone: "Поки немає відповідних локальних голосів.",
    generate: "Згенерувати",
    apply: "Apply",
    idle: "Очікування",
    generateIdleStatus: "Очікування дії.",
    settingsTitle: "Голоси",
    localVoiceLabel: "Локальний голос",
    preview: "Прев’ю",
    refresh: "Оновити",
    previewHint: "Прев’ю використовує локально встановлений голос.",
    library: "Бібліотека",
    librarySearchPlaceholder: "Пошук за мовою, назвою або quality...",
    libraryLoading: "Завантаження каталогу голосів Piper...",
    step2Title: "Результат і швидкість",
    recordMetaEmpty: "Історія та плеєр з’являться після генерації.",
    resultEyebrow: "Result WAV",
    resultTitle: "Результат",
    downloadWav: "Завантажити WAV",
    resultEmpty: "WAV ще не згенеровано.",
    speedEyebrow: "Speed",
    speedTitle: "Швидкість",
    speedInitialStatus: "Оберіть швидкість. Плеєр відтворює її наживо; кнопка застосування збереже окремий WAV.",
    step4Title: "Історія",
    historyRefresh: "Оновити",
    historyEmpty: "Історія поки порожня.",
    historyDelete: "Видалити запис",
    historyBase: "base",
    historyProcessed: "processed",
    emptyPreview: "(порожньо)",
    unknown: "невідомо",
    healthOk: "Локальний TTS: {status} • provider: {provider}",
    healthFail: "Не вдалося отримати health: {message}",
    voiceCount: "Доступні голоси: {count}",
    voicesUnavailable: "Голоси поки недоступні.",
    voiceRefreshFail: "Помилка завантаження голосів: {message}",
    libraryLoaded: "Каталог Piper: {count} голосів.",
    libraryLoadedBadge: "{count} голосів",
    libraryError: "Помилка каталогу голосів: {message}",
    loading: "Завантаження",
    error: "Помилка",
    downloading: "Завантаження",
    deleting: "Видалення...",
    use: "Використати",
    download: "Завантажити",
    delete: "Видалити",
    installed: "Встановлено",
    remote: "Віддалено",
    notFound: "Нічого не знайдено.",
    localIds: "локальних ID: {count}",
    notDownloaded: "ще не завантажено",
    speakerOne: "1 голос",
    speakerMany: "{count} голоси",
    generating: "Генерація",
    generateStarted: "Генерацію запущено у фоні...",
    generateDone: "Готово: {voice} • {duration}",
    generateReady: "Готово",
    generateError: "Помилка генерації.",
    ttsReady: "Озвучення готове.",
    enterText: "Введіть текст для озвучення.",
    textTooLong: "Текст перевищує ліміт у {limit} символів.",
    chooseVoice: "Спочатку оберіть голос.",
    baseMissing: "Спочатку створіть базовий WAV.",
    speedCreate: "Створюю окремий WAV зі швидкістю {speed}...",
    speedDone: "Збережено: {speed} • {duration}",
    speedError: "Помилка постобробки.",
    speedSaved: "Прискорений WAV готовий.",
    speedOriginal: "1x використовує оригінальний WAV. Окремий файл не потрібен.",
    speedPreviewOnly: "Відтворення {speed} наживо з оригінального WAV. Натисніть кнопку застосування для збереження.",
    speedSavedStatus: "Активний збережений WAV {speed}.",
    recordDeleted: "Запис видалено.",
    recordDeleteConfirm: "Видалити цей запис історії та пов’язані WAV-файли?",
    previewCreating: "Генерую локальне прев’ю...",
    previewReady: "Прев’ю готове: {label}.",
    previewError: "Не вдалося створити прев’ю.",
    voiceDownloading: "Завантаження голосу {voiceKey}...",
    voiceDownloadedStatus: "Голос {voiceKey} встановлено локально.",
    voiceDownloadedToast: "Голос {voiceKey} завантажено.",
    voiceDeleteConfirm: "Видалити локальний голос {label}?",
    voiceDeletedStatus: "Голос {label} видалено локально.",
    voiceDeletedToast: "Голос {label} видалено.",
    voiceDownloadError: "Не вдалося завантажити голос.",
    voiceDeleteError: "Не вдалося видалити голос.",
    voicePreviewNeedsSelection: "Спочатку оберіть локальний голос.",
    voiceNotDownloaded: "Цей голос ще не завантажено локально.",
    voiceSelectedToast: "Вибрано голос {label}.",
    historyLoadError: "Не вдалося завантажити історію: {message}",
    recordOpenError: "Не вдалося відкрити запис.",
    backgroundTimeout: "Перевищено час очікування фонової задачі.",
    downloadTimeout: "Перевищено час очікування завантаження голосу.",
    clearToast: "Текст очищено.",
    resultBaseMeta: "{voice} • WAV • {duration}",
    resultProcessedMeta: "{voice} • збережено {speed} • {duration} • WAV",
    recordMetaLine: "{voice} • {time} • {status}",
    voiceLabelFallback: "Голос",
    closeSettingsAria: "Закрити налаштування",
    voiceSettingsAria: "Налаштування голосів",
    languageSwitchAria: "Мова",
    themeSwitchAria: "Перемикач теми",
    speedOptionsAria: "Варіанти швидкості",
  },
  ru: {
    documentTitle: "LocalGPT TTS / Voice",
    appTitle: "LocalGPT TTS / Voice",
    appSubtitle: "Локальная генерация озвучки без внешних API и облака.",
    themeDark: "Темная",
    themeLight: "Светлая",
    healthChecking: "Проверка локального TTS...",
    voiceLoading: "Загрузка голосов...",
    step1: "Шаг 1",
    step2: "Шаг 2",
    step4: "Шаг 4",
    textTitle: "Текст",
    settings: "Настройки",
    clear: "Очистить",
    textLabel: "Текст",
    textPlaceholder: "Введите текст для локальной озвучки...",
    textHint: "Длинный текст будет разбит на части и склеен в один WAV.",
    currentVoice: "Текущий голос",
    voiceSummaryHint: "Выбор, загрузка, превью и удаление голосов находятся в настройках.",
    voiceNone: "Подходящих локальных голосов пока нет.",
    generate: "Сгенерировать",
    apply: "Применить",
    idle: "Ожидание",
    generateIdleStatus: "Ожидание действия.",
    settingsTitle: "Голоса",
    localVoiceLabel: "Локальный голос",
    preview: "Превью",
    refresh: "Обновить",
    previewHint: "Превью использует локально установленный голос.",
    library: "Библиотека",
    librarySearchPlaceholder: "Поиск по языку, имени или quality...",
    libraryLoading: "Загрузка каталога голосов Piper...",
    step2Title: "Результат и скорость",
    recordMetaEmpty: "История и плеер появятся после генерации.",
    resultEyebrow: "Result WAV",
    resultTitle: "Результат",
    downloadWav: "Скачать WAV",
    resultEmpty: "WAV пока не сгенерирован.",
    speedEyebrow: "Speed",
    speedTitle: "Скорость",
    speedInitialStatus: "Выберите скорость. Плеер прослушивает её сразу; кнопка применения сохраняет отдельный WAV.",
    step4Title: "История",
    historyRefresh: "Обновить",
    historyEmpty: "История пока пуста.",
    historyDelete: "Удалить запись",
    historyBase: "base",
    historyProcessed: "processed",
    emptyPreview: "(пусто)",
    unknown: "неизвестно",
    healthOk: "Локальный TTS: {status} • provider: {provider}",
    healthFail: "Не удалось получить health: {message}",
    voiceCount: "Голоса доступны: {count}",
    voicesUnavailable: "Голоса пока недоступны.",
    voiceRefreshFail: "Ошибка загрузки голосов: {message}",
    libraryLoaded: "Каталог Piper: {count} голосов.",
    libraryLoadedBadge: "{count} голосов",
    libraryError: "Ошибка каталога голосов: {message}",
    loading: "Загрузка",
    error: "Ошибка",
    downloading: "Загрузка",
    deleting: "Удаление...",
    use: "Использовать",
    download: "Скачать",
    delete: "Удалить",
    installed: "Установлен",
    remote: "Удаленно",
    notFound: "Ничего не найдено.",
    localIds: "локальных ID: {count}",
    notDownloaded: "ещё не загружен",
    speakerOne: "1 голос",
    speakerMany: "{count} голосов",
    generating: "Генерация",
    generateStarted: "Генерация запущена в фоне...",
    generateDone: "Готово: {voice} • {duration}",
    generateReady: "Готово",
    generateError: "Ошибка генерации.",
    ttsReady: "Озвучка готова.",
    enterText: "Введите текст для озвучки.",
    textTooLong: "Текст превышает лимит {limit} символов.",
    chooseVoice: "Сначала выберите голос.",
    baseMissing: "Сначала создайте базовый WAV.",
    speedCreate: "Создаю отдельный WAV со скоростью {speed}...",
    speedDone: "Сохранено: {speed} • {duration}",
    speedError: "Ошибка пост-обработки.",
    speedSaved: "Ускоренный WAV готов.",
    speedOriginal: "1x использует исходный WAV. Отдельный файл не нужен.",
    speedPreviewOnly: "Сейчас {speed} проигрывается в плеере из исходного WAV. Кнопка применения сохранит отдельный файл.",
    speedSavedStatus: "Активен сохранённый WAV {speed}.",
    recordDeleted: "Запись удалена.",
    recordDeleteConfirm: "Удалить запись из истории и связанные WAV-файлы?",
    previewCreating: "Генерирую локальное превью...",
    previewReady: "Превью готово: {label}.",
    previewError: "Не удалось создать превью.",
    voiceDownloading: "Загрузка голоса {voiceKey}...",
    voiceDownloadedStatus: "Голос {voiceKey} загружен локально.",
    voiceDownloadedToast: "Голос {voiceKey} загружен.",
    voiceDeleteConfirm: "Удалить локальный голос {label}?",
    voiceDeletedStatus: "Голос {label} удалён локально.",
    voiceDeletedToast: "Голос {label} удалён.",
    voiceDownloadError: "Не удалось загрузить голос.",
    voiceDeleteError: "Не удалось удалить голос.",
    voicePreviewNeedsSelection: "Сначала выберите локальный голос.",
    voiceNotDownloaded: "Этот голос ещё не загружен локально.",
    voiceSelectedToast: "Выбран голос {label}.",
    historyLoadError: "Не удалось загрузить историю: {message}",
    recordOpenError: "Не удалось открыть запись.",
    backgroundTimeout: "Превышено время ожидания фоновой задачи.",
    downloadTimeout: "Превышено время ожидания загрузки голоса.",
    clearToast: "Текст очищен.",
    resultBaseMeta: "{voice} • WAV • {duration}",
    resultProcessedMeta: "{voice} • сохранено {speed} • {duration} • WAV",
    recordMetaLine: "{voice} • {time} • {status}",
    voiceLabelFallback: "Voice",
    closeSettingsAria: "Закрыть настройки",
    voiceSettingsAria: "Настройки голосов",
    languageSwitchAria: "Язык",
    themeSwitchAria: "Переключатель темы",
    speedOptionsAria: "Варианты скорости",
  },
};

const elements = {
  appTitle: document.getElementById("appTitle"),
  appSubtitle: document.getElementById("appSubtitle"),
  langFlags: Array.from(document.querySelectorAll(".lang-flag")),
  langSwitch: document.querySelector(".lang-switch"),
  themeSwitch: document.querySelector(".theme-switch"),
  btnThemeDark: document.getElementById("btnThemeDark"),
  btnThemeLight: document.getElementById("btnThemeLight"),
  healthStatus: document.getElementById("healthStatus"),
  voiceAvailability: document.getElementById("voiceAvailability"),
  step1Label: document.getElementById("step1Label"),
  step1Title: document.getElementById("step1Title"),
  btnVoiceSettings: document.getElementById("btnVoiceSettings"),
  btnCloseVoiceSettings: document.getElementById("btnCloseVoiceSettings"),
  textLabel: document.getElementById("textLabel"),
  ttsText: document.getElementById("ttsText"),
  textCounter: document.getElementById("textCounter"),
  btnClearText: document.getElementById("btnClearText"),
  textHint: document.getElementById("textHint"),
  currentVoiceLabel: document.getElementById("currentVoiceLabel"),
  voiceInfo: document.getElementById("voiceInfo"),
  voiceSummaryHint: document.getElementById("voiceSummaryHint"),
  generateBadge: document.getElementById("generateBadge"),
  btnGenerate: document.getElementById("btnGenerate"),
  generateStatus: document.getElementById("generateStatus"),
  voiceSettingsPanel: document.getElementById("voiceSettingsPanel"),
  settingsKicker: document.getElementById("settingsKicker"),
  settingsTitle: document.getElementById("settingsTitle"),
  voiceSelectLabel: document.getElementById("voiceSelectLabel"),
  voiceSelect: document.getElementById("voiceSelect"),
  btnPreviewSelected: document.getElementById("btnPreviewSelected"),
  previewStatus: document.getElementById("previewStatus"),
  voicePreviewPlayer: document.getElementById("voicePreviewPlayer"),
  btnRefreshVoiceLibrary: document.getElementById("btnRefreshVoiceLibrary"),
  voiceLibraryLabel: document.getElementById("voiceLibraryLabel"),
  voiceLibraryBadge: document.getElementById("voiceLibraryBadge"),
  voiceLibrarySearch: document.getElementById("voiceLibrarySearch"),
  voiceLibraryStatus: document.getElementById("voiceLibraryStatus"),
  voiceLibraryList: document.getElementById("voiceLibraryList"),
  step2Label: document.getElementById("step2Label"),
  step2Title: document.getElementById("step2Title"),
  recordMeta: document.getElementById("recordMeta"),
  resultCard: document.getElementById("resultCard"),
  resultPlayer: document.getElementById("resultPlayer"),
  resultInfo: document.getElementById("resultInfo"),
  resultEyebrow: document.getElementById("resultEyebrow"),
  resultTitle: document.getElementById("resultTitle"),
  downloadResult: document.getElementById("downloadResult"),
  speedEyebrow: document.getElementById("speedEyebrow"),
  speedTitle: document.getElementById("speedTitle"),
  speedOptions: document.getElementById("speedOptions"),
  btnApplySpeed: document.getElementById("btnApplySpeed"),
  speedStatus: document.getElementById("speedStatus"),
  step4Label: document.getElementById("step4Label"),
  step4Title: document.getElementById("step4Title"),
  historyList: document.getElementById("historyList"),
  btnRefreshHistory: document.getElementById("btnRefreshHistory"),
  appToast: document.getElementById("appToast"),
};

const state = {
  health: null,
  voices: [],
  voiceLibrary: [],
  history: [],
  activeRecordId: null,
  activeRecord: null,
  maxTextChars: 15000,
  speedOptions: [1.0, 1.25, 1.5, 1.75, 2.0],
  selectedSpeed: getSavedSpeed(1.25),
  theme: getSavedTheme(document.documentElement.dataset.theme || "dark"),
  language: getSavedLanguage(document.documentElement.lang || "ru"),
  generating: false,
  processingSpeed: false,
  previewBusy: false,
  voiceLibraryLoading: false,
  downloadingVoiceKey: null,
  deletingVoiceKey: null,
  voiceLibraryQuery: "",
  previewObjectUrl: null,
  voiceSettingsOpen: false,
};

let toastTimer = null;

function formatText(template, params = {}) {
  return String(template || "").replace(/\{(\w+)\}/g, (_, key) => String(params[key] ?? ""));
}

function normalizeLanguage(language) {
  return language === "en" || language === "uk" || language === "ru" ? language : "ru";
}

function localeForLanguage(language = state.language) {
  return LANGUAGE_LOCALES[normalizeLanguage(language)] || LANGUAGE_LOCALES.ru;
}

function t(key, params = {}) {
  const dict = I18N[normalizeLanguage(state.language)] || I18N.ru;
  const template = dict[key] ?? I18N.en[key] ?? key;
  return formatText(template, params);
}

function showToast(message, tone = "info") {
  if (!elements.appToast) return;
  clearTimeout(toastTimer);
  elements.appToast.hidden = false;
  elements.appToast.textContent = message;
  elements.appToast.dataset.tone = tone;
  toastTimer = window.setTimeout(() => {
    elements.appToast.hidden = true;
  }, 2600);
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function versionedUrl(url, version) {
  if (!url) return "";
  const suffix = version ? `&v=${encodeURIComponent(version)}` : "";
  return `${url}${suffix}`;
}

function downloadUrl(url, version) {
  if (!url) return "#";
  return `${versionedUrl(url, version)}&download=1`;
}

function speedKey(speed) {
  return Number(speed || 1)
    .toFixed(2)
    .replace(/\.?0+$/, "");
}

function formatSpeedLabel(speed) {
  return `${String(Number(speed || 1)).replace(".0", "")}x`;
}

function nearestSpeedOption(speed) {
  const target = Number(speed);
  const options = state.speedOptions
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value) && value > 0);
  if (!options.length || !Number.isFinite(target)) {
    return 1;
  }
  return options.reduce((closest, option) =>
    Math.abs(option - target) < Math.abs(closest - target) ? option : closest,
  options[0]);
}

function formatBytes(bytes) {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value <= 0) return "—";
  const mb = value / (1024 * 1024);
  return `${mb.toFixed(1)} MB`;
}

function applyPlayerRate(player, rate) {
  if (!player) return;
  try {
    player.defaultPlaybackRate = rate;
    player.playbackRate = rate;
  } catch {
    // ignore playbackRate assignment issues
  }
}

function normalizedVoiceLanguage(code) {
  return String(code || "")
    .trim()
    .replace("-", "_");
}

function displayLanguage(code) {
  const normalized = normalizedVoiceLanguage(code);
  const label = VOICE_LANGUAGE_LABELS[normalized]?.[state.language];
  if (label) return label;
  return normalized || t("unknown");
}

function currentVoice() {
  const voiceId = elements.voiceSelect?.value || "";
  return state.voices.find((item) => item.id === voiceId) || null;
}

function previewTextCandidate() {
  const text = (elements.ttsText.value || "").trim();
  if (!text) return null;
  if (text.length <= PREVIEW_TEXT_LIMIT) return text;
  return `${text.slice(0, PREVIEW_TEXT_LIMIT - 1).trim()}…`;
}

function setBadgeState(element, label, tone = "idle") {
  if (!element) return;
  element.textContent = label;
  element.dataset.tone = tone;
}

function setVoiceSettingsOpen(open) {
  state.voiceSettingsOpen = Boolean(open);
  elements.voiceSettingsPanel.hidden = !state.voiceSettingsOpen;
  elements.btnVoiceSettings?.setAttribute("aria-expanded", state.voiceSettingsOpen ? "true" : "false");
}

function toggleVoiceSettings() {
  setVoiceSettingsOpen(!state.voiceSettingsOpen);
}

function normalizeTheme(theme) {
  return theme === "light" ? "light" : "dark";
}

function renderThemeSwitch() {
  const theme = normalizeTheme(state.theme);
  [elements.btnThemeDark, elements.btnThemeLight].forEach((button) => {
    if (!button) return;
    const isActive = button.dataset.theme === theme;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function applyTheme(theme) {
  const normalized = normalizeTheme(theme);
  state.theme = normalized;
  document.documentElement.dataset.theme = normalized;
  setSavedTheme(normalized);
  renderThemeSwitch();
}

function renderLanguageSwitch() {
  for (const flag of elements.langFlags) {
    const isActive = flag.dataset.lang === state.language;
    flag.classList.toggle("is-active", isActive);
    flag.setAttribute("aria-pressed", isActive ? "true" : "false");
  }
}

function updateCounter() {
  const value = elements.ttsText?.value || "";
  const count = value.length;
  elements.textCounter.textContent = `${count} / ${state.maxTextChars}`;
  elements.textCounter.classList.toggle("is-danger", count > state.maxTextChars);
}

function revokePreviewUrl() {
  if (state.previewObjectUrl) {
    URL.revokeObjectURL(state.previewObjectUrl);
    state.previewObjectUrl = null;
  }
}

function voiceSelectLabel(voice) {
  if (!voice) return t("voiceNone");
  const quality = voice.quality ? ` • ${voice.quality}` : "";
  return `${voice.name} • ${displayLanguage(voice.language)}${quality}`;
}

function renderVoiceInfo() {
  const voice = currentVoice();
  if (!voice) {
    elements.voiceInfo.textContent = t("voiceNone");
    return;
  }
  const quality = voice.quality ? ` • ${voice.quality}` : "";
  const sampleRate = voice.sample_rate ? ` • ${voice.sample_rate} Hz` : "";
  elements.voiceInfo.textContent = `${voice.name} • ${displayLanguage(voice.language)}${quality}${sampleRate}`;
}

function renderVoiceSelect() {
  const savedVoiceId = getSavedVoice();
  const options = state.voices.length
    ? state.voices
        .map((voice) => `<option value="${voice.id}">${voiceSelectLabel(voice)}</option>`)
        .join("")
    : `<option value="">${t("voiceNone")}</option>`;

  elements.voiceSelect.innerHTML = options;
  elements.voiceSelect.setAttribute("aria-label", t("localVoiceLabel"));

  if (!state.voices.length) {
    elements.voiceSelect.value = "";
    renderVoiceInfo();
    setActionState();
    return;
  }

  const selected = state.voices.find((item) => item.id === savedVoiceId) || state.voices[0];
  elements.voiceSelect.value = selected.id;
  setSavedVoice(selected.id);
  renderVoiceInfo();
  setActionState();
}

function speakerLabel(count) {
  return Number(count) > 1 ? t("speakerMany", { count }) : t("speakerOne");
}

function voiceLibraryItemsFiltered() {
  const query = (state.voiceLibraryQuery || "").trim().toLowerCase();
  if (!query) return state.voiceLibrary;
  return state.voiceLibrary.filter((item) => {
    const haystack = [
      item.key,
      item.name,
      item.language_code,
      item.language_name,
      item.country_name,
      item.quality,
      displayLanguage(item.language_code),
      ...(Array.isArray(item.aliases) ? item.aliases : []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function renderVoiceLibraryList() {
  const items = voiceLibraryItemsFiltered();
  if (!items.length) {
    elements.voiceLibraryList.innerHTML = `<p class="voice-library__empty">${t("notFound")}</p>`;
    return;
  }

  elements.voiceLibraryList.innerHTML = items
    .map((item) => {
      const installed = Boolean(item.installed);
      const downloadBusy = state.downloadingVoiceKey === item.key;
      const deleteBusy = state.deletingVoiceKey === item.key;
      const previewDisabled = !item.preview_available || state.previewBusy;
      const useDisabled = !installed || !item.installed_voice_ids?.length;
      const statusPill = installed
        ? `<span class="pill pill--installed">${t("installed")}</span>`
        : downloadBusy
          ? `<span class="pill pill--busy">${t("downloading")}</span>`
          : `<span class="pill pill--remote">${t("remote")}</span>`;
      const languageLabel = displayLanguage(item.language_code);
      const subtitle = `${languageLabel}${item.quality ? ` • ${item.quality}` : ""} • ${speakerLabel(item.num_speakers)}`;

      return `
        <article class="voice-card voice-card--compact ${installed ? "is-installed" : ""}" data-voice-key="${item.key}">
          <div class="voice-card__top">
            <div>
              <p class="voice-card__name">${item.name}</p>
              <p class="voice-card__subtitle">${subtitle}</p>
            </div>
            <div class="voice-card__pills">
              ${statusPill}
            </div>
          </div>
          <div class="voice-card__meta">
            <p class="voice-card__size">${formatBytes(item.download_size_bytes)}</p>
            <p class="voice-card__size">${item.installed_voice_ids?.length ? t("localIds", { count: item.installed_voice_ids.length }) : t("notDownloaded")}</p>
          </div>
          <div class="voice-card__actions">
            <button
              class="btn btn-ghost"
              type="button"
              data-action="use-voice"
              data-voice-key="${item.key}"
              ${useDisabled ? "disabled" : ""}
            >
              ${t("use")}
            </button>
            <button
              class="btn btn-secondary"
              type="button"
              data-action="${installed ? "delete-voice" : "download"}"
              data-voice-key="${item.key}"
              ${downloadBusy || deleteBusy ? "disabled" : ""}
            >
              ${downloadBusy ? t("downloading") : deleteBusy ? t("deleting") : installed ? t("delete") : t("download")}
            </button>
            <button
              class="btn btn-ghost"
              type="button"
              data-action="preview-library"
              data-voice-key="${item.key}"
              ${previewDisabled ? "disabled" : ""}
            >
              ${t("preview")}
            </button>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderSpeedOptions() {
  elements.speedOptions.innerHTML = state.speedOptions
    .map((speed) => {
      const label = formatSpeedLabel(speed);
      const checked = Number(state.selectedSpeed) === Number(speed) ? "is-selected" : "";
      return `<button class="speed-pill ${checked}" type="button" data-speed="${speed}">${label}</button>`;
    })
    .join("");
}

function updateAudioCard(card, player, infoEl, linkEl, payload = null, version = "", filenameFallback = "") {
  const hasAudio = Boolean(payload?.url);
  card.classList.toggle("is-empty", !hasAudio);

  if (hasAudio) {
    player.src = versionedUrl(payload.url, version);
    linkEl.href = downloadUrl(payload.url, version);
    linkEl.classList.remove("is-disabled");
    linkEl.removeAttribute("aria-disabled");
    linkEl.setAttribute("download", filenameFallback);
  } else {
    player.removeAttribute("src");
    player.load();
    linkEl.href = "#";
    linkEl.classList.add("is-disabled");
    linkEl.setAttribute("aria-disabled", "true");
    linkEl.removeAttribute("download");
  }

  infoEl.textContent = payload?.text || t("resultEmpty");
}

function activeProcessedOutput(record, speed = state.selectedSpeed) {
  if (!record?.processed_outputs) return null;
  return record.processed_outputs[speedKey(speed)] || null;
}

function activeAudioPayload(record = state.activeRecord) {
  if (!record?.base_output_url) return null;
  const selectedSpeed = nearestSpeedOption(state.selectedSpeed);
  const processed = Number(selectedSpeed) > 1 ? activeProcessedOutput(record, selectedSpeed) : null;
  if (processed?.url) {
    return {
      url: processed.url,
      variant: "processed",
      speed: selectedSpeed,
      duration: processed.duration_sec ?? record.processed_duration_sec ?? record.duration_sec,
    };
  }
  return {
    url: record.base_output_url,
    variant: "base",
    speed: 1,
    duration: record.duration_sec,
  };
}

function syncPlaybackRates() {
  const active = activeAudioPayload();
  const resultRate = active?.variant === "processed" ? 1 : Number(state.selectedSpeed) || 1;
  applyPlayerRate(elements.resultPlayer, resultRate);
  applyPlayerRate(elements.voicePreviewPlayer, Number(state.selectedSpeed) || 1);
}

function renderResultCard() {
  const record = state.activeRecord;
  const timestamp = record?.updated_at || record?.created_at || record?.id || "";
  const active = activeAudioPayload(record);
  const voiceLabel = record?.voice_name || t("voiceLabelFallback");

  let text = t("resultEmpty");
  let filename = `${record?.id || "tts"}_base.wav`;

  if (active) {
    if (active.variant === "processed") {
      text = t("resultProcessedMeta", {
        voice: voiceLabel,
        speed: formatSpeedLabel(active.speed),
        duration: formatDuration(active.duration, state.language),
      });
      filename = `${record?.id || "tts"}_${speedKey(active.speed).replace(".", "_")}x.wav`;
    } else {
      text = t("resultBaseMeta", {
        voice: voiceLabel,
        duration: formatDuration(active.duration, state.language),
      });
    }
  }

  updateAudioCard(
    elements.resultCard,
    elements.resultPlayer,
    elements.resultInfo,
    elements.downloadResult,
    active ? { url: active.url, text } : null,
    timestamp,
    filename,
  );
  syncPlaybackRates();
}

function renderRecordMeta() {
  const record = state.activeRecord;
  if (!record) {
    elements.recordMeta.textContent = t("recordMetaEmpty");
    return;
  }

  elements.recordMeta.textContent = t("recordMetaLine", {
    voice: record.voice_name || t("voiceLabelFallback"),
    time: formatDateTime(record.updated_at || record.created_at, localeForLanguage()),
    status: record.status || t("unknown"),
  });
}

function renderHistory() {
  renderHistoryList(elements.historyList, state.history, state.activeRecordId, {
    language: state.language,
    locale: localeForLanguage(),
    emptyText: t("historyEmpty"),
    untitledVoice: t("voiceLabelFallback"),
    emptyPreview: t("emptyPreview"),
    baseLabel: t("historyBase"),
    processedLabel: t("historyProcessed"),
    deleteLabel: t("historyDelete"),
    formatLanguage: displayLanguage,
  });
}

function updateSpeedStatus() {
  if (state.processingSpeed) {
    setStatus(elements.speedStatus, t("speedCreate", { speed: formatSpeedLabel(state.selectedSpeed) }), "warning");
    return;
  }

  if (!state.activeRecord?.base_output_url) {
    setStatus(elements.speedStatus, t("speedInitialStatus"), "info");
    return;
  }

  const selectedSpeed = nearestSpeedOption(state.selectedSpeed);
  if (Number(selectedSpeed) === 1) {
    setStatus(elements.speedStatus, t("speedOriginal"), "success");
    return;
  }

  const processed = activeProcessedOutput(state.activeRecord, selectedSpeed);
  if (processed?.url) {
    setStatus(elements.speedStatus, t("speedSavedStatus", { speed: formatSpeedLabel(selectedSpeed) }), "success");
    return;
  }

  setStatus(elements.speedStatus, t("speedPreviewOnly", { speed: formatSpeedLabel(selectedSpeed) }), "warning");
}

function renderGenerateState() {
  if (state.generating) {
    setBadgeState(elements.generateBadge, t("generating"), "busy");
    setStatus(elements.generateStatus, t("generateStarted"), "warning");
    return;
  }

  if (state.activeRecord?.base_output_url) {
    setBadgeState(elements.generateBadge, t("generateReady"), "success");
    setStatus(
      elements.generateStatus,
      t("generateDone", {
        voice: state.activeRecord.voice_name || t("voiceLabelFallback"),
        duration: formatDuration(state.activeRecord.duration_sec, state.language),
      }),
      "success",
    );
    return;
  }

  setBadgeState(elements.generateBadge, t("idle"), "idle");
  setStatus(elements.generateStatus, t("generateIdleStatus"), "info");
}

function renderHealthState() {
  if (!state.health) {
    setStatus(elements.healthStatus, t("healthChecking"), "info");
    setStatus(elements.voiceAvailability, t("voiceLoading"), "info");
    return;
  }

  setStatus(
    elements.healthStatus,
    t("healthOk", {
      status: state.health.status,
      provider: state.health.default_provider,
    }),
    state.health.status === "ok" ? "success" : "warning",
  );

  const providerAvailable = Boolean(state.health.provider?.available);
  setStatus(
    elements.voiceAvailability,
    providerAvailable
      ? t("voiceCount", { count: state.health.provider.voices_count || 0 })
      : state.health.provider?.message || t("voicesUnavailable"),
    providerAvailable ? "info" : "warning",
  );
}

function renderStaticText() {
  document.title = t("documentTitle");
  elements.appTitle.textContent = t("appTitle");
  elements.appSubtitle.textContent = t("appSubtitle");
  elements.btnThemeDark.textContent = t("themeDark");
  elements.btnThemeLight.textContent = t("themeLight");
  elements.step1Label.textContent = t("step1");
  elements.step1Title.textContent = t("textTitle");
  elements.btnVoiceSettings.textContent = t("settings");
  elements.btnClearText.textContent = t("clear");
  elements.textLabel.textContent = t("textLabel");
  elements.ttsText.placeholder = t("textPlaceholder");
  elements.textHint.textContent = t("textHint");
  elements.currentVoiceLabel.textContent = t("currentVoice");
  elements.voiceSummaryHint.textContent = t("voiceSummaryHint");
  elements.btnGenerate.textContent = t("generate");
  elements.settingsKicker.textContent = t("settings");
  elements.settingsTitle.textContent = t("settingsTitle");
  elements.voiceSelectLabel.textContent = t("localVoiceLabel");
  elements.btnPreviewSelected.textContent = t("preview");
  elements.btnRefreshVoiceLibrary.textContent = t("refresh");
  elements.voiceLibraryLabel.textContent = t("library");
  elements.voiceLibrarySearch.placeholder = t("librarySearchPlaceholder");
  elements.step2Label.textContent = t("step2");
  elements.step2Title.textContent = t("step2Title");
  elements.resultEyebrow.textContent = t("resultEyebrow");
  elements.resultTitle.textContent = t("resultTitle");
  elements.downloadResult.textContent = t("downloadWav");
  elements.speedEyebrow.textContent = t("speedEyebrow");
  elements.speedTitle.textContent = t("speedTitle");
  elements.btnApplySpeed.textContent = t("apply");
  elements.step4Label.textContent = t("step4");
  elements.step4Title.textContent = t("step4Title");
  elements.btnRefreshHistory.textContent = t("historyRefresh");
  elements.langSwitch?.setAttribute("aria-label", t("languageSwitchAria"));
  elements.themeSwitch?.setAttribute("aria-label", t("themeSwitchAria"));
  elements.voiceSettingsPanel?.setAttribute("aria-label", t("voiceSettingsAria"));
  elements.btnCloseVoiceSettings?.setAttribute("aria-label", t("closeSettingsAria"));
  elements.speedOptions?.setAttribute("aria-label", t("speedOptionsAria"));
}

function applyLanguage(language, { persist = true } = {}) {
  state.language = normalizeLanguage(language);
  document.documentElement.lang = state.language;
  if (persist) {
    setSavedLanguage(state.language);
  }
  renderLanguageSwitch();
  renderStaticText();
  renderHealthState();
  renderVoiceSelect();
  renderVoiceLibraryList();
  renderVoiceInfo();
  renderRecordMeta();
  renderResultCard();
  renderHistory();
  updateSpeedStatus();
  renderGenerateState();
  if (!state.previewBusy && !state.previewObjectUrl) {
    setStatus(elements.previewStatus, t("previewHint"), "info");
  }
}

function setActionState() {
  const hasVoice = Boolean(elements.voiceSelect?.value);
  const hasRecord = Boolean(state.activeRecord?.base_output_url);
  const hasSavedSpeed = Boolean(activeProcessedOutput(state.activeRecord, state.selectedSpeed)?.url);
  elements.btnGenerate.disabled = state.generating || !hasVoice;
  elements.btnApplySpeed.disabled = state.processingSpeed || !hasRecord || Number(state.selectedSpeed) === 1 || hasSavedSpeed;
  elements.voiceSelect.disabled = state.generating || state.processingSpeed;
  elements.ttsText.disabled = state.generating;
  elements.btnPreviewSelected.disabled = state.previewBusy || !hasVoice;
  elements.btnRefreshVoiceLibrary.disabled =
    state.voiceLibraryLoading || Boolean(state.downloadingVoiceKey) || Boolean(state.deletingVoiceKey);
}

function selectSpeed(speed, { persist = true } = {}) {
  const selected = nearestSpeedOption(speed);
  state.selectedSpeed = selected;
  if (persist) {
    setSavedSpeed(selected);
  }
  renderSpeedOptions();
  renderResultCard();
  updateSpeedStatus();
  setActionState();
}

function loadRecord(record) {
  state.activeRecord = record;
  state.activeRecordId = record?.id || null;

  if (record?.text && !state.generating) {
    elements.ttsText.value = record.text;
    updateCounter();
  }

  if (record?.voice_id) {
    const match = state.voices.find((voice) => voice.id === record.voice_id);
    if (match) {
      elements.voiceSelect.value = match.id;
      setSavedVoice(match.id);
    }
  }

  renderVoiceInfo();
  renderRecordMeta();
  renderResultCard();
  renderHistory();
  updateSpeedStatus();
  renderGenerateState();
  setActionState();
}

async function refreshHealth() {
  try {
    const health = await fetchHealth();
    state.health = health;
    state.maxTextChars = Number(health.max_text_chars) || 15000;
    state.speedOptions = Array.isArray(health.speed_options) && health.speed_options.length
      ? health.speed_options
      : state.speedOptions;
    renderHealthState();
  } catch (error) {
    state.health = null;
    setStatus(elements.healthStatus, t("healthFail", { message: error.message }), "error");
    setStatus(elements.voiceAvailability, t("voicesUnavailable"), "warning");
  }
  updateCounter();
  renderSpeedOptions();
  renderResultCard();
  updateSpeedStatus();
}

async function refreshVoices() {
  try {
    const response = await listVoices();
    state.voices = Array.isArray(response.items) ? response.items.filter((item) => item.available !== false) : [];
    renderVoiceSelect();
  } catch (error) {
    state.voices = [];
    renderVoiceSelect();
    setStatus(elements.voiceAvailability, t("voiceRefreshFail", { message: error.message }), "error");
  }
}

async function refreshVoiceLibrary(forceRefresh = false) {
  state.voiceLibraryLoading = true;
  setBadgeState(elements.voiceLibraryBadge, t("loading"), "busy");
  setActionState();
  try {
    const response = await listVoiceLibrary(forceRefresh);
    state.voiceLibrary = Array.isArray(response.items) ? response.items : [];
    renderVoiceLibraryList();
    setStatus(elements.voiceLibraryStatus, t("libraryLoaded", { count: state.voiceLibrary.length }), "success");
    setBadgeState(elements.voiceLibraryBadge, t("libraryLoadedBadge", { count: state.voiceLibrary.length }), "success");
  } catch (error) {
    state.voiceLibrary = [];
    renderVoiceLibraryList();
    setStatus(elements.voiceLibraryStatus, t("libraryError", { message: error.message }), "error");
    setBadgeState(elements.voiceLibraryBadge, t("error"), "error");
  } finally {
    state.voiceLibraryLoading = false;
    setActionState();
  }
}

async function refreshHistory({ keepActive = true } = {}) {
  try {
    const response = await listHistory();
    state.history = Array.isArray(response.items) ? response.items : [];
    if (!keepActive) {
      state.activeRecordId = state.history[0]?.id || null;
    }
    renderHistory();
  } catch (error) {
    elements.historyList.innerHTML = `<p class="history-empty">${t("historyLoadError", { message: error.message })}</p>`;
  }
}

async function fetchAndLoadRecord(recordId, { syncText = true } = {}) {
  const record = await getHistoryItem(recordId);
  if (!syncText) {
    const currentText = elements.ttsText.value;
    loadRecord({ ...record, text: currentText });
    return record;
  }
  loadRecord(record);
  return record;
}

async function pollRecord(recordId, { expectProcessed = false } = {}) {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    const record = await getHistoryItem(recordId);
    state.activeRecord = record;
    state.activeRecordId = record.id;
    loadRecord(record);
    await refreshHistory();

    const baseReady = Boolean(record.base_output_url);
    const processedReady = !expectProcessed || Boolean(record.processed_output_url);
    if (record.status === "completed" && baseReady && processedReady) {
      return record;
    }
    if (record.status === "error") {
      throw new Error(record.error || t("generateError"));
    }
    await sleep(1200);
  }
  throw new Error(t("backgroundTimeout"));
}

async function pollVoiceDownload(taskId) {
  for (let attempt = 0; attempt < 180; attempt += 1) {
    const task = await fetchVoiceDownloadTask(taskId);
    if (task.state === "completed") return task;
    if (task.state === "error") {
      throw new Error(task.error || task.message || t("voiceDownloadError"));
    }
    await sleep(1000);
  }
  throw new Error(t("downloadTimeout"));
}

async function handleGenerate() {
  const text = (elements.ttsText.value || "").trim();
  const voiceId = elements.voiceSelect.value;

  if (!text) {
    showToast(t("enterText"), "error");
    return;
  }
  if (text.length > state.maxTextChars) {
    showToast(t("textTooLong", { limit: state.maxTextChars }), "error");
    return;
  }
  if (!voiceId) {
    showToast(t("chooseVoice"), "error");
    return;
  }

  state.generating = true;
  renderGenerateState();
  setActionState();

  try {
    const started = await generateSpeech({ text, voice_id: voiceId });
    loadRecord(started);
    await refreshHistory();
    const record = await pollRecord(started.id);
    loadRecord(record);
    showToast(t("ttsReady"), "success");
  } catch (error) {
    setStatus(elements.generateStatus, error.message || t("generateError"), "error");
    setBadgeState(elements.generateBadge, t("error"), "error");
    showToast(error.message || t("generateError"), "error");
  } finally {
    state.generating = false;
    renderGenerateState();
    setActionState();
  }
}

async function handleApplySpeed() {
  if (!state.activeRecordId || !state.activeRecord?.base_output_url) {
    showToast(t("baseMissing"), "error");
    return;
  }

  const selectedSpeed = nearestSpeedOption(state.selectedSpeed);
  if (Number(selectedSpeed) === 1) {
    updateSpeedStatus();
    showToast(t("speedOriginal"), "success");
    return;
  }

  const existing = activeProcessedOutput(state.activeRecord, selectedSpeed);
  if (existing?.url) {
    renderResultCard();
    updateSpeedStatus();
    showToast(t("speedSavedStatus", { speed: formatSpeedLabel(selectedSpeed) }), "success");
    return;
  }

  state.processingSpeed = true;
  updateSpeedStatus();
  setActionState();

  try {
    await processSpeed({ id: state.activeRecordId, speed: Number(selectedSpeed) });
    const record = await pollRecord(state.activeRecordId, { expectProcessed: true });
    loadRecord(record);
    setStatus(
      elements.speedStatus,
      t("speedDone", {
        speed: formatSpeedLabel(selectedSpeed),
        duration: formatDuration(activeProcessedOutput(record, selectedSpeed)?.duration_sec || record.duration_sec, state.language),
      }),
      "success",
    );
    showToast(t("speedSaved"), "success");
  } catch (error) {
    setStatus(elements.speedStatus, error.message || t("speedError"), "error");
    showToast(error.message || t("speedError"), "error");
  } finally {
    state.processingSpeed = false;
    updateSpeedStatus();
    setActionState();
  }
}

async function handleDelete(recordId) {
  if (!recordId) return;
  if (!window.confirm(t("recordDeleteConfirm"))) return;

  try {
    await deleteHistoryItem(recordId);
    if (state.activeRecordId === recordId) {
      state.activeRecordId = null;
      state.activeRecord = null;
      loadRecord(null);
    }
    await refreshHistory();
    showToast(t("recordDeleted"), "success");
  } catch (error) {
    showToast(error.message || t("recordOpenError"), "error");
  }
}

async function handleVoicePreview({ voiceId = null, voiceKey = null, label = "voice" } = {}) {
  state.previewBusy = true;
  setActionState();
  setStatus(elements.previewStatus, t("previewCreating"), "warning");

  try {
    revokePreviewUrl();
    const blob = await previewVoice({
      voice_id: voiceId,
      voice_key: voiceKey,
      text: previewTextCandidate(),
    });
    const objectUrl = URL.createObjectURL(blob);
    state.previewObjectUrl = objectUrl;
    elements.voicePreviewPlayer.src = objectUrl;
    applyPlayerRate(elements.voicePreviewPlayer, Number(state.selectedSpeed) || 1);
    elements.voicePreviewPlayer.load();
    try {
      await elements.voicePreviewPlayer.play();
    } catch {
      // autoplay can be blocked
    }
    setStatus(elements.previewStatus, t("previewReady", { label }), "success");
  } catch (error) {
    setStatus(elements.previewStatus, error.message || t("previewError"), "error");
    showToast(error.message || t("previewError"), "error");
  } finally {
    state.previewBusy = false;
    setActionState();
  }
}

async function handleVoiceDownload(voiceKey) {
  if (!voiceKey) return;

  state.downloadingVoiceKey = voiceKey;
  setBadgeState(elements.voiceLibraryBadge, t("downloading"), "busy");
  setStatus(elements.voiceLibraryStatus, t("voiceDownloading", { voiceKey }), "warning");
  renderVoiceLibraryList();
  setActionState();

  try {
    const task = await downloadVoice({ voice_key: voiceKey });
    const completed = task.state === "completed" ? task : await pollVoiceDownload(task.id);

    await Promise.all([refreshHealth(), refreshVoices(), refreshVoiceLibrary(true)]);

    if (Array.isArray(completed.installed_voice_ids) && completed.installed_voice_ids.length) {
      elements.voiceSelect.value = completed.installed_voice_ids[0];
      setSavedVoice(completed.installed_voice_ids[0]);
      renderVoiceInfo();
    }

    setStatus(elements.voiceLibraryStatus, t("voiceDownloadedStatus", { voiceKey }), "success");
    showToast(t("voiceDownloadedToast", { voiceKey }), "success");
  } catch (error) {
    setStatus(elements.voiceLibraryStatus, error.message || t("voiceDownloadError"), "error");
    showToast(error.message || t("voiceDownloadError"), "error");
  } finally {
    state.downloadingVoiceKey = null;
    renderVoiceLibraryList();
    setActionState();
  }
}

function handleUseVoice(voiceKey) {
  const item = state.voiceLibrary.find((entry) => entry.key === voiceKey);
  const localVoiceId = item?.installed_voice_ids?.[0];
  if (!localVoiceId) {
    showToast(t("voiceNotDownloaded"), "error");
    return;
  }

  elements.voiceSelect.value = localVoiceId;
  setSavedVoice(localVoiceId);
  renderVoiceInfo();
  setActionState();
  showToast(t("voiceSelectedToast", { label: item?.name || voiceKey }), "success");
}

async function handleVoiceDelete(voiceKey) {
  if (!voiceKey) return;
  const item = state.voiceLibrary.find((entry) => entry.key === voiceKey);
  const label = item?.name || voiceKey;
  if (!window.confirm(t("voiceDeleteConfirm", { label }))) return;

  state.deletingVoiceKey = voiceKey;
  renderVoiceLibraryList();
  setActionState();

  try {
    await deleteVoice(voiceKey);
    await Promise.all([refreshHealth(), refreshVoices(), refreshVoiceLibrary(true)]);
    setStatus(elements.voiceLibraryStatus, t("voiceDeletedStatus", { label }), "success");
    showToast(t("voiceDeletedToast", { label }), "success");
  } catch (error) {
    setStatus(elements.voiceLibraryStatus, error.message || t("voiceDeleteError"), "error");
    showToast(error.message || t("voiceDeleteError"), "error");
  } finally {
    state.deletingVoiceKey = null;
    renderVoiceLibraryList();
    setActionState();
  }
}

function bindEvents() {
  elements.btnThemeDark?.addEventListener("click", () => applyTheme("dark"));
  elements.btnThemeLight?.addEventListener("click", () => applyTheme("light"));

  for (const flag of elements.langFlags) {
    flag.addEventListener("click", () => {
      const language = flag.dataset.lang;
      if (!language) return;
      applyLanguage(language);
    });
  }

  elements.btnVoiceSettings?.addEventListener("click", toggleVoiceSettings);
  elements.btnCloseVoiceSettings?.addEventListener("click", () => setVoiceSettingsOpen(false));

  elements.ttsText.addEventListener("input", updateCounter);

  elements.btnClearText.addEventListener("click", () => {
    elements.ttsText.value = "";
    updateCounter();
    showToast(t("clearToast"));
  });

  elements.voiceSelect.addEventListener("change", () => {
    setSavedVoice(elements.voiceSelect.value || "");
    renderVoiceInfo();
    setActionState();
  });

  elements.btnPreviewSelected.addEventListener("click", async () => {
    const voice = currentVoice();
    if (!voice) {
      showToast(t("voicePreviewNeedsSelection"), "error");
      return;
    }
    await handleVoicePreview({ voiceId: voice.id, label: voice.name });
  });

  elements.btnRefreshVoiceLibrary.addEventListener("click", () => refreshVoiceLibrary(true));
  elements.voiceLibrarySearch.addEventListener("input", (event) => {
    state.voiceLibraryQuery = event.target.value || "";
    renderVoiceLibraryList();
  });

  elements.btnGenerate.addEventListener("click", handleGenerate);
  elements.btnApplySpeed.addEventListener("click", handleApplySpeed);
  elements.btnRefreshHistory.addEventListener("click", () => refreshHistory());

  elements.speedOptions.addEventListener("click", (event) => {
    const button = event.target.closest("[data-speed]");
    if (!button) return;
    selectSpeed(Number(button.dataset.speed));
  });

  elements.voiceLibraryList.addEventListener("click", async (event) => {
    const useButton = event.target.closest('[data-action="use-voice"]');
    if (useButton) {
      handleUseVoice(useButton.dataset.voiceKey || "");
      return;
    }

    const downloadButton = event.target.closest('[data-action="download"]');
    if (downloadButton) {
      await handleVoiceDownload(downloadButton.dataset.voiceKey || "");
      return;
    }

    const deleteButton = event.target.closest('[data-action="delete-voice"]');
    if (deleteButton) {
      await handleVoiceDelete(deleteButton.dataset.voiceKey || "");
      return;
    }

    const previewButton = event.target.closest('[data-action="preview-library"]');
    if (previewButton) {
      const voiceKey = previewButton.dataset.voiceKey || "";
      const item = state.voiceLibrary.find((entry) => entry.key === voiceKey);
      await handleVoicePreview({ voiceKey, label: item?.name || voiceKey });
    }
  });

  elements.historyList.addEventListener("click", async (event) => {
    const deleteButton = event.target.closest('[data-action="delete"]');
    if (deleteButton) {
      await handleDelete(deleteButton.dataset.id || "");
      return;
    }

    const openButton = event.target.closest('[data-action="open"]');
    if (!openButton) return;
    try {
      await fetchAndLoadRecord(openButton.dataset.id || "");
    } catch (error) {
      showToast(error.message || t("recordOpenError"), "error");
    }
  });

  document.addEventListener("click", (event) => {
    if (!state.voiceSettingsOpen) return;
    const target = event.target;
    if (!(target instanceof Node)) return;
    if (elements.voiceSettingsPanel?.contains(target) || elements.btnVoiceSettings?.contains(target)) return;
    setVoiceSettingsOpen(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.voiceSettingsOpen) {
      setVoiceSettingsOpen(false);
    }
  });
}

async function init() {
  bindEvents();
  applyTheme(state.theme);
  applyLanguage(state.language, { persist: false });
  updateCounter();
  renderSpeedOptions();
  setVoiceSettingsOpen(false);
  setActionState();

  await refreshHealth();
  await refreshVoices();
  await refreshVoiceLibrary();
  await refreshHistory();

  if (state.history.length) {
    try {
      await fetchAndLoadRecord(state.history[0].id, { syncText: false });
    } catch {
      // ignore initial history load failure
    }
  } else {
    loadRecord(null);
  }
}

window.addEventListener("beforeunload", () => {
  revokePreviewUrl();
});

init().catch((error) => {
  setStatus(elements.healthStatus, error.message || t("healthFail", { message: t("unknown") }), "error");
});
