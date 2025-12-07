import {
  API_BASE,
  addHistoryEntry,
  deleteHistoryEntry,
  ensureSessionId,
  getHrPrefix,
  getSavedLlmModel,
  getSavedModel,
  loadHistory,
  loadTranscripts,
  saveHistory,
  saveTranscripts,
  setHrPrefix,
  setSavedLlmModel,
  setSavedModel,
} from "./storage.js";
import { renderRoleLegend, renderTimeline } from "./timeline.js";
import { CriteriaManager } from "./criteria.js";

const DEFAULT_HR_PREFIX = "Нейро-HR";

const LIMITS = { num_ctx: null, max_tokens: null };
const TRANSCRIPT_LIBRARY_LIMIT = 20;
const MODEL_RECOMMENDATIONS = [
  { name: "qwen2.5:3b", label: "Лёгкая (≈3B)" },
  { name: "qwen2.5:7b-instruct", label: "Инструкционная 7B" },
  { name: "qwen2.5-7b-long", label: "Длинный контекст 7B" },
  { name: "llama3:8b", label: "LLaMA 3 8B" },
  { name: "mistral:7b", label: "Mistral 7B" },
];

function estTokens(value) {
  return Math.ceil(((value || "").length) / 4.2);
}

function debounce(fn, ms = 150) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), ms);
  };
}

function updateStatus(node, message, tone = "info") {
  if (!node) return;
  node.textContent = message || "";
  node.classList.remove("status--error", "status--success", "status--warning");
  if (tone === "error") {
    node.classList.add("status--error");
  } else if (tone === "success") {
    node.classList.add("status--success");
  } else if (tone === "warning") {
    node.classList.add("status--warning");
  }
}

class LgptCard extends HTMLElement {
  connectedCallback() {
    if (this.dataset.upgraded) return;
    const title = this.getAttribute("title") || "";
    const wrapper = document.createElement("section");
    wrapper.className = "card";
    if (title) {
      const heading = document.createElement("h3");
      heading.textContent = title;
      wrapper.appendChild(heading);
    }
    const body = document.createElement("div");
    body.className = "card__body";
    while (this.firstChild) {
      body.appendChild(this.firstChild);
    }
    wrapper.appendChild(body);
    this.appendChild(wrapper);
    this.dataset.upgraded = "true";
  }
}

customElements.define("lgpt-card", LgptCard);

const getElement = (id) => document.getElementById(id);

const elements = {
  prompt: getElement("prompt"),
  answer: getElement("answer"),
  promptStats: getElement("promptStats"),
  llmModelSelect: getElement("llmModelSelect"),
  btnRefreshModels: getElement("btnRefreshModels"),
  btnDeleteModel: getElement("btnDeleteModel"),
  modelStatus: getElement("modelStatus"),
  downloadList: getElement("downloadList"),
  downloadsPanel: getElement("downloadsPanel"),
  modelSuggestions: getElement("modelSuggestions"),
  btnSend: getElement("btnSend"),
  btnStop: getElement("btnStop"),
  btnCopy: getElement("btnCopy"),
  btnClearPrompt: getElement("btnClearPrompt"),
  btnClearAnswer: getElement("btnClearAnswer"),
  btnHistory: getElement("btnHistory"),
  overlay: getElement("overlay"),
  btnCloseModal: getElement("btnCloseModal"),
  btnClearStorage: getElement("btnClearStorage"),
  historyList: getElement("historyList"),
  healthStatus: getElement("healthStatus"),
  fileInput: getElement("fileInput"),
  btnTranscribe: getElement("btnTranscribe"),
  transcribeStatus: getElement("transcribeStatus"),
  transcriptStatus: getElement("transcriptStatus"),
  manualTranscriptInput: getElement("manualTranscriptInput"),
  btnUseManualTranscript: getElement("btnUseManualTranscript"),
  btnSaveManualTranscript: getElement("btnSaveManualTranscript"),
  transcriptList: getElement("transcriptList"),
  timelineContainer: getElement("timelineContainer"),
  timelineLegend: getElement("timelineLegend"),
  timelineNotice: getElement("timelineNotice"),
  btnEditTimeline: getElement("btnEditTimeline"),
  btnSaveTimeline: getElement("btnSaveTimeline"),
  btnCancelTimeline: getElement("btnCancelTimeline"),
  timelineHrName: getElement("timelineHrName"),
  timelineCandidateName: getElement("timelineCandidateName"),
  hrPrefixInput: getElement("hrPrefix"),
  modelSelect: getElement("modelSelect"),
  promptPresetSelect: getElement("promptPresetSelect"),
  criteriaFileInput: getElement("criteriaFile"),
  btnLoadCriteriaFile: getElement("btnLoadCriteriaFile"),
  btnLoadCriteriaSheet: getElement("btnLoadCriteriaSheet"),
  btnClearCriteria: getElement("btnClearCriteria"),
  googleSheetInput: getElement("googleSheetInput"),
  criteriaStatus: getElement("criteriaStatus"),
  criteriaList: getElement("criteriaList"),
  budgetStats: getElement("budgetStats"),
  quickCriterionInput: getElement("quickCriterionInput"),
  btnQuickAddCriterion: getElement("btnQuickAddCriterion"),
};

const tabButtons = Array.from(document.querySelectorAll("[data-tab-target]"));
const tabPanels = Array.from(document.querySelectorAll("[data-panel]"));

const sessionId = ensureSessionId();
let currentTranscript = "";
let currentTimeline = [];
let originalTimeline = [];
let timelineEditMode = false;
let currentRoleKeywords = {};
let timelineLabels = {};
const transcribeBusyState = { defaultLabel: null };
const chatState = { controller: null };
let activeTranscriptId = null;
let transcriptLibrary = [];
let modelState = { installed: [], recommended: MODEL_RECOMMENDATIONS, downloads: [] };
let downloadPollTimer = null;

const criteriaManager = new CriteriaManager({
  listEl: elements.criteriaList,
  statusEl: elements.criteriaStatus,
});

function recalcStats() {
  const prompt = elements.prompt?.value || "";
  const promptTokens = estTokens(prompt);
  const criteriaTokens = estTokens(criteriaManager.getCriteria().join(" "));
  const inputTokens = promptTokens + criteriaTokens;

  if (elements.promptStats) {
    elements.promptStats.textContent = `Символы: ${prompt.length} • Токены≈ ${promptTokens}`;
  }

  if (elements.budgetStats) {
    const numCtx = LIMITS.num_ctx ?? "—";
    const maxOut = LIMITS.max_tokens ?? "—";
    let line = `Входные токены: ${inputTokens} • Резерв на ответ: ${maxOut} • Лимит контекста: ${numCtx}`;
    const details = [];
    details.push(`запрос: ${promptTokens}`);
    if (criteriaTokens) {
      details.push(`критерии: ${criteriaTokens}`);
    }
    if (details.length) {
      line += ` (${details.join(" • ")})`;
    }
    elements.budgetStats.classList.remove("status--error", "status--warning", "status--success");

    if (LIMITS.num_ctx && LIMITS.max_tokens) {
      const total = inputTokens + LIMITS.max_tokens;
      if (total > LIMITS.num_ctx) {
        line += " • ⚠️ не влезет — сократите вход или ответ";
        elements.budgetStats.classList.add("status--error");
      } else if (total > 0.9 * LIMITS.num_ctx) {
        line += " • ⚠️ на грани — лучше сократить";
        elements.budgetStats.classList.add("status--warning");
      }
    }
    elements.budgetStats.textContent = line;
  }
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "—";
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} ГБ`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} МБ`;
  return `${Math.round(bytes / 1024)} КБ`;
}

function isModelInstalled(name) {
  if (!name) return false;
  return modelState.installed.some((item) => item?.name === name);
}

function setModelStatus(message, tone = "info") {
  updateStatus(elements.modelStatus, message, tone);
}

function renderModelSuggestions() {
  if (!elements.modelSuggestions) return;
  const list = modelState.recommended?.length ? modelState.recommended : MODEL_RECOMMENDATIONS;
  if (!list.length) {
    elements.modelSuggestions.textContent = "";
    return;
  }
  const chips = list
    .map((item) => {
      const installed = isModelInstalled(item.name);
      const cls = installed ? "model-chip is-installed" : "model-chip";
      return `<span class="${cls}"><strong>${item.name}</strong>${item.label ? ` — ${item.label}` : ""}</span>`;
    })
    .join(" ");
  elements.modelSuggestions.innerHTML = chips;
}

function updateModelSelect(preferredValue) {
  const select = elements.llmModelSelect;
  if (!select) return;
  const options = new Map();

  const recommended = modelState.recommended?.length ? modelState.recommended : MODEL_RECOMMENDATIONS;
  recommended.forEach((item) => {
    if (!item?.name) return;
    options.set(item.name, item.label || item.name);
  });

  modelState.installed.forEach((item) => {
    if (!item?.name || options.has(item.name)) return;
    options.set(item.name, item.name);
  });

  select.innerHTML = "";
  options.forEach((label, value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = `${value}${label && label !== value ? ` — ${label}` : ""}`;
    select.appendChild(option);
  });

  const saved = preferredValue || getSavedLlmModel();
  const defaultValue = saved && options.has(saved) ? saved : select.options[0]?.value;
  if (defaultValue) {
    select.value = defaultValue;
    setSavedLlmModel(defaultValue);
  }
  setModelStatus(select.value ? "Готово к работе" : "Добавьте или скачайте модель.", select.value ? "success" : "warning");
}

function renderDownloads() {
  if (!elements.downloadList) return;
  const list = Array.isArray(modelState.downloads) ? modelState.downloads : [];
  if (!list.length) {
    elements.downloadList.classList.add("muted");
    elements.downloadList.textContent = "Активных загрузок нет.";
    return;
  }
  elements.downloadList.classList.remove("muted");

  const items = list
    .map((item) => {
      const percent = Number.isFinite(item.percent) ? `${item.percent}%` : "—";
      const completed = formatBytes(item.completed);
      const total = formatBytes(item.total);
      const speed = Number.isFinite(item.speed_mbps) ? `${item.speed_mbps} МБ/с` : "—";
      const eta = Number.isFinite(item.eta_seconds)
        ? `${Math.max(Math.round(item.eta_seconds), 0)} с`
        : "—";
      const stateLabel =
        item.state === "completed"
          ? "Готово"
          : item.state === "error"
            ? `Ошибка: ${item.message || "неизвестно"}`
            : item.message || "Загрузка";
      const width = Number.isFinite(item.percent) ? `${Math.min(item.percent, 100)}%` : "0%";
      return `
        <div class="download-item">
          <div class="download-header">
            <div>
              <div class="download-title">${item.model}</div>
              <div class="download-meta">${completed} / ${total} • ${percent}</div>
            </div>
            <div class="download-meta">${speed} • ETA: ${eta}</div>
          </div>
          <div class="download-progress-bar"><span style="width:${width}"></span></div>
          <div class="download-state">${stateLabel}</div>
        </div>`;
    })
    .join("");

  elements.downloadList.innerHTML = items;
}

async function refreshDownloadStatuses({ silent = false } = {}) {
  try {
    const response = await fetch(`${API_BASE}/models/downloads`, { method: "GET" });
    if (!response.ok) return;
    const data = await response.json();
    const previous = modelState.downloads || [];
    modelState.downloads = Array.isArray(data?.downloads) ? data.downloads : [];
    renderDownloads();

    const completedModels = new Set(
      modelState.downloads
        .filter((item) => item.state === "completed")
        .map((item) => item.model)
        .filter(Boolean),
    );
    const hadCompleted = new Set(previous.filter((item) => item?.state === "completed").map((item) => item.model));
    const hasNewCompletion = [...completedModels].some((m) => !hadCompleted.has(m));
    if (hasNewCompletion) {
      await fetchModelList({ silent: true });
    }
  } catch (error) {
    if (!silent) console.warn("download poll failed", error);
  }
}

async function fetchModelList({ silent = false } = {}) {
  if (!silent) setModelStatus("Обновляю список моделей…");
  try {
    const response = await fetch(`${API_BASE}/models`, { method: "GET" });
    const data = await response.json();
    modelState.installed = Array.isArray(data?.installed) ? data.installed : [];
    modelState.recommended = Array.isArray(data?.recommended) && data.recommended.length
      ? data.recommended
      : MODEL_RECOMMENDATIONS;
    modelState.downloads = Array.isArray(data?.downloads) ? data.downloads : modelState.downloads;
    updateModelSelect();
    renderModelSuggestions();
    renderDownloads();
    const selected = elements.llmModelSelect?.value;
    if (selected) {
      setModelStatus(isModelInstalled(selected) ? `Локальная модель: ${selected}` : `Модель ${selected} не скачана`, isModelInstalled(selected) ? "success" : "warning");
    }
  } catch (error) {
    setModelStatus("Не удалось получить список моделей", "error");
  }
}

async function startModelDownload(model) {
  if (!model) return;
  const active = (modelState.downloads || []).find(
    (item) => item?.model === model && item.state !== "completed" && item.state !== "error",
  );
  if (active) {
    setModelStatus(`Загрузка ${model} уже запущена.`, "warning");
    if (elements.downloadsPanel) elements.downloadsPanel.open = true;
    return;
  }
  try {
    const response = await fetch(`${API_BASE}/models/pull`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (elements.downloadsPanel) {
      elements.downloadsPanel.open = true;
    }
    modelState.downloads = [...(modelState.downloads || []), data];
    renderDownloads();
    startDownloadPolling();
  } catch (error) {
    setModelStatus(`Не удалось запустить загрузку: ${error.message || error}`, "error");
  }
}

async function ensureModelAvailability(model) {
  if (!model) return true;
  if (isModelInstalled(model)) return true;
  const confirm = window.confirm(
    `Модель "${model}" не найдена локально.\nСкачать через Ollama? Загрузка будет идти в фоне, можно работать с другими моделями.`,
  );
  if (!confirm) {
    setModelStatus(`Модель ${model} не скачана. Выберите другую или скачайте.`, "warning");
    return false;
  }
  await startModelDownload(model);
  setModelStatus(`Загрузка модели ${model} запущена. Дождитесь завершения или выберите другую.`, "warning");
  return false;
}

async function deleteSelectedModel() {
  const model = elements.llmModelSelect?.value;
  if (!model) return;
  if (!isModelInstalled(model)) {
    window.alert(`Модель ${model} не найдена локально.`);
    return;
  }
  if (!window.confirm(`Удалить модель "${model}" из Ollama?`)) return;
  try {
    const response = await fetch(`${API_BASE}/models/${encodeURIComponent(model)}`, { method: "DELETE" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    await fetchModelList();
    setModelStatus(`Модель ${model} удалена.`, "success");
  } catch (error) {
    setModelStatus(`Не удалось удалить модель: ${error.message || error}`, "error");
  }
}

function startDownloadPolling() {
  if (downloadPollTimer) return;
  downloadPollTimer = window.setInterval(() => refreshDownloadStatuses({ silent: true }), 2500);
}

function normalizeTimelineItem(item) {
  if (!item || typeof item !== "object") {
    return null;
  }
  const hasStart = item.start !== undefined && item.start !== null && item.start !== "";
  const hasEnd = item.end !== undefined && item.end !== null && item.end !== "";
  const start = hasStart && Number.isFinite(Number(item.start)) ? Number(item.start) : null;
  const end = hasEnd && Number.isFinite(Number(item.end)) ? Number(item.end) : start;
  const speaker = (item.speaker || "unknown").toString().trim().toLowerCase() || "unknown";
  const text = (item.text || "").toString();
  return { start, end, speaker, text };
}

function cloneTimeline(items) {
  return Array.isArray(items) ? items.map((item) => ({ ...item })) : [];
}

function cloneLabels(source) {
  if (!source || typeof source !== "object") return {};
  const result = {};
  for (const [key, value] of Object.entries(source)) {
    if (typeof key !== "string") continue;
    if (typeof value === "string") {
      result[key] = value;
    }
  }
  return result;
}

function cloneRoleKeywords(source) {
  if (!source || typeof source !== "object") return {};
  const result = {};
  for (const [key, value] of Object.entries(source)) {
    if (typeof key !== "string") continue;
    if (Array.isArray(value)) {
      result[key] = value.filter((item) => typeof item === "string");
      continue;
    }
    if (typeof value === "string") {
      result[key] = value;
    }
  }
  return result;
}

function hasTimelineTiming(items = []) {
  return items.some((item) => Number.isFinite(item?.start) || Number.isFinite(item?.end));
}

function buildTextTimelineFromTranscript(transcript) {
  const text = (transcript || "").toString().trim();
  if (!text) return [];
  let chunks = text.split(/\n{2,}/).map((chunk) => chunk.trim()).filter(Boolean);
  if (chunks.length <= 1) {
    chunks = text.split(/\n/).map((line) => line.trim()).filter(Boolean);
  }
  return chunks.map((chunk) => ({ start: null, end: null, speaker: "unknown", text: chunk }));
}

function createTranscriptId() {
  return `tr_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function normalizeTranscriptEntry(entry) {
  if (!entry || typeof entry !== "object") return null;
  const timeline = Array.isArray(entry.timeline)
    ? entry.timeline.map((item) => normalizeTimelineItem(item)).filter(Boolean)
    : [];
  const text = (entry.text || "").toString();
  const title = (entry.title || "").toString().trim();
  const ts = Number(entry.ts) || Date.now();
  const updatedAt = Number(entry.updatedAt) || ts;
  return {
    id: typeof entry.id === "string" ? entry.id : createTranscriptId(),
    title: title || `Транскрипт ${new Date(ts).toLocaleString()}`,
    text,
    timeline,
    roleKeywords: cloneRoleKeywords(entry.roleKeywords),
    labels: cloneLabels(entry.labels),
    ts,
    updatedAt,
  };
}

function newTranscriptEntry({ title, text, timeline, roleKeywords, labels }) {
  return normalizeTranscriptEntry({
    id: createTranscriptId(),
    title,
    text,
    timeline,
    roleKeywords,
    labels,
    ts: Date.now(),
    updatedAt: Date.now(),
  });
}

function suggestTranscriptTitle({ fileName, manual = false } = {}) {
  if (fileName && typeof fileName === "string") {
    return fileName;
  }
  const stamp = new Date().toLocaleString();
  return manual ? `Ручной текст ${stamp}` : `Транскрипт ${stamp}`;
}

function updateTimelineButtons() {
  const hasTimeline = currentTimeline.length > 0;
  if (elements.btnEditTimeline) {
    elements.btnEditTimeline.hidden = !hasTimeline || timelineEditMode;
  }
  if (elements.btnSaveTimeline) {
    elements.btnSaveTimeline.hidden = !timelineEditMode;
    elements.btnSaveTimeline.disabled = !timelineEditMode;
  }
  if (elements.btnCancelTimeline) {
    elements.btnCancelTimeline.hidden = !timelineEditMode;
    elements.btnCancelTimeline.disabled = !timelineEditMode;
  }
  if (elements.timelineHrName) {
    elements.timelineHrName.disabled = !hasTimeline;
  }
  if (elements.timelineCandidateName) {
    elements.timelineCandidateName.disabled = !hasTimeline;
  }
}

function updateTimelineNameInputs() {
  if (elements.timelineHrName) {
    elements.timelineHrName.value = timelineLabels.hr || "";
  }
  if (elements.timelineCandidateName) {
    elements.timelineCandidateName.value = timelineLabels.candidate || "";
  }
}

function updateTimelineLegend() {
  renderRoleLegend(elements.timelineLegend, currentRoleKeywords, timelineLabels);
}

function updateTimelineView() {
  renderTimeline(elements.timelineContainer, currentTimeline, {
    editable: timelineEditMode,
    labels: timelineLabels,
  });
  updateTimelineNotice();
}

function updateTimelineNotice() {
  if (!elements.timelineNotice) return;
  if (!currentTimeline.length) {
    updateStatus(elements.timelineNotice, "", "info");
    return;
  }
  if (hasTimelineTiming(currentTimeline)) {
    updateStatus(elements.timelineNotice, "", "info");
  } else {
    updateStatus(
      elements.timelineNotice,
      "Таймлайн без таймингов: отображается только текст.",
      "warning",
    );
  }
}

function clearTimelineState() {
  currentTimeline = [];
  originalTimeline = [];
  timelineEditMode = false;
  currentRoleKeywords = {};
  timelineLabels = {};
  activeTranscriptId = null;
  updateTimelineView();
  updateTimelineButtons();
  updateTimelineNameInputs();
  updateTimelineLegend();
}

function setTimelineData(items, keywords = null, { resetLabels = false, labels = null } = {}) {
  const normalized = Array.isArray(items)
    ? items.map((item) => normalizeTimelineItem(item)).filter(Boolean)
    : [];
  currentTimeline = normalized;
  originalTimeline = cloneTimeline(normalized);
  timelineEditMode = false;
  currentRoleKeywords = cloneRoleKeywords(keywords);
  if (resetLabels) {
    timelineLabels = {};
  }
  if (labels && typeof labels === "object") {
    timelineLabels = cloneLabels(labels);
  }
  updateTimelineView();
  updateTimelineButtons();
  updateTimelineNameInputs();
  updateTimelineLegend();
}

function rebuildTranscriptFromTimeline() {
  const merged = currentTimeline.map((item) => item.text || "").join("\n").trim();
  currentTranscript = merged;
  if (elements.manualTranscriptInput) {
    elements.manualTranscriptInput.value = merged;
  }
}

function enterTimelineEditMode() {
  if (!currentTimeline.length || timelineEditMode) return;
  originalTimeline = cloneTimeline(currentTimeline);
  timelineEditMode = true;
  updateTimelineView();
  updateTimelineButtons();
}

function cancelTimelineEdit() {
  if (!timelineEditMode) return;
  currentTimeline = cloneTimeline(originalTimeline);
  timelineEditMode = false;
  updateTimelineView();
  updateTimelineButtons();
}

function saveTimelineEdit() {
  if (!timelineEditMode) return false;
  originalTimeline = cloneTimeline(currentTimeline);
  timelineEditMode = false;
  updateTimelineView();
  updateTimelineButtons();
  rebuildTranscriptFromTimeline();
  updateActiveTranscriptEntry(
    { timeline: currentTimeline, text: currentTranscript },
    { silent: true },
  );
  return true;
}

function handleTimelineInput(event) {
  if (!timelineEditMode) return;
  const target = event.target;
  if (!target || typeof target.dataset?.index === "undefined") return;
  const index = Number(target.dataset.index);
  if (!Number.isInteger(index) || !currentTimeline[index]) return;

  if (target.classList.contains("timeline-textarea")) {
    currentTimeline[index].text = target.value;
    return;
  }

  if (target.classList.contains("timeline-speaker-select")) {
    const value = (target.value || "unknown").toString().trim().toLowerCase() || "unknown";
    currentTimeline[index].speaker = value;
    const row = target.closest(".timeline-row");
    if (row) {
      Array.from(row.classList).forEach((cls) => {
        if (cls.startsWith("timeline-") && cls !== "timeline-row" && cls !== "timeline-row--editing") {
          row.classList.remove(cls);
        }
      });
      row.classList.add(`timeline-${value}`);
    }
  }
}

function handleTimelineNameInput(event) {
  const role = event.target?.dataset?.role;
  if (!role) return;
  const value = event.target.value.trim();
  if (value) {
    timelineLabels[role] = value;
  } else {
    delete timelineLabels[role];
  }
  if (!timelineEditMode) {
    updateTimelineView();
  }
  updateTimelineLegend();
  updateActiveTranscriptEntry({ labels: timelineLabels }, { silent: true });
}

function activateTab(target) {
  if (!target) return;
  tabButtons.forEach((button) => {
    const isActive = button.dataset.tabTarget === target;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });

  tabPanels.forEach((panel) => {
    const isActive = panel.dataset.panel === target;
    panel.classList.toggle("is-active", isActive);
    if (isActive) {
      panel.removeAttribute("hidden");
    } else {
      panel.setAttribute("hidden", "");
    }
  });
}

async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE}/health`, { method: "GET" });
    const data = await response.json();
    updateStatus(elements.healthStatus, `сервер: OK • модель: ${data.model}`, "success");
    if (data.num_ctx) LIMITS.num_ctx = Number(data.num_ctx) || null;
    if (data.max_tokens) LIMITS.max_tokens = Number(data.max_tokens) || null;
  } catch (error) {
    updateStatus(elements.healthStatus, "сервер недоступен", "error");
  } finally {
    recalcStats();
  }
}

function tsFmt(ts) {
  return new Date(ts).toLocaleString();
}

function escapeHtml(value) {
  return (value ?? "").toString().replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function setTranscriptStatus(message, tone = "info") {
  if (!elements.transcriptStatus) return;
  updateStatus(elements.transcriptStatus, message, tone);
}

function persistTranscriptLibrary() {
  if (!Array.isArray(transcriptLibrary)) {
    transcriptLibrary = [];
  }
  if (transcriptLibrary.length > TRANSCRIPT_LIBRARY_LIMIT) {
    transcriptLibrary = transcriptLibrary.slice(0, TRANSCRIPT_LIBRARY_LIMIT);
  }
  saveTranscripts(transcriptLibrary);
}

function renderTranscriptLibrary() {
  if (!elements.transcriptList) return;
  if (!Array.isArray(transcriptLibrary) || !transcriptLibrary.length) {
    elements.transcriptList.classList.add("muted");
    elements.transcriptList.innerHTML = '<div class="muted">Сохранённых транскриптов пока нет.</div>';
    return;
  }

  elements.transcriptList.classList.remove("muted");
  const html = transcriptLibrary
    .map((entry) => {
      const activeClass = entry.id === activeTranscriptId ? " transcript-item--active" : "";
      const hasTiming = hasTimelineTiming(entry.timeline);
      const badge = hasTiming
        ? '<span class="badge badge--success">с таймингами</span>'
        : '<span class="badge badge--warning">без таймингов</span>';
      const rawPreview = (entry.text || "").replace(/\s+/g, " ").trim();
      const previewText = rawPreview.slice(0, 180);
      const preview = escapeHtml(previewText + (rawPreview.length > 180 ? "…" : ""));
      const timestamp = escapeHtml(tsFmt(entry.updatedAt || entry.ts));
      return `
        <article class="transcript-item${activeClass}" data-id="${escapeHtml(entry.id)}">
          <header class="transcript-item__header">
            <div>
              <div class="transcript-item__title">${escapeHtml(entry.title)}</div>
              <div class="transcript-item__meta muted">${timestamp}</div>
            </div>
            <div class="transcript-item__badges">${badge}</div>
          </header>
          <div class="transcript-item__preview muted">${preview || "—"}</div>
          <div class="transcript-item__actions buttons mt-xs">
            <button class="secondary" type="button" data-action="use">Загрузить</button>
            <button type="button" data-action="analyze">Анализ</button>
            <button class="warn" type="button" data-action="delete">Удалить</button>
          </div>
        </article>
      `;
    })
    .join("");

  elements.transcriptList.innerHTML = html;
}

function sortTranscriptLibrary() {
  transcriptLibrary.sort((a, b) => (b.updatedAt || b.ts) - (a.updatedAt || a.ts));
}

function loadTranscriptLibrary() {
  const stored = loadTranscripts();
  const items = Array.isArray(stored)
    ? stored
        .map((entry) => normalizeTranscriptEntry(entry))
        .filter(Boolean)
    : [];
  transcriptLibrary = items;
  sortTranscriptLibrary();
  if (transcriptLibrary.length > TRANSCRIPT_LIBRARY_LIMIT) {
    transcriptLibrary = transcriptLibrary.slice(0, TRANSCRIPT_LIBRARY_LIMIT);
  }
  renderTranscriptLibrary();
}

function addTranscriptEntry(entry, { makeActive = false, announce = true } = {}) {
  const normalized = normalizeTranscriptEntry(entry);
  if (!normalized) return null;
  transcriptLibrary = [normalized, ...transcriptLibrary.filter((item) => item.id !== normalized.id)];
  sortTranscriptLibrary();
  if (transcriptLibrary.length > TRANSCRIPT_LIBRARY_LIMIT) {
    transcriptLibrary = transcriptLibrary.slice(0, TRANSCRIPT_LIBRARY_LIMIT);
  }
  persistTranscriptLibrary();
  if (makeActive) {
    activeTranscriptId = normalized.id;
  }
  renderTranscriptLibrary();
  if (announce) {
    setTranscriptStatus(`Транскрипт «${normalized.title}» сохранён.`, "success");
  }
  return normalized;
}

function updateActiveTranscriptEntry(patch = {}, { silent = false } = {}) {
  if (!activeTranscriptId) return;
  const index = transcriptLibrary.findIndex((item) => item.id === activeTranscriptId);
  if (index === -1) return;
  const base = transcriptLibrary[index];
  const next = normalizeTranscriptEntry({
    ...base,
    ...patch,
    id: base.id,
    ts: base.ts,
    updatedAt: Date.now(),
  });
  transcriptLibrary[index] = next;
  sortTranscriptLibrary();
  persistTranscriptLibrary();
  renderTranscriptLibrary();
  if (!silent) {
    setTranscriptStatus(`Транскрипт «${next.title}» обновлён.`, "success");
  }
}

function deleteTranscriptEntry(id) {
  if (!id) return;
  const index = transcriptLibrary.findIndex((item) => item.id === id);
  if (index === -1) return;
  const [removed] = transcriptLibrary.splice(index, 1);
  persistTranscriptLibrary();
  if (activeTranscriptId === id) {
    activeTranscriptId = null;
  }
  renderTranscriptLibrary();
  setTranscriptStatus(`Транскрипт «${removed.title}» удалён.`, "warning");
}

function applyTranscriptEntry(entry, { focusTimeline = true, announce = true } = {}) {
  if (!entry) return false;
  activeTranscriptId = entry.id;
  currentTranscript = entry.text || "";
  setTimelineData(entry.timeline, entry.roleKeywords, { resetLabels: true, labels: entry.labels });
  if (elements.manualTranscriptInput) {
    elements.manualTranscriptInput.value = currentTranscript;
  }
  if (elements.prompt && !elements.prompt.value.trim()) {
    const hrPrefix = getHrPrefix(DEFAULT_HR_PREFIX);
    elements.prompt.value = `${hrPrefix}. Проанализируй собеседование по критериям.`;
  }
  if (focusTimeline) {
    activateTab("timeline");
  }
  recalcStats();
  renderTranscriptLibrary();
  if (announce) {
    setTranscriptStatus(`Транскрипт «${entry.title}» загружен.`, "success");
  }
  return true;
}

function findTranscriptEntry(id) {
  if (!id) return null;
  return transcriptLibrary.find((item) => item.id === id) || null;
}

function useManualTranscript({ save = false } = {}) {
  if (!elements.manualTranscriptInput) return;
  const rawValue = elements.manualTranscriptInput.value || "";
  const text = rawValue.trim();
  if (!text) {
    setTranscriptStatus("Вставьте текст транскрипта перед использованием.", "error");
    return;
  }

  activeTranscriptId = null;
  currentTranscript = text;
  const timeline = buildTextTimelineFromTranscript(text);
  setTimelineData(timeline, {}, { resetLabels: true });

  if (elements.prompt && !elements.prompt.value.trim()) {
    const hrPrefix = getHrPrefix(DEFAULT_HR_PREFIX);
    elements.prompt.value = `${hrPrefix}. Проанализируй собеседование по критериям.`;
  }

  if (save) {
    const firstLine = text.split(/\n/).map((line) => line.trim()).find(Boolean);
    const titleBase = firstLine ? firstLine.slice(0, 80) : null;
    const title = titleBase ? (titleBase.length < firstLine.length ? `${titleBase}…` : titleBase) : suggestTranscriptTitle({ manual: true });
    const entry = newTranscriptEntry({
      title,
      text,
      timeline: currentTimeline,
      roleKeywords: currentRoleKeywords,
      labels: timelineLabels,
    });
    addTranscriptEntry(entry, { makeActive: true, announce: true });
  } else {
    renderTranscriptLibrary();
    setTranscriptStatus("Текст прикреплён. Можно запускать анализ.", "success");
  }

  activateTab("timeline");
  recalcStats();
}

function handleTranscriptListClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  event.preventDefault();
  const item = button.closest(".transcript-item");
  if (!item) return;
  const id = item.dataset.id;
  if (!id) return;
  const action = button.dataset.action;

  if (action === "delete") {
    const confirmed = window.confirm("Удалить сохранённый транскрипт?");
    if (confirmed) {
      deleteTranscriptEntry(id);
    }
    return;
  }

  const entry = findTranscriptEntry(id);
  if (!entry) {
    setTranscriptStatus("Не удалось найти транскрипт.", "error");
    return;
  }

  if (action === "use") {
    applyTranscriptEntry(entry, { focusTimeline: true, announce: true });
    return;
  }

  if (action === "analyze") {
    const applied = applyTranscriptEntry(entry, { focusTimeline: true, announce: true });
    if (applied) {
      activateTab("answer");
      sendPrompt();
      setTranscriptStatus("Запрос отправлен на анализ сохранённого транскрипта.");
    }
  }
}

function stopCurrentChat() {
  if (chatState.controller) {
    chatState.controller.abort();
  }
}

function renderHistory() {
  const items = loadHistory();
  elements.historyList.innerHTML = items.length
    ? items
        .map(
          (item) => `
        <div class="history-item" data-ts="${item.ts}">
          <div class="history-item__header muted">
            <span>${tsFmt(item.ts)}</span>
            <button class="secondary btn-delete" data-ts="${item.ts}" title="Удалить запись">Удалить</button>
          </div>
          <strong>Запрос:</strong>
          <pre>${escapeHtml(item.q)}</pre>
          <strong>Ответ:</strong>
          <pre>${escapeHtml(item.a)}</pre>
        </div>
      `,
        )
        .join("")
    : '<div class="muted">История пуста.</div>';
}

function openHistory() {
  renderHistory();
  elements.overlay?.classList.add("overlay--visible");
}

function closeHistory() {
  elements.overlay?.classList.remove("overlay--visible");
}

function setBusy(isBusy) {
  if (elements.btnSend) {
    elements.btnSend.disabled = Boolean(isBusy);
    elements.btnSend.textContent = isBusy ? "Отправка…" : "Отправить";
  }
  if (elements.btnStop) {
    elements.btnStop.hidden = !isBusy;
    elements.btnStop.disabled = !isBusy;
  }
}

function setTranscribeBusy(isBusy, { label } = {}) {
  if (elements.btnTranscribe) {
    const defaultLabel =
      transcribeBusyState.defaultLabel ||
      elements.btnTranscribe.dataset.defaultLabel ||
      elements.btnTranscribe.textContent ||
      "Транскрибировать файл";
    transcribeBusyState.defaultLabel = defaultLabel;
    elements.btnTranscribe.dataset.defaultLabel = defaultLabel;

    elements.btnTranscribe.disabled = Boolean(isBusy);
    elements.btnTranscribe.textContent = label || (isBusy ? "Транскрибирую…" : defaultLabel);
  }

  if (elements.fileInput) {
    elements.fileInput.disabled = Boolean(isBusy);
  }
}

async function sendPrompt() {
  if (chatState.controller) {
    return;
  }
  const rawQuery = elements.prompt?.value || "";
  const finalQuery = rawQuery.trim() || "проанализируй";

  const selectedModel = (elements.llmModelSelect?.value || "").trim();
  if (selectedModel) {
    const available = await ensureModelAvailability(selectedModel);
    if (!available) {
      return;
    }
  }

  const controller = new AbortController();
  chatState.controller = controller;
  setBusy(true);
  activateTab("answer");
  if (elements.answer) {
    elements.answer.value = "Думаю…";
  }

  let aborted = false;
  try {
    const payload = { query: finalQuery, session_id: sessionId };
    const transcript = currentTranscript.trim();
    if (transcript) {
      payload.transcript = transcript;
    }
    const criteria = criteriaManager.getCriteria();
    if (criteria.length) {
      payload.criteria = criteria;
    }
    if (selectedModel) {
      payload.model = selectedModel;
      setSavedLlmModel(selectedModel);
    }

    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const text = data.reply ?? "";
    if (elements.answer) {
      elements.answer.value = text;
    }
    addHistoryEntry(finalQuery, text);

    if (elements.prompt) {
      elements.prompt.value = "";
    }
    recalcStats();
  } catch (error) {
    if (error?.name === "AbortError") {
      aborted = true;
      if (elements.answer) {
        elements.answer.value = "Ответ остановлен пользователем.";
      }
    } else if (elements.answer) {
      elements.answer.value = `Ошибка: ${error.message || error}`;
    }
  } finally {
    chatState.controller = null;
    setBusy(false);
    if (aborted && elements.prompt) {
      elements.prompt.focus();
    }
  }
}

async function transcribeFile() {
  const file = elements.fileInput?.files?.[0];
  if (!file) {
    updateStatus(elements.transcribeStatus, "выберите аудио/видео файл", "error");
    return;
  }

  setTranscribeBusy(true);
  try {
    updateStatus(elements.transcribeStatus, "транскрибирую…");
    setTranscriptStatus("", "info");
    clearTimelineState();

    const formData = new FormData();
    formData.append("file", file, file.name);
    const model = (elements.modelSelect?.value || "medium").trim();
    formData.append("model", model);
    const preset = (elements.promptPresetSelect?.value || "none").trim();
    formData.append("prompt_preset", preset);
    formData.append("session_id", sessionId);

    const response = await fetch(`${API_BASE}/transcribe`, {
      method: "POST",
      body: formData,
    });

    let data = null;
    try {
      data = await response.json();
    } catch (error) {
      data = null;
    }

    if (!response.ok) {
      const detail = data?.detail;
      if (detail && detail.code === "whisper_model_missing") {
        const missingModel = detail.model || model;
        const message =
          `Модель Whisper "${missingModel}" не найдена локально.\n\n` +
          "Скачайте или скопируйте её в каталог ollama_models/whisper внутри проекта LocalGPT и повторите попытку.";
        window.alert(message);
        updateStatus(elements.transcribeStatus, `❌ ${message}`, "error");
        return;
      }
      throw new Error(`HTTP ${response.status}`);
    }

    const transcript = data?.text || data?.transcript || data?.result || "";
    const timeline = Array.isArray(data?.timeline) ? data.timeline : [];
    const roleKeywords = data?.role_keywords;
    if (!transcript) throw new Error("пустая транскрипция");

    currentTranscript = transcript;
    const hrPrefix = getHrPrefix(DEFAULT_HR_PREFIX);
    if (elements.prompt) {
      elements.prompt.value = `${hrPrefix}. Проанализируй собеседование по критериям.`;
      elements.prompt.focus();
    }

    const preparedTimeline = timeline.length ? timeline : buildTextTimelineFromTranscript(transcript);
    setTimelineData(preparedTimeline, roleKeywords || {}, { resetLabels: true });
    if (elements.manualTranscriptInput) {
      elements.manualTranscriptInput.value = transcript;
    }

    const entry = newTranscriptEntry({
      title: suggestTranscriptTitle({ fileName: file?.name }),
      text: transcript,
      timeline: currentTimeline,
      roleKeywords: currentRoleKeywords,
      labels: timelineLabels,
    });
    addTranscriptEntry(entry, { makeActive: true, announce: false });
    const hasTiming = hasTimelineTiming(currentTimeline);
    setTranscriptStatus(
      hasTiming
        ? `Сохранён новый транскрипт «${entry.title}».`
        : `Сохранён новый транскрипт «${entry.title}» (тайминги отсутствуют).`,
      hasTiming ? "success" : "warning",
    );
    activateTab("timeline");

    const statusTone = hasTiming ? "success" : "warning";
    const timelineNote = hasTiming ? "" : " • тайминги не найдены";
    updateStatus(
      elements.transcribeStatus,
      `✅ Транскрипция готова — модель: ${model}, символов: ${transcript.length}${timelineNote}`,
      statusTone,
    );
    recalcStats();
  } catch (error) {
    updateStatus(elements.transcribeStatus, `❌ ошибка: ${error.message || error}`, "error");
  } finally {
    setTranscribeBusy(false);
  }
}

function addQuickCriterion() {
  const value = elements.quickCriterionInput?.value || "";
  const saved = criteriaManager.addManualCriterion(value);
  if (saved && elements.quickCriterionInput) {
    elements.quickCriterionInput.value = "";
    elements.quickCriterionInput.focus();
    recalcStats();
  }
  return saved;
}

function attachEvents() {
  elements.prompt?.addEventListener("input", debounce(recalcStats, 100));

  elements.llmModelSelect?.addEventListener("change", async () => {
    const value = (elements.llmModelSelect.value || "").trim();
    if (value) {
      setSavedLlmModel(value);
      const available = await ensureModelAvailability(value);
      if (available) {
        setModelStatus(isModelInstalled(value) ? `Локальная модель: ${value}` : `Модель ${value} не скачана`, isModelInstalled(value) ? "success" : "warning");
      }
    }
  });
  elements.btnRefreshModels?.addEventListener("click", () => fetchModelList());
  elements.btnDeleteModel?.addEventListener("click", () => deleteSelectedModel());

  elements.btnSend?.addEventListener("click", sendPrompt);
  elements.btnStop?.addEventListener("click", stopCurrentChat);
  elements.prompt?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!chatState.controller) {
        sendPrompt();
      }
    }
  });

  elements.btnCopy?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(elements.answer?.value || "");
    } catch (error) {
      console.warn("Clipboard write error", error);
    }
  });

  elements.btnClearPrompt?.addEventListener("click", () => {
    if (elements.prompt) {
      elements.prompt.value = "";
      recalcStats();
    }
  });
  elements.btnClearAnswer?.addEventListener("click", () => {
    if (elements.answer) {
      elements.answer.value = "";
    }
  });

  elements.btnHistory?.addEventListener("click", openHistory);
  elements.btnCloseModal?.addEventListener("click", closeHistory);
  elements.overlay?.addEventListener("click", (event) => {
    if (event.target === elements.overlay) {
      closeHistory();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (elements.overlay?.classList.contains("overlay--visible")) {
      closeHistory();
    }
  });

  elements.btnClearStorage?.addEventListener("click", () => {
    saveHistory([]);
    renderHistory();
  });

  elements.historyList?.addEventListener("click", (event) => {
    const button = event.target.closest(".btn-delete");
    if (!button) return;
    const ts = Number(button.dataset.ts);
    if (!Number.isFinite(ts)) return;
    if (!window.confirm("Удалить эту запись из истории?")) return;
    deleteHistoryEntry(ts);
    renderHistory();
  });

  elements.btnLoadCriteriaFile?.addEventListener("click", async () => {
    const file = elements.criteriaFileInput?.files?.[0];
    if (!file) {
      criteriaManager.updateStatus("Выберите CSV или XLSX файл для загрузки.", "error");
      return;
    }
    try {
      await criteriaManager.requestFromBackend({ apiBase: API_BASE, sessionId, file });
      recalcStats();
    } catch (error) {
      console.warn("criteria file load failed", error);
    }
    if (elements.criteriaFileInput) {
      elements.criteriaFileInput.value = "";
    }
  });

  elements.btnLoadCriteriaSheet?.addEventListener("click", async () => {
    const raw = elements.googleSheetInput?.value || "";
    const parsed = criteriaManager.parseGoogleSheetInput(raw);
    if (!parsed || !parsed.sheetId) {
      criteriaManager.updateStatus("Укажите ID или ссылку на Google Sheets.", "error");
      return;
    }
    try {
      await criteriaManager.requestFromBackend({
        apiBase: API_BASE,
        sessionId,
        googleSheetId: parsed.sheetId,
        googleGid: parsed.gid,
      });
      recalcStats();
    } catch (error) {
      console.warn("criteria sheet load failed", error);
    }
  });

  elements.googleSheetInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.btnLoadCriteriaSheet?.click();
    }
  });

  elements.btnClearCriteria?.addEventListener("click", () => {
    criteriaManager.clear();
    recalcStats();
  });

  elements.criteriaList?.addEventListener("click", (event) => {
    const button = event.target.closest('[data-action="remove-criterion"]');
    if (!button) return;
    const index = Number(button.dataset.index);
    if (!Number.isInteger(index)) return;
    const removed = criteriaManager.removeCriterion(index);
    if (removed) {
      recalcStats();
    }
  });

  elements.btnQuickAddCriterion?.addEventListener("click", () => {
    addQuickCriterion();
  });

  elements.quickCriterionInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      addQuickCriterion();
    }
  });

  elements.hrPrefixInput?.addEventListener(
    "input",
    debounce(() => {
      const value = elements.hrPrefixInput.value.trim() || DEFAULT_HR_PREFIX;
      setHrPrefix(value);
    }, 200),
  );

  elements.btnTranscribe?.addEventListener("click", (event) => {
    event.preventDefault();
    transcribeFile();
  });

  elements.btnUseManualTranscript?.addEventListener("click", () => {
    useManualTranscript({ save: false });
  });

  elements.btnSaveManualTranscript?.addEventListener("click", () => {
    useManualTranscript({ save: true });
  });

  elements.transcriptList?.addEventListener("click", handleTranscriptListClick);

  elements.btnEditTimeline?.addEventListener("click", enterTimelineEditMode);
  elements.btnCancelTimeline?.addEventListener("click", cancelTimelineEdit);
  elements.btnSaveTimeline?.addEventListener("click", () => {
    if (saveTimelineEdit()) {
      updateStatus(elements.transcribeStatus, "Изменения таймлайна сохранены.", "success");
    }
  });
  elements.timelineContainer?.addEventListener("input", handleTimelineInput);
  elements.timelineContainer?.addEventListener("change", handleTimelineInput);
  [elements.timelineHrName, elements.timelineCandidateName].forEach((input) => {
    input?.addEventListener("input", handleTimelineNameInput);
  });

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activateTab(button.dataset.tabTarget);
    });
  });
}

function init() {
  const savedModel = getSavedModel("medium");
  if (elements.modelSelect) {
    elements.modelSelect.value = savedModel;
    elements.modelSelect.addEventListener("change", () => {
      setSavedModel(elements.modelSelect.value);
    });
  }

  updateModelSelect(getSavedLlmModel());
  renderModelSuggestions();
  fetchModelList();
  startDownloadPolling();

  if (elements.promptPresetSelect) {
    // placeholder for future logic if needed
  }

  const savedPrefix = getHrPrefix(DEFAULT_HR_PREFIX);
  if (elements.hrPrefixInput) {
    elements.hrPrefixInput.value = savedPrefix || DEFAULT_HR_PREFIX;
  }

  loadTranscriptLibrary();
  setTranscriptStatus("", "info");
  clearTimelineState();
  criteriaManager.loadFromStorage();

  attachEvents();
  checkHealth();
  activateTab("answer");
  recalcStats();
}

init();
