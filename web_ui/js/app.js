import {
  API_BASE,
  addHistoryEntry,
  clearPinnedContext,
  deleteHistoryEntry,
  ensureSessionId,
  getHrPrefix,
  getPinnedContext,
  getSavedModel,
  loadHistory,
  saveHistory,
  setHrPrefix,
  setPinnedContext,
  setSavedModel,
} from "./storage.js";
import { renderRoleLegend, renderTimeline } from "./timeline.js";
import { CriteriaManager } from "./criteria.js";

const DEFAULT_HR_PREFIX = "Нейро-HR";

const LIMITS = { num_ctx: null, max_tokens: null };

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
  contextStats: getElement("contextStats"),
  btnSend: getElement("btnSend"),
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
  timelineContainer: getElement("timelineContainer"),
  timelineLegend: getElement("timelineLegend"),
  contextText: getElement("contextText"),
  btnSaveContext: getElement("btnSaveContext"),
  btnPinFromPrompt: getElement("btnPinFromPrompt"),
  btnClearPinnedContext: getElement("btnClearPinnedContext"),
  contextStatus: getElement("contextStatus"),
  hrPrefixInput: getElement("hrPrefix"),
  modelSelect: getElement("modelSelect"),
  promptPresetSelect: getElement("promptPresetSelect"),
  criteriaFileInput: getElement("criteriaFile"),
  btnLoadCriteriaFile: getElement("btnLoadCriteriaFile"),
  btnLoadCriteriaSheet: getElement("btnLoadCriteriaSheet"),
  btnCriteriaFromContext: getElement("btnCriteriaFromContext"),
  btnClearCriteria: getElement("btnClearCriteria"),
  googleSheetInput: getElement("googleSheetInput"),
  criteriaStatus: getElement("criteriaStatus"),
  criteriaList: getElement("criteriaList"),
  budgetStats: getElement("budgetStats"),
};

const sessionId = ensureSessionId();
let currentTranscript = "";
const transcribeBusyState = { defaultLabel: null };

const criteriaManager = new CriteriaManager({
  listEl: elements.criteriaList,
  statusEl: elements.criteriaStatus,
});

function recalcStats() {
  const prompt = elements.prompt?.value || "";
  const ctx = elements.contextText?.value || "";
  const promptTokens = estTokens(prompt);
  const contextTokens = estTokens(ctx);
  const inputTokens = promptTokens + contextTokens;

  if (elements.promptStats) {
    elements.promptStats.textContent = `Символы: ${prompt.length} • Токены≈ ${promptTokens}`;
  }
  if (elements.contextStats) {
    elements.contextStats.textContent = `Символы: ${ctx.length} • Токены≈ ${contextTokens}`;
  }

  if (elements.budgetStats) {
    const numCtx = LIMITS.num_ctx ?? "—";
    const maxOut = LIMITS.max_tokens ?? "—";
    let line = `Входные токены: ${inputTokens} • Резерв на ответ: ${maxOut} • Лимит контекста: ${numCtx}`;
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
  if (!elements.btnSend) return;
  elements.btnSend.disabled = Boolean(isBusy);
  elements.btnSend.textContent = isBusy ? "Отправка…" : "Отправить";
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

function updateContextStatus() {
  const value = (getPinnedContext() || "").trim();
  const length = value.length;
  if (length) {
    updateStatus(elements.contextStatus, `Контекст закреплён (${length} символов)`, "success");
  } else {
    updateStatus(elements.contextStatus, "Контекст не закреплён");
  }
}

async function sendPrompt() {
  const rawQuery = elements.prompt?.value || "";
  const finalQuery = rawQuery.trim() || "проанализируй";

  setBusy(true);
  if (elements.answer) {
    elements.answer.value = "Думаю…";
  }

  try {
    const payload = { query: finalQuery, session_id: sessionId };
    const pinnedContext = getPinnedContext().trim();
    if (pinnedContext) {
      payload.context = pinnedContext;
    }
    const transcript = currentTranscript.trim();
    if (transcript) {
      payload.transcript = transcript;
    }
    const criteria = criteriaManager.getCriteria();
    if (criteria.length) {
      payload.criteria = criteria;
    }

    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
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
    if (elements.answer) {
      elements.answer.value = `Ошибка: ${error.message || error}`;
    }
  } finally {
    setBusy(false);
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
    renderTimeline(elements.timelineContainer);
    renderRoleLegend(elements.timelineLegend);

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

    renderTimeline(elements.timelineContainer, timeline);
    renderRoleLegend(elements.timelineLegend, roleKeywords);

    updateStatus(
      elements.transcribeStatus,
      `✅ Транскрипция готова — модель: ${model}, символов: ${transcript.length}`,
      "success",
    );
    recalcStats();
  } catch (error) {
    updateStatus(elements.transcribeStatus, `❌ ошибка: ${error.message || error}`, "error");
  } finally {
    setTranscribeBusy(false);
  }
}

function attachEvents() {
  elements.prompt?.addEventListener("input", debounce(recalcStats, 100));
  elements.contextText?.addEventListener("input", debounce(recalcStats, 100));

  elements.btnSend?.addEventListener("click", sendPrompt);
  elements.prompt?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendPrompt();
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

  elements.btnSaveContext?.addEventListener("click", () => {
    const value = (elements.contextText?.value || "").trim();
    setPinnedContext(value);
    updateContextStatus();
  });

  elements.btnPinFromPrompt?.addEventListener("click", () => {
    const value = (elements.prompt?.value || "").trim();
    if (elements.contextText) {
      elements.contextText.value = value;
    }
    setPinnedContext(value);
    updateContextStatus();
    recalcStats();
  });

  elements.btnClearPinnedContext?.addEventListener("click", () => {
    clearPinnedContext();
    if (elements.contextText) {
      elements.contextText.value = "";
    }
    updateContextStatus();
    recalcStats();
  });

  elements.btnLoadCriteriaFile?.addEventListener("click", async () => {
    const file = elements.criteriaFileInput?.files?.[0];
    if (!file) {
      criteriaManager.updateStatus("Выберите CSV или XLSX файл для загрузки.", "error");
      return;
    }
    try {
      await criteriaManager.requestFromBackend({ apiBase: API_BASE, sessionId, file });
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

  elements.btnCriteriaFromContext?.addEventListener("click", async () => {
    const ctx = (elements.contextText?.value || "").trim();
    if (!ctx) {
      criteriaManager.updateStatus("Контекст пустой — нечего извлекать.", "error");
      return;
    }
    try {
      await criteriaManager.requestFromBackend({ apiBase: API_BASE, sessionId, rawText: ctx });
    } catch (error) {
      console.warn("criteria from context failed", error);
    }
  });

  elements.btnClearCriteria?.addEventListener("click", () => {
    criteriaManager.clear();
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
}

function init() {
  const savedModel = getSavedModel("medium");
  if (elements.modelSelect) {
    elements.modelSelect.value = savedModel;
    elements.modelSelect.addEventListener("change", () => {
      setSavedModel(elements.modelSelect.value);
    });
  }

  if (elements.promptPresetSelect) {
    // placeholder for future logic if needed
  }

  const storedContext = getPinnedContext();
  if (elements.contextText) {
    elements.contextText.value = storedContext;
  }
  updateContextStatus();

  const savedPrefix = getHrPrefix(DEFAULT_HR_PREFIX);
  if (elements.hrPrefixInput) {
    elements.hrPrefixInput.value = savedPrefix || DEFAULT_HR_PREFIX;
  }

  renderTimeline(elements.timelineContainer);
  renderRoleLegend(elements.timelineLegend);
  criteriaManager.renderCriteria();
  criteriaManager.updateStatus("Критерии не выбраны.");
  criteriaManager.loadFromStorage();

  attachEvents();
  checkHealth();
  recalcStats();
}

init();
