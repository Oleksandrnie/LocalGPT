import {
  deleteHistoryItem,
  fetchHealth,
  generateSpeech,
  getHistoryItem,
  listHistory,
  listVoices,
  processSpeed,
} from "./api.js";
import { renderHistoryList } from "./history.js";
import { getSavedSpeed, getSavedVoice, setSavedSpeed, setSavedVoice } from "./storage.js";
import { formatDateTime, formatDuration, setStatus } from "./ui.js";

const elements = {
  healthStatus: document.getElementById("healthStatus"),
  voiceAvailability: document.getElementById("voiceAvailability"),
  ttsText: document.getElementById("ttsText"),
  textCounter: document.getElementById("textCounter"),
  btnClearText: document.getElementById("btnClearText"),
  voiceSelect: document.getElementById("voiceSelect"),
  voiceInfo: document.getElementById("voiceInfo"),
  btnGenerate: document.getElementById("btnGenerate"),
  generateBadge: document.getElementById("generateBadge"),
  generateStatus: document.getElementById("generateStatus"),
  recordMeta: document.getElementById("recordMeta"),
  baseCard: document.getElementById("baseCard"),
  basePlayer: document.getElementById("basePlayer"),
  baseInfo: document.getElementById("baseInfo"),
  downloadBase: document.getElementById("downloadBase"),
  speedOptions: document.getElementById("speedOptions"),
  btnApplySpeed: document.getElementById("btnApplySpeed"),
  speedStatus: document.getElementById("speedStatus"),
  processedCard: document.getElementById("processedCard"),
  processedPlayer: document.getElementById("processedPlayer"),
  processedInfo: document.getElementById("processedInfo"),
  downloadProcessed: document.getElementById("downloadProcessed"),
  historyList: document.getElementById("historyList"),
  btnRefreshHistory: document.getElementById("btnRefreshHistory"),
  appToast: document.getElementById("appToast"),
};

const state = {
  health: null,
  voices: [],
  history: [],
  activeRecordId: null,
  activeRecord: null,
  maxTextChars: 15000,
  speedOptions: [1.0, 1.25, 1.5, 1.75, 2.0],
  selectedSpeed: getSavedSpeed(1.25),
  pollingRecordId: null,
  generating: false,
  processingSpeed: false,
};

let toastTimer = null;

function showToast(message, tone = "info") {
  if (!elements.appToast) return;
  clearTimeout(toastTimer);
  elements.appToast.hidden = false;
  elements.appToast.textContent = message;
  elements.appToast.dataset.tone = tone;
  toastTimer = window.setTimeout(() => {
    elements.appToast.hidden = true;
  }, 2600);
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function versionedUrl(url, version) {
  if (!url) return "";
  const suffix = version ? `&v=${encodeURIComponent(version)}` : "";
  return `${url}${suffix}`;
}

function downloadUrl(url, version) {
  if (!url) return "#";
  return `${versionedUrl(url, version)}&download=1`;
}

function currentVoice() {
  const voiceId = elements.voiceSelect?.value || "";
  return state.voices.find((item) => item.id === voiceId) || null;
}

function updateCounter() {
  const value = elements.ttsText?.value || "";
  const count = value.length;
  elements.textCounter.textContent = `${count} / ${state.maxTextChars}`;
  elements.textCounter.classList.toggle("is-danger", count > state.maxTextChars);
}

function setBadge(label, tone = "idle") {
  elements.generateBadge.textContent = label;
  elements.generateBadge.dataset.tone = tone;
}

function setActionState() {
  const hasVoice = Boolean(elements.voiceSelect?.value);
  const hasRecord = Boolean(state.activeRecord?.base_output_url);
  elements.btnGenerate.disabled = state.generating || !hasVoice;
  elements.btnApplySpeed.disabled = state.processingSpeed || !hasRecord;
  elements.voiceSelect.disabled = state.generating || state.processingSpeed;
  elements.ttsText.disabled = state.generating;
}

function renderVoiceInfo() {
  const voice = currentVoice();
  if (!voice) {
    elements.voiceInfo.textContent = "Подходящих локальных голосов пока нет.";
    return;
  }
  const quality = voice.quality ? ` • ${voice.quality}` : "";
  const sampleRate = voice.sample_rate ? ` • ${voice.sample_rate} Hz` : "";
  elements.voiceInfo.textContent = `${voice.name} • ${voice.language || "unknown"}${quality}${sampleRate}`;
}

function renderVoiceSelect() {
  const voiceId = getSavedVoice();
  const options = state.voices.length
    ? state.voices
        .map(
          (voice) =>
            `<option value="${voice.id}">${voice.name} • ${voice.language || "unknown"}${voice.quality ? ` • ${voice.quality}` : ""}</option>`,
        )
        .join("")
    : '<option value="">Нет доступных голосов</option>';

  elements.voiceSelect.innerHTML = options;

  if (!state.voices.length) {
    elements.voiceSelect.value = "";
    renderVoiceInfo();
    setActionState();
    return;
  }

  const selected = state.voices.find((item) => item.id === voiceId) || state.voices[0];
  elements.voiceSelect.value = selected.id;
  setSavedVoice(selected.id);
  renderVoiceInfo();
  setActionState();
}

function renderSpeedOptions() {
  elements.speedOptions.innerHTML = state.speedOptions
    .map((speed) => {
      const label = `${String(speed).replace(".0", "")}x`;
      const checked = Number(state.selectedSpeed) === Number(speed) ? "is-selected" : "";
      return `
        <button
          class="speed-pill ${checked}"
          type="button"
          data-speed="${speed}"
        >${label}</button>
      `;
    })
    .join("");
}

function updateAudioCard(card, player, infoEl, linkEl, url, text, version, filenameFallback) {
  const hasAudio = Boolean(url);
  card.classList.toggle("is-empty", !hasAudio);
  if (hasAudio) {
    player.src = versionedUrl(url, version);
    linkEl.href = downloadUrl(url, version);
    linkEl.classList.remove("is-disabled");
    linkEl.removeAttribute("aria-disabled");
    linkEl.setAttribute("download", filenameFallback);
  } else {
    player.removeAttribute("src");
    player.load();
    linkEl.href = "#";
    linkEl.classList.add("is-disabled");
    linkEl.setAttribute("aria-disabled", "true");
    linkEl.removeAttribute("download");
  }
  infoEl.textContent = text;
}

function loadRecord(record) {
  state.activeRecord = record;
  state.activeRecordId = record?.id || null;
  const timestamp = record?.updated_at || record?.created_at || record?.id || "";

  if (record?.text && !state.generating) {
    elements.ttsText.value = record.text;
    updateCounter();
  }

  if (record?.voice_id) {
    const match = state.voices.find((voice) => voice.id === record.voice_id);
    if (match) {
      elements.voiceSelect.value = match.id;
      setSavedVoice(match.id);
      renderVoiceInfo();
    }
  }

  if (record) {
    elements.recordMeta.textContent =
      `${record.voice_name || "Voice"} • ${formatDateTime(record.updated_at || record.created_at)} • ${record.status}`;
  } else {
    elements.recordMeta.textContent = "История и плеер появятся после генерации.";
  }

  const baseInfo = record?.base_output_url
    ? `${record.voice_name || "Voice"} • ${formatDuration(record.duration_sec)} • WAV`
    : "Базовый WAV пока не сгенерирован.";
  updateAudioCard(
    elements.baseCard,
    elements.basePlayer,
    elements.baseInfo,
    elements.downloadBase,
    record?.base_output_url || null,
    baseInfo,
    timestamp,
    `${record?.id || "tts"}_base.wav`,
  );

  const processedInfo = record?.processed_output_url
    ? `${record.voice_name || "Voice"} • ${String(record.speed).replace(".0", "")}x • ${formatDuration(record.processed_duration_sec || record.duration_sec)}`
    : "Ускоренный WAV ещё не создан.";
  updateAudioCard(
    elements.processedCard,
    elements.processedPlayer,
    elements.processedInfo,
    elements.downloadProcessed,
    record?.processed_output_url || null,
    processedInfo,
    timestamp,
    `${record?.id || "tts"}_processed.wav`,
  );

  renderHistoryList(elements.historyList, state.history, state.activeRecordId);
  setActionState();
}

async function refreshHealth() {
  try {
    const health = await fetchHealth();
    state.health = health;
    state.maxTextChars = Number(health.max_text_chars) || 15000;
    state.speedOptions = Array.isArray(health.speed_options) && health.speed_options.length
      ? health.speed_options
      : state.speedOptions;
    setStatus(elements.healthStatus, `Локальный TTS: ${health.status} • provider: ${health.default_provider}`, "success");
    setStatus(
      elements.voiceAvailability,
      health.provider?.available
        ? `Голоса доступны: ${health.provider.voices_count}`
        : health.provider?.message || "Голоса пока недоступны.",
      health.provider?.available ? "info" : "warning",
    );
  } catch (error) {
    setStatus(elements.healthStatus, `Не удалось получить health: ${error.message}`, "error");
    setStatus(elements.voiceAvailability, "UI работает, но backend не ответил.", "warning");
  }
  updateCounter();
  renderSpeedOptions();
}

async function refreshVoices() {
  try {
    const response = await listVoices();
    state.voices = Array.isArray(response.items) ? response.items.filter((item) => item.available !== false) : [];
    renderVoiceSelect();
  } catch (error) {
    state.voices = [];
    renderVoiceSelect();
    setStatus(elements.voiceAvailability, `Ошибка загрузки голосов: ${error.message}`, "error");
  }
}

async function refreshHistory({ keepActive = true } = {}) {
  try {
    const response = await listHistory();
    state.history = Array.isArray(response.items) ? response.items : [];
    renderHistoryList(elements.historyList, state.history, keepActive ? state.activeRecordId : null);
  } catch (error) {
    elements.historyList.innerHTML = `<p class="history-empty">Не удалось загрузить историю: ${error.message}</p>`;
  }
}

async function fetchAndLoadRecord(recordId, { syncText = true } = {}) {
  const record = await getHistoryItem(recordId);
  if (!syncText) {
    const currentText = elements.ttsText.value;
    loadRecord({ ...record, text: currentText });
    return record;
  }
  loadRecord(record);
  return record;
}

async function pollRecord(recordId, { expectProcessed = false } = {}) {
  state.pollingRecordId = recordId;
  for (let attempt = 0; attempt < 240; attempt += 1) {
    const record = await getHistoryItem(recordId);
    state.activeRecord = record;
    state.activeRecordId = record.id;
    loadRecord(record);
    await refreshHistory();

    const baseReady = Boolean(record.base_output_url);
    const processedReady = !expectProcessed || Boolean(record.processed_output_url);
    if (record.status === "completed" && baseReady && processedReady) {
      return record;
    }
    if (record.status === "error") {
      throw new Error(record.error || "Фоновая задача завершилась ошибкой.");
    }
    await sleep(1200);
  }
  throw new Error("Превышено время ожидания фоновой задачи.");
}

async function handleGenerate() {
  const text = (elements.ttsText.value || "").trim();
  const voiceId = elements.voiceSelect.value;

  if (!text) {
    showToast("Введите текст для озвучки.", "error");
    return;
  }
  if (text.length > state.maxTextChars) {
    showToast(`Текст превышает лимит ${state.maxTextChars} символов.`, "error");
    return;
  }
  if (!voiceId) {
    showToast("Сначала выберите голос.", "error");
    return;
  }

  state.generating = true;
  setBadge("Generating", "busy");
  setStatus(elements.generateStatus, "Генерация запущена в фоне...", "warning");
  setActionState();

  try {
    const started = await generateSpeech({ text, voice_id: voiceId });
    loadRecord(started);
    await refreshHistory();
    const record = await pollRecord(started.id);
    setStatus(elements.generateStatus, `Готово: ${record.voice_name} • ${formatDuration(record.duration_sec)}`, "success");
    setBadge("Ready", "success");
    showToast("Озвучка готова.", "success");
  } catch (error) {
    setStatus(elements.generateStatus, error.message || "Ошибка генерации.", "error");
    setBadge("Error", "error");
    showToast(error.message || "Ошибка генерации.", "error");
  } finally {
    state.generating = false;
    setActionState();
  }
}

async function handleApplySpeed() {
  if (!state.activeRecordId || !state.activeRecord?.base_output_url) {
    showToast("Сначала создайте базовый WAV.", "error");
    return;
  }

  state.processingSpeed = true;
  setStatus(
    elements.speedStatus,
    `Создаю отдельный WAV со скоростью ${String(state.selectedSpeed).replace(".0", "")}x...`,
    "warning",
  );
  setActionState();

  try {
    await processSpeed({ id: state.activeRecordId, speed: Number(state.selectedSpeed) });
    const record = await pollRecord(state.activeRecordId, { expectProcessed: true });
    setStatus(
      elements.speedStatus,
      `Готово: ${String(record.speed).replace(".0", "")}x • ${formatDuration(record.processed_duration_sec || record.duration_sec)}`,
      "success",
    );
    showToast("Ускоренный WAV готов.", "success");
  } catch (error) {
    setStatus(elements.speedStatus, error.message || "Ошибка пост-обработки.", "error");
    showToast(error.message || "Ошибка пост-обработки.", "error");
  } finally {
    state.processingSpeed = false;
    setActionState();
  }
}

async function handleDelete(recordId) {
  if (!recordId) return;
  if (!window.confirm("Удалить запись из истории и связанные WAV-файлы?")) return;

  try {
    await deleteHistoryItem(recordId);
    if (state.activeRecordId === recordId) {
      state.activeRecordId = null;
      state.activeRecord = null;
      loadRecord(null);
    }
    await refreshHistory();
    showToast("Запись удалена.", "success");
  } catch (error) {
    showToast(error.message || "Не удалось удалить запись.", "error");
  }
}

function bindEvents() {
  elements.ttsText.addEventListener("input", updateCounter);

  elements.btnClearText.addEventListener("click", () => {
    elements.ttsText.value = "";
    updateCounter();
    showToast("Текст очищен.");
  });

  elements.voiceSelect.addEventListener("change", () => {
    setSavedVoice(elements.voiceSelect.value || "");
    renderVoiceInfo();
    setActionState();
  });

  elements.btnGenerate.addEventListener("click", handleGenerate);
  elements.btnApplySpeed.addEventListener("click", handleApplySpeed);
  elements.btnRefreshHistory.addEventListener("click", () => refreshHistory());

  elements.speedOptions.addEventListener("click", (event) => {
    const button = event.target.closest("[data-speed]");
    if (!button) return;
    state.selectedSpeed = Number(button.dataset.speed);
    setSavedSpeed(state.selectedSpeed);
    renderSpeedOptions();
  });

  elements.historyList.addEventListener("click", async (event) => {
    const deleteButton = event.target.closest('[data-action="delete"]');
    if (deleteButton) {
      await handleDelete(deleteButton.dataset.id || "");
      return;
    }

    const openButton = event.target.closest('[data-action="open"]');
    if (!openButton) return;
    try {
      await fetchAndLoadRecord(openButton.dataset.id || "");
    } catch (error) {
      showToast(error.message || "Не удалось открыть запись.", "error");
    }
  });
}

async function init() {
  bindEvents();
  updateCounter();
  setActionState();
  renderSpeedOptions();

  await refreshHealth();
  await refreshVoices();
  await refreshHistory();

  if (state.history.length) {
    try {
      await fetchAndLoadRecord(state.history[0].id, { syncText: false });
    } catch {
      // ignore initial history load failure
    }
  }
}

init().catch((error) => {
  setStatus(elements.healthStatus, error.message || "Не удалось инициализировать UI.", "error");
});
