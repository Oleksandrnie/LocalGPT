import {
  createTranscript,
  deleteTranscriptApi,
  listTranscripts,
  parseCriteria,
  transcribeFile,
} from "./api.js";
import { elements, state, updateStatus, renderTimeline, renderRoleLegend } from "./app-state.js";
import { getSavedModel, getSavedPromptPreset, setSavedModel, setSavedPromptPreset } from "./storage.js";
import { recalcStats } from "./chat.js";

function hasTimelineTiming(items) {
  return Array.isArray(items) && items.some((item) => Number.isFinite(item?.start) || Number.isFinite(item?.end));
}

function renderTimelineView() {
  if (!elements.timelineContainer || !elements.timelineNotice || !elements.timelineLegend) return;
  const hasTiming = hasTimelineTiming(state.currentTimeline);
  if (!state.currentTimeline.length) {
    elements.timelineNotice.textContent = "Таймлайн появится после транскрибации.";
  } else if (!hasTiming) {
    elements.timelineNotice.textContent = "Тайминги не найдены, отображается текстовый таймлайн.";
  } else {
    elements.timelineNotice.textContent = "";
  }
  renderRoleLegend(elements.timelineLegend, state.currentRoleKeywords, state.timelineLabels);
  renderTimeline(elements.timelineContainer, state.currentTimeline, { labels: state.timelineLabels });
}

function setTranscript(text, timeline = [], roleKeywords = {}, labels = {}) {
  state.currentTranscript = text || "";
  state.currentTimeline = Array.isArray(timeline) ? timeline : [];
  state.currentRoleKeywords = roleKeywords || {};
  state.timelineLabels = labels || {};
  if (elements.manualTranscriptInput) {
    elements.manualTranscriptInput.value = state.currentTranscript;
  }
  renderTimelineView();
  recalcStats();
}

async function saveTranscript(name, content) {
  if (!state.activeProfileId) return null;
  const payload = {
    profile_id: state.activeProfileId,
    session_id: state.currentSessionId || undefined,
    name,
    content,
    timeline: state.currentTimeline,
    role_keywords: state.currentRoleKeywords,
    labels: state.timelineLabels,
  };
  return createTranscript(payload);
}

function renderTranscribeDefaults() {
  if (!elements.transcribeDefaults) return;
  const model = elements.modelSelect?.value || "";
  const preset = elements.promptPresetSelect?.value || "";
  elements.transcribeDefaults.textContent = `Модель: ${model || "medium"} • Промпт: ${preset || "auto"}`;
}

function normalizePromptPreset(promptPreset) {
  const preset = String(promptPreset || "").trim().toLowerCase();
  if (preset === "none") {
    return "auto";
  }
  return ["auto", "ru", "en"].includes(preset) ? preset : "ru";
}

function languageForPromptPreset(promptPreset) {
  const preset = normalizePromptPreset(promptPreset);
  if (preset === "ru" || preset === "en") {
    return preset;
  }
  return "auto";
}

export async function loadTranscriptLibrary({ silent = false } = {}) {
  if (!state.activeProfileId) return;
  try {
    const data = await listTranscripts(state.activeProfileId, state.currentSessionId);
    state.transcriptLibrary = Array.isArray(data?.transcripts) ? data.transcripts : [];
    renderTranscriptLibrary();
    if (!silent) {
      updateStatus(elements.transcriptStatus, `Транскриптов: ${state.transcriptLibrary.length}`, "info");
    }
  } catch (error) {
    if (!silent) {
      updateStatus(elements.transcriptStatus, `Ошибка загрузки транскриптов: ${error.message || error}`, "error");
    }
  }
}

function renderTranscriptLibrary() {
  if (!elements.transcriptList) return;
  const items = state.transcriptLibrary
    .map(
      (item) => `
        <div class="transcript-row" data-id="${item.id}">
          <div class="transcript-row__meta">
            <strong>${item.name}</strong>
            <span class="muted">${item.language || ""}</span>
          </div>
          <div class="transcript-row__actions">
            <button class="secondary" data-action="apply">Использовать</button>
            <button class="warn" data-action="delete">Удалить</button>
          </div>
        </div>
      `,
    )
    .join("");
  elements.transcriptList.innerHTML = items || '<p class="muted">Сохранённых транскриптов пока нет.</p>';
  elements.transcriptList.hidden = !items;
}

async function applyTranscriptById(id) {
  const entry = state.transcriptLibrary.find((item) => item.id === id);
  if (!entry) return;
  setTranscript(entry.content || "", entry.timeline || [], entry.role_keywords || {}, entry.labels || {});
  updateStatus(elements.transcriptStatus, `Транскрипт «${entry.name}» применён.`, "success");
}

async function deleteTranscriptById(id) {
  try {
    await deleteTranscriptApi(id);
    state.transcriptLibrary = state.transcriptLibrary.filter((item) => item.id !== id);
    renderTranscriptLibrary();
  } catch (error) {
    updateStatus(elements.transcriptStatus, `Не удалось удалить транскрипт: ${error.message || error}`, "error");
  }
}

async function handleTranscribe() {
  if (!elements.fileInput?.files?.length) return;
  if (!state.activeProfileId) {
    updateStatus(elements.transcribeStatus, "Сначала выберите профиль.", "warning");
    return;
  }
  const file = elements.fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);
  formData.append("profile_id", state.activeProfileId);
  formData.append("session_id", state.currentSessionId || "");
  formData.append("model", elements.modelSelect?.value || getSavedModel("medium"));
  const promptPreset = normalizePromptPreset(elements.promptPresetSelect?.value || getSavedPromptPreset("ru"));
  formData.append("prompt_preset", promptPreset);
  formData.append("language", languageForPromptPreset(promptPreset));
  try {
    state.transcribeBusyState.defaultLabel = elements.btnTranscribe?.textContent || "Транскрибировать файл";
    if (elements.btnTranscribe) {
      elements.btnTranscribe.disabled = true;
      elements.btnTranscribe.textContent = "Ждите...";
    }
    const data = await transcribeFile(formData);
    const transcript = data?.text || "";
    const timeline = Array.isArray(data?.timeline) ? data.timeline : [];
    const roleKeywords = data?.role_keywords || {};
    setTranscript(transcript, timeline, roleKeywords, state.timelineLabels);
    const entry = await saveTranscript(file.name || "Транскрипт", transcript);
    if (entry) {
      state.transcriptLibrary = [entry, ...state.transcriptLibrary];
      renderTranscriptLibrary();
    }
    const hasTiming = hasTimelineTiming(timeline);
    const tone = hasTiming ? "success" : "warning";
    const suffix = hasTiming ? "" : " • тайминги не найдены";
    updateStatus(
      elements.transcribeStatus,
      `✅ Транскрипция готова — модель: ${data.model}, символов: ${transcript.length}${suffix}`,
      tone,
    );
  } catch (error) {
    updateStatus(elements.transcribeStatus, `❌ ошибка: ${error.message || error}`, "error");
  } finally {
    if (elements.btnTranscribe) {
      elements.btnTranscribe.disabled = false;
      elements.btnTranscribe.textContent = state.transcribeBusyState.defaultLabel || "Транскрибировать файл";
    }
  }
}

function handleCriteriaFile() {
  const file = elements.criteriaFileInput?.files?.[0];
  if (!file || !criteriaManagerRef) return;
  const formData = new FormData();
  formData.append("file", file);
  formData.append("profile_id", state.activeProfileId || "");
  formData.append("session_id", state.currentSessionId || "");
  parseCriteria(formData)
    .then((data) => {
      const criteria = data?.criteria || [];
      criteriaManagerRef.setCriteria(criteria, { source: data?.source || "file" });
      recalcStats();
    })
    .catch((error) => {
      updateStatus(elements.criteriaStatus, `Ошибка загрузки критериев: ${error.message || error}`, "error");
    });
}

function handleCriteriaSheet() {
  if (!elements.googleSheetInput?.value) return;
  const formData = new FormData();
  formData.append("google_sheet_id", elements.googleSheetInput.value);
  formData.append("profile_id", state.activeProfileId || "");
  formData.append("session_id", state.currentSessionId || "");
  parseCriteria(formData)
    .then((data) => {
      const criteria = data?.criteria || [];
      criteriaManagerRef.setCriteria(criteria, { source: data?.source || "google_sheets" });
      recalcStats();
    })
    .catch((error) => {
      updateStatus(elements.criteriaStatus, `Ошибка загрузки критериев: ${error.message || error}`, "error");
    });
}

let criteriaManagerRef = null;
let transcriptHistoryVisible = false;

export function initTranscripts(criteriaManager) {
  criteriaManagerRef = criteriaManager;
  if (elements.modelSelect) {
    elements.modelSelect.value = getSavedModel(elements.modelSelect.value || "medium");
    elements.modelSelect.addEventListener("change", () => {
      setSavedModel(elements.modelSelect.value);
      renderTranscribeDefaults();
    });
  }
  if (elements.promptPresetSelect) {
    elements.promptPresetSelect.value = normalizePromptPreset(getSavedPromptPreset(elements.promptPresetSelect.value || "ru"));
    elements.promptPresetSelect.addEventListener("change", () => {
      elements.promptPresetSelect.value = normalizePromptPreset(elements.promptPresetSelect.value);
      setSavedPromptPreset(elements.promptPresetSelect.value);
      renderTranscribeDefaults();
    });
  }
  renderTranscribeDefaults();

  elements.btnTranscribe?.addEventListener("click", () => handleTranscribe());
  elements.btnUseManualTranscript?.addEventListener("click", () => {
    const text = elements.manualTranscriptInput?.value || "";
    if (!text.trim()) {
      updateStatus(elements.transcriptStatus, "Введите текст транскрипта.", "warning");
      return;
    }
    setTranscript(text, [], {}, {});
    updateStatus(elements.transcriptStatus, "Текст применён для анализа.", "success");
  });
  elements.btnSaveManualTranscript?.addEventListener("click", async () => {
    const text = elements.manualTranscriptInput?.value || "";
    if (!text.trim()) {
      updateStatus(elements.transcriptStatus, "Введите текст транскрипта.", "warning");
      return;
    }
    setTranscript(text, [], {}, {});
    const entry = await saveTranscript("Ручной транскрипт", text);
    if (entry) {
      state.transcriptLibrary = [entry, ...state.transcriptLibrary];
      renderTranscriptLibrary();
    }
    updateStatus(elements.transcriptStatus, "Транскрипт сохранён и применён.", "success");
  });

  elements.transcriptList?.addEventListener("click", async (event) => {
    const row = event.target.closest("[data-id]");
    if (!row) return;
    const id = Number(row.dataset.id);
    const action = event.target.closest("[data-action]")?.dataset?.action;
    if (action === "apply") {
      await applyTranscriptById(id);
    } else if (action === "delete") {
      await deleteTranscriptById(id);
    }
  });

  elements.btnAddTranscriptHistoryEntry?.addEventListener("click", () => {
    elements.transcriptHistoryOverlay?.classList.add("overlay--visible");
    transcriptHistoryVisible = true;
  });
  elements.btnCloseTranscriptHistory?.addEventListener("click", () => {
    elements.transcriptHistoryOverlay?.classList.remove("overlay--visible");
    transcriptHistoryVisible = false;
  });
  elements.transcriptHistoryOverlay?.addEventListener("click", (event) => {
    if (event.target === elements.transcriptHistoryOverlay) {
      elements.transcriptHistoryOverlay.classList.remove("overlay--visible");
      transcriptHistoryVisible = false;
    }
  });

  elements.btnLoadCriteriaFile?.addEventListener("click", handleCriteriaFile);
  elements.btnLoadCriteriaSheet?.addEventListener("click", handleCriteriaSheet);
  elements.btnClearCriteria?.addEventListener("click", () => {
    criteriaManagerRef?.clear();
    recalcStats();
  });
  elements.btnQuickAddCriterion?.addEventListener("click", () => {
    const value = elements.quickCriterionInput?.value || "";
    if (criteriaManagerRef?.addManualCriterion(value)) {
      elements.quickCriterionInput.value = "";
      recalcStats();
    }
  });

  loadTranscriptLibrary({ silent: true });
}

export function clearTranscriptContext() {
  setTranscript("", [], {}, {});
  updateStatus(elements.transcriptStatus, "", "info");
}
