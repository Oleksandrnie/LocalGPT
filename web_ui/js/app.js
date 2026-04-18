const WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"];
const VOICE_INPUT_WHISPER_MODEL = "large-v3-turbo";
const STORAGE_KEYS = {
  activeProfileId: "localgpt_simple_profile_id",
  activeSessionId: "localgpt_simple_session_id",
  llmModel: "localgpt_simple_llm_model",
  whisperModel: "localgpt_simple_whisper_model",
  promptPreset: "localgpt_simple_prompt_preset",
  ttsProvider: "localgpt_simple_tts_provider",
  ttsVoiceId: "localgpt_simple_tts_voice_id",
};

const els = {
  sidebar: document.getElementById("sidebar"),
  sidebarBackdrop: document.getElementById("sidebarBackdrop"),
  toggleSidebarButton: document.getElementById("toggleSidebarButton"),
  newChatButton: document.getElementById("newChatButton"),
  sessionList: document.getElementById("sessionList"),
  profileField: document.getElementById("profileField"),
  profileSelect: document.getElementById("profileSelect"),
  chatTitle: document.getElementById("chatTitle"),
  healthStatus: document.getElementById("healthStatus"),
  contextStatus: document.getElementById("contextStatus"),
  copyLanUrlButton: document.getElementById("copyLanUrlButton"),
  openSettingsButton: document.getElementById("openSettingsButton"),
  messageScroll: document.getElementById("messageScroll"),
  messageList: document.getElementById("messageList"),
  emptyState: document.getElementById("emptyState"),
  composerForm: document.getElementById("composerForm"),
  promptInput: document.getElementById("promptInput"),
  voiceRecordButton: document.getElementById("voiceRecordButton"),
  sendButton: document.getElementById("sendButton"),
  composerMenuButton: document.getElementById("composerMenuButton"),
  composerMenu: document.getElementById("composerMenu"),
  transcribeMenuItem: document.getElementById("transcribeMenuItem"),
  speakMenuItem: document.getElementById("speakMenuItem"),
  transcribeInput: document.getElementById("transcribeInput"),
  scrollTopButton: document.getElementById("scrollTopButton"),
  footerStatus: document.getElementById("footerStatus"),
  settingsBackdrop: document.getElementById("settingsBackdrop"),
  closeSettingsButton: document.getElementById("closeSettingsButton"),
  llmModelSelect: document.getElementById("llmModelSelect"),
  refreshModelsButton: document.getElementById("refreshModelsButton"),
  deleteModelButton: document.getElementById("deleteModelButton"),
  downloadModelInput: document.getElementById("downloadModelInput"),
  downloadModelButton: document.getElementById("downloadModelButton"),
  recommendedModels: document.getElementById("recommendedModels"),
  activeProfileSummary: document.getElementById("activeProfileSummary"),
  profileNameInput: document.getElementById("profileNameInput"),
  profileDescriptionInput: document.getElementById("profileDescriptionInput"),
  createProfileButton: document.getElementById("createProfileButton"),
  deleteProfileButton: document.getElementById("deleteProfileButton"),
  profileStatus: document.getElementById("profileStatus"),
  modelSettingsSummary: document.getElementById("modelSettingsSummary"),
  temperatureInput: document.getElementById("temperatureInput"),
  maxTokensInput: document.getElementById("maxTokensInput"),
  numCtxInput: document.getElementById("numCtxInput"),
  memTurnsInput: document.getElementById("memTurnsInput"),
  saveModelSettingsButton: document.getElementById("saveModelSettingsButton"),
  resetModelSettingsButton: document.getElementById("resetModelSettingsButton"),
  modelSettingsStatus: document.getElementById("modelSettingsStatus"),
  whisperModelSelect: document.getElementById("whisperModelSelect"),
  promptPresetSelect: document.getElementById("promptPresetSelect"),
  ttsProviderSelect: document.getElementById("ttsProviderSelect"),
  ttsVoiceSelect: document.getElementById("ttsVoiceSelect"),
  refreshTtsVoicesButton: document.getElementById("refreshTtsVoicesButton"),
  ttsSettingsStatus: document.getElementById("ttsSettingsStatus"),
  modelsDirInput: document.getElementById("modelsDirInput"),
  applyModelsDirButton: document.getElementById("applyModelsDirButton"),
  moveModelsDirButton: document.getElementById("moveModelsDirButton"),
  lanUrlValue: document.getElementById("lanUrlValue"),
  copyLanUrlFromSettingsButton: document.getElementById("copyLanUrlFromSettingsButton"),
  shutdownButton: document.getElementById("shutdownButton"),
  downloadList: document.getElementById("downloadList"),
};

const state = {
  profiles: [],
  activeProfileId: null,
  sessions: [],
  currentSessionId: null,
  messages: [],
  installedModels: [],
  recommendedModels: [],
  downloads: [],
  selectedLlmModel: "",
  selectedWhisperModel: readStored(STORAGE_KEYS.whisperModel, "small"),
  selectedPromptPreset: readStored(STORAGE_KEYS.promptPreset, "none"),
  selectedTtsProvider: readStored(STORAGE_KEYS.ttsProvider, "piper"),
  selectedTtsVoiceId: readStored(STORAGE_KEYS.ttsVoiceId, ""),
  latestTranscript: null,
  serverHealthy: false,
  ttsHealthy: false,
  defaultModel: "",
  lanUrl: "",
  isSending: false,
  isTranscribing: false,
  isRecordingVoice: false,
  isVoiceTranscribing: false,
  isSpeaking: false,
  autoScrollPinned: true,
  modelsDir: "",
  ttsVoices: [],
  voiceRecorder: null,
  voiceStream: null,
  ttsAudio: null,
  modelSettingsState: {
    effective: {},
    overrides: {},
    defaults: {},
  },
};

let downloadsPollTimer = null;
let healthPollTimer = null;

function readStored(key, fallback = "") {
  try {
    const raw = window.localStorage.getItem(key);
    return raw || fallback;
  } catch {
    return fallback;
  }
}

function writeStored(key, value) {
  try {
    if (value === null || value === undefined || value === "") {
      window.localStorage.removeItem(key);
      return;
    }
    window.localStorage.setItem(key, String(value));
  } catch {
    // ignore storage failures
  }
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatMultiline(value) {
  return escapeHtml(value).replace(/\n/g, "<br />");
}

function formatDateTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isMobileLayout() {
  return window.matchMedia("(max-width: 980px)").matches;
}

function syncMessageScrollState() {
  if (!els.messageScroll) return;
  const remaining = els.messageScroll.scrollHeight - els.messageScroll.scrollTop - els.messageScroll.clientHeight;
  state.autoScrollPinned = remaining <= 96;
  if (els.scrollTopButton) {
    els.scrollTopButton.hidden = els.messageScroll.scrollTop < 320;
  }
}

function scrollMessagesToBottom({ force = false } = {}) {
  if (!els.messageScroll) return;
  if (!force && !state.autoScrollPinned) return;
  requestAnimationFrame(() => {
    els.messageScroll?.scrollTo({ top: els.messageScroll.scrollHeight, behavior: "smooth" });
    syncMessageScrollState();
  });
}

function scrollMessagesToTop() {
  els.messageScroll?.scrollTo({ top: 0, behavior: "smooth" });
}

function toggleComposerMenu(forceState) {
  if (!els.composerMenu || !els.composerMenuButton) return;
  const nextState = typeof forceState === "boolean"
    ? forceState
    : els.composerMenu.hidden;
  els.composerMenu.hidden = !nextState;
  els.composerMenuButton.setAttribute("aria-expanded", nextState ? "true" : "false");
}

function renderVoiceRecordButton() {
  if (!els.voiceRecordButton) return;
  const isBusy = state.isVoiceTranscribing;
  const isRecording = state.isRecordingVoice;
  els.voiceRecordButton.disabled = isBusy;
  els.voiceRecordButton.setAttribute("aria-disabled", isBusy ? "true" : "false");
  els.voiceRecordButton.classList.toggle("input-mic-button--recording", isRecording);
  els.voiceRecordButton.classList.toggle("input-mic-button--busy", isBusy);
  if (isRecording) {
    els.voiceRecordButton.setAttribute("aria-label", "Остановить запись");
    els.voiceRecordButton.title = "Остановить запись";
    return;
  }
  if (isBusy) {
    els.voiceRecordButton.setAttribute("aria-label", "Распознаю запись");
    els.voiceRecordButton.title = "";
    return;
  }
  els.voiceRecordButton.setAttribute("aria-label", "Записать голос");
  els.voiceRecordButton.title = "Записать голос";
}

function pickVoiceRecorderMimeType() {
  if (!window.MediaRecorder?.isTypeSupported) {
    return "";
  }
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  return candidates.find((value) => window.MediaRecorder.isTypeSupported(value)) || "";
}

function audioExtensionForMimeType(mimeType) {
  const normalized = String(mimeType || "").toLowerCase();
  if (normalized.includes("mp4") || normalized.includes("m4a")) return "m4a";
  if (normalized.includes("ogg")) return "ogg";
  if (normalized.includes("mpeg") || normalized.includes("mp3")) return "mp3";
  return "webm";
}

function stopVoiceStreamTracks() {
  if (!state.voiceStream) return;
  state.voiceStream.getTracks().forEach((track) => track.stop());
  state.voiceStream = null;
}

function insertVoiceTranscript(text) {
  const nextText = String(text || "").trim();
  if (!els.promptInput || !nextText) return;
  const current = els.promptInput.value.trim();
  els.promptInput.value = current ? `${current}\n${nextText}` : nextText;
  autoResizePrompt();
  updateSendButtonState();
  els.promptInput.focus();
  const length = els.promptInput.value.length;
  els.promptInput.setSelectionRange(length, length);
}

async function transcribeVoiceBlob(blob, mimeType) {
  state.isVoiceTranscribing = true;
  renderVoiceRecordButton();
  setFooter("Распознаю голос через large-v3-turbo…");

  try {
    const extension = audioExtensionForMimeType(mimeType || blob.type);
    const formData = new FormData();
    formData.append("file", blob, `voice-note.${extension}`);
    formData.append("model", VOICE_INPUT_WHISPER_MODEL);
    formData.append("prompt_preset", "none");
    formData.append("language", "auto");
    formData.append("store_result", "false");

    const data = await request("/transcribe", { method: "POST", body: formData });
    const text = String(data?.text || "").trim();
    if (!text) {
      throw new Error("Whisper вернул пустой текст.");
    }
    insertVoiceTranscript(text);
    setFooter("Текст из микрофона добавлен в поле ввода.", "success");
  } catch (error) {
    setFooter(`Ошибка голосовой транскрибации: ${error.message || error}`, "error");
  } finally {
    state.isVoiceTranscribing = false;
    renderVoiceRecordButton();
  }
}

async function startVoiceRecording() {
  if (state.isRecordingVoice || state.isVoiceTranscribing) return;
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    setFooter("Запись с микрофона не поддерживается в этом браузере.", "warning");
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = pickVoiceRecorderMimeType();
    const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    const chunks = [];

    recorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size > 0) {
        chunks.push(event.data);
      }
    });

    recorder.addEventListener("stop", async () => {
      const outputType = recorder.mimeType || mimeType || "audio/webm";
      stopVoiceStreamTracks();
      state.voiceRecorder = null;
      const blob = new Blob(chunks, { type: outputType });
      if (!blob.size) {
        setFooter("Запись пустая, попробуйте ещё раз.", "warning");
        renderVoiceRecordButton();
        return;
      }
      await transcribeVoiceBlob(blob, outputType);
    });

    recorder.addEventListener("error", () => {
      stopVoiceStreamTracks();
      state.voiceRecorder = null;
      state.isRecordingVoice = false;
      renderVoiceRecordButton();
      setFooter("Не удалось записать звук с микрофона.", "error");
    });

    state.voiceStream = stream;
    state.voiceRecorder = recorder;
    state.isRecordingVoice = true;
    renderVoiceRecordButton();
    recorder.start();
    setFooter("Запись началась. Нажмите на микрофон ещё раз, чтобы остановить.", "warning");
  } catch (error) {
    stopVoiceStreamTracks();
    state.voiceRecorder = null;
    state.isRecordingVoice = false;
    renderVoiceRecordButton();
    setFooter(`Микрофон недоступен: ${error.message || error}`, "error");
  }
}

function stopVoiceRecording() {
  if (!state.voiceRecorder || state.voiceRecorder.state === "inactive") return;
  state.isRecordingVoice = false;
  renderVoiceRecordButton();
  state.voiceRecorder.stop();
  setFooter("Запись остановлена. Начинаю распознавание…");
}

async function toggleVoiceRecording() {
  if (state.isVoiceTranscribing) return;
  if (state.isRecordingVoice) {
    stopVoiceRecording();
    return;
  }
  await startVoiceRecording();
}

function findLatestAssistantMessage() {
  return [...state.messages].reverse().find((message) => message.role === "assistant" && String(message.content || "").trim());
}

function stopTtsPlayback() {
  if (!state.ttsAudio) return;
  state.ttsAudio.pause();
  state.ttsAudio.currentTime = 0;
  state.ttsAudio = null;
}

async function playTtsAudio(url) {
  if (!url) {
    throw new Error("Файл озвучки не найден.");
  }

  stopTtsPlayback();
  const audio = new Audio(url);
  state.ttsAudio = audio;

  audio.addEventListener("ended", () => {
    if (state.ttsAudio === audio) {
      state.ttsAudio = null;
    }
    setFooter("Озвучивание завершено.", "success");
  });

  audio.addEventListener("error", () => {
    if (state.ttsAudio === audio) {
      state.ttsAudio = null;
    }
    setFooter("Не удалось воспроизвести озвучку.", "error");
  });

  try {
    await audio.play();
  } catch (error) {
    if (state.ttsAudio === audio) {
      state.ttsAudio = null;
    }
    throw error;
  }
}

async function waitForTtsRecord(recordId, timeoutMs = 120000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const data = await request(`/tts/history/${encodeURIComponent(recordId)}`);
    const status = String(data?.status || "");
    if (status === "completed") {
      return data;
    }
    if (status === "error") {
      throw new Error(data?.error || "Локальная озвучка завершилась с ошибкой.");
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
  }
  throw new Error("Истекло время ожидания локальной озвучки.");
}

async function speakLatestAssistantMessage() {
  const message = findLatestAssistantMessage();
  if (!message) {
    setFooter("Пока нет ответа, который можно озвучить.", "warning");
    return;
  }

  if (state.isSpeaking) {
    setFooter("Локальная озвучка уже выполняется.", "warning");
    return;
  }

  if (!state.selectedTtsVoiceId) {
    setFooter("Сначала выберите локальный голос в настройках.", "warning");
    openSettings();
    return;
  }

  state.isSpeaking = true;
  setFooter("Генерирую локальную озвучку последнего ответа…");

  try {
    const created = await request("/tts/generate", {
      method: "POST",
      body: {
        text: String(message.content || "").trim(),
        voice_id: state.selectedTtsVoiceId,
        provider: state.selectedTtsProvider || "piper",
      },
    });
    const record = await waitForTtsRecord(created?.id);
    await playTtsAudio(record?.base_output_url);
    setFooter("Озвучивание запущено.", "success");
  } catch (error) {
    const messageText = error?.message || error;
    setFooter(`Ошибка озвучки: ${messageText}`, "error");
  } finally {
    state.isSpeaking = false;
  }
}

function autoResizePrompt() {
  if (!els.promptInput) return;
  els.promptInput.style.height = "0px";
  const nextHeight = Math.min(Math.max(els.promptInput.scrollHeight, 60), 200);
  els.promptInput.style.height = `${nextHeight}px`;
}

function updateSendButtonState() {
  if (!els.sendButton) return;
  const hasText = Boolean((els.promptInput?.value || "").trim());
  els.sendButton.disabled = state.isSending || !hasText;
}

function setFooter(message = "", tone = "info") {
  if (!els.footerStatus) return;
  els.footerStatus.textContent = message;
  els.footerStatus.className = "footer-status";
  if (tone === "success") {
    els.footerStatus.classList.add("footer-status--success");
  } else if (tone === "warning") {
    els.footerStatus.classList.add("footer-status--warning");
  } else if (tone === "error") {
    els.footerStatus.classList.add("footer-status--error");
  }
}

function setHealthBadge(message, tone = "neutral") {
  if (!els.healthStatus) return;
  els.healthStatus.textContent = message;
  els.healthStatus.className = "status-pill";
  if (tone === "success") {
    els.healthStatus.classList.add("status-pill--success");
  } else if (tone === "error") {
    els.healthStatus.classList.add("status-pill--error");
  }
}

function setInlineStatus(element, message = "", tone = "neutral") {
  if (!element) return;
  element.textContent = message;
  element.className = "inline-status";
  if (tone === "success") {
    element.classList.add("inline-status--success");
  } else if (tone === "warning") {
    element.classList.add("inline-status--warning");
  } else if (tone === "error") {
    element.classList.add("inline-status--error");
  }
}

function getActiveProfile() {
  return state.profiles.find((profile) => profile.id === state.activeProfileId) || null;
}

function fallbackLanUrl() {
  const host = (window.location.hostname || "").trim().toLowerCase();
  if (!host || host === "localhost" || host === "127.0.0.1" || host === "::1") {
    return "";
  }

  try {
    const url = new URL(window.location.href);
    url.protocol = "https:";
    if (!url.port || url.port === "8000") {
      url.port = "8443";
    }
    url.pathname = "/ui/gui_html.html";
    url.search = "";
    url.hash = "";
    return url.toString();
  } catch {
    return "";
  }
}

async function request(path, options = {}) {
  const config = {
    method: options.method || "GET",
    headers: options.headers || {},
    signal: options.signal,
  };

  if (options.body instanceof FormData) {
    config.body = options.body;
  } else if (options.body !== undefined) {
    config.headers["Content-Type"] = "application/json";
    config.body = JSON.stringify(options.body);
  }

  const response = await fetch(path, config);
  const raw = await response.text();
  let payload = {};

  if (raw) {
    try {
      payload = JSON.parse(raw);
    } catch {
      payload = { message: raw };
    }
  }

  if (response.ok) {
    return payload;
  }

  const detail = payload?.detail;
  const message = typeof detail === "string"
    ? detail
    : detail?.message || payload?.message || response.statusText || `HTTP ${response.status}`;
  const error = new Error(message);
  error.status = response.status;
  error.code = detail?.code || payload?.code || null;
  error.payload = payload;
  throw error;
}

function syncDownloadsPolling() {
  const hasRunning = state.downloads.some((item) => ["pending", "running", "paused"].includes(item.state));
  if (!hasRunning && downloadsPollTimer) {
    window.clearInterval(downloadsPollTimer);
    downloadsPollTimer = null;
    return;
  }
  if (hasRunning && !downloadsPollTimer) {
    downloadsPollTimer = window.setInterval(() => {
      loadModels({ silent: true });
    }, 2500);
  }
}

function renderProfileOptions() {
  if (!els.profileSelect || !els.profileField) return;
  els.profileSelect.innerHTML = state.profiles
    .map((profile) => `<option value="${profile.id}">${escapeHtml(profile.name)}</option>`)
    .join("");

  if (state.activeProfileId) {
    els.profileSelect.value = String(state.activeProfileId);
  }

  els.profileField.hidden = state.profiles.length <= 1;
}

function renderProfileManagement() {
  const activeProfile = getActiveProfile();
  if (els.activeProfileSummary) {
    els.activeProfileSummary.textContent = activeProfile?.name || "Не выбран";
  }
  if (els.deleteProfileButton) {
    els.deleteProfileButton.disabled = !activeProfile || state.profiles.length <= 1;
  }
}

function renderSessionList() {
  if (!els.sessionList) return;
  if (!state.sessions.length) {
    els.sessionList.innerHTML = '<div class="session-card"><p class="subtle">Пока нет диалогов.</p></div>';
    return;
  }

  els.sessionList.innerHTML = state.sessions
    .map((session) => {
      const active = session.id === state.currentSessionId ? " session-card--active" : "";
      const metaParts = [session.model_name, formatDateTime(session.updated_at)].filter(Boolean);
      return `
        <article class="session-card${active}" data-session-id="${escapeHtml(session.id)}">
          <div class="session-card__top">
            <div>
              <h3 class="session-card__title">${escapeHtml(session.title || "Новый чат")}</h3>
              <p class="session-card__meta">${escapeHtml(metaParts.join(" • "))}</p>
            </div>
            <div class="session-card__actions">
              <button class="session-mini-button" type="button" data-action="open" data-session-id="${escapeHtml(session.id)}" aria-label="Открыть чат">↗</button>
              <button class="session-mini-button" type="button" data-action="delete" data-session-id="${escapeHtml(session.id)}" aria-label="Удалить чат">✕</button>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderContextSummary() {
  if (!els.contextStatus) return;
  const model = state.currentSessionId
    ? (state.sessions.find((item) => item.id === state.currentSessionId)?.model_name || state.selectedLlmModel)
    : state.selectedLlmModel;

  if (state.latestTranscript) {
    const parts = [
      state.latestTranscript.language || "auto",
      `${(state.latestTranscript.content || "").length} символов`,
    ];
    els.contextStatus.textContent = `Транскрипт подключён • ${parts.join(" • ")}`;
    return;
  }

  if (model) {
    els.contextStatus.textContent = `Модель ${model}`;
    return;
  }

  els.contextStatus.textContent = "Без прикреплённого транскрипта";
}

function renderTranscriptStrip() {
  renderContextSummary();
}

function renderMessages() {
  if (!els.messageList || !els.emptyState) return;

  const items = state.messages || [];
  els.emptyState.hidden = items.length > 0;
  els.messageList.innerHTML = items
    .map((message, index) => {
      const role = message.role === "user" ? "user" : message.role === "assistant" ? "assistant" : "system";
      const author = role === "user" ? "Вы" : role === "assistant" ? "LocalGPT" : "Система";
      const canCopy = role !== "user" && message.content;
      return `
        <div class="message-row message-row--${role}">
          <article class="message-card">
            <div class="message-card__top">
              <span class="message-card__author">${escapeHtml(author)}</span>
              <span class="message-card__time">${escapeHtml(formatDateTime(message.created_at))}</span>
            </div>
            <div class="message-card__body">${formatMultiline(message.content || "")}</div>
            ${canCopy
              ? `<div class="message-card__actions"><button class="message-copy-button" type="button" data-copy-index="${index}">Скопировать</button></div>`
              : ""}
          </article>
        </div>
      `;
    })
    .join("");
  requestAnimationFrame(() => {
    syncMessageScrollState();
  });
}

function renderModelControls() {
  if (!els.llmModelSelect || !els.recommendedModels) return;

  const installedNames = new Set(state.installedModels.map((item) => item.name));
  const mergedOptions = [
    ...state.installedModels.map((item) => item.name),
    ...state.recommendedModels.map((item) => item.name).filter((name) => !installedNames.has(name)),
  ];

  els.llmModelSelect.innerHTML = mergedOptions
    .map((name) => {
      const recommended = state.recommendedModels.some((item) => item.name === name) && !installedNames.has(name);
      return `<option value="${escapeHtml(name)}">${escapeHtml(name)}${recommended ? " (рекомендовано)" : ""}</option>`;
    })
    .join("");

  const preferredModel = state.selectedLlmModel || readStored(STORAGE_KEYS.llmModel, state.defaultModel);
  if (preferredModel && mergedOptions.includes(preferredModel)) {
    els.llmModelSelect.value = preferredModel;
  } else if (mergedOptions.length) {
    els.llmModelSelect.value = mergedOptions[0];
    state.selectedLlmModel = mergedOptions[0];
    writeStored(STORAGE_KEYS.llmModel, mergedOptions[0]);
  }

  els.recommendedModels.innerHTML = state.recommendedModels
    .map((item) => {
      const installed = installedNames.has(item.name);
      return `<button class="chip-button${installed ? " chip-button--installed" : ""}" type="button" data-recommended-model="${escapeHtml(item.name)}">${escapeHtml(item.label || item.name)}</button>`;
    })
    .join("");
}

function renderModelSettings() {
  const profile = getActiveProfile();
  const modelName = state.selectedLlmModel || els.llmModelSelect?.value || "";
  if (els.modelSettingsSummary) {
    els.modelSettingsSummary.textContent = profile && modelName
      ? `${profile.name} • ${modelName}`
      : "Профиль и модель не выбраны";
  }

  const disabled = !profile || !modelName;
  const { effective = {}, overrides = {} } = state.modelSettingsState || {};
  const values = {
    temperature: overrides.temperature ?? effective.temperature ?? "",
    max_tokens: overrides.max_tokens ?? effective.max_tokens ?? "",
    num_ctx: overrides.num_ctx ?? effective.num_ctx ?? "",
    mem_turns: overrides.mem_turns ?? effective.mem_turns ?? "",
  };

  if (els.temperatureInput) {
    els.temperatureInput.disabled = disabled;
    els.temperatureInput.value = values.temperature === "" ? "" : String(values.temperature);
  }
  if (els.maxTokensInput) {
    els.maxTokensInput.disabled = disabled;
    els.maxTokensInput.value = values.max_tokens === "" ? "" : String(values.max_tokens);
  }
  if (els.numCtxInput) {
    els.numCtxInput.disabled = disabled;
    els.numCtxInput.value = values.num_ctx === "" ? "" : String(values.num_ctx);
  }
  if (els.memTurnsInput) {
    els.memTurnsInput.disabled = disabled;
    els.memTurnsInput.value = values.mem_turns === "" ? "" : String(values.mem_turns);
  }
  if (els.saveModelSettingsButton) {
    els.saveModelSettingsButton.disabled = disabled;
  }
  if (els.resetModelSettingsButton) {
    els.resetModelSettingsButton.disabled = disabled;
  }
}

function renderWhisperControls() {
  if (!els.whisperModelSelect || !els.promptPresetSelect) return;
  els.whisperModelSelect.innerHTML = WHISPER_MODELS
    .map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`)
    .join("");
  els.whisperModelSelect.value = WHISPER_MODELS.includes(state.selectedWhisperModel) ? state.selectedWhisperModel : "small";
  els.promptPresetSelect.value = ["none", "ru", "en"].includes(state.selectedPromptPreset) ? state.selectedPromptPreset : "none";
}

function renderTtsControls() {
  if (!els.ttsProviderSelect || !els.ttsVoiceSelect || !els.ttsSettingsStatus) return;

  const provider = (state.selectedTtsProvider || "piper").trim() || "piper";
  els.ttsProviderSelect.value = provider;
  els.ttsProviderSelect.disabled = true;

  if (!state.ttsVoices.length) {
    els.ttsVoiceSelect.innerHTML = '<option value="">Нет локальных голосов</option>';
    els.ttsVoiceSelect.value = "";
    els.ttsVoiceSelect.disabled = true;
    setInlineStatus(
      els.ttsSettingsStatus,
      state.ttsHealthy
        ? "Локальные Piper-голоса не найдены в models/tts/piper."
        : "Локальный TTS пока недоступен. Проверьте Piper и локальные голоса.",
      state.ttsHealthy ? "warning" : "error",
    );
    return;
  }

  const selectedExists = state.ttsVoices.some((voice) => voice.id === state.selectedTtsVoiceId);
  if (!selectedExists) {
    state.selectedTtsVoiceId = state.ttsVoices[0]?.id || "";
    writeStored(STORAGE_KEYS.ttsVoiceId, state.selectedTtsVoiceId);
  }

  els.ttsVoiceSelect.innerHTML = state.ttsVoices
    .map((voice) => `<option value="${escapeHtml(voice.id)}">${escapeHtml(voice.label || voice.name || voice.id)}</option>`)
    .join("");
  els.ttsVoiceSelect.value = state.selectedTtsVoiceId;
  els.ttsVoiceSelect.disabled = false;

  const selectedVoice = state.ttsVoices.find((voice) => voice.id === state.selectedTtsVoiceId);
  setInlineStatus(
    els.ttsSettingsStatus,
    selectedVoice
      ? `Кнопка "Озвучить" использует голос: ${selectedVoice.label || selectedVoice.name || selectedVoice.id}`
      : 'Кнопка "Озвучить" использует выбранный локальный голос.',
    "success",
  );
}

function renderDownloads() {
  if (!els.downloadList) return;
  if (!state.downloads.length) {
    els.downloadList.innerHTML = '<p class="subtle">Активных загрузок нет.</p>';
    return;
  }

  els.downloadList.innerHTML = state.downloads
    .map((item) => {
      const percent = typeof item.percent === "number" ? Math.max(0, Math.min(100, item.percent)) : 0;
      const eta = item.eta_seconds ? ` • ETA ${item.eta_seconds}s` : "";
      const canCancel = ["pending", "running", "paused"].includes(item.state);
      return `
        <article class="download-card">
          <div class="download-card__top">
            <strong>${escapeHtml(item.model || "модель")}</strong>
            <span class="subtle">${escapeHtml(item.state || "")}</span>
          </div>
          <div class="download-progress"><div class="download-progress__bar" style="width:${percent}%;"></div></div>
          <div class="subtle">${escapeHtml(item.message || "Ожидание")} ${escapeHtml(eta)}</div>
          ${canCancel ? `<div class="button-row"><button class="button button--ghost" type="button" data-cancel-download="${escapeHtml(item.task_id || "")}">Остановить</button></div>` : ""}
        </article>
      `;
    })
    .join("");
}

function renderLanUrl() {
  const value = state.lanUrl || "Недоступно";
  if (els.lanUrlValue) {
    els.lanUrlValue.textContent = value;
  }
  if (els.copyLanUrlButton) {
    els.copyLanUrlButton.disabled = !state.lanUrl;
  }
  if (els.copyLanUrlFromSettingsButton) {
    els.copyLanUrlFromSettingsButton.disabled = !state.lanUrl;
  }
}

function renderSettings() {
  renderProfileOptions();
  renderProfileManagement();
  renderSessionList();
  renderModelControls();
  renderModelSettings();
  renderWhisperControls();
  renderTtsControls();
  renderDownloads();
  renderLanUrl();

  if (els.modelsDirInput && !els.modelsDirInput.value && state.modelsDir) {
    els.modelsDirInput.value = state.modelsDir;
  }
}

function applyCurrentSessionMeta() {
  const session = state.sessions.find((item) => item.id === state.currentSessionId);
  const title = session?.title || "Новый чат";
  state.selectedLlmModel = session?.model_name || state.selectedLlmModel || state.defaultModel;
  writeStored(STORAGE_KEYS.llmModel, state.selectedLlmModel || "");
  if (els.chatTitle) {
    els.chatTitle.textContent = title;
  }
  renderContextSummary();
  renderSettings();
  void refreshModelSettings({ silent: true });
}

function openSidebar() {
  if (!isMobileLayout() || !els.sidebar || !els.sidebarBackdrop) return;
  els.sidebar.classList.add("sidebar--open");
  els.sidebarBackdrop.hidden = false;
}

function closeSidebar() {
  if (!els.sidebar || !els.sidebarBackdrop) return;
  els.sidebar.classList.remove("sidebar--open");
  els.sidebarBackdrop.hidden = true;
}

function openSettings() {
  if (!els.settingsBackdrop) return;
  els.settingsBackdrop.hidden = false;
  renderSettings();
  void refreshModelSettings({ silent: true });
  void loadTtsSettings({ silent: true });
}

function closeSettings() {
  if (!els.settingsBackdrop) return;
  els.settingsBackdrop.hidden = true;
}

async function copyText(value) {
  if (!value) return;
  await navigator.clipboard.writeText(value);
}

async function loadHealth({ silent = false } = {}) {
  try {
    const data = await request("/health");
    state.serverHealthy = true;
    state.defaultModel = data?.model || state.defaultModel;
    state.lanUrl = data?.ios_url || fallbackLanUrl();
    state.modelsDir = data?.models_dir || state.modelsDir || "";
    setHealthBadge("Онлайн", "success");
    renderLanUrl();
    renderContextSummary();
  } catch (error) {
    state.serverHealthy = false;
    state.lanUrl = fallbackLanUrl();
    setHealthBadge("Нет связи", "error");
    renderLanUrl();
    if (!silent) {
      setFooter(`Сервер недоступен: ${error.message || error}`, "error");
    }
  }
}

async function loadModels({ silent = false } = {}) {
  try {
    const data = await request("/models");
    state.installedModels = Array.isArray(data?.installed) ? data.installed : [];
    state.recommendedModels = Array.isArray(data?.recommended) ? data.recommended : [];
    state.downloads = Array.isArray(data?.downloads) ? data.downloads : [];
    const savedModel = readStored(STORAGE_KEYS.llmModel, state.defaultModel);
    if (!state.selectedLlmModel) {
      state.selectedLlmModel = savedModel || state.installedModels[0]?.name || state.recommendedModels[0]?.name || state.defaultModel;
    }
    renderModelControls();
    renderDownloads();
    void refreshModelSettings({ silent: true });
    syncDownloadsPolling();
  } catch (error) {
    if (!silent) {
      setFooter(`Не удалось получить список моделей: ${error.message || error}`, "error");
    }
  }
}

async function loadStoragePaths() {
  try {
    const data = await request("/storage/paths");
    state.modelsDir = data?.paths?.base || state.modelsDir || "";
    if (els.modelsDirInput) {
      els.modelsDirInput.value = state.modelsDir;
    }
  } catch {
    // ignore
  }
}

async function loadTtsSettings({ silent = false } = {}) {
  try {
    const [health, voicesData] = await Promise.all([
      request("/tts/health"),
      request("/tts/voices"),
    ]);
    state.ttsHealthy = Boolean(health?.tts_enabled && health?.provider?.available);
    state.selectedTtsProvider = String(health?.default_provider || state.selectedTtsProvider || "piper").trim() || "piper";
    writeStored(STORAGE_KEYS.ttsProvider, state.selectedTtsProvider);
    state.ttsVoices = Array.isArray(voicesData?.items) ? voicesData.items : [];
    renderTtsControls();
    return true;
  } catch (error) {
    state.ttsHealthy = false;
    state.ttsVoices = [];
    renderTtsControls();
    if (!silent) {
      setFooter(`Не удалось получить настройки озвучки: ${error.message || error}`, "error");
    }
    return false;
  }
}

async function refreshModelSettings({ silent = false } = {}) {
  const modelName = state.selectedLlmModel || els.llmModelSelect?.value || "";
  if (!state.activeProfileId || !modelName) {
    state.modelSettingsState = { effective: {}, overrides: {}, defaults: {} };
    renderModelSettings();
    if (!silent) {
      setInlineStatus(els.modelSettingsStatus, "Выберите профиль и модель.", "warning");
    }
    return;
  }

  try {
    const data = await request(`/model_settings?profile_id=${encodeURIComponent(state.activeProfileId)}&model_name=${encodeURIComponent(modelName)}`);
    state.modelSettingsState = data || { effective: {}, overrides: {}, defaults: {} };
    renderModelSettings();
    if (!silent) {
      setInlineStatus(els.modelSettingsStatus, "Настройки модели загружены.", "success");
    }
  } catch (error) {
    if (!silent) {
      setInlineStatus(els.modelSettingsStatus, `Не удалось загрузить настройки: ${error.message || error}`, "error");
    }
  }
}

async function openSession(sessionId) {
  state.currentSessionId = sessionId || null;
  writeStored(STORAGE_KEYS.activeSessionId, state.currentSessionId || "");

  if (!sessionId) {
    state.messages = [];
    state.latestTranscript = null;
    if (els.chatTitle) {
      els.chatTitle.textContent = "Новый чат";
    }
    renderMessages();
    renderTranscriptStrip();
    renderSessionList();
    renderContextSummary();
    closeSidebar();
    return;
  }

  const session = state.sessions.find((item) => item.id === sessionId);
  if (session) {
    state.selectedLlmModel = session.model_name || state.selectedLlmModel;
  }

  renderSessionList();
  applyCurrentSessionMeta();

  try {
    const [messagesData, transcriptsData] = await Promise.all([
      request(`/sessions/${encodeURIComponent(sessionId)}/messages`),
      request(`/transcripts?profile_id=${encodeURIComponent(state.activeProfileId)}&session_id=${encodeURIComponent(sessionId)}`),
    ]);

    state.messages = Array.isArray(messagesData?.messages) ? messagesData.messages : [];
    const transcripts = Array.isArray(transcriptsData?.transcripts) ? transcriptsData.transcripts : [];
    state.latestTranscript = transcripts[0] || null;
    renderMessages();
    renderTranscriptStrip();
    scrollMessagesToBottom({ force: true });
  } catch (error) {
    setFooter(`Не удалось загрузить чат: ${error.message || error}`, "error");
  } finally {
    closeSidebar();
  }
}

async function loadSessions({ preferredSessionId = null } = {}) {
  if (!state.activeProfileId) return;
  try {
    const data = await request(`/sessions?profile_id=${encodeURIComponent(state.activeProfileId)}`);
    state.sessions = Array.isArray(data?.sessions) ? data.sessions : [];
    renderSessionList();

    const savedSessionId = preferredSessionId || readStored(STORAGE_KEYS.activeSessionId, "");
    const nextSession = state.sessions.find((item) => item.id === savedSessionId)?.id
      || (state.currentSessionId && state.sessions.some((item) => item.id === state.currentSessionId) ? state.currentSessionId : null)
      || state.sessions[0]?.id
      || null;

    if (nextSession && state.sessions.some((item) => item.id === nextSession)) {
      await openSession(nextSession);
    } else if (!state.currentSessionId) {
      await openSession(null);
    } else if (!state.sessions.some((item) => item.id === state.currentSessionId)) {
      await openSession(state.sessions[0]?.id || null);
    }
  } catch (error) {
    setFooter(`Не удалось загрузить список диалогов: ${error.message || error}`, "error");
  }
}

async function setActiveProfile(profileId, { preferredSessionId = null } = {}) {
  state.activeProfileId = profileId || null;
  writeStored(STORAGE_KEYS.activeProfileId, state.activeProfileId || "");
  renderProfileOptions();
  await loadSessions({ preferredSessionId });
  await refreshModelSettings({ silent: true });
}

async function loadProfiles() {
  try {
    const data = await request("/profiles");
    state.profiles = Array.isArray(data?.profiles) ? data.profiles : [];
    renderProfileOptions();
    renderProfileManagement();

    const stored = Number(readStored(STORAGE_KEYS.activeProfileId, ""));
    const preferred = state.profiles.find((item) => item.id === stored)?.id || state.profiles[0]?.id || null;
    if (preferred) {
      await setActiveProfile(preferred);
    }
  } catch (error) {
    setFooter(`Не удалось загрузить профили: ${error.message || error}`, "error");
  }
}

function parseOptionalNumber(value, mode = "int") {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const parsed = mode === "float" ? Number(raw) : Number.parseInt(raw, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

async function saveModelSettingsFlow() {
  const modelName = state.selectedLlmModel || els.llmModelSelect?.value || "";
  if (!state.activeProfileId || !modelName) {
    setInlineStatus(els.modelSettingsStatus, "Нет активного профиля или модели.", "warning");
    return;
  }

  try {
    const data = await request("/model_settings", {
      method: "POST",
      body: {
        profile_id: state.activeProfileId,
        model_name: modelName,
        temperature: parseOptionalNumber(els.temperatureInput?.value, "float"),
        max_tokens: parseOptionalNumber(els.maxTokensInput?.value, "int"),
        num_ctx: parseOptionalNumber(els.numCtxInput?.value, "int"),
        mem_turns: parseOptionalNumber(els.memTurnsInput?.value, "int"),
      },
    });
    state.modelSettingsState = data || state.modelSettingsState;
    renderModelSettings();
    setInlineStatus(els.modelSettingsStatus, "Настройки модели сохранены.", "success");
  } catch (error) {
    setInlineStatus(els.modelSettingsStatus, `Не удалось сохранить настройки: ${error.message || error}`, "error");
  }
}

async function resetModelSettingsFlow() {
  const modelName = state.selectedLlmModel || els.llmModelSelect?.value || "";
  if (!state.activeProfileId || !modelName) {
    setInlineStatus(els.modelSettingsStatus, "Нет активного профиля или модели.", "warning");
    return;
  }

  try {
    const data = await request("/model_settings/reset_to_defaults", {
      method: "POST",
      body: {
        profile_id: state.activeProfileId,
        model_name: modelName,
      },
    });
    state.modelSettingsState = data || state.modelSettingsState;
    await refreshModelSettings({ silent: true });
    setInlineStatus(els.modelSettingsStatus, "Настройки модели сброшены.", "success");
  } catch (error) {
    setInlineStatus(els.modelSettingsStatus, `Не удалось сбросить настройки: ${error.message || error}`, "error");
  }
}

async function createProfileFlow() {
  const name = (els.profileNameInput?.value || "").trim();
  const description = (els.profileDescriptionInput?.value || "").trim();
  if (!name) {
    setInlineStatus(els.profileStatus, "Введите название профиля.", "warning");
    return;
  }

  try {
    const profile = await request("/profiles", {
      method: "POST",
      body: {
        name,
        description: description || null,
      },
    });
    state.profiles = [...state.profiles, profile];
    renderProfileOptions();
    renderProfileManagement();
    if (els.profileNameInput) {
      els.profileNameInput.value = "";
    }
    if (els.profileDescriptionInput) {
      els.profileDescriptionInput.value = "";
    }
    await setActiveProfile(profile.id);
    setInlineStatus(els.profileStatus, `Профиль «${profile.name}» создан.`, "success");
  } catch (error) {
    setInlineStatus(els.profileStatus, `Не удалось создать профиль: ${error.message || error}`, "error");
  }
}

async function deleteCurrentProfileFlow() {
  const profile = getActiveProfile();
  if (!profile) {
    setInlineStatus(els.profileStatus, "Нет активного профиля.", "warning");
    return;
  }
  if (!window.confirm(`Удалить профиль «${profile.name}» и все его данные?`)) return;

  try {
    await request(`/profiles/${encodeURIComponent(profile.id)}`, { method: "DELETE" });
    setInlineStatus(els.profileStatus, "Профиль удалён.", "warning");
    await loadProfiles();
  } catch (error) {
    setInlineStatus(els.profileStatus, `Не удалось удалить профиль: ${error.message || error}`, "error");
  }
}

async function createSessionForCurrentContext() {
  if (!state.activeProfileId) {
    throw new Error("Сначала выберите профиль");
  }

  const payload = {
    profile_id: state.activeProfileId,
    title: "Новый чат",
    model_name: state.selectedLlmModel || state.defaultModel,
  };

  const session = await request("/sessions", { method: "POST", body: payload });
  await loadSessions({ preferredSessionId: session.id });
  return session.id;
}

function appendOptimisticMessages(userText) {
  const now = new Date().toISOString();
  state.messages = [
    ...state.messages,
    { role: "user", content: userText, created_at: now },
    { role: "assistant", content: "Думаю…", created_at: now },
  ];
  renderMessages();
  scrollMessagesToBottom({ force: true });
}

async function ensureModelInstalled(modelName) {
  if (!modelName) return true;
  if (state.installedModels.some((item) => item.name === modelName)) {
    return true;
  }

  await startModelDownload(modelName);
  return false;
}

async function sendCurrentPrompt() {
  const query = (els.promptInput?.value || "").trim();
  if (!query || state.isSending) return;
  if (!state.activeProfileId) {
    setFooter("Сначала выберите профиль.", "warning");
    return;
  }

  const selectedModel = state.selectedLlmModel || state.defaultModel;
  const modelAvailable = await ensureModelInstalled(selectedModel);
  if (!modelAvailable) {
    setFooter(`Модель ${selectedModel} загружается. Повторите отправку после завершения.`, "warning");
    openSettings();
    return;
  }

  state.isSending = true;
  updateSendButtonState();
  appendOptimisticMessages(query);
  setFooter("Генерация ответа…");

  try {
    const payload = {
      query,
      profile_id: state.activeProfileId,
      model: selectedModel,
      model_name: selectedModel,
    };

    if (state.currentSessionId) {
      payload.session_id = state.currentSessionId;
    }

    const data = await request("/chat", { method: "POST", body: payload });
    const nextSessionId = data?.session_id || state.currentSessionId;
    state.selectedLlmModel = data?.model_name || selectedModel;
    writeStored(STORAGE_KEYS.llmModel, state.selectedLlmModel || "");

    if (els.promptInput) {
      els.promptInput.value = "";
      autoResizePrompt();
      updateSendButtonState();
    }

    await loadSessions({ preferredSessionId: nextSessionId });
    setFooter("Ответ готов.", "success");
  } catch (error) {
    state.messages = [
      ...state.messages.slice(0, -1),
      {
        role: "system",
        content: `Ошибка: ${error.message || error}`,
        created_at: new Date().toISOString(),
      },
    ];
    renderMessages();
    setFooter(`Ошибка чата: ${error.message || error}`, "error");
  } finally {
    state.isSending = false;
    updateSendButtonState();
    scrollMessagesToBottom({ force: true });
  }
}

async function handleTranscription(file) {
  if (!file || state.isTranscribing) return;
  if (!state.activeProfileId) {
    setFooter("Сначала выберите профиль.", "warning");
    return;
  }

  state.isTranscribing = true;
  if (els.composerMenuButton) {
    els.composerMenuButton.disabled = true;
  }
  setFooter(`Транскрибация ${file.name}…`);

  try {
    const sessionId = state.currentSessionId || await createSessionForCurrentContext();
    const formData = new FormData();
    formData.append("file", file);
    formData.append("profile_id", String(state.activeProfileId));
    formData.append("session_id", sessionId);
    formData.append("model", state.selectedWhisperModel || "small");
    formData.append("prompt_preset", state.selectedPromptPreset || "none");
    formData.append("language", "auto");

    const data = await request("/transcribe", { method: "POST", body: formData });
    await loadSessions({ preferredSessionId: sessionId });
    setFooter(
      `Транскрипт прикреплён: ${file.name} • ${(data?.text || "").length} символов`,
      "success",
    );
  } catch (error) {
    setFooter(`Ошибка транскрибации: ${error.message || error}`, "error");
  } finally {
    state.isTranscribing = false;
    if (els.composerMenuButton) {
      els.composerMenuButton.disabled = false;
    }
    if (els.transcribeInput) {
      els.transcribeInput.value = "";
    }
  }
}

async function startModelDownload(modelName) {
  const target = (modelName || "").trim();
  if (!target) {
    setFooter("Укажите модель Ollama для загрузки.", "warning");
    return;
  }

  try {
    await request("/models/pull", { method: "POST", body: { model: target } });
    state.selectedLlmModel = target;
    writeStored(STORAGE_KEYS.llmModel, target);
    await loadModels();
    renderSettings();
    setFooter(`Загрузка модели ${target} запущена.`, "success");
  } catch (error) {
    setFooter(`Не удалось запустить загрузку модели: ${error.message || error}`, "error");
  }
}

async function cancelDownload(taskId) {
  if (!taskId) return;
  try {
    await request(`/models/pull/${encodeURIComponent(taskId)}/cancel`, { method: "POST", body: {} });
    await loadModels();
    setFooter("Загрузка остановлена.", "warning");
  } catch (error) {
    setFooter(`Не удалось остановить загрузку: ${error.message || error}`, "error");
  }
}

async function deleteCurrentModel() {
  const modelName = (els.llmModelSelect?.value || "").trim();
  if (!modelName) return;
  if (!window.confirm(`Удалить модель ${modelName}?`)) return;

  try {
    await request(`/models/${encodeURIComponent(modelName)}`, { method: "DELETE" });
    if (state.selectedLlmModel === modelName) {
      state.selectedLlmModel = "";
      writeStored(STORAGE_KEYS.llmModel, "");
    }
    await loadModels();
    setFooter(`Модель ${modelName} удалена.`, "success");
  } catch (error) {
    setFooter(`Не удалось удалить модель: ${error.message || error}`, "error");
  }
}

async function updateCurrentSessionMeta(patch) {
  if (!state.currentSessionId) return;
  try {
    const updated = await request(`/sessions/${encodeURIComponent(state.currentSessionId)}`, {
      method: "PATCH",
      body: patch,
    });
    state.sessions = state.sessions.map((item) => (item.id === updated.id ? updated : item));
    renderSessionList();
    applyCurrentSessionMeta();
  } catch (error) {
    setFooter(`Не удалось обновить настройки чата: ${error.message || error}`, "error");
  }
}

async function saveModelsDir(moveExisting) {
  const target = (els.modelsDirInput?.value || "").trim();
  if (!target) {
    setFooter("Укажите путь к папке моделей.", "warning");
    return;
  }

  try {
    const data = await request("/storage/paths", {
      method: "POST",
      body: { models_dir: target, move_existing: moveExisting },
    });
    state.modelsDir = data?.paths?.base || target;
    if (els.modelsDirInput) {
      els.modelsDirInput.value = state.modelsDir;
    }
    setFooter(`Путь к моделям обновлён: ${state.modelsDir}`, "success");
  } catch (error) {
    setFooter(`Не удалось сохранить путь к моделям: ${error.message || error}`, "error");
  }
}

async function deleteSessionById(sessionId) {
  if (!sessionId) return;
  if (!window.confirm("Удалить этот диалог и историю сообщений?")) return;

  try {
    await request(`/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
    const nextSession = state.sessions.find((item) => item.id !== sessionId)?.id || null;
    state.sessions = state.sessions.filter((item) => item.id !== sessionId);
    if (state.currentSessionId === sessionId) {
      state.currentSessionId = null;
      writeStored(STORAGE_KEYS.activeSessionId, "");
    }
    renderSessionList();
    await openSession(nextSession);
    setFooter("Диалог удалён.", "warning");
  } catch (error) {
    setFooter(`Не удалось удалить диалог: ${error.message || error}`, "error");
  }
}

async function copyLanUrl() {
  if (!state.lanUrl) {
    setFooter("LAN URL пока недоступен.", "warning");
    return;
  }
  try {
    await copyText(state.lanUrl);
    setFooter("LAN URL скопирован.", "success");
  } catch {
    setFooter("Не удалось скопировать LAN URL.", "error");
  }
}

function isExpectedShutdownError(error) {
  const raw = String(error?.message || error || "").toLowerCase();
  return raw.includes("failed to fetch")
    || raw.includes("load failed")
    || raw.includes("networkerror")
    || raw.includes("network request failed")
    || raw.includes("the network connection was lost");
}

async function shutdownRuntime() {
  if (!window.confirm("Остановить backend и Caddy?")) return;
  try {
    await request("/runtime/shutdown", { method: "POST", body: {} });
    setFooter("Остановка запущена. Для нового старта снова откройте launcher.", "warning");
    setHealthBadge("Остановка…", "error");
  } catch (error) {
    if (isExpectedShutdownError(error)) {
      setFooter("Остановка запущена. Для нового старта снова откройте launcher.", "warning");
      setHealthBadge("Остановлено", "error");
      return;
    }
    setFooter(`Не удалось остановить приложение: ${error.message || error}`, "error");
  }
}

function bindEvents() {
  els.toggleSidebarButton?.addEventListener("click", () => openSidebar());
  els.sidebarBackdrop?.addEventListener("click", () => closeSidebar());
  els.newChatButton?.addEventListener("click", async () => {
    state.currentSessionId = null;
    writeStored(STORAGE_KEYS.activeSessionId, "");
    await openSession(null);
  });

  els.sessionList?.addEventListener("click", async (event) => {
    const openButton = event.target.closest("[data-action='open']");
    const deleteButton = event.target.closest("[data-action='delete']");
    const card = event.target.closest("[data-session-id]");

    if (deleteButton) {
      await deleteSessionById(deleteButton.dataset.sessionId);
      return;
    }

    const sessionId = openButton?.dataset.sessionId || card?.dataset.sessionId;
    if (sessionId) {
      await openSession(sessionId);
    }
  });

  els.profileSelect?.addEventListener("change", async () => {
    const nextId = Number(els.profileSelect.value);
    if (Number.isFinite(nextId)) {
      await setActiveProfile(nextId);
    }
  });

  els.composerForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await sendCurrentPrompt();
  });

  els.promptInput?.addEventListener("input", () => {
    autoResizePrompt();
    updateSendButtonState();
  });
  els.promptInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!state.isSending) {
        sendCurrentPrompt();
      }
    }
  });

  els.voiceRecordButton?.addEventListener("click", async () => {
    toggleComposerMenu(false);
    await toggleVoiceRecording();
  });

  els.messageScroll?.addEventListener("scroll", () => {
    syncMessageScrollState();
  });

  els.scrollTopButton?.addEventListener("click", () => {
    scrollMessagesToTop();
  });

  els.composerMenuButton?.addEventListener("click", () => {
    toggleComposerMenu();
  });

  els.transcribeMenuItem?.addEventListener("click", () => {
    toggleComposerMenu(false);
    els.transcribeInput?.click();
  });
  els.speakMenuItem?.addEventListener("click", () => {
    toggleComposerMenu(false);
    speakLatestAssistantMessage();
  });
  els.transcribeInput?.addEventListener("change", async () => {
    const file = els.transcribeInput.files?.[0];
    if (file) {
      await handleTranscription(file);
    }
  });

  els.messageList?.addEventListener("click", async (event) => {
    const copyButton = event.target.closest("[data-copy-index]");
    if (!copyButton) return;
    try {
      const index = Number(copyButton.dataset.copyIndex);
      const message = Number.isFinite(index) ? state.messages[index] : null;
      await copyText(message?.content || "");
      setFooter("Сообщение скопировано.", "success");
    } catch {
      setFooter("Не удалось скопировать сообщение.", "error");
    }
  });

  els.openSettingsButton?.addEventListener("click", () => openSettings());
  els.closeSettingsButton?.addEventListener("click", () => closeSettings());
  els.settingsBackdrop?.addEventListener("click", (event) => {
    if (event.target === els.settingsBackdrop) {
      closeSettings();
    }
  });

  els.copyLanUrlButton?.addEventListener("click", async () => copyLanUrl());
  els.copyLanUrlFromSettingsButton?.addEventListener("click", async () => copyLanUrl());
  els.shutdownButton?.addEventListener("click", async () => shutdownRuntime());
  els.createProfileButton?.addEventListener("click", async () => createProfileFlow());
  els.deleteProfileButton?.addEventListener("click", async () => deleteCurrentProfileFlow());
  els.saveModelSettingsButton?.addEventListener("click", async () => saveModelSettingsFlow());
  els.resetModelSettingsButton?.addEventListener("click", async () => resetModelSettingsFlow());

  els.llmModelSelect?.addEventListener("change", async () => {
    state.selectedLlmModel = (els.llmModelSelect.value || "").trim();
    writeStored(STORAGE_KEYS.llmModel, state.selectedLlmModel);
    renderContextSummary();
    renderModelSettings();
    if (state.currentSessionId && state.selectedLlmModel) {
      await updateCurrentSessionMeta({ model_name: state.selectedLlmModel });
    }
    await refreshModelSettings({ silent: true });
  });

  els.whisperModelSelect?.addEventListener("change", () => {
    state.selectedWhisperModel = els.whisperModelSelect.value || "small";
    writeStored(STORAGE_KEYS.whisperModel, state.selectedWhisperModel);
  });

  els.promptPresetSelect?.addEventListener("change", () => {
    state.selectedPromptPreset = els.promptPresetSelect.value || "none";
    writeStored(STORAGE_KEYS.promptPreset, state.selectedPromptPreset);
  });

  els.ttsVoiceSelect?.addEventListener("change", () => {
    state.selectedTtsVoiceId = els.ttsVoiceSelect.value || "";
    writeStored(STORAGE_KEYS.ttsVoiceId, state.selectedTtsVoiceId);
    renderTtsControls();
  });

  els.refreshTtsVoicesButton?.addEventListener("click", async () => {
    const ok = await loadTtsSettings();
    if (ok) {
      setFooter("Список локальных TTS-голосов обновлён.", "success");
    }
  });

  els.refreshModelsButton?.addEventListener("click", async () => {
    await loadModels();
    setFooter("Список моделей обновлён.", "success");
  });

  els.downloadModelButton?.addEventListener("click", async () => {
    const target = (els.downloadModelInput?.value || "").trim();
    await startModelDownload(target);
    if (els.downloadModelInput) {
      els.downloadModelInput.value = "";
    }
  });

  els.deleteModelButton?.addEventListener("click", async () => {
    await deleteCurrentModel();
  });

  els.recommendedModels?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-recommended-model]");
    if (!button) return;
    const modelName = button.dataset.recommendedModel || "";
    const isInstalled = state.installedModels.some((item) => item.name === modelName);
    if (isInstalled) {
      state.selectedLlmModel = modelName;
      writeStored(STORAGE_KEYS.llmModel, modelName);
      renderSettings();
      renderContextSummary();
      if (state.currentSessionId) {
        await updateCurrentSessionMeta({ model_name: modelName });
      }
      await refreshModelSettings({ silent: true });
      return;
    }
    await startModelDownload(modelName);
  });

  els.downloadList?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-cancel-download]");
    if (!button) return;
    await cancelDownload(button.dataset.cancelDownload || "");
  });

  els.applyModelsDirButton?.addEventListener("click", async () => {
    await saveModelsDir(false);
  });

  els.moveModelsDirButton?.addEventListener("click", async () => {
    await saveModelsDir(true);
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeSidebar();
      closeSettings();
      toggleComposerMenu(false);
    }
  });

  window.addEventListener("click", (event) => {
    if (!els.composerMenu || !els.composerMenuButton) return;
    const target = event.target instanceof Element ? event.target : null;
    const insideMenu = target?.closest("#composerMenu") || target?.closest("#composerMenuButton");
    if (!insideMenu) {
      toggleComposerMenu(false);
    }
  });

  window.addEventListener("resize", () => {
    if (!isMobileLayout()) {
      closeSidebar();
    }
    toggleComposerMenu(false);
    autoResizePrompt();
    syncMessageScrollState();
  });
}

async function bootstrap() {
  renderWhisperControls();
  renderTtsControls();
  renderVoiceRecordButton();
  autoResizePrompt();
  updateSendButtonState();
  bindEvents();
  await loadHealth();
  await loadModels();
  await loadStoragePaths();
  await loadTtsSettings({ silent: true });
  await loadProfiles();
  renderMessages();
  renderTranscriptStrip();
  renderContextSummary();

  healthPollTimer = window.setInterval(() => {
    loadHealth({ silent: true });
  }, 30000);
}

bootstrap().catch((error) => {
  setFooter(`Ошибка запуска интерфейса: ${error.message || error}`, "error");
});
