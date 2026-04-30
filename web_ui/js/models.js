import {
  cancelPull,
  deleteModelApi,
  fetchModelSettings,
  fetchStoragePaths,
  listModels,
  pullModel,
  pullStatuses,
  resetModelSettings,
  saveModelSettings,
  updateStoragePaths,
} from "./api.js";
import { elements, state, updateStatus } from "./app-state.js";
import { getSavedLlmModel, setSavedLlmModel } from "./storage.js";

let onModelChanged = null;
let downloadsTimer = null;

function modelId(model) {
  return String(model?.id || model?.name || "").trim();
}

function modelTitle(model) {
  return String(model?.title || model?.label || modelId(model)).trim();
}

function isModelInstalled(name) {
  return state.modelState.installed.some((item) => item.name === name);
}

function hasActiveDownload(model) {
  return (state.modelState.downloads || []).some(
    (item) => item.model === model && ["pending", "running"].includes(item.state),
  );
}

function renderModelSelect(preselect) {
  if (!elements.llmModelSelect) return;
  const installed = state.modelState.installed || [];
  const installedNames = new Set(installed.map((item) => item.name));
  const catalog = state.modelState.recommended || [];
  const source = catalog.length
    ? catalog
    : installed.map((item) => ({ id: item.name, title: item.name }));
  const options = [
    '<option value="" hidden>Модель не выбрана</option>',
    ...source.map((item) => {
      const id = modelId(item);
      const title = modelTitle(item);
      const missing = !installedNames.has(id);
      return `<option value="${id}">${title}${missing ? " (не загружена)" : ""}</option>`;
    }),
  ];
  elements.llmModelSelect.innerHTML = options.join("") || '<option value="">Нет доступных моделей</option>';
  elements.llmModelSelect.disabled = !source.length;
  if (preselect && source.some((item) => modelId(item) === preselect)) {
    elements.llmModelSelect.value = preselect;
  }
}

function renderModelSuggestions() {
  if (!elements.modelSuggestions) return;
  const installedNames = new Set(state.modelState.installed.map((m) => m.name));
  const chips = state.modelState.recommended
    .map((model) => {
      const id = modelId(model);
      const installed = installedNames.has(id);
      return `<button class="model-chip${installed ? " is-installed" : ""}" data-model="${id}" data-installed="${installed ? "1" : "0"}" title="${model.description || ""}">${
        modelTitle(model)
      }</button>`;
    })
    .join("");
  elements.modelSuggestions.innerHTML = chips;
}

function renderDownloads() {
  if (!elements.downloadList || !elements.downloadsPanel) return;
  const downloads = state.modelState.downloads || [];
  if (!downloads.length) {
    elements.downloadsPanel.hidden = true;
    elements.downloadList.innerHTML = "";
    return;
  }
  const items = downloads
    .map((item) => {
      const percent = typeof item.percent === "number" ? item.percent : null;
      const eta = item.eta_seconds ? `ETA ${item.eta_seconds}s` : "";
      const cancellable = ["pending", "running"].includes(item.state);
      return `<li class="download-item" data-task="${item.task_id || ""}">
        <div class="download-header">
          <div class="download-title">${item.model || "модель"}</div>
          <div class="download-meta">${percent !== null ? `${percent.toFixed(2)}%` : ""} ${eta}</div>
        </div>
        <div class="download-state">${item.message || item.state || ""}</div>
        <div class="download-actions">
          ${
            cancellable
              ? `<button class="secondary" data-action="cancel-download" data-task="${item.task_id}">Отменить загрузку</button>`
              : `<span class="muted">state: ${item.state}</span>`
          }
        </div>
      </li>`;
    })
    .join("");
  elements.downloadList.innerHTML = items;
  elements.downloadsPanel.hidden = false;
}

async function refreshDownloads() {
  try {
    const data = await pullStatuses();
    state.modelState.downloads = Array.isArray(data?.downloads) ? data.downloads : [];
    renderDownloads();
  } catch (error) {
    // ignore polling errors
  }
}

function scheduleDownloadsPoll() {
  if (downloadsTimer) {
    clearInterval(downloadsTimer);
  }
  downloadsTimer = window.setInterval(refreshDownloads, 2500);
}

export async function fetchModelList() {
  try {
    const data = await listModels();
    state.modelState.installed = Array.isArray(data?.installed) ? data.installed : [];
    state.modelState.recommended = Array.isArray(data?.catalog)
      ? data.catalog
      : (Array.isArray(data?.recommended) ? data.recommended : state.modelState.recommended);
    state.modelState.downloads = Array.isArray(data?.downloads) ? data.downloads : [];
    renderModelSelect(state.currentSessionModel || getSavedLlmModel());
    renderModelSuggestions();
    renderDownloads();
    if (state.modelState.downloads.length) {
      scheduleDownloadsPoll();
    }
  } catch (error) {
    updateStatus(elements.modelStatus, `Не удалось получить список моделей: ${error.message || error}`, "error");
  }
}

export async function startModelDownload(model) {
  if (hasActiveDownload(model)) {
    updateStatus(elements.modelStatus, `Загрузка ${model} уже выполняется`, "info");
    return;
  }
  const confirmed = window.confirm(`Загрузить модель ${model}?`);
  if (!confirmed) return;
  try {
    await pullModel({ model });
    await fetchModelList();
    updateStatus(elements.modelStatus, `Загрузка модели ${model} запущена.`, "info");
  } catch (error) {
    updateStatus(elements.modelStatus, `Не удалось запустить загрузку: ${error.message || error}`, "error");
  }
}

export async function deleteSelectedModel() {
  const model = elements.llmModelSelect?.value;
  if (!model) return;
  const confirmed = window.confirm(`Удалить модель ${model}?`);
  if (!confirmed) return;
  try {
    await deleteModelApi(model);
    await fetchModelList();
    updateStatus(elements.modelStatus, `Модель ${model} удалена.`, "success");
  } catch (error) {
    updateStatus(elements.modelStatus, `Не удалось удалить модель: ${error.message || error}`, "error");
  }
}

export async function ensureModelAvailability(modelName) {
  if (!modelName) {
    updateStatus(elements.healthStatus, "Нет доступных моделей. Загрузите модель и повторите отправку.", "warning");
    return false;
  }
  if (isModelInstalled(modelName)) return true;
  updateStatus(elements.healthStatus, "Модель не загружена. Загрузите модель и повторите отправку.", "warning");
  return false;
}

export async function refreshModelSettings(modelName) {
  if (!state.activeProfileId || !modelName) return;
  try {
    const data = await fetchModelSettings(state.activeProfileId, modelName);
    state.modelSettingsState = data || { effective: {}, overrides: {}, defaults: {} };
    const { effective, overrides, defaults } = state.modelSettingsState;
    if (elements.temperatureInput) elements.temperatureInput.value = overrides.temperature ?? effective.temperature ?? "";
    if (elements.maxTokensInput) elements.maxTokensInput.value = overrides.max_tokens ?? effective.max_tokens ?? "";
    if (elements.numCtxInput) elements.numCtxInput.value = overrides.num_ctx ?? effective.num_ctx ?? "";
    if (elements.memTurnsInput) elements.memTurnsInput.value = overrides.mem_turns ?? effective.mem_turns ?? "";
    updateStatus(elements.modelSettingsStatus, "Настройки модели загружены", "success");
  } catch (error) {
    updateStatus(elements.modelSettingsStatus, `Не удалось загрузить настройки: ${error.message || error}`, "error");
  }
}

export async function saveModelSettingsFlow() {
  if (!state.activeProfileId || !elements.llmModelSelect) return;
  const modelName = elements.llmModelSelect.value;
  const payload = {
    profile_id: state.activeProfileId,
    model_name: modelName,
    temperature: elements.temperatureInput?.value ? Number(elements.temperatureInput.value) : null,
    max_tokens: elements.maxTokensInput?.value ? Number(elements.maxTokensInput.value) : null,
    num_ctx: elements.numCtxInput?.value ? Number(elements.numCtxInput.value) : null,
    mem_turns: elements.memTurnsInput?.value ? Number(elements.memTurnsInput.value) : null,
  };
  try {
    const data = await saveModelSettings(payload);
    state.modelSettingsState = data || state.modelSettingsState;
    updateStatus(elements.modelSettingsStatus, "Сохранено", "success");
  } catch (error) {
    updateStatus(elements.modelSettingsStatus, `Не удалось сохранить: ${error.message || error}`, "error");
  }
}

export async function resetModelSettingsFlow() {
  if (!state.activeProfileId || !elements.llmModelSelect) return;
  const modelName = elements.llmModelSelect.value;
  try {
    const data = await resetModelSettings({ profile_id: state.activeProfileId, model_name: modelName });
    state.modelSettingsState = data || state.modelSettingsState;
    await refreshModelSettings(modelName);
    updateStatus(elements.modelSettingsStatus, "Настройки сброшены", "success");
  } catch (error) {
    updateStatus(elements.modelSettingsStatus, `Не удалось сбросить: ${error.message || error}`, "error");
  }
}

export async function syncModelSelection(modelName, { silent = false } = {}) {
  if (elements.llmModelSelect) {
    if (modelName && !elements.llmModelSelect.value) {
      const optionExists = Array.from(elements.llmModelSelect.options).some((opt) => opt.value === modelName);
      if (!optionExists) {
        const option = document.createElement("option");
        option.value = modelName;
        option.textContent = modelName;
        elements.llmModelSelect.appendChild(option);
      }
    }
    if (modelName) {
      elements.llmModelSelect.value = modelName;
      state.currentSessionModel = modelName;
      setSavedLlmModel(modelName);
    }
  }
  if (!silent && typeof onModelChanged === "function") {
    onModelChanged(modelName);
  }
  if (modelName) {
    await refreshModelSettings(modelName);
  }
}

async function applyStorageDir(moveExisting = false) {
  if (!elements.modelsDirInput) return;
  const target = elements.modelsDirInput.value.trim();
  if (!target) {
    updateStatus(elements.modelStatus, "Укажите путь к папке моделей", "warning");
    return;
  }
  try {
    const data = await updateStoragePaths({ models_dir: target, move_existing: moveExisting });
    updateStatus(elements.modelStatus, `Путь к моделям обновлён: ${data?.paths?.base || target}`, "success");
    await fetchModelList();
  } catch (error) {
    updateStatus(elements.modelStatus, `Не удалось обновить путь к моделям: ${error.message || error}`, "error");
  }
}

async function loadStorageDir() {
  try {
    const data = await fetchStoragePaths();
    const base = data?.paths?.base || "";
    if (elements.modelsDirInput) {
      elements.modelsDirInput.value = base;
    }
  } catch (error) {
    // ignore
  }
}

export function initModels({ onModelChange } = {}) {
  onModelChanged = onModelChange || null;
  fetchModelList();
  loadStorageDir();

  elements.llmModelSelect?.addEventListener("change", async () => {
    const value = (elements.llmModelSelect.value || "").trim();
    if (value) {
      await syncModelSelection(value);
    }
  });
  elements.btnRefreshModels?.addEventListener("click", () => fetchModelList());
  elements.btnDeleteModel?.addEventListener("click", () => deleteSelectedModel());
  elements.modelSuggestions?.addEventListener("click", async (event) => {
    const chip = event.target.closest("[data-model]");
    if (!chip) return;
    const model = chip.dataset.model;
    const installed = chip.dataset.installed === "1";
    if (installed) {
      await syncModelSelection(model);
      return;
    }
    await startModelDownload(model);
  });
  elements.downloadList?.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-action='cancel-download']");
    if (!btn) return;
    const taskId = btn.dataset.task;
    if (!taskId) return;
    btn.disabled = true;
    try {
      await cancelPull(taskId);
      updateStatus(elements.modelStatus, "Загрузка остановлена", "warning");
      await fetchModelList();
    } catch (error) {
      updateStatus(elements.modelStatus, `Не удалось остановить загрузку: ${error.message || error}`, "error");
    } finally {
      btn.disabled = false;
    }
  });
  elements.btnSaveModelSettings?.addEventListener("click", () => saveModelSettingsFlow());
  elements.btnResetModelSettings?.addEventListener("click", () => resetModelSettingsFlow());
  elements.btnApplyModelsDir?.addEventListener("click", () => applyStorageDir(false));
  elements.btnMoveModelsDir?.addEventListener("click", () => applyStorageDir(true));
}
