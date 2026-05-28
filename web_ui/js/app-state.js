import { API_BASE, getHrPrefix, getLastChatSessionId, getLastProfileId } from "./storage.js";
import { renderRoleLegend, renderTimeline } from "./timeline.js";
import { CriteriaManager } from "./criteria.js";

export const DEFAULT_HR_PREFIX = "Нейро-HR";
export const LIMITS = { num_ctx: null, max_tokens: null };
export const TRANSCRIPT_LIBRARY_LIMIT = 20;
export const MODEL_CATALOG = [
  {
    id: "qwen2.5:3b-instruct",
    title: "Qwen 2.5 3B Instruct",
    category: "fast_rag",
    weight: "light",
    recommended: true,
    experimental: false,
    description: "Быстрый слой: RAG, короткие ответы и быстрые уточнения. Для ASR pipeline это fallback, когда важна скорость, а не качество длинной встречи.",
  },
  {
    id: "qwen2.5:7b-instruct",
    title: "Qwen 2.5 7B Instruct",
    category: "default_chat",
    weight: "medium",
    recommended: true,
    experimental: false,
    description: "Основная рабочая модель: обычный чат, RAG с нормальным качеством, рабочие формулировки, summary среднего размера.",
  },
  {
    id: "qwen3:8b",
    title: "Qwen 3 8B",
    category: "thinking",
    weight: "medium",
    recommended: true,
    experimental: false,
    description: "Thinking/reasoning-модель: сложные вопросы, анализ, проверка логики, ситуации где нужно подумать, а не быстро ответить.",
  },
  {
    id: "mistral-nemo:12b",
    title: "Mistral Nemo 12B",
    category: "pipeline_heavy",
    weight: "heavy",
    recommended: true,
    experimental: false,
    description: "Тяжёлая модель для pipeline: summary, structuring, выделение decisions/tasks/risks/open questions. На M1 Pro 16GB может работать медленнее.",
  },
  {
    id: "qwen2.5-coder:7b",
    title: "Qwen 2.5 Coder 7B",
    category: "code",
    weight: "medium",
    recommended: true,
    experimental: false,
    description: "Основная модель для кода: Python, FastAPI, JavaScript, Docker, отладка, рефакторинг и анализ ошибок.",
  },
  {
    id: "deepseek-coder:6.7b",
    title: "DeepSeek Coder 6.7B",
    category: "code_alt",
    weight: "medium",
    recommended: true,
    experimental: false,
    description: "Альтернативная кодовая модель для сравнения с Qwen Coder. Полезна для проверки решений, генерации патчей и разбора ошибок.",
  },
  {
    id: "qwen3:4b",
    title: "Qwen 3 4B",
    category: "experimental",
    weight: "light_medium",
    recommended: false,
    experimental: true,
    description: "Экспериментальная модель: компромисс между qwen2.5 3B и qwen3 8B. Проверить как быстрый reasoning/RAG fallback.",
  },
];
export const MODEL_RECOMMENDATIONS = MODEL_CATALOG.map((item) => ({
  ...item,
  name: item.id,
  label: item.title,
}));
export const SIDEBAR_STATE_KEY = "localgpt_sidebar_collapsed";

const getElement = (id) => document.getElementById(id);

export const elements = {
  prompt: getElement("prompt"),
  answer: getElement("answer"),
  promptStats: getElement("promptStats"),
  btnProfile: getElement("btnProfile"),
  profileLabel: getElement("profileLabel"),
  profileTitle: getElement("profileTitle"),
  btnSidebarHeader: getElement("btnSidebarHeader"),
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
  transcriptHistoryBody: getElement("transcriptHistoryBody"),
  transcriptHistoryContent: getElement("transcriptHistoryContent"),
  btnApplyTranscriptFromHistory: getElement("btnApplyTranscriptFromHistory"),
  btnSaveTranscriptFromHistory: getElement("btnSaveTranscriptFromHistory"),
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
  roleSelect: getElement("roleSelect"),
  roleTooltip: getElement("roleTooltip"),
  themeToggle: getElement("themeToggle"),
  modelsDirInput: getElement("modelsDirInput"),
  btnApplyModelsDir: getElement("btnApplyModelsDir"),
  btnMoveModelsDir: getElement("btnMoveModelsDir"),
};

export const tabButtons = Array.from(document.querySelectorAll("[data-tab-target]"));
export const tabPanels = Array.from(document.querySelectorAll("[data-panel]"));

export const state = {
  profileList: [],
  activeProfileId: null,
  sessionList: [],
  currentSessionId: getLastChatSessionId(),
  currentSessionModel: null,
  currentTranscript: "",
  currentTimeline: [],
  originalTimeline: [],
  timelineEditMode: false,
  currentRoleKeywords: {},
  timelineLabels: {},
  transcribeBusyState: { defaultLabel: null },
  chatState: { controller: null },
  activeTranscriptId: null,
  transcriptLibrary: [],
  selectedTranscriptHistoryId: null,
  transcriptEditorMode: "view",
  modelState: { installed: [], recommended: MODEL_RECOMMENDATIONS, downloads: [] },
  downloadPollTimer: null,
  modelSettingsState: { effective: {}, overrides: {}, defaults: {} },
  roles: [],
  currentRole: "free",
};

export function estTokens(value) {
  return Math.ceil(((value || "").length) / 4.2);
}

export function debounce(fn, ms = 150) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), ms);
  };
}

export function updateStatus(node, message, tone = "info") {
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

export function createCriteriaManager() {
  return new CriteriaManager({
    listEl: elements.criteriaList,
    statusEl: elements.criteriaStatus,
  });
}

export { API_BASE, renderRoleLegend, renderTimeline, getHrPrefix, getLastProfileId };
