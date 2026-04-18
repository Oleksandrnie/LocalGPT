import { createCriteriaManager, elements, state, updateStatus } from "./app-state.js";
import { fetchHealth, updateSession } from "./api.js";
import { initChat, recalcStats } from "./chat.js";
import { initModels, syncModelSelection } from "./models.js";
import { initRoles, setCurrentRole } from "./roles.js";
import { initSessions, loadProfiles, loadSessions } from "./sessions.js";
import { initTranscripts, loadTranscriptLibrary, clearTranscriptContext } from "./transcripts.js";
import { initTheme } from "./theme.js";
import { initUi } from "./ui.js";
import { getSavedLlmModel } from "./storage.js";

async function checkHealth() {
  try {
    const data = await fetchHealth();
    updateStatus(
      elements.healthStatus,
      `Сервер OK • модель: ${data.model} • контекст: ${data.num_ctx}`,
      "success",
    );
  } catch (error) {
    updateStatus(elements.healthStatus, `Сервер недоступен: ${error.message || error}`, "error");
  }
}

let criteriaManager = null;

async function handleSessionChange(sessionId) {
  const session = state.sessionList.find((s) => s.id === sessionId);
  if (session) {
    state.currentSessionModel = session.model_name;
    await syncModelSelection(session.model_name, { silent: true });
    if (session.role) {
      setCurrentRole(session.role, { persist: false, silent: true });
      state.currentRole = session.role;
    }
  } else {
    state.currentSessionModel = null;
    await syncModelSelection(getSavedLlmModel(), { silent: true });
  }
  if (criteriaManager) {
    await criteriaManager.setContext(sessionId, state.activeProfileId);
  }
  await loadTranscriptLibrary({ silent: true });
  recalcStats();
}

async function handleModelChange(modelName) {
  state.currentSessionModel = modelName;
  if (state.currentSessionId) {
    try {
      await updateSession(state.currentSessionId, { model_name: modelName });
      await loadSessions(state.activeProfileId);
    } catch (error) {
      updateStatus(elements.healthStatus, `Не удалось обновить модель сессии: ${error.message || error}`, "error");
    }
  }
}

async function handleRoleChange(roleKey) {
  state.currentRole = roleKey;
  if (state.currentSessionId) {
    try {
      await updateSession(state.currentSessionId, { role: roleKey });
      await loadSessions(state.activeProfileId);
    } catch (error) {
      // ignore soft error
    }
  }
}

async function bootstrap() {
  initTheme();
  initUi();
  criteriaManager = createCriteriaManager();
  initChat(criteriaManager);
  initTranscripts(criteriaManager);
  initRoles({
    onChange: (role) => handleRoleChange(role),
  });
  initModels({ onModelChange: (model) => handleModelChange(model) });
  initSessions({
    onSessionChange: handleSessionChange,
    onProfileChange: async () => {
      await loadTranscriptLibrary({ silent: true });
      clearTranscriptContext();
    },
  });
  await loadProfiles();
  await checkHealth();
  recalcStats();
}

bootstrap();
