import {
  API_BASE,
  addHistoryEntry,
  deleteHistoryEntry,
  getHrPrefix,
  getLastChatSessionId,
  getLastProfileId,
  getSavedLlmModel,
  getSavedModel,
  getSavedPromptPreset,
  loadHistory,
  saveHistory,
  setHrPrefix,
  setLastChatSessionId,
  setLastProfileId,
  setSavedLlmModel,
  setSavedModel,
  setSavedPromptPreset,
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
  btnProfile: getElement("btnProfile"),
  profileLabel: getElement("profileLabel"),
  profileTitle: getElement("profileTitle"),
  btnNewSession: getElement("btnNewSession"),
  btnToggleSidebar: getElement("btnToggleSidebar"),
  sessionList: getElement("sessionList"),
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
  btnSettings: getElement("btnSettings"),
  overlay: getElement("overlay"),
  settingsOverlay: getElement("settingsOverlay"),
  btnCloseModal: getElement("btnCloseModal"),
  btnCloseSettings: getElement("btnCloseSettings"),
  btnClearStorage: getElement("btnClearStorage"),
  historyList: getElement("historyList"),
  healthStatus: getElement("healthStatus"),
  fileInput: getElement("fileInput"),
  btnTranscribe: getElement("btnTranscribe"),
  transcribeStatus: getElement("transcribeStatus"),
  transcribeDefaults: getElement("transcribeDefaults"),
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
  transcriptHistoryList: getElement("transcriptHistoryList"),
  transcriptHistoryDetails: getElement("transcriptHistoryDetails"),
  transcriptHistoryTitle: getElement("transcriptHistoryTitle"),
  transcriptHistoryMeta: getElement("transcriptHistoryMeta"),
  transcriptHistoryContent: getElement("transcriptHistoryContent"),
  btnApplyTranscriptFromHistory: getElement("btnApplyTranscriptFromHistory"),
  btnSaveTranscriptHistoryTitle: getElement("btnSaveTranscriptHistoryTitle"),
  transcriptHistoryHeading: getElement("transcriptHistoryHeading"),
  transcriptHistoryOverlay: getElement("transcriptHistoryOverlay"),
  btnCloseTranscriptHistory: getElement("btnCloseTranscriptHistory"),
  btnDeleteTranscriptFromHistory: getElement("btnDeleteTranscriptFromHistory"),
  btnAddTranscriptHistoryEntry: getElement("btnAddTranscriptHistoryEntry"),
  profileOverlay: getElement("profileOverlay"),
  btnCloseProfileModal: getElement("btnCloseProfileModal"),
  btnModalNewProfile: getElement("btnModalNewProfile"),
  profileList: getElement("profileList"),
  btnHelp: getElement("btnHelp"),
  helpOverlay: getElement("helpOverlay"),
  btnCloseHelp: getElement("btnCloseHelp"),
  temperatureInput: getElement("temperatureInput"),
  maxTokensInput: getElement("maxTokensInput"),
  numCtxInput: getElement("numCtxInput"),
  memTurnsInput: getElement("memTurnsInput"),
  btnSaveModelSettings: getElement("btnSaveModelSettings"),
  btnResetModelSettings: getElement("btnResetModelSettings"),
  modelSettingsStatus: getElement("modelSettingsStatus"),
};

const tabButtons = Array.from(document.querySelectorAll("[data-tab-target]"));
const tabPanels = Array.from(document.querySelectorAll("[data-panel]"));

let profileList = [];
let activeProfileId = null;
let sessionListState = [];
let currentSessionId = getLastChatSessionId();
let currentSessionModel = null;
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
let selectedTranscriptHistoryId = null;
let modelState = { installed: [], recommended: MODEL_RECOMMENDATIONS, downloads: [] };
let downloadPollTimer = null;
let modelSettingsState = { effective: {}, overrides: {}, defaults: {} };

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

function describePromptPreset(preset) {
  const map = {
    none: "Без промпта",
    ru: "Универсальный (русский)",
    en: "Универсальный (английский)",
  };
  return map[preset] || preset || "—";
}

function renderTranscribeDefaults() {
  if (elements.modelSelect) {
    const savedModel = getSavedModel(elements.modelSelect.value || "medium");
    elements.modelSelect.value = savedModel;
  }
  if (elements.promptPresetSelect) {
    const savedPreset = getSavedPromptPreset(elements.promptPresetSelect.value || "none");
    elements.promptPresetSelect.value = savedPreset;
  }
  if (elements.transcribeDefaults) {
    const presetLabel = describePromptPreset(elements.promptPresetSelect?.value || "none");
    const modelLabel = elements.modelSelect?.value || "medium";
    elements.transcribeDefaults.textContent =
      `По умолчанию: Whisper ${modelLabel}, промпт — ${presetLabel}. Меняется в настройках.`;
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

function updateDownloadStatusIndicator() {
  const running = (modelState.downloads || []).filter(
    (d) => d.state === "running" || d.state === "pending",
  );
  if (!running.length) return;
  const first = running[0];
  const percent = Number.isFinite(first.percent) ? `${first.percent}%` : "—";
  setModelStatus(`Загрузка модели ${first.model || ""}: ${percent}`, "warning");
}

function syncModelActions() {
  const selected = elements.llmModelSelect?.value;
  const installed = selected && isModelInstalled(selected);
  if (elements.btnDeleteModel) {
    elements.btnDeleteModel.disabled = !installed;
  }
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
      return `
        <button type="button" class="${cls}" data-model="${item.name}" data-installed="${installed ? "1" : "0"}">
          <strong>${item.name}</strong>${item.label ? ` — ${item.label}` : ""}
          <span class="model-chip__hint">${installed ? "Выбрать" : "Скачать и выбрать"}</span>
        </button>
      `;
    })
    .join("");
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
  syncModelActions();
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
            : item.state === "canceled"
              ? "Остановлено пользователем"
            : item.message || "Загрузка";
      const width = Number.isFinite(item.percent) ? `${Math.min(item.percent, 100)}%` : "0%";
      const actions =
        item.state === "running" || item.state === "pending"
          ? `<div class="download-actions"><button class="secondary" type="button" data-action="cancel-download" data-task="${item.task_id}">Пауза/отмена</button></div>`
          : "";
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
          ${actions}
        </div>`;
    })
    .join("");

  elements.downloadList.innerHTML = items;
  updateDownloadStatusIndicator();
  if (!hasActiveDownloads()) {
    stopDownloadPolling();
  }
}

function renderProfiles() {
  const activeProfile = profileList.find((p) => p.id === activeProfileId);
  if (elements.profileLabel) {
    elements.profileLabel.textContent = activeProfile ? activeProfile.name : "Профиль";
  }
  if (elements.profileTitle) {
    elements.profileTitle.textContent = activeProfile ? `Сессии: ${activeProfile.name}` : "Сессии профиля";
  }
  if (!elements.profileList) return;
  if (!profileList.length) {
    elements.profileList.classList.add("muted");
    elements.profileList.textContent = "Профили не найдены.";
    return;
  }
  elements.profileList.classList.remove("muted");
  const html = profileList
    .map((profile) => {
      const isActive = profile.id === activeProfileId;
      return `
        <div class="profile-list__item" data-id="${profile.id}">
          <div class="profile-list__meta">
            <strong>${escapeHtml(profile.name || `Профиль ${profile.id}`)}</strong>
            <span class="muted">ID: ${profile.id}</span>
          </div>
          <div class="profile-list__actions">
            <button class="secondary" type="button" data-action="select">${isActive ? "Активен" : "Выбрать"}</button>
            <button class="warn" type="button" data-action="delete" ${isActive && profileList.length === 1 ? "disabled" : ""}>×</button>
          </div>
        </div>
      `;
    })
    .join("");
  elements.profileList.innerHTML = html;
}

function renderSessions() {
  if (!elements.sessionList) return;
  if (!sessionListState.length) {
    elements.sessionList.classList.add("muted");
    elements.sessionList.innerHTML = '<div class="muted">Диалогов пока нет. Создайте новый.</div>';
    return;
  }
  elements.sessionList.classList.remove("muted");
  const html = sessionListState
    .map((session) => {
      const isActive = session.id === currentSessionId;
      const updated = session.updated_at || session.updatedAt;
      const stamp = updated ? tsFmt(updated) : "";
      const model = session.model_name || session.model || "";
      return `
        <article class="session-item${isActive ? " session-item--active" : ""}" data-id="${session.id}">
          <div class="session-item__meta">
            <div class="session-item__title">${escapeHtml(session.title || "Диалог")}</div>
            <div class="muted">${escapeHtml(stamp)} • ${escapeHtml(model)}</div>
          </div>
          <div class="session-item__actions">
            <button class="secondary" type="button" data-action="open">Открыть</button>
            <button class="warn" type="button" data-action="delete">×</button>
          </div>
        </article>
      `;
    })
    .join("");
  elements.sessionList.innerHTML = html;
}

async function setActiveSession(sessionId, { refreshOnly = false } = {}) {
  currentSessionId = sessionId;
  setLastChatSessionId(sessionId || null);
  if (!sessionId) {
    currentSessionModel = null;
  }
  const session = sessionListState.find((item) => item.id === sessionId);
  currentSessionModel = session?.model_name || currentSessionModel || null;
  if (elements.llmModelSelect && currentSessionModel) {
    const exists = Array.from(elements.llmModelSelect.options).some((opt) => opt.value === currentSessionModel);
    if (!exists) {
      updateModelSelect(currentSessionModel);
    }
    elements.llmModelSelect.value = currentSessionModel;
    setSavedLlmModel(currentSessionModel);
  }
  renderSessions();
  if (!refreshOnly) {
    await refreshModelSettings(currentSessionModel || elements.llmModelSelect?.value || "");
    await loadTranscriptLibrary({ silent: true });
  }
}

async function loadSessionsForProfile(profileId) {
  if (!profileId) {
    sessionListState = [];
    renderSessions();
    return;
  }
  try {
    const response = await fetch(`${API_BASE}/sessions?profile_id=${profileId}`, { method: "GET" });
    const data = await response.json();
    sessionListState = Array.isArray(data?.sessions) ? data.sessions : [];
    const preferred = sessionListState.find((item) => item.id === getLastChatSessionId());
    const next = preferred || sessionListState[0] || null;
    await setActiveSession(next?.id || null, { refreshOnly: false });
    renderSessions();
  } catch (error) {
    updateStatus(elements.healthStatus, "Список сессий недоступен", "error");
  }
}

async function fetchProfilesAndInit() {
  try {
    const response = await fetch(`${API_BASE}/profiles`, { method: "GET" });
    const data = await response.json();
    profileList = Array.isArray(data?.profiles) ? data.profiles : [];
    const preferred = profileList.find((p) => p.id === getLastProfileId());
    activeProfileId = preferred?.id ?? profileList[0]?.id ?? null;
    if (activeProfileId) {
      setLastProfileId(activeProfileId);
    }
    renderProfiles();
    await loadSessionsForProfile(activeProfileId);
  } catch (error) {
    updateStatus(elements.healthStatus, "Профили недоступны", "error");
  }
}

async function createProfileFlow() {
  const name = window.prompt("Название профиля", "Новый профиль")?.trim();
  if (!name) return;
  try {
    const response = await fetch(`${API_BASE}/profiles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const profile = await response.json();
    profileList = [...profileList, profile];
    activeProfileId = profile.id;
    setLastProfileId(activeProfileId);
    renderProfiles();
    await loadSessionsForProfile(activeProfileId);
    closeProfileModal();
  } catch (error) {
    updateStatus(elements.healthStatus, `Не удалось создать профиль: ${error.message || error}`, "error");
  }
}

async function deleteProfileFlow(profileId = activeProfileId) {
  if (!profileId) return;
  const confirmed = window.confirm("Удалить профиль и все связанные данные?");
  if (!confirmed) return;
  try {
    const response = await fetch(`${API_BASE}/profiles/${profileId}`, { method: "DELETE" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    profileList = profileList.filter((p) => p.id !== profileId);
    activeProfileId = profileList[0]?.id || null;
    setLastProfileId(activeProfileId);
    renderProfiles();
    await loadSessionsForProfile(activeProfileId);
    closeProfileModal();
  } catch (error) {
    updateStatus(elements.healthStatus, `Не удалось удалить профиль: ${error.message || error}`, "error");
  }
}

function openProfileModal() {
  renderProfiles();
  elements.profileOverlay?.classList.add("overlay--visible");
}

function closeProfileModal() {
  elements.profileOverlay?.classList.remove("overlay--visible");
}

function handleProfileListClick(event) {
  const row = event.target.closest(".profile-list__item");
  if (!row) return;
  const profileId = Number(row.dataset.id);
  const action = event.target.closest("[data-action]")?.dataset?.action;
  if (!Number.isFinite(profileId)) return;
  if (action === "select") {
    activeProfileId = profileId;
    setLastProfileId(activeProfileId);
    renderProfiles();
    closeProfileModal();
    void loadSessionsForProfile(activeProfileId);
    void refreshModelSettings(currentModelName());
    void loadTranscriptLibrary({ silent: true });
    return;
  }
  if (action === "delete") {
    deleteProfileFlow(profileId);
  }
}

function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  const workspace = document.querySelector(".workspace-grid");
  if (!sidebar) return;
  const collapsed = sidebar.classList.toggle("sidebar-collapsed");
  if (workspace) {
    workspace.classList.toggle("is-collapsed", collapsed);
  }
  if (elements.btnToggleSidebar) {
    elements.btnToggleSidebar.textContent = collapsed ? "▶" : "◀";
    elements.btnToggleSidebar.title = collapsed ? "Развернуть список" : "Свернуть список";
  }
}

async function createSessionFlow() {
  if (!activeProfileId) {
    updateStatus(elements.healthStatus, "Сначала выберите профиль", "warning");
    return;
  }
  const title = window.prompt("Название нового диалога", "Новый диалог")?.trim() || "Новый диалог";
  const model = (elements.llmModelSelect?.value || "").trim();
  try {
    const response = await fetch(`${API_BASE}/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: activeProfileId, title, model_name: model }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const session = await response.json();
    sessionListState = [session, ...sessionListState.filter((s) => s.id !== session.id)];
    renderSessions();
    await setActiveSession(session.id);
  } catch (error) {
    updateStatus(elements.healthStatus, `Не удалось создать сессию: ${error.message || error}`, "error");
  }
}

async function deleteSessionById(sessionId) {
  if (!sessionId) return;
  const confirmed = window.confirm("Удалить диалог и историю сообщений?");
  if (!confirmed) return;
  try {
    const response = await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    sessionListState = sessionListState.filter((item) => item.id !== sessionId);
    if (currentSessionId === sessionId) {
      currentSessionId = null;
      currentSessionModel = null;
    }
    renderSessions();
    const next = sessionListState[0];
    await setActiveSession(next?.id || null);
  } catch (error) {
    updateStatus(elements.healthStatus, `Не удалось удалить сессию: ${error.message || error}`, "error");
  }
}

function handleSessionListClick(event) {
  const card = event.target.closest(".session-item");
  if (!card) return;
  const sessionId = card.dataset.id;
  const action = event.target.closest("[data-action]")?.dataset?.action || "open";
  if (action === "delete") {
    deleteSessionById(sessionId);
  } else {
    setActiveSession(sessionId);
  }
}

function currentModelName() {
  return currentSessionModel || (elements.llmModelSelect?.value || "").trim();
}

function fillModelSettingsForm(bundle) {
  if (!bundle) return;
  const effective = bundle.effective || {};
  if (elements.temperatureInput) elements.temperatureInput.value = effective.temperature ?? "";
  if (elements.maxTokensInput) elements.maxTokensInput.value = effective.max_tokens ?? "";
  if (elements.numCtxInput) elements.numCtxInput.value = effective.num_ctx ?? "";
  if (elements.memTurnsInput) elements.memTurnsInput.value = effective.mem_turns ?? "";
  LIMITS.num_ctx = effective.num_ctx ?? null;
  LIMITS.max_tokens = effective.max_tokens ?? null;
  recalcStats();
  if (elements.modelSettingsStatus) {
    const overrides = bundle.overrides || {};
    const hasOverrides = Object.values(overrides).some((v) => v !== null && v !== undefined);
    elements.modelSettingsStatus.textContent = hasOverrides
      ? "Используются пользовательские настройки"
      : "Используются значения по умолчанию (.env)";
    elements.modelSettingsStatus.classList.toggle("status--success", hasOverrides);
  }
}

async function refreshModelSettings(modelName) {
  if (!activeProfileId || !modelName) return;
  const params = new URLSearchParams({ profile_id: String(activeProfileId), model_name: modelName });
  try {
    const response = await fetch(`${API_BASE}/model_settings?${params.toString()}`, { method: "GET" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    modelSettingsState = data;
    fillModelSettingsForm(data);
  } catch (error) {
    updateStatus(elements.modelSettingsStatus, "Не удалось получить настройки модели.", "error");
  }
}

async function saveModelSettings() {
  const model = currentModelName();
  if (!activeProfileId || !model) {
    updateStatus(elements.modelSettingsStatus, "Выберите профиль и модель.", "warning");
    return;
  }
  const payload = {
    profile_id: activeProfileId,
    model_name: model,
    temperature: elements.temperatureInput?.value ? Number(elements.temperatureInput.value) : null,
    max_tokens: elements.maxTokensInput?.value ? Number(elements.maxTokensInput.value) : null,
    num_ctx: elements.numCtxInput?.value ? Number(elements.numCtxInput.value) : null,
    mem_turns: elements.memTurnsInput?.value ? Number(elements.memTurnsInput.value) : null,
  };
  try {
    const response = await fetch(`${API_BASE}/model_settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    modelSettingsState = data;
    fillModelSettingsForm(data);
    updateStatus(elements.modelSettingsStatus, "Настройки модели сохранены.", "success");
  } catch (error) {
    updateStatus(elements.modelSettingsStatus, `Не удалось сохранить: ${error.message || error}`, "error");
  }
}

async function resetModelSettingsToDefaults() {
  const model = currentModelName();
  if (!activeProfileId || !model) {
    updateStatus(elements.modelSettingsStatus, "Выберите профиль и модель.", "warning");
    return;
  }
  try {
    const response = await fetch(`${API_BASE}/model_settings/reset_to_defaults`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: activeProfileId, model_name: model }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    modelSettingsState = data;
    fillModelSettingsForm(data);
    updateStatus(elements.modelSettingsStatus, "Настройки сброшены к значениям по умолчанию.", "success");
  } catch (error) {
    updateStatus(elements.modelSettingsStatus, `Не удалось сбросить настройки: ${error.message || error}`, "error");
  }
}

async function refreshDownloadStatuses({ silent = false } = {}) {
  try {
    const response = await fetch(`${API_BASE}/models/downloads`, { method: "GET" });
    if (!response.ok) return;
    const data = await response.json();
    const previous = modelState.downloads || [];
    modelState.downloads = Array.isArray(data?.downloads) ? data.downloads : [];
    renderDownloads();
    updateDownloadStatusIndicator();
    if (hasActiveDownloads()) {
      startDownloadPolling();
    } else {
      stopDownloadPolling();
    }

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
    const apiError = data?.error;
    modelState.installed = Array.isArray(data?.installed) ? data.installed : [];
    modelState.recommended = Array.isArray(data?.recommended) && data.recommended.length
      ? data.recommended
      : MODEL_RECOMMENDATIONS;
    modelState.downloads = Array.isArray(data?.downloads) ? data.downloads : modelState.downloads;
    updateModelSelect();
    renderModelSuggestions();
    renderDownloads();
    if (hasActiveDownloads()) {
      startDownloadPolling();
    } else {
      stopDownloadPolling();
    }
    const selected = elements.llmModelSelect?.value;
    if (apiError) {
      const message = typeof apiError === "string" ? apiError : apiError?.message || "Список моделей недоступен.";
      setModelStatus(`Не удалось получить список моделей: ${message}`, "error");
    } else if (selected) {
      setModelStatus(isModelInstalled(selected) ? `Локальная модель: ${selected}` : `Модель ${selected} не скачана`, isModelInstalled(selected) ? "success" : "warning");
    } else {
      setModelStatus("Добавьте или скачайте модель.", "warning");
    }
    syncModelActions();
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
    updateDownloadStatusIndicator();
    startDownloadPolling();
  } catch (error) {
    setModelStatus(`Не удалось запустить загрузку: ${error.message || error}`, "error");
  }
}

async function cancelModelDownload(taskId) {
  if (!taskId) return;
  try {
    const response = await fetch(`${API_BASE}/models/pull/${encodeURIComponent(taskId)}/cancel`, { method: "POST" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    modelState.downloads = (modelState.downloads || []).map((item) => (item.task_id === taskId ? data : item));
    renderDownloads();
  } catch (error) {
    setModelStatus(`Не удалось остановить загрузку: ${error.message || error}`, "error");
  }
}

function handleDownloadListClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  if (button.dataset.action === "cancel-download") {
    cancelModelDownload(button.dataset.task);
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

function stopDownloadPolling() {
  if (!downloadPollTimer) return;
  window.clearInterval(downloadPollTimer);
  downloadPollTimer = null;
}

function hasActiveDownloads() {
  return (modelState.downloads || []).some(
    (item) => item?.state === "running" || item?.state === "pending",
  );
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
  const text = (entry.text || entry.content || "").toString();
  const title = (entry.title || entry.name || "").toString().trim();
  const tsRaw = entry.updatedAt || entry.updated_at || entry.ts || entry.created_at;
  const tsNumber = Number(tsRaw);
  const parsedTs = Number.isFinite(tsNumber) ? tsNumber : Date.parse(tsRaw || "") || Date.now();
  const updatedAt = parsedTs;
  return {
    id: typeof entry.id === "string" ? entry.id : String(entry.id || createTranscriptId()),
    title: title || `Транскрипт ${new Date(parsedTs).toLocaleString()}`,
    text,
    timeline,
    roleKeywords: cloneRoleKeywords(entry.roleKeywords || entry.role_keywords),
    labels: cloneLabels(entry.labels),
    ts: parsedTs,
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
  void updateActiveTranscriptEntry(
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
  void updateActiveTranscriptEntry({ labels: timelineLabels }, { silent: true });
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

function formatTimecode(seconds) {
  if (!Number.isFinite(seconds)) return null;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds - mins * 60)
    .toString()
    .padStart(2, "0");
  return `${mins}:${secs}`;
}

function setTranscriptStatus(message, tone = "info") {
  if (!elements.transcriptStatus) return;
  updateStatus(elements.transcriptStatus, message, tone);
}

function renderTranscriptLibrary() {
  if (!elements.transcriptList) return;
  renderTranscriptHistory();
}

function renderTranscriptHistoryContent(entry) {
  if (!entry) return "";
  const items =
    (Array.isArray(entry.timeline) && entry.timeline.length
      ? entry.timeline
      : buildTextTimelineFromTranscript(entry.text)
    ).slice(0, 120);
  if (!items.length) {
    return '<div class="muted">Нет текста для отображения.</div>';
  }
  return items
    .map((item) => {
      const time = formatTimecode(item.start) || formatTimecode(item.end);
      const labelParts = [];
      if (time) labelParts.push(time);
      if (item.speaker) labelParts.push(item.speaker);
      const meta = labelParts.length ? labelParts.join(" • ") : "Без подписи";
      const text = escapeHtml((item.text || "").trim());
      return `
        <div class="transcript-history__line">
          <div class="transcript-history__line-meta muted">${escapeHtml(meta)}</div>
          <div class="transcript-history__line-text">${text || "—"}</div>
        </div>
      `;
    })
    .join("\n");
}

function showTranscriptHistoryDetails(entry) {
  if (!elements.transcriptHistoryDetails) return;
  if (!entry) {
    selectedTranscriptHistoryId = null;
    elements.transcriptHistoryDetails.setAttribute("hidden", "");
    if (elements.transcriptHistoryHeading) {
      elements.transcriptHistoryHeading.textContent = "Транскрипция";
    }
    return;
  }

  selectedTranscriptHistoryId = entry.id;
  if (elements.transcriptHistoryHeading) {
    elements.transcriptHistoryHeading.textContent = entry.title || "Транскрипция";
  }
  elements.transcriptHistoryDetails.removeAttribute("hidden");
  if (elements.transcriptHistoryTitle) {
    elements.transcriptHistoryTitle.value = entry.title || "";
  }
  if (elements.transcriptHistoryMeta) {
    const hasTiming = hasTimelineTiming(entry.timeline);
    const updatedAt = tsFmt(entry.updatedAt || entry.ts);
    elements.transcriptHistoryMeta.textContent = `${updatedAt} • Символов: ${(entry.text || "").length} • ${
      hasTiming ? "с таймингами" : "без таймингов"
    }`;
  }
  if (elements.transcriptHistoryContent) {
    elements.transcriptHistoryContent.innerHTML = renderTranscriptHistoryContent(entry);
  }
}

function closeTranscriptHistoryModal() {
  elements.transcriptHistoryOverlay?.classList.remove("overlay--visible");
  if (elements.transcriptHistoryDetails) {
    elements.transcriptHistoryDetails.setAttribute("hidden", "");
  }
}

function refreshTranscriptHistoryModal() {
  if (!elements.transcriptHistoryOverlay?.classList.contains("overlay--visible")) return;
  const entry = selectedTranscriptHistoryId ? findTranscriptEntry(selectedTranscriptHistoryId) : null;
  if (entry) {
    showTranscriptHistoryDetails(entry);
  } else {
    closeTranscriptHistoryModal();
  }
}

function openTranscriptHistoryModal(entry) {
  const target =
    entry ||
    (selectedTranscriptHistoryId ? findTranscriptEntry(selectedTranscriptHistoryId) : null) ||
    (activeTranscriptId ? findTranscriptEntry(activeTranscriptId) : null) ||
    transcriptLibrary[0];
  if (!target) {
    setTranscriptStatus("Транскрипции пока нет. Сначала сохраните текст или распознайте файл.", "warning");
    return;
  }
  showTranscriptHistoryDetails(target);
  elements.transcriptHistoryOverlay?.classList.add("overlay--visible");
}

function renderTranscriptHistory() {
  if (!elements.transcriptHistoryList) return;
  if (!Array.isArray(transcriptLibrary) || !transcriptLibrary.length) {
    selectedTranscriptHistoryId = null;
    elements.transcriptHistoryList.innerHTML =
      '<div class="muted">Транскрипции появятся после распознавания или сохранения текста.</div>';
    showTranscriptHistoryDetails(null);
    closeTranscriptHistoryModal();
    return;
  }

  const html = transcriptLibrary
    .map(
      (entry) => `
        <article class="transcript-history__item" data-id="${escapeHtml(entry.id)}">
          <div class="transcript-history__main">
            <div class="transcript-history__title" title="${escapeHtml(entry.title)}">${escapeHtml(entry.title)}</div>
            <div class="transcript-history__meta">${escapeHtml(
              `${tsFmt(entry.updatedAt || entry.ts)} • Символов: ${(entry.text || "").length} • ${
                hasTimelineTiming(entry.timeline) ? "с таймингами" : "без таймингов"
              }`,
            )}</div>
          </div>
          <div class="transcript-history__controls">
            <button type="button" data-action="use">Использовать</button>
            <button class="secondary" type="button" data-action="edit">Редактировать</button>
            <button class="warn" type="button" data-action="delete">Удалить</button>
          </div>
        </article>
      `,
    )
    .join("");

  elements.transcriptHistoryList.innerHTML = html;
  const preferred =
    (selectedTranscriptHistoryId && findTranscriptEntry(selectedTranscriptHistoryId)) ||
    (activeTranscriptId && findTranscriptEntry(activeTranscriptId)) ||
    transcriptLibrary[0];
  if (!selectedTranscriptHistoryId && preferred) {
    selectedTranscriptHistoryId = preferred.id;
  }
  refreshTranscriptHistoryModal();
}

function sortTranscriptLibrary() {
  transcriptLibrary.sort((a, b) => (b.updatedAt || b.ts) - (a.updatedAt || a.ts));
}

async function loadTranscriptLibrary({ silent = false } = {}) {
  if (!activeProfileId) {
    transcriptLibrary = [];
    renderTranscriptLibrary();
    return;
  }
  try {
    const params = new URLSearchParams({ profile_id: String(activeProfileId) });
    if (currentSessionId) params.append("session_id", currentSessionId);
    const response = await fetch(`${API_BASE}/transcripts?${params.toString()}`, { method: "GET" });
    const data = await response.json();
    const items = Array.isArray(data?.transcripts) ? data.transcripts : [];
    transcriptLibrary = items.map((entry) => normalizeTranscriptEntry(entry)).filter(Boolean);
    sortTranscriptLibrary();
    if (transcriptLibrary.length > TRANSCRIPT_LIBRARY_LIMIT) {
      transcriptLibrary = transcriptLibrary.slice(0, TRANSCRIPT_LIBRARY_LIMIT);
    }
    renderTranscriptLibrary();
  } catch (error) {
    if (!silent) {
      setTranscriptStatus("Не удалось загрузить транскрипты для профиля.", "error");
    }
  }
}

async function addTranscriptEntry(entry, { makeActive = false, announce = true } = {}) {
  if (!activeProfileId) {
    setTranscriptStatus("Сначала выберите профиль.", "warning");
    return null;
  }
  const normalized = normalizeTranscriptEntry(entry);
  if (!normalized) return null;
  const payload = {
    profile_id: activeProfileId,
    session_id: currentSessionId || null,
    name: normalized.title,
    content: normalized.text,
    language: null,
    timeline: normalized.timeline,
    role_keywords: normalized.roleKeywords,
    labels: normalized.labels,
  };
  try {
    const response = await fetch(`${API_BASE}/transcripts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const saved = normalizeTranscriptEntry({ ...normalized, ...data, title: data?.name, text: data?.content });
    transcriptLibrary = [saved, ...transcriptLibrary.filter((item) => item.id !== saved.id)];
    sortTranscriptLibrary();
    if (transcriptLibrary.length > TRANSCRIPT_LIBRARY_LIMIT) {
      transcriptLibrary = transcriptLibrary.slice(0, TRANSCRIPT_LIBRARY_LIMIT);
    }
    if (makeActive) {
      activeTranscriptId = saved.id;
    }
    if (makeActive || !selectedTranscriptHistoryId) {
      selectedTranscriptHistoryId = saved.id;
    }
    renderTranscriptLibrary();
    if (announce) {
      setTranscriptStatus(`Транскрипт «${saved.title}» сохранён.`, "success");
    }
    return saved;
  } catch (error) {
    setTranscriptStatus(`Не удалось сохранить транскрипт: ${error.message || error}`, "error");
    return null;
  }
}

async function addTranscriptFromHistoryPrompt() {
  if (!activeProfileId) {
    setTranscriptStatus("Сначала выберите профиль.", "warning");
    return;
  }
  const text = window.prompt("Вставьте текст транскрипта") || "";
  const cleaned = text.trim();
  if (!cleaned) return;
  const title = window.prompt("Название транскрипта", suggestTranscriptTitle({ manual: true })) || "";
  const entry = newTranscriptEntry({
    title: title.trim() || suggestTranscriptTitle({ manual: true }),
    text: cleaned,
    timeline: buildTextTimelineFromTranscript(cleaned),
    roleKeywords: {},
    labels: {},
  });
  const saved = await addTranscriptEntry(entry, { makeActive: true, announce: false });
  if (saved) {
    renderTranscriptHistory();
    showTranscriptHistoryDetails(saved);
    setTranscriptStatus(`Транскрипт «${saved.title}» добавлен.`, "success");
  }
}

async function updateActiveTranscriptEntry(patch = {}, { silent = false, targetId = null } = {}) {
  const id = targetId || activeTranscriptId;
  if (!id) return;
  const index = transcriptLibrary.findIndex((item) => item.id === id);
  if (index === -1) return;
  const base = transcriptLibrary[index];
  const next = normalizeTranscriptEntry({
    ...base,
    ...patch,
    id: base.id,
    ts: base.ts,
    updatedAt: Date.now(),
  });
  try {
    const response = await fetch(`${API_BASE}/transcripts/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: next.title,
        content: next.text,
        timeline: next.timeline,
        role_keywords: next.roleKeywords,
        labels: next.labels,
      }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    transcriptLibrary[index] = next;
    sortTranscriptLibrary();
    if (targetId) {
      selectedTranscriptHistoryId = targetId;
    }
    renderTranscriptLibrary();
    if (!silent) {
      setTranscriptStatus(`Транскрипт «${next.title}» обновлён.`, "success");
    }
  } catch (error) {
    if (!silent) {
      setTranscriptStatus(`Не удалось обновить транскрипт: ${error.message || error}`, "error");
    }
  }
}

async function deleteTranscriptEntry(id) {
  if (!id) return;
  const index = transcriptLibrary.findIndex((item) => item.id === id);
  if (index === -1) return;
  const wasSelected = selectedTranscriptHistoryId === id;
  try {
    const response = await fetch(`${API_BASE}/transcripts/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const [removed] = transcriptLibrary.splice(index, 1);
    if (activeTranscriptId === id) {
      activeTranscriptId = null;
    }
    if (wasSelected) {
      selectedTranscriptHistoryId = transcriptLibrary[0]?.id || null;
    }
    renderTranscriptLibrary();
    if (wasSelected) {
      closeTranscriptHistoryModal();
    } else {
      refreshTranscriptHistoryModal();
    }
    setTranscriptStatus(`Транскрипт «${removed.title}» удалён.`, "warning");
  } catch (error) {
    setTranscriptStatus(`Не удалось удалить транскрипт: ${error.message || error}`, "error");
  }
}

function applyTranscriptEntry(entry, { focusTimeline = true, announce = true } = {}) {
  if (!entry) return false;
  activeTranscriptId = entry.id;
  selectedTranscriptHistoryId = entry.id;
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

async function useManualTranscript({ save = false } = {}) {
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
    await addTranscriptEntry(entry, { makeActive: true, announce: true });
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

function handleTranscriptHistoryClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const item = button.closest(".transcript-history__item");
  if (!item) return;
  const id = item.dataset.id;
  if (!id) return;
  const entry = findTranscriptEntry(id);
  if (!entry) {
    setTranscriptStatus("Не удалось найти транскрипт в истории.", "error");
    return;
  }

  const action = button.dataset.action;
  if (action === "use") {
    applyTranscriptEntry(entry, { focusTimeline: true, announce: true });
    renderTranscriptHistory();
    return;
  }

  if (action === "edit") {
    openTranscriptHistoryModal(entry);
    return;
  }

  if (action === "delete") {
    const confirmed = window.confirm("Удалить сохранённый транскрипт?");
    if (confirmed) {
      deleteTranscriptEntry(entry.id);
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

function openSettings() {
  elements.settingsOverlay?.classList.add("overlay--visible");
}

function closeSettings() {
  elements.settingsOverlay?.classList.remove("overlay--visible");
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
  if (!activeProfileId) {
    updateStatus(elements.healthStatus, "Сначала выберите профиль.", "warning");
    return;
  }
  const rawQuery = elements.prompt?.value || "";
  const finalQuery = rawQuery.trim() || "проанализируй";

  const selectedModel = (elements.llmModelSelect?.value || "").trim();
  const targetModel = currentSessionModel || selectedModel;
  if (targetModel) {
    const available = await ensureModelAvailability(targetModel);
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
    const payload = { query: finalQuery, profile_id: activeProfileId };
    if (currentSessionId) {
      payload.session_id = currentSessionId;
    }
    const transcript = currentTranscript.trim();
    if (transcript) {
      payload.transcript = transcript;
    }
    const criteria = criteriaManager.getCriteria();
    if (criteria.length) {
      payload.criteria = criteria;
    }
    if (!currentSessionId && targetModel) {
      payload.model = targetModel;
      setSavedLlmModel(targetModel);
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

    if (data.session_id) {
      currentSessionId = data.session_id;
      setLastChatSessionId(currentSessionId);
    }
    if (data.model_name) {
      currentSessionModel = data.model_name;
    }
    if (data.used_settings) {
      LIMITS.num_ctx = data.used_settings.num_ctx ?? LIMITS.num_ctx;
      LIMITS.max_tokens = data.used_settings.max_tokens ?? LIMITS.max_tokens;
    }
    await loadSessionsForProfile(activeProfileId);
    if (currentSessionId) {
      await setActiveSession(currentSessionId, { refreshOnly: true });
    }

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
  if (!activeProfileId) {
    updateStatus(elements.transcribeStatus, "выберите профиль перед транскрибацией", "error");
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
    if (currentSessionId) {
      formData.append("session_id", currentSessionId);
    }
    formData.append("profile_id", activeProfileId);

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
    await addTranscriptEntry(entry, { makeActive: true, announce: false });
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

  elements.btnProfile?.addEventListener("click", () => openProfileModal());
  elements.btnCloseProfileModal?.addEventListener("click", () => closeProfileModal());
  elements.profileOverlay?.addEventListener("click", (event) => {
    if (event.target === elements.profileOverlay) {
      closeProfileModal();
    }
  });
  elements.profileList?.addEventListener("click", handleProfileListClick);
  elements.btnModalNewProfile?.addEventListener("click", () => createProfileFlow());
  elements.btnNewSession?.addEventListener("click", () => createSessionFlow());
  elements.sessionList?.addEventListener("click", handleSessionListClick);
  elements.btnToggleSidebar?.addEventListener("click", () => toggleSidebar());

  elements.llmModelSelect?.addEventListener("change", async () => {
    const value = (elements.llmModelSelect.value || "").trim();
    if (value) {
      setSavedLlmModel(value);
      const available = await ensureModelAvailability(value);
      if (available) {
        setModelStatus(isModelInstalled(value) ? `Локальная модель: ${value}` : `Модель ${value} не скачана`, isModelInstalled(value) ? "success" : "warning");
        if (!currentSessionId) {
          currentSessionModel = value;
        }
        await refreshModelSettings(value);
      }
    }
    syncModelActions();
  });
  elements.btnRefreshModels?.addEventListener("click", () => fetchModelList());
  elements.btnDeleteModel?.addEventListener("click", () => deleteSelectedModel());
  elements.modelSuggestions?.addEventListener("click", async (event) => {
    const chip = event.target.closest("[data-model]");
    if (!chip) return;
    const model = chip.dataset.model;
    if (!model) return;
    const installed = chip.dataset.installed === "1";
    if (elements.llmModelSelect && elements.llmModelSelect.value !== model) {
      const optionExists = Array.from(elements.llmModelSelect.options).some((opt) => opt.value === model);
      if (!optionExists) {
        updateModelSelect(model);
      }
      elements.llmModelSelect.value = model;
      setSavedLlmModel(model);
    }
    if (installed) {
      setModelStatus(`Локальная модель: ${model}`, "success");
      return;
    }
    await startModelDownload(model);
  });

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
  elements.btnCloseTranscriptHistory?.addEventListener("click", closeTranscriptHistoryModal);
  elements.transcriptHistoryOverlay?.addEventListener("click", (event) => {
    if (event.target === elements.transcriptHistoryOverlay) {
      closeTranscriptHistoryModal();
    }
  });
  elements.btnSettings?.addEventListener("click", () => {
    openSettings();
    renderTranscribeDefaults();
  });
  elements.btnCloseSettings?.addEventListener("click", closeSettings);
  elements.settingsOverlay?.addEventListener("click", (event) => {
    if (event.target === elements.settingsOverlay) {
      closeSettings();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (elements.transcriptHistoryOverlay?.classList.contains("overlay--visible")) {
      closeTranscriptHistoryModal();
      return;
    }
    if (elements.profileOverlay?.classList.contains("overlay--visible")) {
      closeProfileModal();
      return;
    }
    if (elements.helpOverlay?.classList.contains("overlay--visible")) {
      elements.helpOverlay.classList.remove("overlay--visible");
      return;
    }
    if (elements.settingsOverlay?.classList.contains("overlay--visible")) {
      closeSettings();
      return;
    }
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

  elements.btnSaveModelSettings?.addEventListener("click", () => saveModelSettings());
  elements.btnResetModelSettings?.addEventListener("click", () => resetModelSettingsToDefaults());

  elements.btnLoadCriteriaFile?.addEventListener("click", async () => {
    const file = elements.criteriaFileInput?.files?.[0];
    if (!file) {
      criteriaManager.updateStatus("Выберите CSV или XLSX файл для загрузки.", "error");
      return;
    }
    try {
      await criteriaManager.requestFromBackend({
        apiBase: API_BASE,
        sessionId: currentSessionId,
        profileId: activeProfileId,
        file,
      });
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
        sessionId: currentSessionId,
        profileId: activeProfileId,
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

  elements.modelSelect?.addEventListener("change", () => {
    setSavedModel(elements.modelSelect.value);
    renderTranscribeDefaults();
  });

  elements.promptPresetSelect?.addEventListener("change", () => {
    setSavedPromptPreset(elements.promptPresetSelect.value);
    renderTranscribeDefaults();
  });

  elements.btnTranscribe?.addEventListener("click", (event) => {
    event.preventDefault();
    transcribeFile();
  });

  elements.btnUseManualTranscript?.addEventListener("click", () => {
    void useManualTranscript({ save: false });
  });

  elements.btnSaveManualTranscript?.addEventListener("click", () => {
    void useManualTranscript({ save: true });
  });

  elements.transcriptList?.addEventListener("click", handleTranscriptListClick);
  elements.downloadList?.addEventListener("click", handleDownloadListClick);
  elements.transcriptHistoryList?.addEventListener("click", handleTranscriptHistoryClick);
  elements.btnApplyTranscriptFromHistory?.addEventListener("click", () => {
    const entry = selectedTranscriptHistoryId ? findTranscriptEntry(selectedTranscriptHistoryId) : null;
    if (!entry) {
      setTranscriptStatus("Выберите транскрипцию из списка.", "warning");
      return;
    }
    applyTranscriptEntry(entry, { focusTimeline: true, announce: true });
    renderTranscriptHistory();
    closeTranscriptHistoryModal();
  });
  elements.btnSaveTranscriptHistoryTitle?.addEventListener("click", () => {
    const entry = selectedTranscriptHistoryId ? findTranscriptEntry(selectedTranscriptHistoryId) : null;
    const title = elements.transcriptHistoryTitle?.value?.trim();
    if (!entry) {
      setTranscriptStatus("Выберите транскрипцию для переименования.", "warning");
      return;
    }
    if (!title) {
      setTranscriptStatus("Введите название транскрибации.", "error");
      return;
    }
    updateActiveTranscriptEntry({ title }, { targetId: entry.id }).then(() => {
      showTranscriptHistoryDetails(findTranscriptEntry(entry.id));
    });
  });
  elements.btnDeleteTranscriptFromHistory?.addEventListener("click", () => {
    const entry = selectedTranscriptHistoryId ? findTranscriptEntry(selectedTranscriptHistoryId) : null;
    if (!entry) {
      setTranscriptStatus("Выберите транскрипцию для удаления.", "warning");
      return;
    }
    if (!window.confirm("Удалить сохранённый транскрипт?")) return;
    deleteTranscriptEntry(entry.id);
  });
  elements.btnAddTranscriptHistoryEntry?.addEventListener("click", () => addTranscriptFromHistoryPrompt());

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

  elements.btnHelp?.addEventListener("click", () => {
    elements.helpOverlay?.classList.add("overlay--visible");
  });
  elements.btnCloseHelp?.addEventListener("click", () => {
    elements.helpOverlay?.classList.remove("overlay--visible");
  });
  elements.helpOverlay?.addEventListener("click", (event) => {
    if (event.target === elements.helpOverlay) {
      elements.helpOverlay.classList.remove("overlay--visible");
    }
  });
}

async function init() {
  if (elements.modelSelect) {
    elements.modelSelect.value = getSavedModel(elements.modelSelect.value || "medium");
    setSavedModel(elements.modelSelect.value);
  }

  if (elements.promptPresetSelect) {
    elements.promptPresetSelect.value = getSavedPromptPreset(elements.promptPresetSelect.value || "none");
    setSavedPromptPreset(elements.promptPresetSelect.value);
  }

  updateModelSelect(getSavedLlmModel());
  renderModelSuggestions();
  attachEvents();
  await fetchProfilesAndInit();
  fetchModelList();

  const savedPrefix = getHrPrefix(DEFAULT_HR_PREFIX);
  if (elements.hrPrefixInput) {
    elements.hrPrefixInput.value = savedPrefix || DEFAULT_HR_PREFIX;
  }

  renderTranscribeDefaults();
  setTranscriptStatus("", "info");
  clearTimelineState();
  criteriaManager.loadFromStorage();

  checkHealth();
  activateTab("answer");
  recalcStats();
}

init();
