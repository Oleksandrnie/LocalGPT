import {
  createTranscript,
  deleteTranscript,
  fetchWhisperModelPrepare,
  fetchHealth,
  fetchWhisperModels,
  getTranscript,
  listTranscripts,
  shutdownRuntime,
  startWhisperModelPrepare,
  transcribeFile,
  updateTranscript,
} from "./api.js";
import { renderHistoryList } from "./history.js";
import { VoiceRecorder } from "./recorder.js";
import { getSavedLanguage, getSavedModel, setSavedLanguage, setSavedModel } from "./storage.js";
import { formatDateTime, setStatus } from "./ui.js";

const I18N = {
  ru: {
    appTitle: "LocalGPT Whisper Transcriber",
    serverChecking: "Проверка сервера...",
    serverOk: "Сервер OK • модель: {model}",
    serverDown: "Сервер недоступен: {error}",
    controlTitle: "Управление",
    modelLabel: "Модель Whisper",
    chooseFile: "Выбрать файл",
    localFileNone: "Локальный файл: не выбран",
    localFilePicked: "Локальный файл: {name} ({size})",
    saveRecording: "Сохранить запись",
    recordButtonTitle: "Запись голоса",
    recordingNotStarted: "Запись не начата.",
    recordingInProgress: "Идет запись...",
    recordingReady: "Запись готова ({duration} сек, {mime})",
    recordingTooShort: "Слишком короткая запись",
    unknownMime: "unknown",
    voiceIdle: "Голос: —",
    voiceYes: "Голос: есть",
    voiceNo: "Голос: нет",
    transcriptTitle: "Транскрибация",
    historyTitle: "История",
    copy: "copy",
    save: "save",
    clear: "clear",
    stagePrefix: "Этап",
    stageIdle: "Ожидание",
    stagePrepare: "Подготовка модели",
    stageTranscribe: "Транскрибация",
    stageSave: "Сохранение",
    stageStopping: "Остановка сервисов",
    stageDone: "Готово",
    stageError: "Ошибка",
    iosShortcutTitle: "Скопировать iOS URL: {url}",
    iosCopied: "iOS URL скопирован в буфер.",
    iosCopyFailed: "Не удалось скопировать iOS URL.",
    runtimeStopTitle: "Остановить backend и Caddy",
    runtimeStopConfirm: "Остановить backend и Caddy сейчас?",
    runtimeStopping: "Остановка сервисов...",
    runtimeStopped: "Сервисы остановлены.",
    runtimeRestartHint: "Откройте LTrnsrb для повторного запуска.",
    runtimeStopFailed: "Не удалось остановить сервисы: {error}",
    outputPlaceholder: "Здесь появится результат транскрибации...",
    historyEmpty: "История пуста.",
    emptyPreview: "(пусто)",
    modalTitleDefault: "Транскрипция",
    modalUpdated: "Обновлено: {date} • {model}",
    close: "Закрыть",
    send: "send",
    delete: "Удалить",
    deleteAria: "Удалить запись",
    confirmDelete: "Удалить эту запись из истории?",
    checkingModel: "Проверка модели...",
    transcribing: "Транскрибация...",
    prepareTimeout: "Превышено время ожидания загрузки модели.",
    doneSymbols: "Готово • {count} символов",
    errorGeneric: "Ошибка: {error}",
    enterText: "Введите текст перед сохранением.",
    savedToHistory: "Текст сохранен в историю.",
    saveError: "Ошибка сохранения: {error}",
    cleared: "Поле очищено.",
    copied: "Текст скопирован в буфер.",
    copyError: "Не удалось скопировать текст.",
    openError: "Не удалось открыть транскрипт: {error}",
    historyLoadError: "Ошибка загрузки истории: {error}",
    sentToMain: "Текст отправлен в основное поле.",
    deleted: "Запись удалена.",
    deleteError: "Ошибка удаления: {error}",
    errUnknown: "Неизвестная ошибка.",
    errNetwork: "Нет связи с сервером. Проверьте сеть и перезапустите запрос.",
    errInvalidModel: "Выбрана недопустимая модель Whisper.",
    errEmptyTranscription: "Whisper вернул пустую транскрибацию.",
    errModelPrepareFailed: "Не удалось подготовить модель Whisper.",
    errAudioFileMissing: "Временный файл транскрибации не найден.",
    errTranscriptionFailed: "Транскрибация завершилась ошибкой.",
    errTranscriptNotFound: "Транскрипт не найден.",
    errEmptyText: "Текст обязателен.",
    errEmptyPatch: "Нет данных для обновления.",
    errTaskNotFound: "Задача подготовки модели не найдена.",
    errInvalidHFToken: "HF_TOKEN содержит недопустимые символы.",
    errDownloadDns: "Ошибка DNS при загрузке модели.",
    errDownloadTimeout: "Превышен тайм-аут загрузки модели.",
    errDownloadModelNotFound: "Репозиторий модели не найден.",
    errDownloadAuthRequired: "Нет доступа к модели. Нужен HF_TOKEN или fallback endpoint.",
    errDownloadAuthFailed: "Нет доступа к модели даже с HF_TOKEN.",
    errDownloadHttp: "HTTP ошибка при загрузке модели.",
    errDownloadIncomplete: "Модель загружена не полностью.",
    errDownloadEmptyList: "Сервер вернул пустой список файлов модели.",
    errRecorderUnsupported: "Браузер не поддерживает запись голоса.",
    errRecorderFailed: "Ошибка записи голоса.",
    errMicPermissionDenied: "Доступ к микрофону запрещен.",
    errMicNotFound: "Микрофон не найден.",
    errMicUnavailable: "Микрофон занят другим приложением.",
    errMicAccessFailed: "Не удалось получить доступ к микрофону.",
    downloadModel: "Модель: {model}",
    downloadSpeed: "Скорость: {speed}",
    downloadPreparing: "Подготовка...",
  },
  uk: {
    appTitle: "LocalGPT Whisper Transcriber",
    serverChecking: "Перевірка сервера...",
    serverOk: "Сервер OK • модель: {model}",
    serverDown: "Сервер недоступний: {error}",
    controlTitle: "Керування",
    modelLabel: "Модель Whisper",
    chooseFile: "Вибрати файл",
    localFileNone: "Локальний файл: не вибрано",
    localFilePicked: "Локальний файл: {name} ({size})",
    saveRecording: "Зберегти запис",
    recordButtonTitle: "Запис голосу",
    recordingNotStarted: "Запис не розпочато.",
    recordingInProgress: "Триває запис...",
    recordingReady: "Запис готовий ({duration} сек, {mime})",
    recordingTooShort: "Занадто короткий запис",
    unknownMime: "unknown",
    voiceIdle: "Голос: —",
    voiceYes: "Голос: є",
    voiceNo: "Голос: немає",
    transcriptTitle: "Транскрибація",
    historyTitle: "Історія",
    copy: "copy",
    save: "save",
    clear: "clear",
    stagePrefix: "Етап",
    stageIdle: "Очікування",
    stagePrepare: "Підготовка моделі",
    stageTranscribe: "Транскрибація",
    stageSave: "Збереження",
    stageStopping: "Зупинка сервісів",
    stageDone: "Готово",
    stageError: "Помилка",
    iosShortcutTitle: "Скопіювати iOS URL: {url}",
    iosCopied: "iOS URL скопійовано в буфер.",
    iosCopyFailed: "Не вдалося скопіювати iOS URL.",
    runtimeStopTitle: "Зупинити backend та Caddy",
    runtimeStopConfirm: "Зупинити backend та Caddy зараз?",
    runtimeStopping: "Зупинка сервісів...",
    runtimeStopped: "Сервіси зупинено.",
    runtimeRestartHint: "Відкрийте LTrnsrb для повторного запуску.",
    runtimeStopFailed: "Не вдалося зупинити сервіси: {error}",
    outputPlaceholder: "Тут з'явиться результат транскрибації...",
    historyEmpty: "Історія порожня.",
    emptyPreview: "(порожньо)",
    modalTitleDefault: "Транскрипція",
    modalUpdated: "Оновлено: {date} • {model}",
    close: "Закрити",
    send: "send",
    delete: "Видалити",
    deleteAria: "Видалити запис",
    confirmDelete: "Видалити цей запис з історії?",
    checkingModel: "Перевірка моделі...",
    transcribing: "Транскрибація...",
    prepareTimeout: "Перевищено час очікування завантаження моделі.",
    doneSymbols: "Готово • {count} символів",
    errorGeneric: "Помилка: {error}",
    enterText: "Введіть текст перед збереженням.",
    savedToHistory: "Текст збережено в історію.",
    saveError: "Помилка збереження: {error}",
    cleared: "Поле очищено.",
    copied: "Текст скопійовано в буфер.",
    copyError: "Не вдалося скопіювати текст.",
    openError: "Не вдалося відкрити транскрипт: {error}",
    historyLoadError: "Помилка завантаження історії: {error}",
    sentToMain: "Текст відправлено в основне поле.",
    deleted: "Запис видалено.",
    deleteError: "Помилка видалення: {error}",
    errUnknown: "Невідома помилка.",
    errNetwork: "Немає зв'язку із сервером. Перевірте мережу та повторіть запит.",
    errInvalidModel: "Вибрано недопустиму модель Whisper.",
    errEmptyTranscription: "Whisper повернув порожню транскрипцію.",
    errModelPrepareFailed: "Не вдалося підготувати модель Whisper.",
    errAudioFileMissing: "Тимчасовий файл транскрипції не знайдено.",
    errTranscriptionFailed: "Транскрибація завершилася з помилкою.",
    errTranscriptNotFound: "Транскрипт не знайдено.",
    errEmptyText: "Текст обов'язковий.",
    errEmptyPatch: "Немає даних для оновлення.",
    errTaskNotFound: "Задачу підготовки моделі не знайдено.",
    errInvalidHFToken: "HF_TOKEN містить недопустимі символи.",
    errDownloadDns: "DNS помилка під час завантаження моделі.",
    errDownloadTimeout: "Перевищено тайм-аут завантаження моделі.",
    errDownloadModelNotFound: "Репозиторій моделі не знайдено.",
    errDownloadAuthRequired: "Немає доступу до моделі. Потрібен HF_TOKEN або fallback endpoint.",
    errDownloadAuthFailed: "Немає доступу до моделі навіть з HF_TOKEN.",
    errDownloadHttp: "HTTP помилка під час завантаження моделі.",
    errDownloadIncomplete: "Модель завантажено не повністю.",
    errDownloadEmptyList: "Сервер повернув порожній список файлів моделі.",
    errRecorderUnsupported: "Браузер не підтримує запис голосу.",
    errRecorderFailed: "Помилка запису голосу.",
    errMicPermissionDenied: "Доступ до мікрофона заборонено.",
    errMicNotFound: "Мікрофон не знайдено.",
    errMicUnavailable: "Мікрофон зайнятий іншим застосунком.",
    errMicAccessFailed: "Не вдалося отримати доступ до мікрофона.",
    downloadModel: "Модель: {model}",
    downloadSpeed: "Швидкість: {speed}",
    downloadPreparing: "Підготовка...",
  },
  en: {
    appTitle: "LocalGPT Whisper Transcriber",
    serverChecking: "Checking server...",
    serverOk: "Server OK • model: {model}",
    serverDown: "Server unavailable: {error}",
    controlTitle: "Controls",
    modelLabel: "Whisper Model",
    chooseFile: "Choose file",
    localFileNone: "Local file: not selected",
    localFilePicked: "Local file: {name} ({size})",
    saveRecording: "Save recording",
    recordButtonTitle: "Voice recording",
    recordingNotStarted: "Recording not started.",
    recordingInProgress: "Recording...",
    recordingReady: "Recording ready ({duration} sec, {mime})",
    recordingTooShort: "Recording is too short",
    unknownMime: "unknown",
    voiceIdle: "Voice: —",
    voiceYes: "Voice: detected",
    voiceNo: "Voice: none",
    transcriptTitle: "Transcription",
    historyTitle: "History",
    copy: "copy",
    save: "save",
    clear: "clear",
    stagePrefix: "Stage",
    stageIdle: "Idle",
    stagePrepare: "Preparing model",
    stageTranscribe: "Transcribing",
    stageSave: "Saving result",
    stageStopping: "Stopping services",
    stageDone: "Done",
    stageError: "Error",
    iosShortcutTitle: "Copy iOS URL: {url}",
    iosCopied: "iOS URL copied to clipboard.",
    iosCopyFailed: "Failed to copy iOS URL.",
    runtimeStopTitle: "Stop backend and Caddy",
    runtimeStopConfirm: "Stop backend and Caddy now?",
    runtimeStopping: "Stopping services...",
    runtimeStopped: "Services stopped.",
    runtimeRestartHint: "Open LTrnsrb to start them again.",
    runtimeStopFailed: "Failed to stop services: {error}",
    outputPlaceholder: "Transcription result will appear here...",
    historyEmpty: "History is empty.",
    emptyPreview: "(empty)",
    modalTitleDefault: "Transcription",
    modalUpdated: "Updated: {date} • {model}",
    close: "Close",
    send: "send",
    delete: "Delete",
    deleteAria: "Delete record",
    confirmDelete: "Delete this transcript from history?",
    checkingModel: "Checking model...",
    transcribing: "Transcribing...",
    prepareTimeout: "Model download wait timeout exceeded.",
    doneSymbols: "Done • {count} chars",
    errorGeneric: "Error: {error}",
    enterText: "Enter text before saving.",
    savedToHistory: "Text saved to history.",
    saveError: "Save error: {error}",
    cleared: "Field cleared.",
    copied: "Text copied to clipboard.",
    copyError: "Failed to copy text.",
    openError: "Unable to open transcript: {error}",
    historyLoadError: "History load error: {error}",
    sentToMain: "Text sent to main field.",
    deleted: "Record deleted.",
    deleteError: "Delete error: {error}",
    errUnknown: "Unknown error.",
    errNetwork: "Server connection failed. Check your network and try again.",
    errInvalidModel: "Invalid Whisper model selected.",
    errEmptyTranscription: "Whisper returned an empty transcription.",
    errModelPrepareFailed: "Failed to prepare Whisper model.",
    errAudioFileMissing: "Temporary transcription file was not found.",
    errTranscriptionFailed: "Transcription failed.",
    errTranscriptNotFound: "Transcript was not found.",
    errEmptyText: "Text is required.",
    errEmptyPatch: "No data provided for update.",
    errTaskNotFound: "Model preparation task was not found.",
    errInvalidHFToken: "HF_TOKEN contains invalid characters.",
    errDownloadDns: "DNS error while downloading model.",
    errDownloadTimeout: "Model download timed out.",
    errDownloadModelNotFound: "Model repository was not found.",
    errDownloadAuthRequired: "Model access denied. Add HF_TOKEN or fallback endpoint.",
    errDownloadAuthFailed: "Model access denied even with HF_TOKEN.",
    errDownloadHttp: "HTTP error while downloading model.",
    errDownloadIncomplete: "Model download is incomplete.",
    errDownloadEmptyList: "Server returned an empty model file list.",
    errRecorderUnsupported: "Browser does not support voice recording.",
    errRecorderFailed: "Voice recording error.",
    errMicPermissionDenied: "Microphone permission denied.",
    errMicNotFound: "No microphone found.",
    errMicUnavailable: "Microphone is busy in another app.",
    errMicAccessFailed: "Failed to access microphone.",
    downloadModel: "Model: {model}",
    downloadSpeed: "Speed: {speed}",
    downloadPreparing: "Preparing...",
  },
};

const elements = {
  appTitle: document.getElementById("appTitle"),
  healthStatus: document.getElementById("healthStatus"),
  controlTitle: document.getElementById("controlTitle"),
  modelLabel: document.getElementById("modelLabel"),
  modelSelect: document.getElementById("modelSelect"),
  fileInput: document.getElementById("fileInput"),
  btnChooseFile: document.getElementById("btnChooseFile"),
  fileHint: document.getElementById("fileHint"),
  btnRecord: document.getElementById("btnRecord"),
  btnSaveRecording: document.getElementById("btnSaveRecording"),
  recordingInfo: document.getElementById("recordingInfo"),
  voiceActivity: document.getElementById("voiceActivity"),
  transcribeStatus: document.getElementById("transcribeStatus"),
  stageWidget: document.getElementById("stageWidget"),
  stageLabel: document.getElementById("stageLabel"),
  stagePercent: document.getElementById("stagePercent"),
  stageProgress: document.getElementById("stageProgress"),
  stageDetail: document.getElementById("stageDetail"),
  downloadWidget: document.getElementById("downloadWidget"),
  downloadModelName: document.getElementById("downloadModelName"),
  downloadPercent: document.getElementById("downloadPercent"),
  downloadProgress: document.getElementById("downloadProgress"),
  downloadSpeed: document.getElementById("downloadSpeed"),
  downloadMessage: document.getElementById("downloadMessage"),
  transcriptTitle: document.getElementById("transcriptTitle"),
  transcriptOutput: document.getElementById("transcriptOutput"),
  btnCopy: document.getElementById("btnCopy"),
  btnSave: document.getElementById("btnSave"),
  btnClear: document.getElementById("btnClear"),
  historyTitle: document.getElementById("historyTitle"),
  historyList: document.getElementById("historyList"),
  historyModal: document.getElementById("historyModal"),
  historyModalTitle: document.getElementById("historyModalTitle"),
  historyModalMeta: document.getElementById("historyModalMeta"),
  historyModalText: document.getElementById("historyModalText"),
  btnCloseModal: document.getElementById("btnCloseModal"),
  btnSendFromModal: document.getElementById("btnSendFromModal"),
  btnDeleteFromModal: document.getElementById("btnDeleteFromModal"),
  iosQuickLink: document.getElementById("iosQuickLink"),
  iosQuickLinkText: document.getElementById("iosQuickLinkText"),
  btnRuntimeStop: document.getElementById("btnRuntimeStop"),
  appToast: document.getElementById("appToast"),
  langFlags: Array.from(document.querySelectorAll(".lang-flag")),
};

const state = {
  activeTranscriptId: null,
  modalTranscriptId: null,
  modalTranscript: null,
  history: [],
  busy: false,
  lastRecordingFile: null,
  selectedUploadFile: null,
  modelPrepareTaskId: null,
  currentDownloadTask: null,
  serverHealthy: false,
  lastHealthError: null,
  iosUrl: null,
  runtimeStopping: false,
  liveStage: {
    visible: false,
    key: "stageIdle",
    percent: 0,
    detail: "",
    tone: "info",
  },
  language: "ru",
};

let recorder = null;
let toastTimer = null;

function formatText(template, params = {}) {
  return String(template || "").replace(/\{(\w+)\}/g, (_, key) => {
    if (params[key] === null || params[key] === undefined) return "";
    return String(params[key]);
  });
}

function t(key, params = {}) {
  const dict = I18N[state.language] || I18N.ru;
  const template = dict[key] ?? I18N.ru[key] ?? key;
  return formatText(template, params);
}

const ERROR_TEXT_KEY_BY_CODE = {
  invalid_model: "errInvalidModel",
  empty_transcription: "errEmptyTranscription",
  model_prepare_failed: "errModelPrepareFailed",
  audio_file_missing: "errAudioFileMissing",
  transcription_failed: "errTranscriptionFailed",
  transcript_not_found: "errTranscriptNotFound",
  empty_text: "errEmptyText",
  empty_patch: "errEmptyPatch",
  task_not_found: "errTaskNotFound",
  invalid_hf_token: "errInvalidHFToken",
  download_dns_error: "errDownloadDns",
  download_timeout: "errDownloadTimeout",
  download_model_not_found: "errDownloadModelNotFound",
  download_auth_required: "errDownloadAuthRequired",
  download_auth_failed: "errDownloadAuthFailed",
  download_http_error: "errDownloadHttp",
  download_incomplete_model: "errDownloadIncomplete",
  download_empty_file_list: "errDownloadEmptyList",
  recorder_unsupported: "errRecorderUnsupported",
  recorder_failed: "errRecorderFailed",
  mic_permission_denied: "errMicPermissionDenied",
  mic_not_found: "errMicNotFound",
  mic_unavailable: "errMicUnavailable",
  mic_access_failed: "errMicAccessFailed",
  prepare_timeout: "prepareTimeout",
};

function localizeError(errorLike) {
  const code = (errorLike && typeof errorLike === "object" && (errorLike.code || errorLike.error_code))
    ? String(errorLike.code || errorLike.error_code)
    : "";

  const key = ERROR_TEXT_KEY_BY_CODE[code];
  if (key) {
    return t(key);
  }

  const message = typeof errorLike === "string"
    ? errorLike
    : String(errorLike?.message || "");

  if (!message) {
    return t("errUnknown");
  }

  const normalized = message.trim();
  if (!normalized) {
    return t("errUnknown");
  }

  if (normalized === "prepare_timeout") {
    return t("prepareTimeout");
  }

  if (
    normalized === "Failed to fetch"
    || normalized === "Load failed"
    || /networkerror/i.test(normalized)
    || /network request failed/i.test(normalized)
  ) {
    return t("errNetwork");
  }

  return normalized;
}

function setBusy(value) {
  state.busy = value;
  elements.btnChooseFile.disabled = value;
  elements.modelSelect.disabled = value;
  elements.btnRecord.disabled = value;
}

function setTranscribeStatus(message, tone = "info") {
  setStatus(elements.transcribeStatus, message, tone);
}

function renderLiveStage() {
  if (!elements.stageWidget || !elements.stageLabel || !elements.stagePercent || !elements.stageProgress || !elements.stageDetail) {
    return;
  }

  const stage = state.liveStage || { visible: false };
  elements.stageWidget.hidden = !stage.visible;
  elements.stageWidget.classList.remove("stage-widget--success", "stage-widget--warning", "stage-widget--error");
  if (!stage.visible) return;

  if (stage.tone === "success") {
    elements.stageWidget.classList.add("stage-widget--success");
  } else if (stage.tone === "warning") {
    elements.stageWidget.classList.add("stage-widget--warning");
  } else if (stage.tone === "error") {
    elements.stageWidget.classList.add("stage-widget--error");
  }

  const percent = Math.max(0, Math.min(100, Number(stage.percent || 0)));
  elements.stageLabel.textContent = `${t("stagePrefix")}: ${t(stage.key || "stageIdle")}`;
  elements.stagePercent.textContent = `${Math.round(percent)}%`;
  elements.stageProgress.value = percent;
  elements.stageDetail.textContent = stage.detail || "";
}

function setLiveStage({
  key = "stageIdle",
  percent = 0,
  detail = "",
  tone = "info",
  visible = true,
} = {}) {
  state.liveStage = {
    visible: Boolean(visible),
    key,
    percent: Math.max(0, Math.min(100, Number(percent || 0))),
    detail: String(detail || ""),
    tone,
  };
  renderLiveStage();
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function formatSpeed(speedBps) {
  const value = Number(speedBps || 0);
  if (!Number.isFinite(value) || value <= 0) {
    return "0 MB/s";
  }
  const mbps = value / (1024 * 1024);
  return `${mbps.toFixed(mbps >= 10 ? 1 : 2)} MB/s`;
}

function formatFileSize(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) {
    return "0 B";
  }
  if (value < 1024) return `${value.toFixed(0)} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function sanitizeUrl(rawUrl) {
  if (!rawUrl) return null;
  try {
    const parsed = new URL(String(rawUrl));
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

function fallbackIosUrlFromLocation() {
  const host = (window.location.hostname || "").trim().toLowerCase();
  if (!host || host === "localhost" || host === "127.0.0.1" || host === "::1") {
    return null;
  }

  const url = new URL(window.location.href);
  url.protocol = "https:";
  url.pathname = "/ui/gui_html.html";
  url.search = "";
  url.hash = "";

  if (!url.port || url.port === "8000") {
    url.port = "8443";
  }

  return url.toString();
}

function showToast(message, durationMs = 2200) {
  if (!elements.appToast) return;

  elements.appToast.textContent = message || "";
  elements.appToast.hidden = !message;

  if (toastTimer) {
    window.clearTimeout(toastTimer);
    toastTimer = null;
  }

  if (!message) return;
  toastTimer = window.setTimeout(() => {
    elements.appToast.hidden = true;
    toastTimer = null;
  }, durationMs);
}

async function copyText(text) {
  const value = String(text || "");
  if (!value) return false;

  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    const area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "readonly");
    area.style.position = "fixed";
    area.style.opacity = "0";
    area.style.pointerEvents = "none";
    document.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, area.value.length);
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  }
}

function currentModel() {
  return (elements.modelSelect.value || "small").trim();
}

function setFileHint(file) {
  state.selectedUploadFile = file || null;
  if (!elements.fileHint) return;

  if (!file) {
    elements.fileHint.textContent = t("localFileNone");
    elements.fileHint.classList.add("file-hint--empty");
    elements.fileHint.classList.remove("file-hint--ready");
    return;
  }

  elements.fileHint.textContent = t("localFilePicked", {
    name: file.name,
    size: formatFileSize(file.size),
  });
  elements.fileHint.classList.add("file-hint--ready");
  elements.fileHint.classList.remove("file-hint--empty");
}

function applyVoiceLabel() {
  if (!elements.voiceActivity) return;
  if (elements.voiceActivity.classList.contains("voice-activity--active")) {
    elements.voiceActivity.textContent = t("voiceYes");
    return;
  }
  if (elements.voiceActivity.classList.contains("voice-activity--silent")) {
    elements.voiceActivity.textContent = t("voiceNo");
    return;
  }
  elements.voiceActivity.textContent = t("voiceIdle");
}

function renderIosQuickLink() {
  if (!elements.iosQuickLink || !elements.iosQuickLinkText) return;

  const resolvedUrl = sanitizeUrl(state.iosUrl) || sanitizeUrl(fallbackIosUrlFromLocation());
  if (!resolvedUrl) {
    delete elements.iosQuickLink.dataset.url;
    elements.iosQuickLink.hidden = true;
    return;
  }

  elements.iosQuickLink.hidden = false;
  elements.iosQuickLink.dataset.url = resolvedUrl;
  elements.iosQuickLinkText.textContent = resolvedUrl;

  const title = t("iosShortcutTitle", { url: resolvedUrl });
  elements.iosQuickLink.title = title;
  elements.iosQuickLink.setAttribute("aria-label", title);
}

function applyStaticTexts() {
  elements.appTitle.textContent = t("appTitle");
  elements.controlTitle.textContent = t("controlTitle");
  elements.modelLabel.textContent = t("modelLabel");
  elements.btnChooseFile.textContent = t("chooseFile");
  elements.btnSaveRecording.textContent = t("saveRecording");
  elements.btnRecord.title = t("recordButtonTitle");
  elements.transcriptTitle.textContent = t("transcriptTitle");
  elements.btnCopy.textContent = t("copy");
  elements.btnSave.textContent = t("save");
  elements.btnClear.textContent = t("clear");
  elements.transcriptOutput.placeholder = t("outputPlaceholder");
  elements.historyTitle.textContent = t("historyTitle");
  elements.btnCloseModal.textContent = t("close");
  elements.btnSendFromModal.textContent = t("send");
  elements.btnDeleteFromModal.textContent = t("delete");
  if (elements.btnRuntimeStop) {
    elements.btnRuntimeStop.title = t("runtimeStopTitle");
    elements.btnRuntimeStop.setAttribute("aria-label", t("runtimeStopTitle"));
  }

  if (!state.lastRecordingFile && !recorder?.isRecording) {
    elements.recordingInfo.textContent = t("recordingNotStarted");
  }

  applyVoiceLabel();
  setFileHint(state.selectedUploadFile);

  if (!state.currentDownloadTask) {
    elements.downloadModelName.textContent = t("downloadModel", { model: "—" });
    elements.downloadSpeed.textContent = t("downloadSpeed", { speed: "0 MB/s" });
    elements.downloadMessage.textContent = t("downloadPreparing");
  } else {
    renderDownloadWidget(state.currentDownloadTask);
  }

  if (!state.modalTranscript) {
    elements.historyModalTitle.textContent = t("modalTitleDefault");
  } else {
    renderModalContent(state.modalTranscript);
  }

  renderLiveStage();
  renderIosQuickLink();
}

function setLanguage(language, { persist = true } = {}) {
  const next = I18N[language] ? language : "ru";
  state.language = next;
  document.documentElement.lang = next;
  if (persist) {
    setSavedLanguage(next);
  }

  for (const flag of elements.langFlags) {
    flag.classList.toggle("is-active", flag.dataset.lang === next);
  }

  applyStaticTexts();
  renderHealthStatus();
  renderHistoryList(elements.historyList, state.history, state.activeTranscriptId, { t });
}

function renderDownloadWidget(task) {
  state.currentDownloadTask = task || null;
  if (!task) {
    elements.downloadWidget.hidden = true;
    return;
  }

  elements.downloadWidget.hidden = false;
  elements.downloadModelName.textContent = t("downloadModel", { model: task.model || "—" });
  elements.downloadPercent.textContent = `${Math.max(0, Math.min(100, Number(task.percent || 0))).toFixed(1)}%`;
  elements.downloadProgress.value = Math.max(0, Math.min(100, Number(task.percent || 0)));
  elements.downloadSpeed.textContent = t("downloadSpeed", { speed: formatSpeed(task.speed_bps) });
  if (task.error_code) {
    const localizedError = localizeError({
      code: task.error_code || null,
      message: task.message || "",
    });
    elements.downloadMessage.textContent = localizedError;
    setLiveStage({
      key: "stageError",
      percent: 100,
      detail: localizedError,
      tone: "error",
      visible: true,
    });
    return;
  }
  const downloadMessage = task.message || t("downloadPreparing");
  elements.downloadMessage.textContent = downloadMessage;
  const rawPercent = Math.max(0, Math.min(100, Number(task.percent || 0)));
  const mappedPercent = 8 + rawPercent * 0.52;
  setLiveStage({
    key: "stagePrepare",
    percent: mappedPercent,
    detail: downloadMessage,
    tone: "info",
    visible: true,
  });
}

async function ensureModelReady(model) {
  const started = await startWhisperModelPrepare(model);
  state.modelPrepareTaskId = started.task_id;
  renderDownloadWidget(started);

  if (started.state === "completed") {
    await sleep(250);
    renderDownloadWidget(null);
    return;
  }

  if (started.state === "error") {
    const error = new Error(started.message || "model_prepare_failed");
    error.code = started.error_code || "model_prepare_failed";
    throw error;
  }

  const maxPolls = 3600;
  for (let poll = 0; poll < maxPolls; poll += 1) {
    await sleep(500);
    const current = await fetchWhisperModelPrepare(state.modelPrepareTaskId);
    renderDownloadWidget(current);

    if (current.state === "completed") {
      await sleep(400);
      renderDownloadWidget(null);
      return;
    }

    if (current.state === "error") {
      const error = new Error(current.message || "model_prepare_failed");
      error.code = current.error_code || "model_prepare_failed";
      throw error;
    }
  }

  const timeoutError = new Error("prepare_timeout");
  timeoutError.code = "prepare_timeout";
  throw timeoutError;
}

function renderHealthStatus() {
  if (elements.btnRuntimeStop) {
    elements.btnRuntimeStop.hidden = !state.serverHealthy;
    elements.btnRuntimeStop.disabled = state.runtimeStopping;
  }

  if (state.serverHealthy) {
    setStatus(elements.healthStatus, t("serverOk", { model: currentModel() || "small" }), "success");
    return;
  }

  if (state.lastHealthError) {
    setStatus(elements.healthStatus, t("serverDown", { error: localizeError(state.lastHealthError) }), "error");
    return;
  }

  setStatus(elements.healthStatus, t("serverChecking"));
}

function selectTranscript(record) {
  elements.transcriptOutput.value = record?.text || "";
  state.activeTranscriptId = record?.id || null;
  renderHistoryList(elements.historyList, state.history, state.activeTranscriptId, { t });
}

async function loadHealth() {
  try {
    const health = await fetchHealth();
    state.serverHealthy = true;
    state.lastHealthError = null;
    state.iosUrl = sanitizeUrl(health?.ios_url) || null;
  } catch (error) {
    state.serverHealthy = false;
    state.lastHealthError = error;
    state.iosUrl = sanitizeUrl(fallbackIosUrlFromLocation()) || null;
  }
  renderHealthStatus();
  renderIosQuickLink();
}

async function loadModels() {
  const fallbackModels = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"];

  try {
    const data = await fetchWhisperModels();
    const models = Array.isArray(data?.models) && data.models.length ? data.models : fallbackModels;
    const saved = getSavedModel(data?.default || "small");

    elements.modelSelect.innerHTML = models
      .map((model) => `<option value="${model}">${model}</option>`)
      .join("");

    if (models.includes(saved)) {
      elements.modelSelect.value = saved;
    } else {
      elements.modelSelect.value = data?.default && models.includes(data.default) ? data.default : models[0];
    }
  } catch {
    elements.modelSelect.innerHTML = fallbackModels
      .map((model) => `<option value="${model}">${model}</option>`)
      .join("");
    elements.modelSelect.value = getSavedModel("small");
  }

  setSavedModel(elements.modelSelect.value);
  renderHealthStatus();
}

async function loadHistory({ keepSelection = true } = {}) {
  try {
    const response = await listTranscripts();
    state.history = Array.isArray(response?.items) ? response.items : [];

    if (!keepSelection) {
      state.activeTranscriptId = null;
    }

    if (keepSelection && state.activeTranscriptId) {
      const exists = state.history.some((item) => item.id === state.activeTranscriptId);
      if (!exists) {
        state.activeTranscriptId = null;
      }
    }

    renderHistoryList(elements.historyList, state.history, state.activeTranscriptId, { t });
  } catch (error) {
    setTranscribeStatus(t("historyLoadError", { error: localizeError(error) }), "error");
  }
}

async function runTranscription(file, sourceType) {
  if (!file) return;

  setBusy(true);
  setTranscribeStatus(t("checkingModel"), "info");
  setLiveStage({
    key: "stagePrepare",
    percent: 6,
    detail: t("checkingModel"),
    tone: "info",
    visible: true,
  });

  try {
    await ensureModelReady(currentModel());
    setTranscribeStatus(t("transcribing"), "info");
    setLiveStage({
      key: "stageTranscribe",
      percent: 72,
      detail: t("transcribing"),
      tone: "info",
      visible: true,
    });

    const result = await transcribeFile(file, currentModel(), sourceType);
    selectTranscript(result);
    setLiveStage({
      key: "stageSave",
      percent: 90,
      detail: t("savedToHistory"),
      tone: "info",
      visible: true,
    });
    await loadHistory();

    const symbols = (result?.text || "").length;
    setTranscribeStatus(t("doneSymbols", { count: symbols }), "success");
    setLiveStage({
      key: "stageDone",
      percent: 100,
      detail: t("doneSymbols", { count: symbols }),
      tone: "success",
      visible: true,
    });
  } catch (error) {
    const message = localizeError(error);
    setTranscribeStatus(t("errorGeneric", { error: message }), "error");
    setLiveStage({
      key: "stageError",
      percent: 100,
      detail: message,
      tone: "error",
      visible: true,
    });
  } finally {
    setBusy(false);
  }
}

async function saveTranscriptText() {
  const text = (elements.transcriptOutput.value || "").trim();
  if (!text) {
    setTranscribeStatus(t("enterText"), "warning");
    return;
  }

  try {
    setLiveStage({
      key: "stageSave",
      percent: 88,
      detail: t("stageSave"),
      tone: "info",
      visible: true,
    });
    let saved;
    if (state.activeTranscriptId) {
      saved = await updateTranscript(state.activeTranscriptId, { text });
    } else {
      saved = await createTranscript({
        text,
        source_type: "manual",
        source_name: "manual_edit",
        model: currentModel(),
      });
    }

    state.activeTranscriptId = saved.id;
    await loadHistory();
    setTranscribeStatus(t("savedToHistory"), "success");
    setLiveStage({
      key: "stageDone",
      percent: 100,
      detail: t("savedToHistory"),
      tone: "success",
      visible: true,
    });
  } catch (error) {
    const localizedError = localizeError(error);
    setTranscribeStatus(t("saveError", { error: localizedError }), "error");
    setLiveStage({
      key: "stageError",
      percent: 100,
      detail: localizedError,
      tone: "error",
      visible: true,
    });
  }
}

function clearOutput() {
  elements.transcriptOutput.value = "";
  state.activeTranscriptId = null;
  renderHistoryList(elements.historyList, state.history, null, { t });
  setTranscribeStatus(t("cleared"), "info");
}

async function copyOutput() {
  try {
    await navigator.clipboard.writeText(elements.transcriptOutput.value || "");
    setTranscribeStatus(t("copied"), "success");
  } catch {
    setTranscribeStatus(t("copyError"), "error");
  }
}

function isExpectedShutdownError(errorLike) {
  const raw = String(errorLike?.message || errorLike || "").toLowerCase();
  if (!raw) return false;
  return (
    raw.includes("failed to fetch")
    || raw.includes("load failed")
    || raw.includes("networkerror")
    || raw.includes("network request failed")
    || raw.includes("the network connection was lost")
  );
}

function markRuntimeStoppedUi() {
  state.runtimeStopping = false;
  state.serverHealthy = false;
  const message = `${t("runtimeStopped")} ${t("runtimeRestartHint")}`;
  setStatus(elements.healthStatus, message, "warning");
  setTranscribeStatus(message, "warning");
  setLiveStage({
    key: "stageStopping",
    percent: 100,
    detail: message,
    tone: "warning",
    visible: true,
  });
  if (elements.btnRuntimeStop) {
    elements.btnRuntimeStop.hidden = false;
    elements.btnRuntimeStop.disabled = true;
  }
  showToast(message, 5000);
}

async function stopRuntimeFromUi() {
  if (state.runtimeStopping) return;
  if (!window.confirm(t("runtimeStopConfirm"))) return;

  state.runtimeStopping = true;
  renderHealthStatus();
  setLiveStage({
    key: "stageStopping",
    percent: 100,
    detail: t("runtimeStopping"),
    tone: "warning",
    visible: true,
  });
  showToast(t("runtimeStopping"));

  try {
    await shutdownRuntime();
    markRuntimeStoppedUi();
  } catch (error) {
    if (isExpectedShutdownError(error)) {
      markRuntimeStoppedUi();
      return;
    }

    state.runtimeStopping = false;
    renderHealthStatus();
    setLiveStage({
      key: "stageError",
      percent: 100,
      detail: localizeError(error),
      tone: "error",
      visible: true,
    });
    showToast(t("runtimeStopFailed", { error: localizeError(error) }));
  }
}

function renderModalContent(item) {
  elements.historyModalTitle.textContent = item.source_name || t("modalTitleDefault");
  elements.historyModalMeta.textContent = t("modalUpdated", {
    date: formatDateTime(item.updated_at),
    model: item.model || "—",
  });
  elements.historyModalText.value = item.text || "";
}

async function openHistoryModal(transcriptId) {
  try {
    const item = await getTranscript(transcriptId);
    state.modalTranscriptId = item.id;
    state.modalTranscript = item;
    renderModalContent(item);
    elements.historyModal.hidden = false;
  } catch (error) {
    setTranscribeStatus(t("openError", { error: localizeError(error) }), "error");
  }
}

function closeHistoryModal() {
  elements.historyModal.hidden = true;
  state.modalTranscriptId = null;
  state.modalTranscript = null;
}

function downloadRecordingFile() {
  if (!state.lastRecordingFile) return;

  const url = URL.createObjectURL(state.lastRecordingFile);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = state.lastRecordingFile.name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function deleteTranscriptById(transcriptId) {
  if (!transcriptId) return;

  if (!window.confirm(t("confirmDelete"))) {
    return;
  }

  try {
    await deleteTranscript(transcriptId);

    if (state.activeTranscriptId === transcriptId) {
      elements.transcriptOutput.value = "";
      state.activeTranscriptId = null;
    }

    if (state.modalTranscriptId === transcriptId) {
      closeHistoryModal();
    }

    await loadHistory();
    setTranscribeStatus(t("deleted"), "success");
  } catch (error) {
    setTranscribeStatus(t("deleteError", { error: localizeError(error) }), "error");
  }
}

function initRecorder() {
  recorder = new VoiceRecorder({
    minDurationSeconds: 3,
    onStateChange: ({ isRecording, duration, hasRecording, mimeType }) => {
      elements.btnRecord.classList.toggle("is-recording", Boolean(isRecording));
      if (!isRecording) {
        elements.voiceActivity.classList.remove("voice-activity--active", "voice-activity--silent");
        elements.voiceActivity.classList.add("voice-activity--idle");
        elements.voiceActivity.textContent = t("voiceIdle");
      }
      elements.recordingInfo.textContent = isRecording
        ? t("recordingInProgress")
        : hasRecording
          ? t("recordingReady", { duration: duration.toFixed(1), mime: mimeType || t("unknownMime") })
          : t("recordingNotStarted");
    },
    onTooShort: () => {
      state.lastRecordingFile = null;
      elements.btnSaveRecording.disabled = true;
      elements.recordingInfo.textContent = t("recordingTooShort");
      setTranscribeStatus(t("recordingTooShort"), "warning");
    },
    onError: (errorLike) => {
      state.lastRecordingFile = null;
      elements.btnSaveRecording.disabled = true;
      setTranscribeStatus(t("errorGeneric", { error: localizeError(errorLike) }), "error");
    },
    onVoiceLevel: ({ voiceDetected }) => {
      if (!recorder?.isRecording) return;
      elements.voiceActivity.classList.remove("voice-activity--idle");
      if (voiceDetected) {
        elements.voiceActivity.classList.add("voice-activity--active");
        elements.voiceActivity.classList.remove("voice-activity--silent");
        elements.voiceActivity.textContent = t("voiceYes");
      } else {
        elements.voiceActivity.classList.add("voice-activity--silent");
        elements.voiceActivity.classList.remove("voice-activity--active");
        elements.voiceActivity.textContent = t("voiceNo");
      }
    },
    onReady: async (file) => {
      state.lastRecordingFile = file;
      elements.btnSaveRecording.disabled = false;
      await runTranscription(file, "recording");
    },
  });

  elements.btnRecord.addEventListener("click", () => recorder.toggle());
}

function bindEvents() {
  elements.modelSelect.addEventListener("change", () => {
    setSavedModel(elements.modelSelect.value);
    renderHealthStatus();
  });

  elements.btnChooseFile.addEventListener("click", () => {
    elements.fileInput.click();
  });

  elements.fileInput.addEventListener("change", async () => {
    const file = elements.fileInput.files?.[0];
    elements.fileInput.value = "";
    if (!file) {
      setFileHint(null);
      return;
    }
    setFileHint(file);
    await runTranscription(file, "upload");
  });

  elements.btnSaveRecording.addEventListener("click", () => {
    downloadRecordingFile();
  });

  elements.btnCopy.addEventListener("click", () => copyOutput());
  elements.btnSave.addEventListener("click", () => saveTranscriptText());
  elements.btnClear.addEventListener("click", () => clearOutput());

  elements.historyList.addEventListener("click", (event) => {
    const deleteButton = event.target.closest('[data-action="delete"]');
    if (deleteButton) {
      const transcriptId = deleteButton.dataset.id;
      if (transcriptId) {
        deleteTranscriptById(transcriptId);
      }
      return;
    }

    const openButton = event.target.closest('[data-action="open"]');
    if (!openButton) return;
    const transcriptId = openButton.dataset.id;
    if (!transcriptId) return;
    openHistoryModal(transcriptId);
  });

  elements.btnCloseModal.addEventListener("click", () => closeHistoryModal());
  elements.historyModal.addEventListener("click", (event) => {
    if (event.target === elements.historyModal) {
      closeHistoryModal();
    }
  });

  elements.btnSendFromModal.addEventListener("click", () => {
    elements.transcriptOutput.value = elements.historyModalText.value || "";
    state.activeTranscriptId = state.modalTranscriptId;
    renderHistoryList(elements.historyList, state.history, state.activeTranscriptId, { t });
    closeHistoryModal();
    setTranscribeStatus(t("sentToMain"), "success");
  });

  elements.btnDeleteFromModal.addEventListener("click", () => {
    if (!state.modalTranscriptId) return;
    deleteTranscriptById(state.modalTranscriptId);
  });

  for (const flag of elements.langFlags) {
    flag.addEventListener("click", () => {
      const lang = flag.dataset.lang;
      if (!lang) return;
      setLanguage(lang);
    });
  }

  elements.iosQuickLink?.addEventListener("click", async () => {
    const url = elements.iosQuickLink?.dataset?.url || "";
    if (!url) return;

    const copied = await copyText(url);
    if (copied) {
      showToast(`${t("iosCopied")} ${url}`);
    } else {
      showToast(t("iosCopyFailed"));
    }
  });

  elements.btnRuntimeStop?.addEventListener("click", async () => {
    await stopRuntimeFromUi();
  });
}

async function bootstrap() {
  bindEvents();
  setLanguage(getSavedLanguage("ru"), { persist: false });
  initRecorder();
  await loadModels();
  await loadHealth();
  await loadHistory();
}

bootstrap();
