const WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"];
const STORAGE_KEYS = {
  activeProfileId: "localgpt_simple_profile_id",
  activeSessionId: "localgpt_simple_session_id",
  llmModel: "localgpt_simple_llm_model",
  whisperModel: "localgpt_simple_whisper_model",
  promptPreset: "localgpt_simple_prompt_preset",
  ttsProvider: "localgpt_simple_tts_provider",
  ttsVoiceId: "localgpt_simple_tts_voice_id",
  ttsSpeed: "localgpt_simple_tts_speed",
  chatLibraryOpen: "localgpt_simple_chat_library_open",
  asrLibraryOpen: "localgpt_simple_asr_library_open",
  ttsLibraryOpen: "localgpt_simple_tts_library_open",
};

const DEFAULT_TTS_SPEED_OPTIONS = [1, 1.25, 1.5, 1.75, 1.9, 2];
const ASR_TOOL_ORIGIN = "asr_tool";
const TTS_TOOL_MIN_WIDTH = 960;
const TTS_TOOL_MIN_HEIGHT = 720;

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
  quickModelSelect: document.getElementById("quickModelSelect"),
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
  fileMenuItem: document.getElementById("fileMenuItem"),
  transcribeMenuItem: document.getElementById("transcribeMenuItem"),
  speakMenuItem: document.getElementById("speakMenuItem"),
  transcribeInput: document.getElementById("transcribeInput"),
  ocrImageInput: document.getElementById("ocrImageInput"),
  scrollTopButton: document.getElementById("scrollTopButton"),
  footerStatus: document.getElementById("footerStatus"),
  toolDock: document.getElementById("toolDock"),
  asrToolWindow: document.getElementById("asrToolWindow"),
  asrToolHeader: document.querySelector("#asrToolWindow [data-tool-drag='asr']"),
  asrToolResizeHandle: document.querySelector("#asrToolWindow [data-tool-resize='asr']"),
  asrToolMinimizeButton: document.getElementById("asrToolMinimizeButton"),
  asrToolFullscreenButton: document.getElementById("asrToolFullscreenButton"),
  asrToolCloseButton: document.getElementById("asrToolCloseButton"),
  asrToolModelSelect: document.getElementById("asrToolModelSelect"),
  asrToolChooseFileButton: document.getElementById("asrToolChooseFileButton"),
  asrToolRefreshHistoryButton: document.getElementById("asrToolRefreshHistoryButton"),
  asrToolFileInput: document.getElementById("asrToolFileInput"),
  asrToolStatus: document.getElementById("asrToolStatus"),
  asrToolMeta: document.getElementById("asrToolMeta"),
  asrToolOutput: document.getElementById("asrToolOutput"),
  asrToolInsertPromptButton: document.getElementById("asrToolInsertPromptButton"),
  asrToolSendButton: document.getElementById("asrToolSendButton"),
  asrToolSaveButton: document.getElementById("asrToolSaveButton"),
  asrToolClearButton: document.getElementById("asrToolClearButton"),
  asrToolDeleteButton: document.getElementById("asrToolDeleteButton"),
  asrToolClearHistoryButton: document.getElementById("asrToolClearHistoryButton"),
  asrToolHistoryList: document.getElementById("asrToolHistoryList"),
  ttsToolWindow: document.getElementById("ttsToolWindow"),
  ttsToolHeader: document.querySelector("#ttsToolWindow [data-tool-drag='tts']"),
  ttsToolResizeHandle: document.querySelector("#ttsToolWindow [data-tool-resize='tts']"),
  ttsToolMinimizeButton: document.getElementById("ttsToolMinimizeButton"),
  ttsToolFullscreenButton: document.getElementById("ttsToolFullscreenButton"),
  ttsToolCloseButton: document.getElementById("ttsToolCloseButton"),
  ttsToolProviderSelect: document.getElementById("ttsToolProviderSelect"),
  ttsToolVoiceSelect: document.getElementById("ttsToolVoiceSelect"),
  ttsToolSpeedSelect: document.getElementById("ttsToolSpeedSelect"),
  ttsToolStatus: document.getElementById("ttsToolStatus"),
  ttsToolMeta: document.getElementById("ttsToolMeta"),
  ttsToolText: document.getElementById("ttsToolText"),
  ttsToolGenerateButton: document.getElementById("ttsToolGenerateButton"),
  ttsToolUseAssistantButton: document.getElementById("ttsToolUseAssistantButton"),
  ttsToolRefreshButton: document.getElementById("ttsToolRefreshButton"),
  ttsToolDownloadButton: document.getElementById("ttsToolDownloadButton"),
  ttsToolDeleteButton: document.getElementById("ttsToolDeleteButton"),
  ttsToolClearButton: document.getElementById("ttsToolClearButton"),
  ttsToolPlayer: document.getElementById("ttsToolPlayer"),
  ttsToolHistoryList: document.getElementById("ttsToolHistoryList"),
  ocrBackdrop: document.getElementById("ocrBackdrop"),
  closeOcrButton: document.getElementById("closeOcrButton"),
  ocrStatus: document.getElementById("ocrStatus"),
  ocrMeta: document.getElementById("ocrMeta"),
  ocrTextOutput: document.getElementById("ocrTextOutput"),
  ocrInsertPromptButton: document.getElementById("ocrInsertPromptButton"),
  ocrSendButton: document.getElementById("ocrSendButton"),
  ocrClearButton: document.getElementById("ocrClearButton"),
  settingsBackdrop: document.getElementById("settingsBackdrop"),
  closeSettingsButton: document.getElementById("closeSettingsButton"),
  llmModelSelect: document.getElementById("llmModelSelect"),
  refreshModelsButton: document.getElementById("refreshModelsButton"),
  deleteModelButton: document.getElementById("deleteModelButton"),
  downloadModelInput: document.getElementById("downloadModelInput"),
  downloadModelButton: document.getElementById("downloadModelButton"),
  recommendedModels: document.getElementById("recommendedModels"),
  chatLibraryToggle: document.getElementById("chatLibraryToggle"),
  chatLibraryMeta: document.getElementById("chatLibraryMeta"),
  chatLibraryPanel: document.getElementById("chatLibraryPanel"),
  chatModelLibrary: document.getElementById("chatModelLibrary"),
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
  refreshAsrModelsButton: document.getElementById("refreshAsrModelsButton"),
  asrSettingsStatus: document.getElementById("asrSettingsStatus"),
  asrLibraryToggle: document.getElementById("asrLibraryToggle"),
  asrLibraryMeta: document.getElementById("asrLibraryMeta"),
  asrLibraryPanel: document.getElementById("asrLibraryPanel"),
  asrModelLibrary: document.getElementById("asrModelLibrary"),
  ttsProviderSelect: document.getElementById("ttsProviderSelect"),
  ttsVoiceSelect: document.getElementById("ttsVoiceSelect"),
  refreshTtsVoicesButton: document.getElementById("refreshTtsVoicesButton"),
  refreshTtsLibraryButton: document.getElementById("refreshTtsLibraryButton"),
  ttsSettingsStatus: document.getElementById("ttsSettingsStatus"),
  ttsLibraryToggle: document.getElementById("ttsLibraryToggle"),
  ttsLibraryMeta: document.getElementById("ttsLibraryMeta"),
  ttsLibraryPanel: document.getElementById("ttsLibraryPanel"),
  ttsVoiceSearchInput: document.getElementById("ttsVoiceSearchInput"),
  ttsVoiceLibrary: document.getElementById("ttsVoiceLibrary"),
  modelsDirInput: document.getElementById("modelsDirInput"),
  applyModelsDirButton: document.getElementById("applyModelsDirButton"),
  moveModelsDirButton: document.getElementById("moveModelsDirButton"),
  lanUrlValue: document.getElementById("lanUrlValue"),
  copyLanUrlFromSettingsButton: document.getElementById("copyLanUrlFromSettingsButton"),
  shutdownButton: document.getElementById("shutdownButton"),
  downloadList: document.getElementById("downloadList"),
};

const VOICE_RECORD_ICON = els.voiceRecordButton?.innerHTML || "";

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
  selectedWhisperModel: readStored(STORAGE_KEYS.whisperModel, "medium"),
  selectedPromptPreset: readStored(STORAGE_KEYS.promptPreset, "none"),
  selectedTtsProvider: readStored(STORAGE_KEYS.ttsProvider, "piper"),
  selectedTtsVoiceId: readStored(STORAGE_KEYS.ttsVoiceId, ""),
  selectedTtsSpeed: readStored(STORAGE_KEYS.ttsSpeed, "1"),
  latestTranscript: null,
  serverHealthy: false,
  ttsHealthy: false,
  defaultModel: "",
  lanUrl: "",
  isSending: false,
  isTranscribing: false,
  isRecordingVoice: false,
  isVoiceTranscribing: false,
  voiceTranscriptionTaskId: null,
  voiceTranscriptionStartController: null,
  chatTaskId: null,
  chatTaskStartController: null,
  isSpeaking: false,
  autoScrollPinned: true,
  modelsDir: "",
  ttsVoices: [],
  ttsSpeedOptions: [...DEFAULT_TTS_SPEED_OPTIONS],
  ttsVoiceCatalog: [],
  ttsVoiceDownloads: [],
  asrModels: [],
  asrDownloads: [],
  asrUpdateChecks: {},
  ttsVoiceSearch: "",
  libraryPanels: {
    chat: readStored(STORAGE_KEYS.chatLibraryOpen, "") === "1",
    asr: readStored(STORAGE_KEYS.asrLibraryOpen, "") === "1",
    tts: readStored(STORAGE_KEYS.ttsLibraryOpen, "") === "1",
  },
  voiceRecorder: null,
  voiceStream: null,
  ttsAudio: null,
  ttsPreviewAudio: null,
  ocrBusy: false,
  ocrFileName: "",
  ocrText: "",
  ttsHistory: [],
  asrToolHistory: [],
  asrToolSelectedTranscriptId: null,
  asrToolSelectedTranscript: null,
  asrToolIsOpen: false,
  asrToolIsMinimized: false,
  asrToolBounds: null,
  asrToolDragSession: null,
  asrToolResizeSession: null,
  asrToolTaskId: null,
  asrToolStartController: null,
  asrToolIsTranscribing: false,
  ttsToolSelectedRecordId: null,
  ttsToolSelectedRecord: null,
  ttsToolIsOpen: false,
  ttsToolIsMinimized: false,
  ttsToolBounds: null,
  ttsToolDragSession: null,
  ttsToolResizeSession: null,
  renderedCodeBlocks: [],
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

function formatInlineRichText(value) {
  return escapeHtml(value)
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*\n](?:[\s\S]*?[^*\n])?)\*\*/g, "<strong>$1</strong>");
}

function registerRenderedCodeBlock(value) {
  const normalized = String(value || "");
  state.renderedCodeBlocks.push(normalized);
  return state.renderedCodeBlocks.length - 1;
}

function formatCodeLanguageLabel(value) {
  const normalized = String(value || "").trim().replace(/[^a-zA-Z0-9#+._-]/g, "");
  return normalized || "code";
}

function formatRichMessage(value) {
  const source = String(value || "").replace(/\r\n?/g, "\n");
  if (!source.trim()) return "";

  const output = [];
  const paragraph = [];
  const codeLines = [];
  let listType = null;
  let inCodeBlock = false;
  let codeBlockLanguage = "";

  const flushParagraph = () => {
    if (!paragraph.length) return;
    output.push(`<p class="message-md-paragraph">${paragraph.map((line) => formatInlineRichText(line)).join("<br />")}</p>`);
    paragraph.length = 0;
  };

  const closeList = () => {
    if (!listType) return;
    output.push(listType === "ol" ? "</ol>" : "</ul>");
    listType = null;
  };

  const flushCodeBlock = () => {
    const rawCode = codeLines.join("\n").replace(/\n+$/, "");
    const codeIndex = registerRenderedCodeBlock(rawCode);
    const languageLabel = formatCodeLanguageLabel(codeBlockLanguage);
    output.push(`
      <div class="message-md-codeblock">
        <div class="message-md-codeblock__toolbar">
          <span class="message-md-codeblock__lang">${escapeHtml(languageLabel)}</span>
          <button class="message-md-codeblock__copy" type="button" data-code-copy-index="${codeIndex}">Копировать код</button>
        </div>
        <pre class="message-md-codeblock__pre"><code>${escapeHtml(rawCode)}</code></pre>
      </div>
    `);
    codeLines.length = 0;
    codeBlockLanguage = "";
  };

  for (const rawLine of source.split("\n")) {
    const trimmed = rawLine.trim();

    if (inCodeBlock) {
      if (trimmed.startsWith("```")) {
        flushCodeBlock();
        inCodeBlock = false;
      } else {
        codeLines.push(rawLine);
      }
      continue;
    }

    if (trimmed.startsWith("```")) {
      flushParagraph();
      closeList();
      inCodeBlock = true;
      codeLines.length = 0;
      codeBlockLanguage = trimmed.slice(3).trim();
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      closeList();
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      closeList();
      const level = Math.min(4, headingMatch[1].length);
      output.push(
        `<div class="message-md-heading message-md-heading--${level}">${formatInlineRichText(headingMatch[2])}</div>`,
      );
      continue;
    }

    const orderedMatch = trimmed.match(/^\d+\.\s+(.+)$/);
    if (orderedMatch) {
      flushParagraph();
      if (listType !== "ol") {
        closeList();
        output.push('<ol class="message-md-list message-md-list--ordered">');
        listType = "ol";
      }
      output.push(`<li>${formatInlineRichText(orderedMatch[1])}</li>`);
      continue;
    }

    const unorderedMatch = trimmed.match(/^[-*•]\s+(.+)$/);
    if (unorderedMatch) {
      flushParagraph();
      if (listType !== "ul") {
        closeList();
        output.push('<ul class="message-md-list message-md-list--unordered">');
        listType = "ul";
      }
      output.push(`<li>${formatInlineRichText(unorderedMatch[1])}</li>`);
      continue;
    }

    if (listType) {
      closeList();
    }
    paragraph.push(trimmed);
  }

  if (inCodeBlock) {
    flushCodeBlock();
  }
  flushParagraph();
  closeList();
  return output.join("");
}

function stripRichTextToPlain(value) {
  return String(value || "")
    .replace(/\r\n?/g, "\n")
    .replace(/```([\s\S]*?)```/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/^\s*[-*•]\s+/gm, "")
    .replace(/\*\*([^*\n](?:[\s\S]*?[^*\n])?)\*\*/g, "$1")
    .replace(/`([^`\n]+)`/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function formatDateTime(value) {
  if (!value) return "";
  let normalized = String(value).trim();
  if (!normalized) return "";

  // Backend chat/session timestamps may be stored as UTC without an explicit timezone.
  // Treat those naive ISO-like strings as UTC, then render them in the local computer timezone.
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(normalized)) {
    normalized = normalized.replace(" ", "T");
  }
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(normalized)) {
    normalized = `${normalized}Z`;
  }

  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "";
  const mb = bytes / (1024 * 1024);
  if (mb < 1024) {
    return `${mb.toFixed(mb >= 100 ? 0 : 1)} MB`;
  }
  return `${(mb / 1024).toFixed(1)} GB`;
}

function formatTtsSpeedLabel(value) {
  const num = Number(value || 1);
  if (!Number.isFinite(num)) return "1";
  return num.toFixed(2).replace(/\.?0+$/, "");
}

function getSelectedTtsSpeed() {
  const parsed = Number(state.selectedTtsSpeed || 1);
  if (!Number.isFinite(parsed)) return 1;
  if ((state.ttsSpeedOptions || []).some((item) => Number(item) === parsed)) {
    return parsed;
  }
  return Number(state.ttsSpeedOptions?.[0] || 1) || 1;
}

function getProcessedTtsPayload(record, speedValue) {
  const normalizedLabel = formatTtsSpeedLabel(speedValue);
  const outputs = record?.processed_outputs || {};
  if (outputs[normalizedLabel]?.url) {
    return outputs[normalizedLabel];
  }
  return Object.values(outputs).find((item) => Number(item?.speed) === Number(speedValue) && item?.url) || null;
}

function setLibraryOpen(kind, isOpen) {
  const normalizedKind = kind === "asr" || kind === "tts" ? kind : "chat";
  state.libraryPanels[normalizedKind] = Boolean(isOpen);
  const storageKey = normalizedKind === "chat"
    ? STORAGE_KEYS.chatLibraryOpen
    : normalizedKind === "asr"
      ? STORAGE_KEYS.asrLibraryOpen
      : STORAGE_KEYS.ttsLibraryOpen;
  writeStored(storageKey, Boolean(isOpen) ? "1" : "");
  renderLibraryPanels();
  if (normalizedKind === "chat") {
    renderChatModelLibrary();
  } else if (normalizedKind === "asr") {
    renderAsrModelLibrary();
  } else {
    renderTtsVoiceLibrary();
  }
}

function getFilteredTtsVoiceCatalog() {
  const query = String(state.ttsVoiceSearch || "").trim().toLowerCase();
  const sorted = [...state.ttsVoiceCatalog].sort((left, right) => {
    const installedDelta = Number(Boolean(right.installed)) - Number(Boolean(left.installed));
    if (installedDelta !== 0) return installedDelta;
    const leftLabel = String(left.label || left.name || left.key || "");
    const rightLabel = String(right.label || right.name || right.key || "");
    return leftLabel.localeCompare(rightLabel, "ru");
  });

  if (!query) {
    return sorted;
  }

  return sorted.filter((item) => {
    const haystack = [
      item.label,
      item.name,
      item.key,
      item.language_name,
      item.language_code,
      item.country_name,
      item.quality,
      ...(Array.isArray(item.aliases) ? item.aliases : []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function renderLibraryPanels() {
  const chatInstalled = state.installedModels.length;
  const chatTotal = new Set([
    ...state.recommendedModels.map((item) => item.name),
    ...state.installedModels.map((item) => item.name),
  ]).size;
  const asrInstalled = state.asrModels.filter((item) => item.installed).length;
  const asrTotal = state.asrModels.length || WHISPER_MODELS.length;
  const filteredTts = getFilteredTtsVoiceCatalog();
  const ttsInstalled = state.ttsVoiceCatalog.filter((item) => item.installed).length;
  const ttsTotal = state.ttsVoiceCatalog.length;

  const configs = [
    {
      kind: "chat",
      open: state.libraryPanels.chat,
      toggle: els.chatLibraryToggle,
      panel: els.chatLibraryPanel,
      meta: els.chatLibraryMeta,
      metaText: `${chatInstalled} локально • ${chatTotal} вариантов`,
    },
    {
      kind: "asr",
      open: state.libraryPanels.asr,
      toggle: els.asrLibraryToggle,
      panel: els.asrLibraryPanel,
      meta: els.asrLibraryMeta,
      metaText: `${asrInstalled} локально • ${asrTotal} моделей`,
    },
    {
      kind: "tts",
      open: state.libraryPanels.tts,
      toggle: els.ttsLibraryToggle,
      panel: els.ttsLibraryPanel,
      meta: els.ttsLibraryMeta,
      metaText: state.ttsVoiceSearch
        ? `${ttsInstalled} локально • найдено ${filteredTts.length} из ${ttsTotal}`
        : `${ttsInstalled} локально • поиск по ${ttsTotal} голосам`,
    },
  ];

  configs.forEach((entry) => {
    if (entry.toggle) {
      entry.toggle.setAttribute("aria-expanded", entry.open ? "true" : "false");
      entry.toggle.classList.toggle("library-toggle--open", entry.open);
    }
    if (entry.panel) {
      entry.panel.hidden = !entry.open;
    }
    if (entry.meta) {
      entry.meta.textContent = entry.open ? entry.metaText : `${entry.metaText} • свернуто`;
    }
  });

  if (els.ttsVoiceSearchInput) {
    els.ttsVoiceSearchInput.value = state.ttsVoiceSearch;
  }
}

function collectModelOperations() {
  const chat = (state.downloads || []).map((item) => ({ ...item, source: "chat" }));
  const asr = (state.asrDownloads || []).map((item) => ({ ...item, source: "asr", task_id: item.task_id || item.id }));
  const tts = (state.ttsVoiceDownloads || []).map((item) => ({
    ...item,
    source: "tts",
    task_id: item.id || item.task_id,
    model: item.voice_key,
  }));
  return [...chat, ...asr, ...tts].sort((left, right) => {
    const leftTs = Number(left.started_at || left.created_at || 0);
    const rightTs = Number(right.started_at || right.created_at || 0);
    return rightTs - leftTs;
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
  els.voiceRecordButton.disabled = false;
  els.voiceRecordButton.setAttribute("aria-disabled", "false");
  els.voiceRecordButton.classList.toggle("input-mic-button--recording", isRecording);
  els.voiceRecordButton.classList.toggle("input-mic-button--busy", isBusy);
  els.voiceRecordButton.classList.toggle("input-mic-button--transcribing", isBusy);
  if (isRecording) {
    if (els.voiceRecordButton.innerHTML !== VOICE_RECORD_ICON) {
      els.voiceRecordButton.innerHTML = VOICE_RECORD_ICON;
    }
    els.voiceRecordButton.setAttribute("aria-label", "Остановить запись");
    els.voiceRecordButton.title = "Остановить запись";
    return;
  }
  if (isBusy) {
    els.voiceRecordButton.innerHTML = '<span class="input-mic-spinner" aria-hidden="true"><span class="input-mic-spinner__stop"></span></span>';
    els.voiceRecordButton.setAttribute("aria-label", "Остановить распознавание");
    els.voiceRecordButton.title = "Остановить распознавание";
    return;
  }
  if (els.voiceRecordButton.innerHTML !== VOICE_RECORD_ICON) {
    els.voiceRecordButton.innerHTML = VOICE_RECORD_ICON;
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

function isAbortError(error) {
  return error?.name === "AbortError" || String(error?.message || error || "").toLowerCase().includes("aborted");
}

function appendAssistantThinkingPlaceholder() {
  const lastMessage = state.messages[state.messages.length - 1];
  if (lastMessage?.role === "assistant" && lastMessage?._optimisticThinking) {
    return;
  }
  state.messages = [
    ...state.messages,
    {
      role: "assistant",
      content: "Думаю…",
      created_at: new Date().toISOString(),
      _optimisticThinking: true,
    },
  ];
  renderMessages();
  scrollMessagesToBottom({ force: true });
}

function removeAssistantThinkingPlaceholder() {
  const lastMessage = state.messages[state.messages.length - 1];
  if (!lastMessage?._optimisticThinking) {
    return;
  }
  state.messages = state.messages.slice(0, -1);
  renderMessages();
}

async function waitForChatTask(taskId, { timeoutMs = 300000 } = {}) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const task = await request(`/chat/tasks/${encodeURIComponent(taskId)}`);
    const taskState = String(task?.state || "");
    if (taskState === "completed" || taskState === "cancelled") {
      return task;
    }
    if (taskState === "error") {
      throw new Error(task?.message || "Генерация ответа завершилась ошибкой.");
    }
    await new Promise((resolve) => window.setTimeout(resolve, 700));
  }
  throw new Error("Истекло время ожидания генерации ответа.");
}

async function cancelCurrentChatGeneration() {
  const controller = state.chatTaskStartController;
  const taskId = state.chatTaskId;

  if (!controller && !taskId) {
    return;
  }

  setFooter("Останавливаю генерацию ответа…", "warning");

  if (controller) {
    controller.abort();
  }

  if (taskId) {
    try {
      await request(`/chat/tasks/${encodeURIComponent(taskId)}/cancel`, {
        method: "POST",
        body: {},
      });
    } catch (error) {
      if ((error?.status || 0) !== 404) {
        setFooter(`Не удалось остановить генерацию: ${error.message || error}`, "error");
        return;
      }
    }
  }

  state.chatTaskId = null;
  state.chatTaskStartController = null;
  state.isSending = false;
  removeAssistantThinkingPlaceholder();
  if (state.currentSessionId) {
    await loadSessions({ preferredSessionId: state.currentSessionId });
  }
  updateSendButtonState();
  scrollMessagesToBottom({ force: true });
  setFooter("Генерация ответа остановлена.", "warning");
}

function insertPromptText(text, { append = true } = {}) {
  const nextText = String(text || "").trim();
  if (!els.promptInput || !nextText) return;
  const current = els.promptInput.value.trim();
  els.promptInput.value = append && current ? `${current}\n${nextText}` : nextText;
  autoResizePrompt();
  updateSendButtonState();
  els.promptInput.focus();
  const length = els.promptInput.value.length;
  els.promptInput.setSelectionRange(length, length);
}

function insertVoiceTranscript(text) {
  insertPromptText(text, { append: true });
}

async function waitForVoiceTranscriptionTask(taskId, { timeoutMs = 180000 } = {}) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const task = await request(`/transcribe/tasks/${encodeURIComponent(taskId)}`);
    const taskState = String(task?.state || "");
    if (taskState === "completed") {
      return task?.result || null;
    }
    if (taskState === "cancelled") {
      return { cancelled: true };
    }
    if (taskState === "error") {
      throw new Error(task?.message || "Транскрибация завершилась ошибкой.");
    }
    await new Promise((resolve) => window.setTimeout(resolve, 700));
  }
  throw new Error("Истекло время ожидания распознавания голоса.");
}

async function cancelVoiceTranscription() {
  const controller = state.voiceTranscriptionStartController;
  const taskId = state.voiceTranscriptionTaskId;

  if (!controller && !taskId) {
    return;
  }

  setFooter("Останавливаю распознавание голоса…", "warning");

  if (controller) {
    controller.abort();
  }

  if (taskId) {
    try {
      await request(`/transcribe/tasks/${encodeURIComponent(taskId)}/cancel`, {
        method: "POST",
        body: {},
      });
    } catch (error) {
      if ((error?.status || 0) !== 404) {
        setFooter(`Не удалось остановить распознавание: ${error.message || error}`, "error");
        return;
      }
    }
  }

  state.voiceTranscriptionTaskId = null;
  state.voiceTranscriptionStartController = null;
  state.isVoiceTranscribing = false;
  renderVoiceRecordButton();
  setFooter("Распознавание голоса остановлено.", "warning");
}

async function transcribeVoiceBlob(blob, mimeType) {
  state.isVoiceTranscribing = true;
  state.voiceTranscriptionTaskId = null;
  const controller = new AbortController();
  state.voiceTranscriptionStartController = controller;
  renderVoiceRecordButton();
  setFooter("Распознаю голос… Нажмите квадрат, чтобы остановить.", "warning");

  try {
    const extension = audioExtensionForMimeType(mimeType || blob.type);
    const formData = new FormData();
    formData.append("file", blob, `voice-note.${extension}`);
    formData.append("model", state.selectedWhisperModel || "medium");
    formData.append("prompt_preset", "none");
    formData.append("language", "auto");
    formData.append("store_result", "false");

    const task = await request("/transcribe/tasks", {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
    state.voiceTranscriptionStartController = null;
    state.voiceTranscriptionTaskId = task?.id || null;

    const result = await waitForVoiceTranscriptionTask(task?.id || "");
    if (result?.cancelled) {
      setFooter("Распознавание голоса остановлено.", "warning");
      return;
    }

    const text = String(result?.text || "").trim();
    if (!text) {
      throw new Error("Whisper вернул пустой текст.");
    }
    insertVoiceTranscript(text);
    setFooter("Текст из микрофона добавлен в поле ввода.", "success");
  } catch (error) {
    if (isAbortError(error)) {
      setFooter("Распознавание голоса остановлено.", "warning");
    } else {
      setFooter(`Ошибка голосовой транскрибации: ${error.message || error}`, "error");
    }
  } finally {
    state.voiceTranscriptionTaskId = null;
    state.voiceTranscriptionStartController = null;
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
  if (state.isVoiceTranscribing) {
    await cancelVoiceTranscription();
    return;
  }
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
  els.sendButton.disabled = state.isSending ? false : !hasText;
  els.sendButton.textContent = state.isSending ? "Стоп" : "Отправить";
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
  const hasRunning = collectModelOperations().some((item) => ["pending", "queued", "running", "paused"].includes(item.state));
  if (!hasRunning && downloadsPollTimer) {
    window.clearInterval(downloadsPollTimer);
    downloadsPollTimer = null;
    return;
  }
  if (hasRunning && !downloadsPollTimer) {
    downloadsPollTimer = window.setInterval(() => {
      loadModels({ silent: true });
      loadWhisperModels({ silent: true });
      loadTtsLibrary({ silent: true });
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
  if (state.latestTranscript) {
    const parts = [
      state.latestTranscript.language || "auto",
      `${(state.latestTranscript.content || "").length} символов`,
    ];
    els.contextStatus.textContent = `Транскрипт подключён • ${parts.join(" • ")}`;
    els.contextStatus.hidden = false;
    return;
  }

  els.contextStatus.textContent = "";
  els.contextStatus.hidden = true;
}

function renderTranscriptStrip() {
  renderContextSummary();
}

function renderMessages() {
  if (!els.messageList || !els.emptyState) return;

  const items = state.messages || [];
  state.renderedCodeBlocks = [];
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
            <div class="message-card__body">${formatRichMessage(message.content || "")}</div>
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

  const optionsMarkup = mergedOptions
    .map((name) => {
      const recommended = state.recommendedModels.some((item) => item.name === name) && !installedNames.has(name);
      return `<option value="${escapeHtml(name)}">${escapeHtml(name)}${recommended ? " (рекомендовано)" : ""}</option>`;
    })
    .join("");

  [els.llmModelSelect, els.quickModelSelect].filter(Boolean).forEach((select) => {
    select.innerHTML = optionsMarkup;
    select.disabled = !mergedOptions.length;
  });

  const preferredModel = state.selectedLlmModel || readStored(STORAGE_KEYS.llmModel, state.defaultModel);
  if (preferredModel && mergedOptions.includes(preferredModel)) {
    els.llmModelSelect.value = preferredModel;
    if (els.quickModelSelect) {
      els.quickModelSelect.value = preferredModel;
    }
  } else if (mergedOptions.length) {
    els.llmModelSelect.value = mergedOptions[0];
    if (els.quickModelSelect) {
      els.quickModelSelect.value = mergedOptions[0];
    }
    state.selectedLlmModel = mergedOptions[0];
    writeStored(STORAGE_KEYS.llmModel, mergedOptions[0]);
  }

  els.recommendedModels.innerHTML = state.recommendedModels
    .map((item) => {
      const installed = installedNames.has(item.name);
      const active = item.name === state.selectedLlmModel;
      return `<button class="chip-button${installed ? " chip-button--installed" : ""}${active ? " chip-button--active" : ""}" type="button" data-recommended-model="${escapeHtml(item.name)}">${escapeHtml(item.label || item.name)}</button>`;
    })
    .join("");

  renderLibraryPanels();
  renderChatModelLibrary();
}

async function applySelectedLlmModel(nextModel) {
  const modelName = String(nextModel || "").trim();
  if (!modelName) return;

  state.selectedLlmModel = modelName;
  writeStored(STORAGE_KEYS.llmModel, state.selectedLlmModel);

  [els.llmModelSelect, els.quickModelSelect].filter(Boolean).forEach((select) => {
    const hasOption = Array.from(select.options || []).some((option) => option.value === modelName);
    if (hasOption) {
      select.value = modelName;
    }
  });

  renderContextSummary();
  renderModelSettings();
  if (state.currentSessionId && state.selectedLlmModel) {
    await updateCurrentSessionMeta({ model_name: state.selectedLlmModel });
  }
  await refreshModelSettings({ silent: true });
}

function renderChatModelLibrary() {
  if (!els.chatModelLibrary) return;
  if (!state.libraryPanels.chat) {
    els.chatModelLibrary.innerHTML = "";
    return;
  }

  const installedByName = new Map(state.installedModels.map((item) => [item.name, item]));
  const recommendedByName = new Map(state.recommendedModels.map((item) => [item.name, item]));
  const allNames = [
    ...new Set([
      ...state.recommendedModels.map((item) => item.name),
      ...state.installedModels.map((item) => item.name),
    ]),
  ];

  if (!allNames.length) {
    els.chatModelLibrary.innerHTML = '<p class="subtle">Список Ollama-моделей пока пуст.</p>';
    return;
  }

  els.chatModelLibrary.innerHTML = allNames
    .map((name) => {
      const installed = installedByName.get(name);
      const recommended = recommendedByName.get(name);
      const active = state.selectedLlmModel === name;
      const task = state.downloads.find((item) => item.model === name && ["pending", "running", "paused"].includes(item.state));
      const badge = task
        ? `<span class="status-badge status-badge--warning">${escapeHtml(task.state || "running")}</span>`
        : installed
          ? '<span class="status-badge status-badge--success">Установлена</span>'
          : '<span class="status-badge">Не загружена</span>';
      const meta = [
        recommended?.label || null,
        installed?.size_gb ? `${installed.size_gb} GB` : null,
        installed?.modified_at ? formatDateTime(installed.modified_at) : null,
      ].filter(Boolean).join(" • ");
      const note = task?.message || (recommended ? "Можно загрузить или обновить прямо из настроек." : "");
      return `
        <article class="model-card${installed ? " model-card--installed" : ""}${active ? " model-card--active" : ""}">
          <div class="model-card__head">
            <div>
              <h5 class="model-card__title">${escapeHtml(name)}</h5>
              <p class="model-card__meta">${escapeHtml(meta || "Локальная Ollama-модель")}</p>
            </div>
            <div class="model-card__badges">${badge}${active ? '<span class="status-badge status-badge--active">Активна</span>' : ""}</div>
          </div>
          <p class="model-card__note">${escapeHtml(note || (installed ? "Модель готова к использованию в чате." : "Сначала загрузите модель локально."))}</p>
          <div class="button-row">
            <button class="button ${active ? "button--primary" : "button--ghost"}" type="button" data-chat-model-action="select" data-chat-model="${escapeHtml(name)}">Выбрать</button>
            <button class="button button--ghost" type="button" data-chat-model-action="download" data-chat-model="${escapeHtml(name)}">${installed ? "Обновить" : "Загрузить"}</button>
            ${installed ? `<button class="button button--ghost" type="button" data-chat-model-action="delete" data-chat-model="${escapeHtml(name)}">Удалить</button>` : ""}
          </div>
        </article>
      `;
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
  const items = state.asrModels.length ? state.asrModels : WHISPER_MODELS.map((name) => ({ name, installed: false }));
  const names = items.map((item) => item.name);
  if (!names.includes(state.selectedWhisperModel)) {
    state.selectedWhisperModel = names[0] || "small";
    writeStored(STORAGE_KEYS.whisperModel, state.selectedWhisperModel);
  }
  els.whisperModelSelect.innerHTML = names
    .map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`)
    .join("");
  els.whisperModelSelect.value = state.selectedWhisperModel;
  els.promptPresetSelect.value = ["none", "ru", "en"].includes(state.selectedPromptPreset) ? state.selectedPromptPreset : "none";

  if (els.asrSettingsStatus) {
    const selectedItem = items.find((item) => item.name === state.selectedWhisperModel);
    const isInstalled = Boolean(selectedItem?.installed);
    setInlineStatus(
      els.asrSettingsStatus,
      isInstalled
        ? `Кнопка "Транскрибировать" использует модель ${state.selectedWhisperModel}.`
        : `Модель ${state.selectedWhisperModel} выбрана, но ещё не загружена локально.`,
      isInstalled ? "success" : "warning",
    );
  }

  renderLibraryPanels();
  renderAsrModelLibrary();
  renderAsrTool();
}

function renderAsrModelLibrary() {
  if (!els.asrModelLibrary) return;
  if (!state.libraryPanels.asr) {
    els.asrModelLibrary.innerHTML = "";
    return;
  }
  const items = state.asrModels.length ? state.asrModels : WHISPER_MODELS.map((name) => ({ name, installed: false, repo_id: "" }));

  els.asrModelLibrary.innerHTML = items
    .map((item) => {
      const active = state.selectedWhisperModel === item.name;
      const task = item.active_task || state.asrDownloads.find((entry) => entry.model === item.name && ["pending", "running"].includes(entry.state));
      const update = state.asrUpdateChecks[item.name];
      let badge = '<span class="status-badge">Не загружена</span>';
      if (task) {
        const percent = typeof task.percent === "number" && task.percent > 0 ? ` ${Math.round(task.percent)}%` : "";
        badge = `<span class="status-badge status-badge--warning">${escapeHtml((task.state || "running") + percent)}</span>`;
      } else if (update?.status === "update_available") {
        badge = '<span class="status-badge status-badge--warning">Есть обновление</span>';
      } else if (item.installed) {
        badge = '<span class="status-badge status-badge--success">Установлена</span>';
      }
      const meta = [
        item.repo_id || null,
        item.local_revision ? `rev ${String(item.local_revision).slice(0, 8)}` : null,
      ].filter(Boolean).join(" • ");
      const note = task?.message || update?.message || (item.installed ? "Whisper-модель готова к транскрибации." : "Сначала загрузите модель локально.");
      return `
        <article class="model-card${item.installed ? " model-card--installed" : ""}${active ? " model-card--active" : ""}">
          <div class="model-card__head">
            <div>
              <h5 class="model-card__title">${escapeHtml(item.name)}</h5>
              <p class="model-card__meta">${escapeHtml(meta || "Whisper model")}</p>
            </div>
            <div class="model-card__badges">${badge}${active ? '<span class="status-badge status-badge--active">Активна</span>' : ""}</div>
          </div>
          <p class="model-card__note">${escapeHtml(note)}</p>
          <div class="button-row">
            <button class="button ${active ? "button--primary" : "button--ghost"}" type="button" data-asr-model-action="select" data-asr-model="${escapeHtml(item.name)}">Выбрать</button>
            <button class="button button--ghost" type="button" data-asr-model-action="download" data-asr-model="${escapeHtml(item.name)}" data-asr-force="${item.installed ? "1" : "0"}">${item.installed ? "Обновить" : "Загрузить"}</button>
            <button class="button button--ghost" type="button" data-asr-model-action="check" data-asr-model="${escapeHtml(item.name)}">Проверить</button>
            ${item.installed ? `<button class="button button--ghost" type="button" data-asr-model-action="delete" data-asr-model="${escapeHtml(item.name)}">Удалить</button>` : ""}
          </div>
        </article>
      `;
    })
    .join("");
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
    renderTtsTool();
    renderLibraryPanels();
    renderTtsVoiceLibrary();
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
      ? `Voice Studio использует голос: ${selectedVoice.label || selectedVoice.name || selectedVoice.id}`
      : "Voice Studio использует выбранный локальный голос.",
    "success",
  );
  renderTtsTool();
  renderLibraryPanels();
  renderTtsVoiceLibrary();
}

function renderTtsVoiceLibrary() {
  if (!els.ttsVoiceLibrary) return;
  if (!state.libraryPanels.tts) {
    els.ttsVoiceLibrary.innerHTML = "";
    return;
  }
  if (!state.ttsVoiceCatalog.length) {
    els.ttsVoiceLibrary.innerHTML = '<p class="subtle">Каталог Piper ещё не загружен.</p>';
    return;
  }

  const query = String(state.ttsVoiceSearch || "").trim();
  const allItems = getFilteredTtsVoiceCatalog();
  const items = query ? allItems : allItems.filter((item) => item.installed);
  const intro = query
    ? ""
    : '<p class="subtle">Каталог скрыт по умолчанию. Введите запрос выше, чтобы найти новый голос для загрузки.</p>';

  if (!items.length) {
    els.ttsVoiceLibrary.innerHTML = query
      ? '<p class="subtle">По этому запросу голоса не найдены.</p>'
      : `${intro}<p class="subtle">Локальных TTS-голосов пока нет.</p>`;
    return;
  }

  els.ttsVoiceLibrary.innerHTML = `${intro}${items
    .map((item) => {
      const installedVoiceIds = Array.isArray(item.installed_voice_ids) ? item.installed_voice_ids : [];
      const active = installedVoiceIds.includes(state.selectedTtsVoiceId);
      const task = state.ttsVoiceDownloads.find((entry) => entry.voice_key === item.key && ["queued", "running"].includes(entry.state));
      let badge = '<span class="status-badge">Не загружен</span>';
      if (task) {
        badge = `<span class="status-badge status-badge--warning">${escapeHtml(task.state || "queued")}</span>`;
      } else if (item.installed) {
        badge = '<span class="status-badge status-badge--success">Установлен</span>';
      }
      const meta = [
        item.language_name || item.language_code || null,
        item.quality || null,
        item.download_size_bytes ? formatBytes(item.download_size_bytes) : null,
      ].filter(Boolean).join(" • ");
      const note = task?.message
        || (item.installed
          ? `Доступно локально: ${installedVoiceIds.join(", ")}`
          : "Голос можно загрузить в локальную библиотеку Piper.");
      return `
        <article class="model-card${item.installed ? " model-card--installed" : ""}${active ? " model-card--active" : ""}">
          <div class="model-card__head">
            <div>
              <h5 class="model-card__title">${escapeHtml(item.label || item.name || item.key)}</h5>
              <p class="model-card__meta">${escapeHtml(meta || item.key)}</p>
            </div>
            <div class="model-card__badges">${badge}${active ? '<span class="status-badge status-badge--active">Активен</span>' : ""}</div>
          </div>
          <p class="model-card__note">${escapeHtml(note)}</p>
          <div class="button-row">
            ${installedVoiceIds[0]
              ? `<button class="button ${active ? "button--primary" : "button--ghost"}" type="button" data-tts-voice-action="select" data-tts-voice-id="${escapeHtml(installedVoiceIds[0])}" data-tts-voice-key="${escapeHtml(item.key)}">Выбрать</button>`
              : ""}
            ${item.installed
              ? `<button class="button button--ghost" type="button" data-tts-voice-action="preview" data-tts-voice-key="${escapeHtml(item.key)}">Превью</button>`
              : ""}
            <button class="button button--ghost" type="button" data-tts-voice-action="download" data-tts-voice-key="${escapeHtml(item.key)}" data-tts-force="${item.installed ? "1" : "0"}">${item.installed ? "Обновить" : "Загрузить"}</button>
            ${item.installed ? `<button class="button button--ghost" type="button" data-tts-voice-action="delete" data-tts-voice-key="${escapeHtml(item.key)}">Удалить</button>` : ""}
          </div>
        </article>
      `;
    })
    .join("")}`;
}

function renderToolDock() {
  if (!els.toolDock) return;
  const items = [];
  if (state.asrToolIsMinimized) {
    items.push(`
      <button class="tool-dock__item tool-dock__item--minimized" type="button" data-tool-dock="asr" aria-pressed="false">
        <span class="tool-dock__title">Транскрибация</span>
        <span class="tool-dock__meta">Свернуто</span>
      </button>
    `);
  }
  if (state.ttsToolIsMinimized) {
    items.push(`
      <button class="tool-dock__item tool-dock__item--minimized" type="button" data-tool-dock="tts" aria-pressed="false">
        <span class="tool-dock__title">Озвучивание</span>
        <span class="tool-dock__meta">Свернуто</span>
      </button>
    `);
  }

  if (!items.length) {
    els.toolDock.innerHTML = "";
    els.toolDock.hidden = true;
    return;
  }

  els.toolDock.hidden = false;
  els.toolDock.innerHTML = items.join("");
}

function shouldForceTtsToolFullscreen() {
  const edge = 18;
  const viewportWidth = Math.max(window.innerWidth || 0, 360);
  const viewportHeight = Math.max(window.innerHeight || 0, 360);
  return viewportWidth - edge * 2 < TTS_TOOL_MIN_WIDTH || viewportHeight - edge * 2 < TTS_TOOL_MIN_HEIGHT;
}

function syncTtsToolWindowMode() {
  const tool = els.ttsToolWindow;
  if (!tool || isMobileLayout()) return;
  if (shouldForceTtsToolFullscreen()) {
    tool.classList.add("tool-window--fullscreen");
    tool.dataset.autoFullscreen = "1";
    return;
  }
  if (tool.dataset.autoFullscreen === "1") {
    tool.classList.remove("tool-window--fullscreen");
    delete tool.dataset.autoFullscreen;
  }
}

function getDefaultTtsToolBounds() {
  const viewportWidth = window.innerWidth || 1440;
  const viewportHeight = window.innerHeight || 900;
  const width = Math.max(TTS_TOOL_MIN_WIDTH, Math.min(1460, viewportWidth - 36));
  const height = Math.max(TTS_TOOL_MIN_HEIGHT, Math.min(900, viewportHeight - 36));
  const left = Math.max(18, Math.round((viewportWidth - width) / 2));
  const top = Math.max(18, Math.round((viewportHeight - height) / 2));
  return { left, top, width, height };
}

function normalizeTtsToolBounds(bounds) {
  const edge = 18;
  const viewportWidth = Math.max(window.innerWidth || 0, 360);
  const viewportHeight = Math.max(window.innerHeight || 0, 360);
  const maxWidth = Math.max(320, viewportWidth - edge * 2);
  const maxHeight = Math.max(320, viewportHeight - edge * 2);
  const minWidth = Math.min(TTS_TOOL_MIN_WIDTH, maxWidth);
  const minHeight = Math.min(TTS_TOOL_MIN_HEIGHT, maxHeight);
  const width = Math.min(Math.max(Math.round(bounds.width || minWidth), minWidth), maxWidth);
  const height = Math.min(Math.max(Math.round(bounds.height || minHeight), minHeight), maxHeight);
  const left = Math.min(Math.max(Math.round(bounds.left ?? edge), edge), Math.max(edge, viewportWidth - edge - width));
  const top = Math.min(Math.max(Math.round(bounds.top ?? edge), edge), Math.max(edge, viewportHeight - edge - height));
  return { left, top, width, height };
}

function applyTtsToolBounds(bounds) {
  const tool = els.ttsToolWindow;
  if (!tool || isMobileLayout()) return;
  const normalized = normalizeTtsToolBounds(bounds);
  state.ttsToolBounds = normalized;
  tool.style.left = `${normalized.left}px`;
  tool.style.top = `${normalized.top}px`;
  tool.style.width = `${normalized.width}px`;
  tool.style.height = `${normalized.height}px`;
}

function setTtsToolWindowBounds() {
  const tool = els.ttsToolWindow;
  if (!tool || isMobileLayout()) return;
  syncTtsToolWindowMode();
  if (tool.classList.contains("tool-window--fullscreen")) return;
  applyTtsToolBounds(state.ttsToolBounds || getDefaultTtsToolBounds());
}

function stopTtsToolDrag() {
  const session = state.ttsToolDragSession;
  if (!session) return;
  window.removeEventListener("mousemove", session.onMove);
  window.removeEventListener("mouseup", session.onUp);
  state.ttsToolDragSession = null;
}

function startTtsToolDrag(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (!els.ttsToolWindow || els.ttsToolWindow.hidden || isMobileLayout()) return;
  if (els.ttsToolWindow.classList.contains("tool-window--fullscreen")) return;
  if (target?.closest(".tool-window__actions, button, input, select, textarea, audio")) return;

  event.preventDefault();
  stopTtsToolResize();
  stopTtsToolDrag();

  const rect = els.ttsToolWindow.getBoundingClientRect();
  const session = {
    startX: event.clientX,
    startY: event.clientY,
    startLeft: rect.left,
    startTop: rect.top,
    startWidth: rect.width,
    startHeight: rect.height,
    onMove: null,
    onUp: null,
  };

  session.onMove = (moveEvent) => {
    applyTtsToolBounds({
      left: session.startLeft + (moveEvent.clientX - session.startX),
      top: session.startTop + (moveEvent.clientY - session.startY),
      width: session.startWidth,
      height: session.startHeight,
    });
  };

  session.onUp = () => {
    stopTtsToolDrag();
  };

  state.ttsToolDragSession = session;
  window.addEventListener("mousemove", session.onMove);
  window.addEventListener("mouseup", session.onUp);
}

function stopTtsToolResize() {
  const session = state.ttsToolResizeSession;
  if (!session) return;
  window.removeEventListener("mousemove", session.onMove);
  window.removeEventListener("mouseup", session.onUp);
  state.ttsToolResizeSession = null;
}

function startTtsToolResize(event) {
  if (!els.ttsToolWindow || els.ttsToolWindow.hidden || isMobileLayout()) return;
  if (els.ttsToolWindow.classList.contains("tool-window--fullscreen")) return;

  event.preventDefault();
  event.stopPropagation();
  stopTtsToolDrag();
  stopTtsToolResize();

  const rect = els.ttsToolWindow.getBoundingClientRect();
  const session = {
    startX: event.clientX,
    startY: event.clientY,
    startLeft: rect.left,
    startTop: rect.top,
    startWidth: rect.width,
    startHeight: rect.height,
    onMove: null,
    onUp: null,
  };

  session.onMove = (moveEvent) => {
    applyTtsToolBounds({
      left: session.startLeft,
      top: session.startTop,
      width: session.startWidth + (moveEvent.clientX - session.startX),
      height: session.startHeight + (moveEvent.clientY - session.startY),
    });
  };

  session.onUp = () => {
    stopTtsToolResize();
  };

  state.ttsToolResizeSession = session;
  window.addEventListener("mousemove", session.onMove);
  window.addEventListener("mouseup", session.onUp);
}

function stopTtsToolPlayer() {
  if (!els.ttsToolPlayer) return;
  try {
    els.ttsToolPlayer.pause();
  } catch {
    // ignore
  }
  els.ttsToolPlayer.removeAttribute("src");
  els.ttsToolPlayer.hidden = true;
  try {
    els.ttsToolPlayer.load();
  } catch {
    // ignore
  }
}

function syncTtsToolPlayer(record) {
  if (!els.ttsToolPlayer) return;
  const selectedSpeed = getSelectedTtsSpeed();
  const processedOutput = selectedSpeed === 1 ? null : getProcessedTtsPayload(record, selectedSpeed);
  const audioUrl = processedOutput?.url || record?.base_output_url || "";
  if (!audioUrl) {
    stopTtsToolPlayer();
    return;
  }

  if ((els.ttsToolPlayer.getAttribute("src") || "") === audioUrl) {
    els.ttsToolPlayer.hidden = false;
    return;
  }

  els.ttsToolPlayer.src = audioUrl;
  els.ttsToolPlayer.hidden = false;
  try {
    els.ttsToolPlayer.load();
  } catch {
    // ignore
  }
}

function getTtsToolDownloadUrl(record) {
  const selectedSpeed = getSelectedTtsSpeed();
  const baseUrl = selectedSpeed === 1
    ? (record?.base_output_url || "")
    : (getProcessedTtsPayload(record, selectedSpeed)?.url || "");
  if (!baseUrl) return "";
  const url = new URL(baseUrl, window.location.origin);
  url.searchParams.set("download", "true");
  return `${url.pathname}${url.search}`;
}

function renderTtsToolHistory() {
  if (!els.ttsToolHistoryList) return;
  if (!state.ttsHistory.length) {
    els.ttsToolHistoryList.innerHTML = '<p class="subtle">Записей озвучки пока нет.</p>';
    return;
  }

  const selectedId = state.ttsToolSelectedRecordId;
  const prioritized = selectedId
    ? [
      ...state.ttsHistory.filter((item) => item.id === selectedId),
      ...state.ttsHistory.filter((item) => item.id !== selectedId),
    ]
    : [...state.ttsHistory];
  const visibleItems = prioritized.slice(0, 4);

  els.ttsToolHistoryList.innerHTML = visibleItems
    .map((item) => {
      const active = item.id === selectedId ? " tool-history__item--active" : "";
      const voiceLabel = item.voice_name || item.voice_id || "voice";
      const meta = [voiceLabel, item.status || "", formatDateTime(item.updated_at || item.created_at)]
        .filter(Boolean)
        .join(" • ");
      const preview = stripRichTextToPlain(item.preview || "Без текста");
      return `
        <button class="tool-history__item${active}" type="button" data-tts-history-id="${escapeHtml(item.id)}">
          <span class="tool-history__title">${escapeHtml(preview || "Без текста")}</span>
          <span class="tool-history__meta">${escapeHtml(meta)}</span>
        </button>
      `;
    })
    .join("");
}

function renderTtsTool() {
  if (!els.ttsToolWindow) return;

  const selectedRecord = state.ttsToolSelectedRecord;
  const latestAssistantMessage = findLatestAssistantMessage();
  let selectedVoiceId = String(state.selectedTtsVoiceId || "").trim();
  const selectedVoiceExists = state.ttsVoices.some((voice) => voice.id === selectedVoiceId);
  if (!selectedVoiceExists) {
    selectedVoiceId = String(state.ttsVoices[0]?.id || "").trim();
    if (selectedVoiceId !== state.selectedTtsVoiceId) {
      state.selectedTtsVoiceId = selectedVoiceId;
      writeStored(STORAGE_KEYS.ttsVoiceId, state.selectedTtsVoiceId);
    }
  }
  const hasText = Boolean((els.ttsToolText?.value || "").trim());
  const hasVoice = Boolean(selectedVoiceId);
  const selectedSpeed = getSelectedTtsSpeed();
  const canDownload = Boolean(
    selectedRecord?.base_output_url
    || (selectedSpeed !== 1 && getProcessedTtsPayload(selectedRecord, selectedSpeed)?.url),
  );

  if (els.ttsToolProviderSelect) {
    els.ttsToolProviderSelect.value = (state.selectedTtsProvider || "piper").trim() || "piper";
    els.ttsToolProviderSelect.disabled = true;
  }

  if (els.ttsToolVoiceSelect) {
    if (!state.ttsVoices.length) {
      els.ttsToolVoiceSelect.innerHTML = '<option value="">Нет локальных голосов</option>';
      els.ttsToolVoiceSelect.value = "";
      els.ttsToolVoiceSelect.disabled = true;
    } else {
      els.ttsToolVoiceSelect.innerHTML = state.ttsVoices
        .map((voice) => `<option value="${escapeHtml(voice.id)}">${escapeHtml(voice.label || voice.name || voice.id)}</option>`)
        .join("");
      els.ttsToolVoiceSelect.value = selectedVoiceId || state.ttsVoices[0]?.id || "";
      els.ttsToolVoiceSelect.disabled = false;
    }
  }
  if (els.ttsToolSpeedSelect) {
    const options = (state.ttsSpeedOptions || DEFAULT_TTS_SPEED_OPTIONS).map((item) => Number(item)).filter(Number.isFinite);
    els.ttsToolSpeedSelect.innerHTML = options
      .map((item) => `<option value="${formatTtsSpeedLabel(item)}">${formatTtsSpeedLabel(item)}x</option>`)
      .join("");
    els.ttsToolSpeedSelect.value = formatTtsSpeedLabel(selectedSpeed);
    els.ttsToolSpeedSelect.disabled = state.isSpeaking;
  }

  if (els.ttsToolGenerateButton) {
    els.ttsToolGenerateButton.disabled = state.isSpeaking || !hasText || !hasVoice;
    els.ttsToolGenerateButton.textContent = state.isSpeaking ? "Генерация…" : "Озвучить";
  }
  if (els.ttsToolUseAssistantButton) {
    els.ttsToolUseAssistantButton.disabled = !latestAssistantMessage;
  }
  if (els.ttsToolRefreshButton) {
    els.ttsToolRefreshButton.disabled = state.isSpeaking;
  }
  if (els.ttsToolDeleteButton) {
    els.ttsToolDeleteButton.disabled = state.isSpeaking || !selectedRecord;
  }
  if (els.ttsToolClearButton) {
    els.ttsToolClearButton.disabled = state.isSpeaking || !state.ttsHistory.length;
  }
  if (els.ttsToolDownloadButton) {
    els.ttsToolDownloadButton.disabled = !canDownload;
  }
  if (els.ttsToolFullscreenButton) {
    els.ttsToolFullscreenButton.setAttribute(
      "aria-pressed",
      els.ttsToolWindow.classList.contains("tool-window--fullscreen") ? "true" : "false",
    );
  }
  if (els.ttsToolMeta) {
    const metaParts = [
      selectedRecord?.voice_name || selectedRecord?.voice_id || selectedVoiceId || "Голос не выбран",
      `Скорость ${formatTtsSpeedLabel(selectedSpeed)}x`,
      selectedRecord?.status || (hasVoice ? "Готово к генерации" : "Выберите голос в настройках"),
      formatDateTime(selectedRecord?.updated_at || selectedRecord?.created_at),
    ].filter(Boolean);
    els.ttsToolMeta.textContent = metaParts.join(" • ");
  }

  syncTtsToolPlayer(selectedRecord);
  renderTtsToolHistory();
}

async function ensureTtsToolSpeed(record, { silent = false, manageBusy = true } = {}) {
  const selectedSpeed = getSelectedTtsSpeed();
  if (!record?.id || selectedSpeed === 1) {
    return record;
  }

  if (getProcessedTtsPayload(record, selectedSpeed)?.url) {
    return record;
  }

  const alreadyBusy = state.isSpeaking;
  if (manageBusy && !alreadyBusy) {
    state.isSpeaking = true;
    renderTtsTool();
  }

  if (!silent) {
    setInlineStatus(els.ttsToolStatus, `Применяю скорость ${formatTtsSpeedLabel(selectedSpeed)}x…`, "warning");
    setFooter(`Применяю скорость ${formatTtsSpeedLabel(selectedSpeed)}x…`);
  }

  try {
    await request("/tts/process-speed", {
      method: "POST",
      body: {
        id: record.id,
        speed: selectedSpeed,
      },
    });
    const updated = await waitForTtsRecord(record.id);
    state.ttsToolSelectedRecordId = updated.id;
    state.ttsToolSelectedRecord = updated;
    await loadTtsHistory({ silent: true });
    return updated;
  } finally {
    if (manageBusy && !alreadyBusy) {
      state.isSpeaking = false;
      renderTtsTool();
    }
  }
}

async function loadAsrToolHistory({ silent = false } = {}) {
  if (!state.activeProfileId) {
    state.asrToolHistory = [];
    renderAsrTool();
    return false;
  }

  try {
    const data = await request(
      `/transcripts?profile_id=${encodeURIComponent(state.activeProfileId)}&origin=${encodeURIComponent(ASR_TOOL_ORIGIN)}`,
    );
    state.asrToolHistory = Array.isArray(data?.transcripts) ? data.transcripts : [];
    if (
      state.asrToolSelectedTranscriptId
      && !state.asrToolHistory.some((item) => Number(item.id) === Number(state.asrToolSelectedTranscriptId))
    ) {
      state.asrToolSelectedTranscriptId = null;
      state.asrToolSelectedTranscript = null;
    }
    renderAsrTool();
    return true;
  } catch (error) {
    state.asrToolHistory = [];
    renderAsrTool();
    if (!silent) {
      setFooter(`Не удалось загрузить историю ASR: ${error.message || error}`, "error");
    }
    return false;
  }
}

function renderAsrToolHistory() {
  if (!els.asrToolHistoryList) return;
  if (!state.asrToolHistory.length) {
    els.asrToolHistoryList.innerHTML = '<p class="subtle">История транскрибаций пока пуста.</p>';
    return;
  }

  const selectedId = Number(state.asrToolSelectedTranscriptId || 0);
  const prioritized = selectedId
    ? [
      ...state.asrToolHistory.filter((item) => Number(item.id) === selectedId),
      ...state.asrToolHistory.filter((item) => Number(item.id) !== selectedId),
    ]
    : [...state.asrToolHistory];

  els.asrToolHistoryList.innerHTML = prioritized.slice(0, 6)
    .map((item) => {
      const active = Number(item.id) === selectedId ? " tool-history__item--active" : "";
      const meta = [
        item.language || null,
        formatDateTime(item.updated_at || item.created_at),
      ].filter(Boolean).join(" • ");
      const preview = stripRichTextToPlain(item.content || item.name || "Без текста");
      return `
        <button class="tool-history__item${active}" type="button" data-asr-history-id="${escapeHtml(item.id)}">
          <span class="tool-history__title">${escapeHtml(preview || item.name || "Транскрипт")}</span>
          <span class="tool-history__meta">${escapeHtml(meta || item.name || "Транскрипт")}</span>
        </button>
      `;
    })
    .join("");
}

function getDefaultAsrToolBounds() {
  const viewportWidth = window.innerWidth || 1440;
  const viewportHeight = window.innerHeight || 900;
  const width = Math.max(900, Math.min(1400, viewportWidth - 36));
  const height = Math.max(620, Math.min(880, viewportHeight - 36));
  const left = Math.max(18, Math.round((viewportWidth - width) / 2));
  const top = Math.max(18, Math.round((viewportHeight - height) / 2));
  return { left, top, width, height };
}

function normalizeAsrToolBounds(bounds) {
  const edge = 18;
  const viewportWidth = Math.max(window.innerWidth || 0, 360);
  const viewportHeight = Math.max(window.innerHeight || 0, 360);
  const maxWidth = Math.max(320, viewportWidth - edge * 2);
  const maxHeight = Math.max(320, viewportHeight - edge * 2);
  const minWidth = Math.min(760, maxWidth);
  const minHeight = Math.min(520, maxHeight);
  const width = Math.min(Math.max(Math.round(bounds.width || minWidth), minWidth), maxWidth);
  const height = Math.min(Math.max(Math.round(bounds.height || minHeight), minHeight), maxHeight);
  const left = Math.min(Math.max(Math.round(bounds.left ?? edge), edge), Math.max(edge, viewportWidth - edge - width));
  const top = Math.min(Math.max(Math.round(bounds.top ?? edge), edge), Math.max(edge, viewportHeight - edge - height));
  return { left, top, width, height };
}

function applyAsrToolBounds(bounds) {
  const tool = els.asrToolWindow;
  if (!tool || isMobileLayout()) return;
  const normalized = normalizeAsrToolBounds(bounds);
  state.asrToolBounds = normalized;
  tool.style.left = `${normalized.left}px`;
  tool.style.top = `${normalized.top}px`;
  tool.style.width = `${normalized.width}px`;
  tool.style.height = `${normalized.height}px`;
}

function setAsrToolWindowBounds() {
  const tool = els.asrToolWindow;
  if (!tool || isMobileLayout()) return;
  applyAsrToolBounds(state.asrToolBounds || getDefaultAsrToolBounds());
}

function stopAsrToolDrag() {
  const session = state.asrToolDragSession;
  if (!session) return;
  window.removeEventListener("mousemove", session.onMove);
  window.removeEventListener("mouseup", session.onUp);
  state.asrToolDragSession = null;
}

function startAsrToolDrag(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (!els.asrToolWindow || els.asrToolWindow.hidden || isMobileLayout()) return;
  if (els.asrToolWindow.classList.contains("tool-window--fullscreen")) return;
  if (target?.closest(".tool-window__actions, button, input, select, textarea, audio")) return;

  event.preventDefault();
  stopAsrToolResize();
  stopAsrToolDrag();

  const rect = els.asrToolWindow.getBoundingClientRect();
  const session = {
    startX: event.clientX,
    startY: event.clientY,
    startLeft: rect.left,
    startTop: rect.top,
    startWidth: rect.width,
    startHeight: rect.height,
    onMove: null,
    onUp: null,
  };

  session.onMove = (moveEvent) => {
    applyAsrToolBounds({
      left: session.startLeft + (moveEvent.clientX - session.startX),
      top: session.startTop + (moveEvent.clientY - session.startY),
      width: session.startWidth,
      height: session.startHeight,
    });
  };

  session.onUp = () => {
    stopAsrToolDrag();
  };

  state.asrToolDragSession = session;
  window.addEventListener("mousemove", session.onMove);
  window.addEventListener("mouseup", session.onUp);
}

function stopAsrToolResize() {
  const session = state.asrToolResizeSession;
  if (!session) return;
  window.removeEventListener("mousemove", session.onMove);
  window.removeEventListener("mouseup", session.onUp);
  state.asrToolResizeSession = null;
}

function startAsrToolResize(event) {
  if (!els.asrToolWindow || els.asrToolWindow.hidden || isMobileLayout()) return;
  if (els.asrToolWindow.classList.contains("tool-window--fullscreen")) return;

  event.preventDefault();
  event.stopPropagation();
  stopAsrToolDrag();
  stopAsrToolResize();

  const rect = els.asrToolWindow.getBoundingClientRect();
  const session = {
    startX: event.clientX,
    startY: event.clientY,
    startLeft: rect.left,
    startTop: rect.top,
    startWidth: rect.width,
    startHeight: rect.height,
    onMove: null,
    onUp: null,
  };

  session.onMove = (moveEvent) => {
    applyAsrToolBounds({
      left: session.startLeft,
      top: session.startTop,
      width: session.startWidth + (moveEvent.clientX - session.startX),
      height: session.startHeight + (moveEvent.clientY - session.startY),
    });
  };

  session.onUp = () => {
    stopAsrToolResize();
  };

  state.asrToolResizeSession = session;
  window.addEventListener("mousemove", session.onMove);
  window.addEventListener("mouseup", session.onUp);
}

function renderAsrTool() {
  if (!els.asrToolWindow) return;

  const historyCount = state.asrToolHistory.length;
  const hasSelectedTranscript = Boolean(state.asrToolSelectedTranscript);
  const hasOutput = Boolean((els.asrToolOutput?.value || "").trim());

  if (els.asrToolModelSelect) {
    const items = state.asrModels.length ? state.asrModels : WHISPER_MODELS.map((name) => ({ name, installed: false }));
    const names = items.map((item) => item.name);
    els.asrToolModelSelect.innerHTML = names
      .map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`)
      .join("");
    els.asrToolModelSelect.value = names.includes(state.selectedWhisperModel) ? state.selectedWhisperModel : (names[0] || "small");
  }

  if (els.asrToolChooseFileButton) {
    els.asrToolChooseFileButton.disabled = state.asrToolIsTranscribing || !state.activeProfileId;
    els.asrToolChooseFileButton.textContent = state.asrToolIsTranscribing ? "Транскрибация…" : "Выбрать файл";
  }
  if (els.asrToolRefreshHistoryButton) {
    els.asrToolRefreshHistoryButton.disabled = state.asrToolIsTranscribing || !state.activeProfileId;
  }
  if (els.asrToolInsertPromptButton) {
    els.asrToolInsertPromptButton.disabled = !hasOutput;
  }
  if (els.asrToolSendButton) {
    els.asrToolSendButton.disabled = !hasOutput || state.isSending;
  }
  if (els.asrToolSaveButton) {
    els.asrToolSaveButton.disabled = !hasOutput || !state.activeProfileId || state.asrToolIsTranscribing;
  }
  if (els.asrToolClearButton) {
    els.asrToolClearButton.disabled = !hasOutput && !hasSelectedTranscript;
  }
  if (els.asrToolDeleteButton) {
    els.asrToolDeleteButton.disabled = !hasSelectedTranscript || state.asrToolIsTranscribing;
  }
  if (els.asrToolClearHistoryButton) {
    els.asrToolClearHistoryButton.disabled = !historyCount || state.asrToolIsTranscribing;
  }
  if (els.asrToolFullscreenButton) {
    els.asrToolFullscreenButton.setAttribute(
      "aria-pressed",
      els.asrToolWindow.classList.contains("tool-window--fullscreen") ? "true" : "false",
    );
  }
  if (els.asrToolMeta) {
    const metaParts = [
      state.selectedWhisperModel || "Whisper модель не выбрана",
      hasSelectedTranscript ? (state.asrToolSelectedTranscript?.language || "Язык auto") : "Отдельная база ASR Studio",
      hasSelectedTranscript ? formatDateTime(state.asrToolSelectedTranscript?.updated_at || state.asrToolSelectedTranscript?.created_at) : `${historyCount} записей`,
    ].filter(Boolean);
    els.asrToolMeta.textContent = metaParts.join(" • ");
  }

  renderAsrToolHistory();
}

async function selectAsrToolTranscript(transcriptId, { silent = false } = {}) {
  const target = Number(transcriptId || 0);
  if (!Number.isFinite(target) || target <= 0) return;

  try {
    const transcript = await request(`/transcripts/${encodeURIComponent(target)}`);
    if (String(transcript?.labels?.origin || "") !== ASR_TOOL_ORIGIN) {
      throw new Error("Эта запись не относится к ASR Studio.");
    }
    state.asrToolSelectedTranscriptId = transcript.id;
    state.asrToolSelectedTranscript = transcript;
    if (els.asrToolOutput) {
      els.asrToolOutput.value = transcript.content || "";
    }
    setInlineStatus(els.asrToolStatus, "Транскрипт загружен. Можно редактировать и отправить в чат.", "success");
    renderAsrTool();
  } catch (error) {
    if (!silent) {
      setInlineStatus(els.asrToolStatus, `Не удалось открыть транскрипт: ${error.message || error}`, "error");
      setFooter(`Не удалось открыть транскрипт: ${error.message || error}`, "error");
    }
  }
}

async function openAsrTool({ focusText = false } = {}) {
  if (!els.asrToolWindow) return;
  state.asrToolIsOpen = true;
  state.asrToolIsMinimized = false;
  els.asrToolWindow.hidden = false;
  setAsrToolWindowBounds();
  setInlineStatus(
    els.asrToolStatus,
    state.asrToolSelectedTranscript
      ? "Транскрипт загружен. Можно редактировать и отправить в чат."
      : "Выберите файл и запустите отдельную транскрибацию.",
    state.asrToolSelectedTranscript ? "success" : "warning",
  );
  renderAsrTool();
  await loadAsrToolHistory({ silent: true });
  if (focusText) {
    els.asrToolOutput?.focus();
  }
  renderToolDock();
}

function closeAsrTool() {
  if (!els.asrToolWindow) return;
  stopAsrToolDrag();
  stopAsrToolResize();
  state.asrToolIsOpen = false;
  state.asrToolIsMinimized = false;
  els.asrToolWindow.hidden = true;
  els.asrToolWindow.classList.remove("tool-window--fullscreen");
  renderToolDock();
}

function minimizeAsrTool() {
  if (!els.asrToolWindow) return;
  stopAsrToolDrag();
  stopAsrToolResize();
  state.asrToolIsOpen = false;
  state.asrToolIsMinimized = true;
  els.asrToolWindow.hidden = true;
  els.asrToolWindow.classList.remove("tool-window--fullscreen");
  renderToolDock();
}

function toggleAsrToolFullscreen() {
  if (!els.asrToolWindow) return;
  stopAsrToolDrag();
  stopAsrToolResize();
  els.asrToolWindow.classList.toggle("tool-window--fullscreen");
  if (!els.asrToolWindow.classList.contains("tool-window--fullscreen")) {
    setAsrToolWindowBounds();
  }
  renderAsrTool();
}

async function runAsrToolTranscription(file) {
  if (!file || state.asrToolIsTranscribing) return;
  if (!state.activeProfileId) {
    setInlineStatus(els.asrToolStatus, "Сначала выберите профиль.", "warning");
    return;
  }

  state.asrToolIsTranscribing = true;
  renderAsrTool();
  setInlineStatus(els.asrToolStatus, `Транскрибирую ${file.name}…`, "warning");
  setFooter(`ASR Studio: транскрибация ${file.name}…`);

  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("profile_id", String(state.activeProfileId));
    formData.append("model", state.selectedWhisperModel || "small");
    formData.append("prompt_preset", state.selectedPromptPreset || "none");
    formData.append("language", "auto");
    formData.append("store_result", "true");
    formData.append("origin", ASR_TOOL_ORIGIN);

    const controller = new AbortController();
    state.asrToolStartController = controller;
    const task = await request("/transcribe/tasks", { method: "POST", body: formData, signal: controller.signal });
    state.asrToolStartController = null;
    state.asrToolTaskId = task?.id || null;

    const result = await waitForVoiceTranscriptionTask(task?.id || "");
    if (result?.cancelled) {
      setInlineStatus(els.asrToolStatus, "Транскрибация остановлена.", "warning");
      return;
    }

    if (els.asrToolOutput) {
      els.asrToolOutput.value = result?.text || "";
    }
    await loadAsrToolHistory({ silent: true });
    if (result?.transcript_id) {
      await selectAsrToolTranscript(result.transcript_id, { silent: true });
    } else {
      renderAsrTool();
    }
    setInlineStatus(els.asrToolStatus, `Транскрибация готова: ${file.name}`, "success");
    setFooter(`ASR Studio: ${file.name} готово.`, "success");
  } catch (error) {
    if (!isAbortError(error)) {
      setInlineStatus(els.asrToolStatus, `Ошибка транскрибации: ${error.message || error}`, "error");
      setFooter(`Ошибка ASR Studio: ${error.message || error}`, "error");
    }
  } finally {
    state.asrToolTaskId = null;
    state.asrToolStartController = null;
    state.asrToolIsTranscribing = false;
    renderAsrTool();
    if (els.asrToolFileInput) {
      els.asrToolFileInput.value = "";
    }
  }
}

async function saveAsrToolTranscript() {
  const content = String(els.asrToolOutput?.value || "").trim();
  if (!content) {
    setInlineStatus(els.asrToolStatus, "Введите текст перед сохранением.", "warning");
    return;
  }
  if (!state.activeProfileId) {
    setInlineStatus(els.asrToolStatus, "Сначала выберите профиль.", "warning");
    return;
  }

  try {
    let transcript;
    if (state.asrToolSelectedTranscriptId) {
      transcript = await request(`/transcripts/${encodeURIComponent(state.asrToolSelectedTranscriptId)}`, {
        method: "PATCH",
        body: { content },
      });
    } else {
      transcript = await request("/transcripts", {
        method: "POST",
        body: {
          profile_id: state.activeProfileId,
          name: "Ручная транскрибация",
          content,
          labels: { origin: ASR_TOOL_ORIGIN },
        },
      });
    }
    state.asrToolSelectedTranscriptId = transcript.id;
    state.asrToolSelectedTranscript = transcript;
    await loadAsrToolHistory({ silent: true });
    setInlineStatus(els.asrToolStatus, "Транскрипт сохранён.", "success");
    setFooter("Транскрипт сохранён.", "success");
  } catch (error) {
    setInlineStatus(els.asrToolStatus, `Не удалось сохранить транскрипт: ${error.message || error}`, "error");
    setFooter(`Не удалось сохранить транскрипт: ${error.message || error}`, "error");
  }
}

function clearAsrToolEditor() {
  state.asrToolSelectedTranscriptId = null;
  state.asrToolSelectedTranscript = null;
  if (els.asrToolOutput) {
    els.asrToolOutput.value = "";
  }
  setInlineStatus(els.asrToolStatus, "Редактор ASR Studio очищен.", "warning");
  renderAsrTool();
}

async function deleteSelectedAsrToolTranscript() {
  if (!state.asrToolSelectedTranscriptId) {
    setInlineStatus(els.asrToolStatus, "Сначала выберите запись в истории.", "warning");
    return;
  }
  if (!window.confirm("Удалить выбранную запись транскрибации?")) return;

  try {
    await request(`/transcripts/${encodeURIComponent(state.asrToolSelectedTranscriptId)}`, { method: "DELETE" });
    clearAsrToolEditor();
    await loadAsrToolHistory({ silent: true });
    setFooter("Запись ASR удалена.", "success");
  } catch (error) {
    setInlineStatus(els.asrToolStatus, `Не удалось удалить запись: ${error.message || error}`, "error");
    setFooter(`Не удалось удалить запись ASR: ${error.message || error}`, "error");
  }
}

async function clearAsrToolHistory() {
  if (!state.activeProfileId || !state.asrToolHistory.length) {
    setInlineStatus(els.asrToolStatus, "История ASR Studio уже пуста.", "warning");
    return;
  }
  if (!window.confirm("Удалить все записи из ASR Studio?")) return;

  try {
    const result = await request(
      `/transcripts?profile_id=${encodeURIComponent(state.activeProfileId)}&origin=${encodeURIComponent(ASR_TOOL_ORIGIN)}`,
      { method: "DELETE" },
    );
    clearAsrToolEditor();
    await loadAsrToolHistory({ silent: true });
    setInlineStatus(
      els.asrToolStatus,
      Number(result?.deleted || 0) > 0
        ? `История ASR очищена. Удалено записей: ${result.deleted}.`
        : "История ASR очищена.",
      "success",
    );
    setFooter("История ASR очищена.", "success");
  } catch (error) {
    setInlineStatus(els.asrToolStatus, `Не удалось очистить историю: ${error.message || error}`, "error");
    setFooter(`Не удалось очистить историю ASR: ${error.message || error}`, "error");
  }
}

function insertAsrToolIntoPrompt() {
  const text = String(els.asrToolOutput?.value || "").trim();
  if (!text) {
    setInlineStatus(els.asrToolStatus, "Нет текста для вставки в чат.", "warning");
    return;
  }
  insertPromptText(text, { append: true });
  setInlineStatus(els.asrToolStatus, "Транскрипт вставлен в поле ввода.", "success");
  setFooter("Транскрипт вставлен в поле ввода.", "success");
}

async function sendAsrToolTextToChat() {
  const text = String(els.asrToolOutput?.value || "").trim();
  if (!text) {
    setInlineStatus(els.asrToolStatus, "Нет текста для отправки в чат.", "warning");
    return;
  }
  await sendPromptText(text, { clearInput: false });
}

function renderOcrEditor() {
  if (!els.ocrBackdrop) return;
  if (els.ocrTextOutput && els.ocrTextOutput.value !== state.ocrText) {
    els.ocrTextOutput.value = state.ocrText || "";
  }
  if (els.ocrMeta) {
    els.ocrMeta.textContent = state.ocrFileName
      ? `Источник: ${state.ocrFileName}. OCR-текст можно отредактировать, затем вставить в чат или сразу отправить.`
      : "OCR-текст можно поправить и затем вставить в чат или сразу отправить.";
  }
  if (els.ocrInsertPromptButton) {
    els.ocrInsertPromptButton.disabled = !String(state.ocrText || "").trim();
  }
  if (els.ocrSendButton) {
    els.ocrSendButton.disabled = !String(state.ocrText || "").trim() || state.isSending;
  }
  if (els.ocrClearButton) {
    els.ocrClearButton.disabled = !String(state.ocrText || "").trim() && !state.ocrFileName;
  }
}

function openOcrEditor() {
  if (!els.ocrBackdrop) return;
  els.ocrBackdrop.hidden = false;
  renderOcrEditor();
}

function closeOcrEditor() {
  if (!els.ocrBackdrop) return;
  els.ocrBackdrop.hidden = true;
}

function clearOcrEditor() {
  state.ocrFileName = "";
  state.ocrText = "";
  if (els.ocrTextOutput) {
    els.ocrTextOutput.value = "";
  }
  setInlineStatus(els.ocrStatus, "OCR-редактор очищен.", "warning");
  renderOcrEditor();
}

async function runOcrForImage(file) {
  if (!file || state.ocrBusy) return;
  state.ocrBusy = true;
  state.ocrFileName = file.name || "";
  state.ocrText = "";
  openOcrEditor();
  setInlineStatus(els.ocrStatus, `Запускаю OCR для изображения ${file.name}…`, "warning");
  setFooter(`OCR: распознаю ${file.name}…`);
  renderOcrEditor();

  try {
    const formData = new FormData();
    formData.append("file", file);
    const data = await request("/ocr/extract", { method: "POST", body: formData });
    state.ocrText = String(data?.text || "").trim();
    state.ocrFileName = String(data?.file_name || file.name || "").trim();
    renderOcrEditor();
    setInlineStatus(els.ocrStatus, "Текст с изображения извлечён. Можно редактировать, вставлять и отправлять.", "success");
    setFooter("OCR: текст извлечён.", "success");
  } catch (error) {
    setInlineStatus(els.ocrStatus, `Ошибка OCR: ${error.message || error}`, "error");
    setFooter(`Ошибка OCR: ${error.message || error}`, "error");
  } finally {
    state.ocrBusy = false;
    if (els.ocrImageInput) {
      els.ocrImageInput.value = "";
    }
    renderOcrEditor();
  }
}

function insertOcrIntoPrompt() {
  const text = String(els.ocrTextOutput?.value || "").trim();
  if (!text) {
    setInlineStatus(els.ocrStatus, "Нет текста для вставки в чат.", "warning");
    return;
  }
  state.ocrText = text;
  insertPromptText(text, { append: true });
  setInlineStatus(els.ocrStatus, "Текст из изображения вставлен в поле ввода.", "success");
  setFooter("OCR: текст вставлен в поле ввода.", "success");
}

async function sendOcrTextToChat() {
  const text = String(els.ocrTextOutput?.value || "").trim();
  if (!text) {
    setInlineStatus(els.ocrStatus, "Нет текста для отправки в чат.", "warning");
    return;
  }
  state.ocrText = text;
  await sendPromptText(text, { clearInput: false });
}

async function loadTtsHistory({ silent = false } = {}) {
  try {
    const data = await request("/tts/history");
    state.ttsHistory = Array.isArray(data?.items) ? data.items : [];
    if (state.ttsToolSelectedRecordId && !state.ttsHistory.some((item) => item.id === state.ttsToolSelectedRecordId)) {
      state.ttsToolSelectedRecordId = null;
      state.ttsToolSelectedRecord = null;
    }
    renderTtsTool();
    return true;
  } catch (error) {
    state.ttsHistory = [];
    renderTtsTool();
    if (!silent) {
      setFooter(`Не удалось загрузить историю TTS: ${error.message || error}`, "error");
    }
    return false;
  }
}

async function selectTtsToolRecord(recordId, { silent = false } = {}) {
  const target = String(recordId || "").trim();
  if (!target) return;

  try {
    const record = await request(`/tts/history/${encodeURIComponent(target)}`);
    state.ttsToolSelectedRecordId = record.id;
    state.ttsToolSelectedRecord = record;
    if (els.ttsToolText) {
      els.ttsToolText.value = record.text || "";
    }
    const preparedRecord = await ensureTtsToolSpeed(record, { silent: true });
    state.ttsToolSelectedRecord = preparedRecord;
    setInlineStatus(
      els.ttsToolStatus,
      preparedRecord.status === "completed"
        ? "Запись загружена. Можно скачать файл или сгенерировать заново."
        : `Статус записи: ${preparedRecord.status || "unknown"}`,
      preparedRecord.status === "completed" ? "success" : preparedRecord.status === "error" ? "error" : "warning",
    );
    renderTtsTool();
  } catch (error) {
    if (!silent) {
      setFooter(`Не удалось открыть запись озвучки: ${error.message || error}`, "error");
      setInlineStatus(els.ttsToolStatus, `Не удалось открыть запись: ${error.message || error}`, "error");
    }
  }
}

function fillTtsToolWithLatestAssistant({ silent = false } = {}) {
  const message = findLatestAssistantMessage();
  if (!message) {
    if (!silent) {
      setInlineStatus(els.ttsToolStatus, "Пока нет ответа ассистента для подстановки.", "warning");
      setFooter("Пока нет ответа, который можно подставить в Voice Studio.", "warning");
    }
    return false;
  }

  state.ttsToolSelectedRecordId = null;
  state.ttsToolSelectedRecord = null;
  stopTtsToolPlayer();
  if (els.ttsToolText) {
    els.ttsToolText.value = String(message.content || "").trim();
  }
  setInlineStatus(els.ttsToolStatus, "Последний ответ подставлен в Voice Studio.", "success");
  renderTtsTool();
  return true;
}

async function openTtsTool({ focusText = false } = {}) {
  if (!els.ttsToolWindow) return;
  state.ttsToolIsOpen = true;
  state.ttsToolIsMinimized = false;
  els.ttsToolWindow.hidden = false;
  syncTtsToolWindowMode();
  setTtsToolWindowBounds();

  setInlineStatus(
    els.ttsToolStatus,
    state.ttsToolSelectedRecord
      ? "Запись готова к прослушиванию или скачиванию."
      : "Введите текст, выберите голос и нажмите «Озвучить».",
    state.ttsToolSelectedRecord ? "success" : "warning",
  );
  renderTtsTool();
  await loadTtsHistory({ silent: true });

  if (focusText) {
    els.ttsToolText?.focus();
  }
  renderToolDock();
}

function closeTtsTool() {
  if (!els.ttsToolWindow) return;
  stopTtsToolDrag();
  stopTtsToolResize();
  state.ttsToolIsOpen = false;
  state.ttsToolIsMinimized = false;
  els.ttsToolWindow.hidden = true;
  els.ttsToolWindow.classList.remove("tool-window--fullscreen");
  stopTtsToolPlayer();
  renderToolDock();
}

function minimizeTtsTool() {
  if (!els.ttsToolWindow) return;
  stopTtsToolDrag();
  stopTtsToolResize();
  state.ttsToolIsOpen = false;
  state.ttsToolIsMinimized = true;
  els.ttsToolWindow.hidden = true;
  els.ttsToolWindow.classList.remove("tool-window--fullscreen");
  stopTtsToolPlayer();
  renderToolDock();
}

function toggleTtsToolFullscreen() {
  if (!els.ttsToolWindow) return;
  stopTtsToolDrag();
  stopTtsToolResize();
  if (shouldForceTtsToolFullscreen()) {
    els.ttsToolWindow.classList.add("tool-window--fullscreen");
    els.ttsToolWindow.dataset.autoFullscreen = "1";
    renderTtsTool();
    return;
  }
  delete els.ttsToolWindow.dataset.autoFullscreen;
  els.ttsToolWindow.classList.toggle("tool-window--fullscreen");
  if (!els.ttsToolWindow.classList.contains("tool-window--fullscreen")) {
    setTtsToolWindowBounds();
  }
  renderTtsTool();
}

async function generateFromTtsTool() {
  const text = String(els.ttsToolText?.value || "").trim();
  const voiceId = String(
    els.ttsToolVoiceSelect?.value
      || state.selectedTtsVoiceId
      || state.ttsVoices[0]?.id
      || "",
  ).trim();
  if (!text) {
    setInlineStatus(els.ttsToolStatus, "Введите текст для озвучки.", "warning");
    return;
  }
  if (voiceId !== state.selectedTtsVoiceId) {
    state.selectedTtsVoiceId = voiceId;
    writeStored(STORAGE_KEYS.ttsVoiceId, state.selectedTtsVoiceId);
  }
  if (!voiceId) {
    setInlineStatus(els.ttsToolStatus, "Сначала выберите локальный голос в настройках.", "warning");
    return;
  }
  if (state.isSpeaking) return;

  state.isSpeaking = true;
  renderTtsTool();
  setInlineStatus(els.ttsToolStatus, "Генерирую локальную озвучку…", "warning");
  setFooter("Генерирую локальную озвучку…");

  try {
    const created = await request("/tts/generate", {
      method: "POST",
      body: {
        text,
        voice_id: voiceId,
        provider: state.selectedTtsProvider || "piper",
      },
    });
    let record = await waitForTtsRecord(created?.id);
    record = await ensureTtsToolSpeed(record, { silent: true, manageBusy: false });
    await loadTtsHistory({ silent: true });
    state.ttsToolSelectedRecordId = record.id;
    state.ttsToolSelectedRecord = record;
    syncTtsToolPlayer(record);
    setInlineStatus(els.ttsToolStatus, "Озвучка готова. Можно прослушать или скачать файл.", "success");
    setFooter("Озвучка готова.", "success");
  } catch (error) {
    setInlineStatus(els.ttsToolStatus, `Ошибка озвучки: ${error.message || error}`, "error");
    setFooter(`Ошибка озвучки: ${error.message || error}`, "error");
  } finally {
    state.isSpeaking = false;
    renderTtsTool();
  }
}

async function deleteSelectedTtsToolRecord() {
  const record = state.ttsToolSelectedRecord;
  if (!record?.id) {
    setInlineStatus(els.ttsToolStatus, "Сначала выберите запись в истории.", "warning");
    return;
  }
  if (!window.confirm("Удалить выбранную запись озвучки?")) return;

  try {
    await request(`/tts/history/${encodeURIComponent(record.id)}`, { method: "DELETE" });
    state.ttsToolSelectedRecordId = null;
    state.ttsToolSelectedRecord = null;
    stopTtsToolPlayer();
    await loadTtsHistory({ silent: true });
    setInlineStatus(els.ttsToolStatus, "Запись озвучки удалена.", "success");
    setFooter("Запись озвучки удалена.", "success");
  } catch (error) {
    setInlineStatus(els.ttsToolStatus, `Не удалось удалить запись: ${error.message || error}`, "error");
    setFooter(`Не удалось удалить запись озвучки: ${error.message || error}`, "error");
  }
}

async function clearAllTtsToolHistory() {
  if (!state.ttsHistory.length) {
    setInlineStatus(els.ttsToolStatus, "История озвучки уже пуста.", "warning");
    return;
  }
  if (!window.confirm("Удалить все генерации озвучки из Voice Studio?")) return;

  try {
    const result = await request("/tts/history", { method: "DELETE" });
    state.ttsToolSelectedRecordId = null;
    state.ttsToolSelectedRecord = null;
    stopTtsToolPlayer();
    await loadTtsHistory({ silent: true });
    const deleted = Number(result?.deleted || 0);
    setInlineStatus(
      els.ttsToolStatus,
      deleted > 0 ? `История озвучки очищена. Удалено записей: ${deleted}.` : "История озвучки очищена.",
      "success",
    );
    setFooter(
      deleted > 0 ? `История TTS очищена. Удалено записей: ${deleted}.` : "История TTS очищена.",
      "success",
    );
  } catch (error) {
    setInlineStatus(els.ttsToolStatus, `Не удалось очистить историю: ${error.message || error}`, "error");
    setFooter(`Не удалось очистить историю TTS: ${error.message || error}`, "error");
  }
}

async function downloadSelectedTtsToolRecord() {
  try {
    let record = state.ttsToolSelectedRecord;
    if (!record) {
      setInlineStatus(els.ttsToolStatus, "Для скачивания сначала выберите готовую запись.", "warning");
      return;
    }

    record = await ensureTtsToolSpeed(record, { silent: false });
    const url = getTtsToolDownloadUrl(record);
    if (!url) {
      setInlineStatus(els.ttsToolStatus, "Для скачивания сначала выберите готовую запись.", "warning");
      return;
    }

    const link = document.createElement("a");
    link.href = url;
    link.download = "";
    document.body.append(link);
    link.click();
    link.remove();
    setInlineStatus(els.ttsToolStatus, "Скачивание записи запущено.", "success");
    setFooter("Скачивание записи запущено.", "success");
  } catch (error) {
    setInlineStatus(els.ttsToolStatus, `Не удалось подготовить файл: ${error.message || error}`, "error");
    setFooter(`Не удалось подготовить файл: ${error.message || error}`, "error");
  }
}

function renderDownloads() {
  if (!els.downloadList) return;
  const items = collectModelOperations();
  if (!items.length) {
    els.downloadList.innerHTML = '<p class="subtle">Активных загрузок нет.</p>';
    return;
  }

  els.downloadList.innerHTML = items
    .map((item) => {
      const percent = typeof item.percent === "number" ? Math.max(0, Math.min(100, item.percent)) : 0;
      const eta = item.eta_seconds ? ` • ETA ${item.eta_seconds}s` : "";
      const downloaded = item.downloaded_bytes ? formatBytes(item.downloaded_bytes) : "";
      const total = item.total_bytes ? formatBytes(item.total_bytes) : "";
      const transfer = downloaded && total ? ` • ${downloaded} / ${total}` : downloaded ? ` • ${downloaded}` : "";
      const canCancel = item.source === "chat" && ["pending", "running", "paused"].includes(item.state);
      const sourceLabel = item.source === "asr" ? "ASR" : item.source === "tts" ? "TTS" : "CHAT";
      return `
        <article class="download-card">
          <div class="download-card__top">
            <strong>${escapeHtml(item.model || item.voice_key || "модель")}</strong>
            <span class="subtle">${escapeHtml(sourceLabel)} • ${escapeHtml(item.state || "")}</span>
          </div>
          <div class="download-progress"><div class="download-progress__bar" style="width:${percent}%;"></div></div>
          <div class="subtle">${escapeHtml(item.message || "Ожидание")}${escapeHtml(eta)}${escapeHtml(transfer)}</div>
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
  renderLibraryPanels();
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
  void loadWhisperModels({ silent: true });
  void loadTtsSettings({ silent: true });
  void loadTtsLibrary({ silent: true });
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
    state.lanUrl = data?.lan_url || data?.ios_url || fallbackLanUrl();
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

async function loadWhisperModels({ silent = false } = {}) {
  try {
    const data = await request("/whisper/models");
    state.asrModels = Array.isArray(data?.items) ? data.items : [];
    state.asrDownloads = Array.isArray(data?.downloads) ? data.downloads : [];
    if (!state.selectedWhisperModel) {
      state.selectedWhisperModel = data?.default || state.asrModels[0]?.name || "small";
      writeStored(STORAGE_KEYS.whisperModel, state.selectedWhisperModel);
    }
    renderWhisperControls();
    renderDownloads();
    syncDownloadsPolling();
    return true;
  } catch (error) {
    if (!silent) {
      setInlineStatus(els.asrSettingsStatus, `Не удалось получить список ASR-моделей: ${error.message || error}`, "error");
      setFooter(`Не удалось получить список ASR-моделей: ${error.message || error}`, "error");
    }
    return false;
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
    state.ttsSpeedOptions = Array.isArray(health?.speed_options) && health.speed_options.length
      ? health.speed_options.map((item) => Number(item)).filter(Number.isFinite)
      : [...DEFAULT_TTS_SPEED_OPTIONS];
    if (!state.ttsSpeedOptions.some((item) => formatTtsSpeedLabel(item) === formatTtsSpeedLabel(state.selectedTtsSpeed))) {
      state.selectedTtsSpeed = formatTtsSpeedLabel(state.ttsSpeedOptions[0] || 1);
      writeStored(STORAGE_KEYS.ttsSpeed, state.selectedTtsSpeed);
    }
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

async function loadTtsLibrary({ silent = false, forceRefresh = false } = {}) {
  try {
    const [catalogData, downloadsData] = await Promise.all([
      request(`/tts/voice-library?force_refresh=${forceRefresh ? "true" : "false"}`),
      request("/tts/voice-library/downloads"),
    ]);
    state.ttsVoiceCatalog = Array.isArray(catalogData?.items) ? catalogData.items : [];
    state.ttsVoiceDownloads = Array.isArray(downloadsData?.items) ? downloadsData.items : [];
    renderTtsControls();
    renderDownloads();
    syncDownloadsPolling();
    return true;
  } catch (error) {
    state.ttsVoiceCatalog = [];
    state.ttsVoiceDownloads = [];
    renderTtsControls();
    if (!silent) {
      setFooter(`Не удалось получить каталог TTS-голосов: ${error.message || error}`, "error");
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
  state.asrToolSelectedTranscriptId = null;
  state.asrToolSelectedTranscript = null;
  state.asrToolHistory = [];
  renderProfileOptions();
  await loadSessions({ preferredSessionId });
  await loadAsrToolHistory({ silent: true });
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

async function ensureModelInstalled(modelName) {
  if (!modelName) return true;
  if (state.installedModels.some((item) => item.name === modelName)) {
    return true;
  }

  await startModelDownload(modelName);
  return false;
}

async function sendPromptText(rawQuery, { clearInput = false } = {}) {
  const query = String(rawQuery || "").trim();
  if (state.isSending) {
    await cancelCurrentChatGeneration();
    return;
  }
  if (!query) return;
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
  state.chatTaskId = null;
  const controller = new AbortController();
  state.chatTaskStartController = controller;
  updateSendButtonState();
  if (clearInput && els.promptInput) {
    els.promptInput.value = "";
    autoResizePrompt();
    updateSendButtonState();
  }
  setFooter("Генерация ответа… Нажмите «Стоп», чтобы остановить.", "warning");

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

    const task = await request("/chat/tasks", { method: "POST", body: payload, signal: controller.signal });
    state.chatTaskStartController = null;
    state.chatTaskId = task?.id || null;
    const nextSessionId = task?.session_id || state.currentSessionId;
    state.selectedLlmModel = task?.model_name || selectedModel;
    writeStored(STORAGE_KEYS.llmModel, state.selectedLlmModel || "");

    if (nextSessionId) {
      await loadSessions({ preferredSessionId: nextSessionId });
    }

    if (String(task?.state || "") === "completed") {
      setFooter("Ответ готов.", "success");
      return;
    }

    appendAssistantThinkingPlaceholder();
    const completedTask = await waitForChatTask(task?.id || "");
    state.chatTaskId = null;

    if (String(completedTask?.state || "") === "cancelled") {
      removeAssistantThinkingPlaceholder();
      if (nextSessionId) {
        await loadSessions({ preferredSessionId: nextSessionId });
      }
      setFooter("Генерация ответа остановлена.", "warning");
      return;
    }

    if (nextSessionId) {
      await loadSessions({ preferredSessionId: nextSessionId });
    }
    setFooter("Ответ готов.", "success");
  } catch (error) {
    if (isAbortError(error)) {
      removeAssistantThinkingPlaceholder();
      setFooter("Генерация ответа остановлена.", "warning");
      return;
    }
    removeAssistantThinkingPlaceholder();
    if (state.currentSessionId) {
      await loadSessions({ preferredSessionId: state.currentSessionId });
    }
    setFooter(`Ошибка чата: ${error.message || error}`, "error");
  } finally {
    state.chatTaskId = null;
    state.chatTaskStartController = null;
    state.isSending = false;
    updateSendButtonState();
    scrollMessagesToBottom({ force: true });
  }
}

async function sendCurrentPrompt() {
  const query = (els.promptInput?.value || "").trim();
  await sendPromptText(query, { clearInput: true });
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

async function deleteCurrentModel(modelNameOverride = null) {
  const modelName = (modelNameOverride || els.llmModelSelect?.value || "").trim();
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

async function prepareAsrModel(modelName, { force = false } = {}) {
  const target = (modelName || "").trim();
  if (!target) return;
  try {
    await request("/whisper/models/prepare", {
      method: "POST",
      body: { model: target, force: Boolean(force) },
    });
    await loadWhisperModels({ silent: true });
    renderDownloads();
    setFooter(`${force ? "Обновление" : "Загрузка"} ASR-модели ${target} запущено.`, "success");
  } catch (error) {
    setFooter(`Не удалось подготовить ASR-модель: ${error.message || error}`, "error");
  }
}

async function checkAsrModelUpdate(modelName) {
  const target = (modelName || "").trim();
  if (!target) return;
  try {
    const result = await request(`/whisper/models/update-check/${encodeURIComponent(target)}`);
    state.asrUpdateChecks = { ...state.asrUpdateChecks, [target]: result };
    renderWhisperControls();
    const status = String(result?.status || "");
    const tone = status === "update_available" ? "warning" : status === "up_to_date" ? "success" : "warning";
    setFooter(result?.message || `Статус модели ${target} обновлён.`, tone);
  } catch (error) {
    setFooter(`Не удалось проверить обновление ASR-модели: ${error.message || error}`, "error");
  }
}

async function deleteAsrModel(modelName) {
  const target = (modelName || "").trim();
  if (!target) return;
  if (!window.confirm(`Удалить локальную ASR-модель ${target}?`)) return;
  try {
    await request(`/whisper/models/${encodeURIComponent(target)}`, { method: "DELETE" });
    state.asrUpdateChecks = { ...state.asrUpdateChecks, [target]: null };
    await loadWhisperModels({ silent: true });
    setFooter(`ASR-модель ${target} удалена.`, "success");
  } catch (error) {
    setFooter(`Не удалось удалить ASR-модель: ${error.message || error}`, "error");
  }
}

function stopTtsPreviewAudio() {
  const audio = state.ttsPreviewAudio;
  if (!audio) return;
  try {
    audio.pause();
  } catch {
    // ignore
  }
  if (audio._objectUrl) {
    URL.revokeObjectURL(audio._objectUrl);
  }
  state.ttsPreviewAudio = null;
}

async function downloadTtsVoice(voiceKey, { force = false } = {}) {
  const target = (voiceKey || "").trim();
  if (!target) return;
  try {
    await request("/tts/voice-library/download", {
      method: "POST",
      body: { voice_key: target, force: Boolean(force) },
    });
    await loadTtsLibrary({ silent: true });
    setFooter(`${force ? "Обновление" : "Загрузка"} TTS-голоса запущено.`, "success");
  } catch (error) {
    setFooter(`Не удалось загрузить TTS-голос: ${error.message || error}`, "error");
  }
}

async function deleteTtsVoice(voiceKey) {
  const target = (voiceKey || "").trim();
  if (!target) return;
  if (!window.confirm(`Удалить локальный TTS-голос ${target}?`)) return;
  try {
    await request(`/tts/voice-library/${encodeURIComponent(target)}`, { method: "DELETE" });
    stopTtsPreviewAudio();
    await loadTtsSettings({ silent: true });
    await loadTtsLibrary({ silent: true, forceRefresh: true });
    setFooter(`TTS-голос ${target} удалён.`, "success");
  } catch (error) {
    setFooter(`Не удалось удалить TTS-голос: ${error.message || error}`, "error");
  }
}

async function previewTtsVoice(voiceKey) {
  const target = (voiceKey || "").trim();
  if (!target) return;
  stopTtsPreviewAudio();

  try {
    const response = await fetch("/tts/voice-library/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voice_key: target }),
    });
    if (!response.ok) {
      const raw = await response.text();
      let payload = {};
      try {
        payload = raw ? JSON.parse(raw) : {};
      } catch {
        payload = { message: raw };
      }
      throw new Error(payload?.detail?.message || payload?.message || response.statusText || "voice_preview_failed");
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const audio = new Audio(objectUrl);
    audio._objectUrl = objectUrl;
    audio.addEventListener("ended", () => {
      if (audio._objectUrl) {
        URL.revokeObjectURL(audio._objectUrl);
      }
      if (state.ttsPreviewAudio === audio) {
        state.ttsPreviewAudio = null;
      }
    }, { once: true });
    state.ttsPreviewAudio = audio;
    await audio.play();
    setFooter("Превью TTS-голоса запущено.", "success");
  } catch (error) {
    setFooter(`Не удалось воспроизвести превью голоса: ${error.message || error}`, "error");
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

  els.fileMenuItem?.addEventListener("click", () => {
    toggleComposerMenu(false);
    els.ocrImageInput?.click();
  });
  els.transcribeMenuItem?.addEventListener("click", async () => {
    toggleComposerMenu(false);
    await openAsrTool({ focusText: false });
  });
  els.speakMenuItem?.addEventListener("click", async () => {
    toggleComposerMenu(false);
    await openTtsTool({ focusText: true });
  });
  els.transcribeInput?.addEventListener("change", async () => {
    const file = els.transcribeInput.files?.[0];
    if (file) {
      await handleTranscription(file);
    }
  });
  els.ocrImageInput?.addEventListener("change", async () => {
    const file = els.ocrImageInput.files?.[0];
    if (file) {
      await runOcrForImage(file);
    }
  });

  els.messageList?.addEventListener("click", async (event) => {
    const codeCopyButton = event.target.closest("[data-code-copy-index]");
    if (codeCopyButton) {
      try {
        const index = Number(codeCopyButton.dataset.codeCopyIndex);
        const code = Number.isFinite(index) ? state.renderedCodeBlocks[index] : "";
        await copyText(code || "");
        setFooter("Код скопирован.", "success");
      } catch {
        setFooter("Не удалось скопировать код.", "error");
      }
      return;
    }

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
    await applySelectedLlmModel(els.llmModelSelect.value || "");
  });

  els.quickModelSelect?.addEventListener("change", async () => {
    await applySelectedLlmModel(els.quickModelSelect.value || "");
  });

  els.whisperModelSelect?.addEventListener("change", () => {
    state.selectedWhisperModel = els.whisperModelSelect.value || "small";
    writeStored(STORAGE_KEYS.whisperModel, state.selectedWhisperModel);
    renderWhisperControls();
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

  els.asrToolCloseButton?.addEventListener("click", () => closeAsrTool());
  els.asrToolMinimizeButton?.addEventListener("click", () => minimizeAsrTool());
  els.asrToolFullscreenButton?.addEventListener("click", () => toggleAsrToolFullscreen());
  els.asrToolHeader?.addEventListener("mousedown", (event) => {
    startAsrToolDrag(event);
  });
  els.asrToolResizeHandle?.addEventListener("mousedown", (event) => {
    startAsrToolResize(event);
  });
  els.asrToolModelSelect?.addEventListener("change", () => {
    state.selectedWhisperModel = els.asrToolModelSelect.value || "small";
    writeStored(STORAGE_KEYS.whisperModel, state.selectedWhisperModel);
    renderWhisperControls();
    renderAsrTool();
  });
  els.asrToolOutput?.addEventListener("input", () => {
    renderAsrTool();
  });
  els.asrToolChooseFileButton?.addEventListener("click", () => {
    els.asrToolFileInput?.click();
  });
  els.asrToolFileInput?.addEventListener("change", async () => {
    const file = els.asrToolFileInput.files?.[0];
    if (file) {
      await runAsrToolTranscription(file);
    }
  });
  els.asrToolRefreshHistoryButton?.addEventListener("click", async () => {
    const ok = await loadAsrToolHistory();
    if (ok) {
      setInlineStatus(els.asrToolStatus, "История ASR Studio обновлена.", "success");
      setFooter("История ASR обновлена.", "success");
    }
  });
  els.asrToolInsertPromptButton?.addEventListener("click", () => {
    insertAsrToolIntoPrompt();
  });
  els.asrToolSendButton?.addEventListener("click", async () => {
    await sendAsrToolTextToChat();
  });
  els.asrToolSaveButton?.addEventListener("click", async () => {
    await saveAsrToolTranscript();
  });
  els.asrToolClearButton?.addEventListener("click", () => {
    clearAsrToolEditor();
  });
  els.asrToolDeleteButton?.addEventListener("click", async () => {
    await deleteSelectedAsrToolTranscript();
  });
  els.asrToolClearHistoryButton?.addEventListener("click", async () => {
    await clearAsrToolHistory();
  });
  els.asrToolHistoryList?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-asr-history-id]");
    if (!button) return;
    await selectAsrToolTranscript(button.dataset.asrHistoryId);
  });

  els.refreshTtsVoicesButton?.addEventListener("click", async () => {
    const ok = await loadTtsSettings();
    if (ok) {
      setFooter("Список локальных TTS-голосов обновлён.", "success");
    }
  });

  els.refreshTtsLibraryButton?.addEventListener("click", async () => {
    const ok = await loadTtsLibrary({ forceRefresh: true });
    if (ok) {
      setFooter("Каталог TTS-голосов обновлён.", "success");
    }
  });

  els.ttsToolCloseButton?.addEventListener("click", () => closeTtsTool());
  els.ttsToolMinimizeButton?.addEventListener("click", () => minimizeTtsTool());
  els.ttsToolFullscreenButton?.addEventListener("click", () => toggleTtsToolFullscreen());
  els.ttsToolHeader?.addEventListener("mousedown", (event) => {
    startTtsToolDrag(event);
  });
  els.ttsToolResizeHandle?.addEventListener("mousedown", (event) => {
    startTtsToolResize(event);
  });
  els.ttsToolVoiceSelect?.addEventListener("change", () => {
    state.selectedTtsVoiceId = els.ttsToolVoiceSelect.value || "";
    writeStored(STORAGE_KEYS.ttsVoiceId, state.selectedTtsVoiceId);
    renderTtsControls();
  });
  els.ttsToolText?.addEventListener("input", () => {
    renderTtsTool();
  });
  els.ttsToolGenerateButton?.addEventListener("click", async () => {
    await generateFromTtsTool();
  });
  els.ttsToolUseAssistantButton?.addEventListener("click", () => {
    fillTtsToolWithLatestAssistant();
  });
  els.ttsToolRefreshButton?.addEventListener("click", async () => {
    const [settingsOk] = await Promise.all([
      loadTtsSettings({ silent: true }),
      loadTtsHistory({ silent: true }),
    ]);
    await loadTtsLibrary({ silent: true, forceRefresh: true });
    if (settingsOk) {
      setInlineStatus(els.ttsToolStatus, "Голоса и история Voice Studio обновлены.", "success");
      setFooter("Голоса TTS обновлены.", "success");
    }
  });
  els.ttsToolSpeedSelect?.addEventListener("change", async () => {
    state.selectedTtsSpeed = formatTtsSpeedLabel(els.ttsToolSpeedSelect.value || 1);
    writeStored(STORAGE_KEYS.ttsSpeed, state.selectedTtsSpeed);
    renderTtsTool();
    if (state.ttsToolSelectedRecord) {
      try {
        const updated = await ensureTtsToolSpeed(state.ttsToolSelectedRecord, { silent: false });
        state.ttsToolSelectedRecord = updated;
        renderTtsTool();
      } catch (error) {
        setInlineStatus(els.ttsToolStatus, `Не удалось применить скорость: ${error.message || error}`, "error");
        setFooter(`Не удалось применить скорость: ${error.message || error}`, "error");
      }
    }
  });
  els.ttsToolDownloadButton?.addEventListener("click", async () => {
    await downloadSelectedTtsToolRecord();
  });
  els.ttsToolDeleteButton?.addEventListener("click", async () => {
    await deleteSelectedTtsToolRecord();
  });
  els.ttsToolClearButton?.addEventListener("click", async () => {
    await clearAllTtsToolHistory();
  });
  els.ttsToolHistoryList?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-tts-history-id]");
    if (!button) return;
    await selectTtsToolRecord(button.dataset.ttsHistoryId);
  });
  els.toolDock?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-tool-dock]");
    if (!button) return;
    const kind = button.dataset.toolDock || "";
    if (kind === "asr") {
      await openAsrTool({ focusText: true });
      return;
    }
    if (kind === "tts") {
      await openTtsTool({ focusText: true });
    }
  });

  els.closeOcrButton?.addEventListener("click", () => closeOcrEditor());
  els.ocrBackdrop?.addEventListener("click", (event) => {
    if (event.target === els.ocrBackdrop) {
      closeOcrEditor();
    }
  });
  els.ocrTextOutput?.addEventListener("input", () => {
    state.ocrText = els.ocrTextOutput.value || "";
    renderOcrEditor();
  });
  els.ocrInsertPromptButton?.addEventListener("click", () => {
    insertOcrIntoPrompt();
  });
  els.ocrSendButton?.addEventListener("click", async () => {
    await sendOcrTextToChat();
  });
  els.ocrClearButton?.addEventListener("click", () => {
    clearOcrEditor();
  });

  els.refreshModelsButton?.addEventListener("click", async () => {
    await loadModels();
    setFooter("Список моделей обновлён.", "success");
  });

  els.chatLibraryToggle?.addEventListener("click", () => {
    setLibraryOpen("chat", !state.libraryPanels.chat);
  });

  els.asrLibraryToggle?.addEventListener("click", () => {
    setLibraryOpen("asr", !state.libraryPanels.asr);
  });

  els.ttsLibraryToggle?.addEventListener("click", () => {
    const nextOpen = !state.libraryPanels.tts;
    setLibraryOpen("tts", nextOpen);
    if (nextOpen) {
      els.ttsVoiceSearchInput?.focus();
    }
  });

  els.ttsVoiceSearchInput?.addEventListener("input", () => {
    state.ttsVoiceSearch = els.ttsVoiceSearchInput.value || "";
    renderLibraryPanels();
    renderTtsVoiceLibrary();
  });

  els.refreshAsrModelsButton?.addEventListener("click", async () => {
    const ok = await loadWhisperModels();
    if (ok) {
      setFooter("Список ASR-моделей обновлён.", "success");
    }
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

  els.chatModelLibrary?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-chat-model-action]");
    if (!button) return;
    const action = button.dataset.chatModelAction || "";
    const modelName = button.dataset.chatModel || "";
    if (!modelName) return;
    if (action === "select") {
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
    if (action === "download") {
      await startModelDownload(modelName);
      return;
    }
    if (action === "delete") {
      await deleteCurrentModel(modelName);
    }
  });

  els.asrModelLibrary?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-asr-model-action]");
    if (!button) return;
    const action = button.dataset.asrModelAction || "";
    const modelName = button.dataset.asrModel || "";
    if (!modelName) return;
    if (action === "select") {
      state.selectedWhisperModel = modelName;
      writeStored(STORAGE_KEYS.whisperModel, modelName);
      renderWhisperControls();
      setFooter(`Активная ASR-модель: ${modelName}`, "success");
      return;
    }
    if (action === "download") {
      await prepareAsrModel(modelName, { force: button.dataset.asrForce === "1" });
      return;
    }
    if (action === "check") {
      await checkAsrModelUpdate(modelName);
      return;
    }
    if (action === "delete") {
      await deleteAsrModel(modelName);
    }
  });

  els.ttsVoiceLibrary?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-tts-voice-action]");
    if (!button) return;
    const action = button.dataset.ttsVoiceAction || "";
    const voiceKey = button.dataset.ttsVoiceKey || "";
    const voiceId = button.dataset.ttsVoiceId || "";

    if (action === "select" && voiceId) {
      state.selectedTtsVoiceId = voiceId;
      writeStored(STORAGE_KEYS.ttsVoiceId, voiceId);
      renderTtsControls();
      setFooter(`Активный TTS-голос: ${voiceId}`, "success");
      return;
    }
    if (action === "preview") {
      await previewTtsVoice(voiceKey);
      return;
    }
    if (action === "download") {
      await downloadTtsVoice(voiceKey, { force: button.dataset.ttsForce === "1" });
      return;
    }
    if (action === "delete") {
      await deleteTtsVoice(voiceKey);
    }
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
      closeOcrEditor();
      closeSettings();
      stopAsrToolDrag();
      stopAsrToolResize();
      closeAsrTool();
      stopTtsToolDrag();
      stopTtsToolResize();
      closeTtsTool();
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
    stopAsrToolDrag();
    stopAsrToolResize();
    stopTtsToolDrag();
    stopTtsToolResize();
    toggleComposerMenu(false);
    if (state.asrToolIsOpen && !els.asrToolWindow?.classList.contains("tool-window--fullscreen")) {
      setAsrToolWindowBounds();
    }
    if (state.ttsToolIsOpen) {
      syncTtsToolWindowMode();
      if (!els.ttsToolWindow?.classList.contains("tool-window--fullscreen")) {
        setTtsToolWindowBounds();
      }
    }
    autoResizePrompt();
    syncMessageScrollState();
  });
}

async function bootstrap() {
  renderWhisperControls();
  renderTtsControls();
  renderAsrTool();
  renderOcrEditor();
  renderToolDock();
  renderVoiceRecordButton();
  autoResizePrompt();
  updateSendButtonState();
  bindEvents();
  await loadHealth();
  await loadModels();
  await loadWhisperModels({ silent: true });
  await loadStoragePaths();
  await loadTtsSettings({ silent: true });
  await loadTtsLibrary({ silent: true });
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
