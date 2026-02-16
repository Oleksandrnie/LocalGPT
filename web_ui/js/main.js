import {
  createTranscript,
  deleteTranscript,
  fetchWhisperModelPrepare,
  fetchHealth,
  fetchWhisperModels,
  getTranscript,
  listTranscripts,
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
  lastHealthError: "",
  language: "ru",
};

let recorder = null;

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

function setBusy(value) {
  state.busy = value;
  elements.btnChooseFile.disabled = value;
  elements.modelSelect.disabled = value;
  elements.btnRecord.disabled = value;
}

function setTranscribeStatus(message, tone = "info") {
  setStatus(elements.transcribeStatus, message, tone);
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
  elements.downloadMessage.textContent = task.message || t("downloadPreparing");
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
    throw new Error(started.message || t("errorGeneric", { error: "model_prepare_failed" }));
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
      throw new Error(current.message || t("errorGeneric", { error: "model_prepare_failed" }));
    }
  }

  throw new Error("prepare_timeout");
}

function renderHealthStatus() {
  if (state.serverHealthy) {
    setStatus(elements.healthStatus, t("serverOk", { model: currentModel() || "small" }), "success");
    return;
  }

  if (state.lastHealthError) {
    setStatus(elements.healthStatus, t("serverDown", { error: state.lastHealthError }), "error");
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
    await fetchHealth();
    state.serverHealthy = true;
    state.lastHealthError = "";
  } catch (error) {
    state.serverHealthy = false;
    state.lastHealthError = error.message || String(error);
  }
  renderHealthStatus();
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
    setTranscribeStatus(t("historyLoadError", { error: error.message || error }), "error");
  }
}

async function runTranscription(file, sourceType) {
  if (!file) return;

  setBusy(true);
  setTranscribeStatus(t("checkingModel"), "info");

  try {
    await ensureModelReady(currentModel());
    setTranscribeStatus(t("transcribing"), "info");

    const result = await transcribeFile(file, currentModel(), sourceType);
    selectTranscript(result);
    await loadHistory();

    const symbols = (result?.text || "").length;
    setTranscribeStatus(t("doneSymbols", { count: symbols }), "success");
  } catch (error) {
    const raw = error?.message || String(error);
    const message = raw === "prepare_timeout" ? t("prepareTimeout") : raw;
    setTranscribeStatus(t("errorGeneric", { error: message }), "error");
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
  } catch (error) {
    setTranscribeStatus(t("saveError", { error: error.message || error }), "error");
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
    setTranscribeStatus(t("openError", { error: error.message || error }), "error");
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
    setTranscribeStatus(t("deleteError", { error: error.message || error }), "error");
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
    onError: (message) => {
      state.lastRecordingFile = null;
      elements.btnSaveRecording.disabled = true;
      setTranscribeStatus(t("errorGeneric", { error: message }), "error");
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
