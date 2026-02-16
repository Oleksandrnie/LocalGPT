import {
  createTranscript,
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
import { getSavedModel, setSavedModel } from "./storage.js";
import { formatDateTime, setStatus } from "./ui.js";

const elements = {
  healthStatus: document.getElementById("healthStatus"),
  modelSelect: document.getElementById("modelSelect"),
  fileInput: document.getElementById("fileInput"),
  btnChooseFile: document.getElementById("btnChooseFile"),
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
  transcriptOutput: document.getElementById("transcriptOutput"),
  btnCopy: document.getElementById("btnCopy"),
  btnSave: document.getElementById("btnSave"),
  btnClear: document.getElementById("btnClear"),
  historyList: document.getElementById("historyList"),
  historyModal: document.getElementById("historyModal"),
  historyModalTitle: document.getElementById("historyModalTitle"),
  historyModalMeta: document.getElementById("historyModalMeta"),
  historyModalText: document.getElementById("historyModalText"),
  btnCloseModal: document.getElementById("btnCloseModal"),
  btnSendFromModal: document.getElementById("btnSendFromModal"),
};

const state = {
  activeTranscriptId: null,
  modalTranscriptId: null,
  history: [],
  busy: false,
  lastRecordingFile: null,
  modelPrepareTaskId: null,
  serverHealthy: false,
};

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

function renderDownloadWidget(task) {
  if (!task) {
    elements.downloadWidget.hidden = true;
    return;
  }

  elements.downloadWidget.hidden = false;
  elements.downloadModelName.textContent = `Модель: ${task.model || "—"}`;
  elements.downloadPercent.textContent = `${Math.max(0, Math.min(100, Number(task.percent || 0))).toFixed(1)}%`;
  elements.downloadProgress.value = Math.max(0, Math.min(100, Number(task.percent || 0)));
  elements.downloadSpeed.textContent = `Скорость: ${formatSpeed(task.speed_bps)}`;
  elements.downloadMessage.textContent = task.message || "Подготовка...";
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
    throw new Error(started.message || "Ошибка загрузки модели");
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
      throw new Error(current.message || "Ошибка загрузки модели");
    }
  }

  throw new Error("Превышено время ожидания загрузки модели");
}

function currentModel() {
  return (elements.modelSelect.value || "small").trim();
}

function renderHealthStatus() {
  if (!state.serverHealthy) return;
  setStatus(elements.healthStatus, `Сервер OK • модель: ${currentModel() || "small"}`, "success");
}

function selectTranscript(record) {
  elements.transcriptOutput.value = record?.text || "";
  state.activeTranscriptId = record?.id || null;
  renderHistoryList(elements.historyList, state.history, state.activeTranscriptId);
}

async function loadHealth() {
  try {
    await fetchHealth();
    state.serverHealthy = true;
    renderHealthStatus();
  } catch (error) {
    state.serverHealthy = false;
    setStatus(elements.healthStatus, `Сервер недоступен: ${error.message || error}`, "error");
  }
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

    renderHistoryList(elements.historyList, state.history, state.activeTranscriptId);
  } catch (error) {
    setTranscribeStatus(`Ошибка загрузки истории: ${error.message || error}`, "error");
  }
}

async function runTranscription(file, sourceType) {
  if (!file) return;

  setBusy(true);
  setTranscribeStatus("Проверка модели...", "info");

  try {
    await ensureModelReady(currentModel());
    setTranscribeStatus("Транскрибация...", "info");

    const result = await transcribeFile(file, currentModel(), sourceType);
    selectTranscript(result);
    await loadHistory();

    const symbols = (result?.text || "").length;
    setTranscribeStatus(`Готово • ${symbols} символов`, "success");
  } catch (error) {
    setTranscribeStatus(`Ошибка: ${error.message || error}`, "error");
  } finally {
    setBusy(false);
  }
}

async function saveTranscriptText() {
  const text = (elements.transcriptOutput.value || "").trim();
  if (!text) {
    setTranscribeStatus("Введите текст перед сохранением.", "warning");
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
    setTranscribeStatus("Текст сохранен в историю.", "success");
  } catch (error) {
    setTranscribeStatus(`Ошибка сохранения: ${error.message || error}`, "error");
  }
}

function clearOutput() {
  elements.transcriptOutput.value = "";
  state.activeTranscriptId = null;
  renderHistoryList(elements.historyList, state.history, null);
  setTranscribeStatus("Поле очищено.", "info");
}

async function copyOutput() {
  try {
    await navigator.clipboard.writeText(elements.transcriptOutput.value || "");
    setTranscribeStatus("Текст скопирован в буфер.", "success");
  } catch {
    setTranscribeStatus("Не удалось скопировать текст.", "error");
  }
}

async function openHistoryModal(transcriptId) {
  try {
    const item = await getTranscript(transcriptId);
    state.modalTranscriptId = item.id;
    elements.historyModalTitle.textContent = item.source_name || "Транскрипция";
    elements.historyModalMeta.textContent = `Обновлено: ${formatDateTime(item.updated_at)} • ${item.model || "—"}`;
    elements.historyModalText.value = item.text || "";
    elements.historyModal.hidden = false;
  } catch (error) {
    setTranscribeStatus(`Не удалось открыть транскрипт: ${error.message || error}`, "error");
  }
}

function closeHistoryModal() {
  elements.historyModal.hidden = true;
  state.modalTranscriptId = null;
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

function initRecorder() {
  const recorder = new VoiceRecorder({
    minDurationSeconds: 3,
    onStateChange: ({ isRecording, duration, hasRecording, mimeType }) => {
      elements.btnRecord.classList.toggle("is-recording", Boolean(isRecording));
      if (!isRecording) {
        elements.voiceActivity.classList.remove("voice-activity--active", "voice-activity--silent");
        elements.voiceActivity.classList.add("voice-activity--idle");
        elements.voiceActivity.textContent = "Голос: —";
      }
      elements.recordingInfo.textContent = isRecording
        ? "Идет запись..."
        : hasRecording
          ? `Запись готова (${duration.toFixed(1)} сек, ${mimeType || "unknown"})`
          : "Запись не начата.";
    },
    onTooShort: () => {
      state.lastRecordingFile = null;
      elements.btnSaveRecording.disabled = true;
      elements.recordingInfo.textContent = "Слишком короткая запись";
      setTranscribeStatus("Слишком короткая запись", "warning");
    },
    onError: (message) => {
      state.lastRecordingFile = null;
      elements.btnSaveRecording.disabled = true;
      setTranscribeStatus(message, "error");
    },
    onVoiceLevel: ({ voiceDetected }) => {
      if (!recorder.isRecording) return;
      elements.voiceActivity.classList.remove("voice-activity--idle");
      if (voiceDetected) {
        elements.voiceActivity.classList.add("voice-activity--active");
        elements.voiceActivity.classList.remove("voice-activity--silent");
        elements.voiceActivity.textContent = "Голос: есть";
      } else {
        elements.voiceActivity.classList.add("voice-activity--silent");
        elements.voiceActivity.classList.remove("voice-activity--active");
        elements.voiceActivity.textContent = "Голос: нет";
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
    if (!file) return;
    await runTranscription(file, "upload");
  });

  elements.btnSaveRecording.addEventListener("click", () => {
    downloadRecordingFile();
  });

  elements.btnCopy.addEventListener("click", () => copyOutput());
  elements.btnSave.addEventListener("click", () => saveTranscriptText());
  elements.btnClear.addEventListener("click", () => clearOutput());

  elements.historyList.addEventListener("click", (event) => {
    const row = event.target.closest("[data-id]");
    if (!row) return;
    const transcriptId = row.dataset.id;
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
    renderHistoryList(elements.historyList, state.history, state.activeTranscriptId);
    closeHistoryModal();
    setTranscribeStatus("Текст отправлен в основное поле.", "success");
  });
}

async function bootstrap() {
  initRecorder();
  bindEvents();
  await loadModels();
  await loadHealth();
  await loadHistory();
}

bootstrap();
