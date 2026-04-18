import { sendChat } from "./api.js";
import { elements, state, updateStatus, estTokens, LIMITS, DEFAULT_HR_PREFIX } from "./app-state.js";
import { setSavedLlmModel, addHistoryEntry } from "./storage.js";
import { ensureModelAvailability } from "./models.js";
import { setActiveSession, loadSessions } from "./sessions.js";

let criteriaManagerRef = null;

function setBusy(isBusy) {
  if (elements.btnSend) elements.btnSend.disabled = isBusy;
  if (elements.btnStop) elements.btnStop.hidden = !isBusy;
  if (elements.prompt) elements.prompt.readOnly = isBusy;
}

function currentModel() {
  const selectedModel = (elements.llmModelSelect?.value || "").trim();
  return state.currentSessionModel || selectedModel;
}

export function recalcStats() {
  const prompt = elements.prompt?.value || "";
  const transcript = state.currentTranscript || "";
  const criteria = criteriaManagerRef?.getCriteria() || [];
  const promptTokens = estTokens(prompt);
  const transcriptTokens = estTokens(transcript);
  const criteriaTokens = estTokens(criteria.join(" "));
  const total = promptTokens + transcriptTokens + criteriaTokens;
  if (elements.promptStats) {
    elements.promptStats.textContent = `Символы: ${prompt.length} • Токены≈ ${promptTokens}`;
  }
  if (elements.budgetStats) {
    const limitCtx = LIMITS.num_ctx || "—";
    const limitResp = LIMITS.max_tokens || "—";
    elements.budgetStats.textContent = `Входные токены: ${total} • Резерв на ответ: ${limitResp} • Лимит контекста: ${limitCtx}`;
  }
}

export function stopCurrentChat() {
  if (state.chatState.controller) {
    state.chatState.controller.abort();
    state.chatState.controller = null;
  }
}

export async function sendPrompt() {
  if (state.chatState.controller) return;
  if (!state.activeProfileId) {
    updateStatus(elements.healthStatus, "Сначала выберите профиль.", "warning");
    return;
  }
  const rawQuery = elements.prompt?.value || "";
  const finalQuery = rawQuery.trim() || "проанализируй";
  const targetModel = currentModel();
  if (targetModel) {
    const available = await ensureModelAvailability(targetModel);
    if (!available) {
      return;
    }
  }

  const controller = new AbortController();
  state.chatState.controller = controller;
  setBusy(true);
  if (elements.answer) {
    elements.answer.value = "Думаю…";
  }

  let aborted = false;
  try {
    const payload = {
      query: finalQuery,
      profile_id: state.activeProfileId,
      role: state.currentRole,
    };
    if (state.currentSessionId) {
      payload.session_id = state.currentSessionId;
    }
    if (targetModel) {
      payload.model = targetModel;
      payload.model_name = targetModel;
      setSavedLlmModel(targetModel);
    }
    const transcript = state.currentTranscript.trim();
    if (transcript) {
      payload.transcript = transcript;
    }
    const criteria = criteriaManagerRef?.getCriteria() || [];
    if (criteria.length) {
      payload.criteria = criteria;
    }
    const response = await sendChat(payload, { signal: controller.signal });
    const text = response.reply ?? "";
    if (elements.answer) {
      elements.answer.value = text;
    }
    addHistoryEntry(finalQuery, text);

    if (response.session_id) {
      state.currentSessionId = response.session_id;
      await setActiveSession(response.session_id, { silent: true });
    }
    if (response.model_name) {
      state.currentSessionModel = response.model_name;
    } else if (targetModel) {
      state.currentSessionModel = targetModel;
    }
    if (response.used_settings) {
      LIMITS.num_ctx = response.used_settings.num_ctx ?? LIMITS.num_ctx;
      LIMITS.max_tokens = response.used_settings.max_tokens ?? LIMITS.max_tokens;
    }
    if (state.activeProfileId) {
      await loadSessions(state.activeProfileId);
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
    state.chatState.controller = null;
    setBusy(false);
    if (!aborted && elements.prompt) {
      elements.prompt.focus();
    }
  }
}

export function initChat(criteriaManager) {
  criteriaManagerRef = criteriaManager;
  elements.prompt?.addEventListener("input", () => recalcStats());
  elements.btnSend?.addEventListener("click", () => sendPrompt());
  elements.btnStop?.addEventListener("click", () => stopCurrentChat());
  elements.prompt?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!state.chatState.controller) {
        sendPrompt();
      }
    }
  });
  elements.btnCopy?.addEventListener("click", () => {
    if (elements.answer) {
      navigator.clipboard.writeText(elements.answer.value || "");
    }
  });
  elements.btnClearPrompt?.addEventListener("click", () => {
    if (elements.prompt) {
      elements.prompt.value = "";
      recalcStats();
    }
  });
  elements.btnClearAnswer?.addEventListener("click", () => {
    if (elements.answer) elements.answer.value = "";
  });

  const savedPrefix = DEFAULT_HR_PREFIX;
  if (elements.hrPrefixInput) {
    elements.hrPrefixInput.value = savedPrefix;
  }
  recalcStats();
}
