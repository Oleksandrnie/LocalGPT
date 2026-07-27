import { formatRichMessage as formatMarkdownMessage } from "./markdown.mjs";

const WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"];
const ASR_STUDIO_DEFAULT_MODEL = "large-v3-turbo";
const ASR_STUDIO_DEFAULT_PROMPT_PRESET = "ru";
const ASR_ANALYSIS_LANGUAGE_DEFAULT = "auto";
const ASR_DEFAULT_BEAM_SIZE = 5;
const ASR_DEFAULT_THREADS = 4;
const ASR_PROMPT_PRESETS = ["auto", "ru", "en"];
const ASR_ANALYSIS_LANGUAGES = ["auto", "ru", "en"];
const ASR_FULL_ANALYSIS_WARNING = "Полный анализ запускает все стадии ASR pipeline и может заметно нагружать CPU/GPU, повышать температуру Mac и держать Ollama занятой несколько минут. Включайте и запускайте его только осознанно.";
const ASR_PIPELINE_DISABLED_VALUE = "__disabled__";
const CREATE_PROFILE_VALUE = "__create_profile__";
const AUTO_MODEL_ID = "__auto_router__";
const AUTO_MODEL_TITLE = "Auto / Smart Router";
const AUTO_MODEL_HELP = "Автоматически классифицирует chat-запрос через qwen3:0.6b и выбирает подходящую LLM из локального каталога. Local Calculator запускается только при ручном выборе.";
const LOCAL_CALCULATOR_MODEL_ID = "__local_calculator__";
const LOCAL_CALCULATOR_TITLE = "Local Calculator";
const LOCAL_CALCULATOR_HELP = "Детерминированный локальный калькулятор для явной арифметики: суммы, вычитание, проценты, часы/минуты и ставка × часы. Не использует LLM и не отвечает на обычные вопросы.";
const ASR_PIPELINE_SETTINGS_MODEL_ID = "__asr_pipeline__";
const STREAM_TYPEWRITER_INTERVAL_MS = 28;
const STREAM_TYPEWRITER_MIN_CHARS = 1;
const STREAM_TYPEWRITER_MAX_CHARS = 8;
const STREAM_TYPEWRITER_BACKLOG_STEP = 60;
const STREAM_TYPEWRITER_FINAL_FLUSH_CHARS = 24;
const ACTIVE_DOWNLOAD_STATES = new Set(["pending", "queued", "running", "paused"]);
const STORAGE_KEYS = {
  activeProfileId: "localgpt_simple_profile_id",
  activeSessionId: "localgpt_simple_session_id",
  llmModel: "localgpt_simple_llm_model",
  chatWhisperModel: "localgpt_simple_chat_whisper_model",
  whisperModel: "localgpt_simple_whisper_model",
  promptPreset: "localgpt_simple_prompt_preset",
  ttsProvider: "localgpt_simple_tts_provider",
  ttsVoiceId: "localgpt_simple_tts_voice_id",
  ttsSpeed: "localgpt_simple_tts_speed",
  theme: "localgpt_simple_theme",
  sidebarOpen: "sidebar_open",
  chatLibraryOpen: "localgpt_simple_chat_library_open",
  asrLibraryOpen: "localgpt_simple_asr_library_open",
  asrPipelineSettingsOpen: "localgpt_simple_asr_pipeline_settings_open",
  asrAnalysisMode: "localgpt_simple_asr_analysis_mode",
  asrHistoryCollapsed: "localgpt_simple_asr_history_collapsed",
  ttsHistoryCollapsed: "localgpt_simple_tts_history_collapsed",
  ttsLibraryOpen: "localgpt_simple_tts_library_open",
  settingsTab: "localgpt_simple_settings_tab",
};

const MESSAGE_STATUSES = new Set(["generating", "streaming", "completed", "failed", "cancelled"]);
const MESSAGE_FINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);
const DEFAULT_TTS_SPEED_OPTIONS = [1, 1.25, 1.5, 1.75, 1.9, 2];
const ASR_TOOL_ORIGIN = "asr_tool";
const ASR_PIPELINE_STAGES = [
  { key: "cleaner", label: "Очистка" },
  { key: "segmenter", label: "Сегменты" },
  { key: "speaker_resolver", label: "Роли" },
  { key: "structurer", label: "Структура" },
  { key: "summary", label: "Саммари" },
];
const ASR_PIPELINE_MODEL_CATALOG = [
  { id: "qwen2.5:7b-instruct", title: "Qwen 2.5 7B Instruct", note: "базовое качество для cleaner, segmenter и ролей" },
  { id: "qwen2.5:3b-instruct", title: "Qwen 2.5 3B Instruct", note: "быстрый fallback, когда важнее скорость" },
  { id: "qwen3:8b", title: "Qwen 3 8B", note: "reasoning для структуры, решений, задач и рисков" },
  { id: "mistral-nemo:12b", title: "Mistral Nemo 12B", note: "heavy summary для длинных транскриптов" },
  { id: "qwen3:4b", title: "Qwen 3 4B", note: "experimental fallback для быстрых проверок" },
  { id: "qwen2.5-coder:7b", title: "Qwen 2.5 Coder 7B", note: "только для технических транскриптов с кодом" },
  { id: "deepseek-coder:6.7b", title: "DeepSeek Coder 6.7B", note: "code-alt для технических транскриптов" },
];
const ASR_PIPELINE_MODEL_IDS = ASR_PIPELINE_MODEL_CATALOG.map((item) => item.id);
const ASR_PIPELINE_LEGACY_MODEL_IDS = new Set(["qwen2.5:3b", "mistral:7b", "mistral"]);
const ASR_PIPELINE_RECOMMENDATIONS = {
  cleaner: {
    primary: "qwen2.5:7b-instruct",
    alternatives: ["qwen2.5:3b-instruct"],
    text: "базовый качественный вариант для очистки длинных встреч; 3B используй только как быстрый fallback.",
  },
  segmenter: {
    primary: "qwen2.5:7b-instruct",
    alternatives: ["qwen2.5:3b-instruct"],
    text: "базовый качественный вариант для разбиения transcript на смысловые сегменты; 3B оставь только для скорости.",
  },
  speaker_resolver: {
    primary: "qwen2.5:7b-instruct",
    alternatives: ["qwen2.5:3b-instruct"],
    text: "стабильнее сопоставляет роли и говорящих; 3B оставь для скорости.",
  },
  structurer: {
    primary: "qwen3:8b",
    alternatives: ["mistral-nemo:12b", "qwen2.5:7b-instruct"],
    text: "лучше подходит для решений, задач, рисков и open questions.",
  },
  summary: {
    primary: "qwen3:8b",
    alternatives: ["mistral-nemo:12b", "qwen2.5:7b-instruct"],
    text: "основной вариант для summary.",
  },
};
const ASR_PIPELINE_DEFAULTS = {
  cleaner: { enabled: false, model: "qwen2.5:7b-instruct", temperature: 0, max_tokens: 6000 },
  segmenter: { enabled: false, model: "qwen2.5:7b-instruct", temperature: 0.05, max_tokens: 6000 },
  speaker_resolver: { enabled: false, model: "qwen2.5:7b-instruct", temperature: 0, max_tokens: 3000 },
  structurer: { enabled: true, model: "qwen3:8b", temperature: 0.05, max_tokens: 6000 },
  summary: { enabled: true, model: "qwen3:8b", temperature: 0.05, max_tokens: 7000 },
};
const ASR_ANALYSIS_MODE_DEFAULT = "smart_summary";
const ASR_ANALYSIS_MODES = [
  {
    id: "summary",
    label: "Быстрое саммари",
    action: "summary",
    preset: "fast",
    tab: "summary",
    description: "Минимальная нагрузка: raw transcript -> summary.",
  },
  {
    id: "smart_summary",
    label: "Умное саммари",
    action: "smart_summary",
    preset: "balanced",
    tab: "summary",
    description: "Рекомендуемый режим: raw transcript/chunks -> structurer -> summary, без cleaner и ролей.",
  },
  {
    id: "full",
    label: "Полный анализ",
    action: "full",
    preset: "balanced",
    tab: "summary",
    requiresFullAnalysis: true,
    description: "Тяжёлый режим: segmenter -> speaker resolver -> structurer -> summary; доступен только после явного разрешения.",
  },
];
const MODEL_SETTINGS_OVERRIDE_KEYS = [
  "temperature",
  "max_tokens",
  "num_ctx",
  "ollama_keep_alive",
  "ollama_think",
  "pipeline_enabled",
  "summary_memory_enabled",
  "rag_enabled",
  "default_pipeline_preset",
  "max_transcript_chars",
  "max_context_chars",
  "summary_memory_limit",
  "rag_top_k",
  "rag_max_context_chars",
  "pipeline",
];
const RESIDENCY_DEFAULTS = {
  max_resident_target_models: 1,
  allow_light_with_heavy: false,
  single_large_target_model: true,
  preload_model_on_manual_select: false,
  auto_target_keep_alive: "4m",
  manual_keep_alive: "5m",
  code_model_keep_alive: "2m",
  heavy_model_keep_alive: "60s",
  router_keep_alive: "2m",
};
const THINKING_MODEL_PATTERNS = [/^qwen3\b/i, /^deepseek-r1\b/i, /^gpt-oss\b/i, /^deepseek-v3\.1\b/i];
const TTS_TOOL_MIN_WIDTH = 960;
const TTS_TOOL_MIN_HEIGHT = 720;
const MOBILE_LAYOUT_QUERY = "(max-width: 768px), (max-width: 960px) and (max-height: 480px)";
const IMAGE_FILE_EXTENSIONS = new Set(["png", "jpg", "jpeg", "gif", "bmp", "webp", "tif", "tiff", "heic", "heif"]);
const CHAT_IMAGE_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/jpg", "image/webp"]);
const CHAT_IMAGE_EXTENSIONS = new Set(["png", "jpg", "jpeg", "webp"]);
const MEDIA_FILE_EXTENSIONS = new Set([
  "mp3", "wav", "m4a", "aac", "ogg", "oga", "flac", "opus", "aiff", "aif", "wma",
  "mp4", "mov", "m4v", "avi", "mkv", "webm", "mpeg", "mpg", "ts", "mts", "m2ts",
]);

const els = {
  sidebar: document.getElementById("sidebar"),
  sidebarBackdrop: document.getElementById("sidebarBackdrop"),
  toggleSidebarButton: document.getElementById("toggleSidebarButton"),
  sidebarCollapseButton: document.getElementById("sidebarCollapseButton"),
  newChatButton: document.getElementById("newChatButton"),
  sessionList: document.getElementById("sessionList"),
  sessionContextMenu: document.getElementById("sessionContextMenu"),
  renameSessionMenuItem: document.getElementById("renameSessionMenuItem"),
  asrHistoryContextMenu: document.getElementById("asrHistoryContextMenu"),
  renameAsrTranscriptMenuItem: document.getElementById("renameAsrTranscriptMenuItem"),
  profileField: document.getElementById("profileField"),
  profileSelect: document.getElementById("profileSelect"),
  chatTitle: document.getElementById("chatTitle"),
  healthStatus: document.getElementById("healthStatus"),
  contextStatus: document.getElementById("contextStatus"),
  clearContextButton: document.getElementById("clearContextButton"),
  quickModelButton: document.getElementById("quickModelButton"),
  quickModelValue: document.getElementById("quickModelValue"),
  quickModelMeta: document.getElementById("quickModelMeta"),
  quickModelMenu: document.getElementById("quickModelMenu"),
  quickModelMobileControl: document.getElementById("quickModelMobileControl"),
  quickModelMobileButton: document.getElementById("quickModelMobileButton"),
  quickModelMobileMenu: document.getElementById("quickModelMobileMenu"),
  quickModelSelect: document.getElementById("quickModelSelect"),
  copyLanUrlButton: document.getElementById("copyLanUrlButton"),
  networkAddressMenu: document.getElementById("networkAddressMenu"),
  openSettingsButton: document.getElementById("openSettingsButton"),
  openRagButton: document.getElementById("openRagButton"),
  themeToggleButton: document.getElementById("themeToggleButton"),
  chatShell: document.getElementById("chatShell"),
  messageScroll: document.getElementById("messageScroll"),
  chatModelNotice: document.getElementById("chatModelNotice"),
  chatModelNoticeSettingsButton: document.getElementById("chatModelNoticeSettingsButton"),
  messageList: document.getElementById("messageList"),
  messageScrollEnd: document.getElementById("messageScrollEnd"),
  emptyState: document.getElementById("emptyState"),
  composerForm: document.getElementById("composerForm"),
  composerAttachments: document.getElementById("composerAttachments"),
  promptInput: document.getElementById("promptInput"),
  voiceRecordButton: document.getElementById("voiceRecordButton"),
  voiceModelMenu: document.getElementById("voiceModelMenu"),
  sendButton: document.getElementById("sendButton"),
  composerMenuButton: document.getElementById("composerMenuButton"),
  composerMenu: document.getElementById("composerMenu"),
  imageMenuItem: document.getElementById("imageMenuItem"),
  fileMenuItem: document.getElementById("fileMenuItem"),
  transcribeMenuItem: document.getElementById("transcribeMenuItem"),
  speakMenuItem: document.getElementById("speakMenuItem"),
  chatImageInput: document.getElementById("chatImageInput"),
  transcribeInput: document.getElementById("transcribeInput"),
  ocrImageInput: document.getElementById("ocrImageInput"),
  scrollTopButton: document.getElementById("scrollTopButton"),
  footerStatus: document.getElementById("footerStatus"),
  chatDropOverlay: document.getElementById("chatDropOverlay"),
  chatDropOverlayTitle: document.getElementById("chatDropOverlayTitle"),
  chatDropOverlayMeta: document.getElementById("chatDropOverlayMeta"),
  toolDock: document.getElementById("toolDock"),
  asrToolWindow: document.getElementById("asrToolWindow"),
  asrLayoutGrid: document.getElementById("asrLayoutGrid"),
  asrToolDropOverlay: document.getElementById("asrToolDropOverlay"),
  asrToolDropOverlayTitle: document.getElementById("asrToolDropOverlayTitle"),
  asrToolDropOverlayMeta: document.getElementById("asrToolDropOverlayMeta"),
  asrToolHeader: document.querySelector("#asrToolWindow [data-tool-drag='asr']"),
  asrToolResizeHandle: document.querySelector("#asrToolWindow [data-tool-resize='asr']"),
  asrToolMinimizeButton: document.getElementById("asrToolMinimizeButton"),
  asrToolFullscreenButton: document.getElementById("asrToolFullscreenButton"),
  asrToolCloseButton: document.getElementById("asrToolCloseButton"),
  asrToolModelSelect: document.getElementById("asrToolModelSelect"),
  asrToolPromptPresetSelect: document.getElementById("asrToolPromptPresetSelect"),
  asrToolAnalysisLanguageSelect: document.getElementById("asrToolAnalysisLanguageSelect"),
  asrToolChooseFileButton: document.getElementById("asrToolChooseFileButton"),
  asrToolPipelineSettingsButton: document.getElementById("asrToolPipelineSettingsButton"),
  asrToolRefreshHistoryButton: document.getElementById("asrToolRefreshHistoryButton"),
  asrToolStopButton: document.getElementById("asrToolStopButton"),
  asrToolFileInput: document.getElementById("asrToolFileInput"),
  asrToolFileCard: document.getElementById("asrToolFileCard"),
  asrToolFileTitle: document.getElementById("asrToolFileTitle"),
  asrToolFileMeta: document.getElementById("asrToolFileMeta"),
  asrToolRetranscribeButton: document.getElementById("asrToolRetranscribeButton"),
  asrToolSearchInput: document.getElementById("asrToolSearchInput"),
  asrToolHistorySearchInput: document.getElementById("asrToolHistorySearchInput"),
  asrHistoryToggleButton: document.getElementById("asrHistoryToggleButton"),
  asrHistoryReopenButton: document.getElementById("asrHistoryReopenButton"),
  asrToolDownloadButton: document.getElementById("asrToolDownloadButton"),
  asrToolStatus: document.getElementById("asrToolStatus"),
  asrToolMeta: document.getElementById("asrToolMeta"),
  asrToolOutput: document.getElementById("asrToolOutput"),
  asrToolCleanButton: document.getElementById("asrToolCleanButton"),
  asrToolAnalysisModeControl: document.getElementById("asrToolAnalysisModeControl"),
  asrToolAnalysisModeButton: document.getElementById("asrToolAnalysisModeButton"),
  asrToolAnalysisHelpButton: document.getElementById("asrToolAnalysisHelpButton"),
  asrToolAnalysisModeLabel: document.getElementById("asrToolAnalysisModeLabel"),
  asrToolAnalysisModeMenu: document.getElementById("asrToolAnalysisModeMenu"),
  asrToolAnalysisModeDescription: document.getElementById("asrToolAnalysisModeDescription"),
  asrToolRunAnalysisButton: document.getElementById("asrToolRunAnalysisButton"),
  asrToolSummaryButton: document.getElementById("asrToolSummaryButton"),
  asrToolTasksButton: document.getElementById("asrToolTasksButton"),
  asrToolInsertPromptButton: document.getElementById("asrToolInsertPromptButton"),
  asrToolSendButton: document.getElementById("asrToolSendButton"),
  asrToolSaveContextButton: document.getElementById("asrToolSaveContextButton"),
  asrToolCopyButton: document.getElementById("asrToolCopyButton"),
  asrToolSaveButton: document.getElementById("asrToolSaveButton"),
  asrToolClearButton: document.getElementById("asrToolClearButton"),
  asrToolDeleteButton: document.getElementById("asrToolDeleteButton"),
  asrToolClearHistoryButton: document.getElementById("asrToolClearHistoryButton"),
  asrToolHistoryList: document.getElementById("asrToolHistoryList"),
  asrToolPipelinePanel: document.getElementById("asrToolPipelinePanel"),
  asrToolPipelineMeta: document.getElementById("asrToolPipelineMeta"),
  asrToolPipelineSteps: document.getElementById("asrToolPipelineSteps"),
  asrToolPipelineOutput: document.getElementById("asrToolPipelineOutput"),
  asrToolSpeakerPanel: document.getElementById("asrToolSpeakerPanel"),
  asrToolSpeakerEditor: document.getElementById("asrToolSpeakerEditor"),
  asrToolSaveSpeakersButton: document.getElementById("asrToolSaveSpeakersButton"),
  asrToolRegenerateSummaryButton: document.getElementById("asrToolRegenerateSummaryButton"),
  asrToolTasksOutput: document.getElementById("asrToolTasksOutput"),
  asrToolRolesButton: document.getElementById("asrToolRolesButton"),
  asrToolFullAnalysisButton: document.getElementById("asrToolFullAnalysisButton"),
  asrToolOpenAnalysisButton: document.getElementById("asrToolOpenAnalysisButton"),
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
  ttsHistoryToggleButton: document.getElementById("ttsHistoryToggleButton"),
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
  settingsTabList: document.getElementById("settingsTabList"),
  closeSettingsButton: document.getElementById("closeSettingsButton"),
  ragBackdrop: document.getElementById("ragBackdrop"),
  closeRagButton: document.getElementById("closeRagButton"),
  ragQuickMenu: document.getElementById("ragQuickMenu"),
  ragQuickEnabledToggle: document.getElementById("ragQuickEnabledToggle"),
  ragSourceDirValue: document.getElementById("ragSourceDirValue"),
  ragEnabledToggle: document.getElementById("ragEnabledToggle"),
  ragAddFilesButton: document.getElementById("ragAddFilesButton"),
  ragFileInput: document.getElementById("ragFileInput"),
  ragIngestButton: document.getElementById("ragIngestButton"),
  ragForceIngestButton: document.getElementById("ragForceIngestButton"),
  ragRefreshButton: document.getElementById("ragRefreshButton"),
  ragCopyPathButton: document.getElementById("ragCopyPathButton"),
  ragStatusText: document.getElementById("ragStatusText"),
  ragFileList: document.getElementById("ragFileList"),
  confirmBackdrop: document.getElementById("confirmBackdrop"),
  confirmEyebrow: document.getElementById("confirmEyebrow"),
  confirmTitle: document.getElementById("confirmTitle"),
  confirmMessage: document.getElementById("confirmMessage"),
  confirmCancelButton: document.getElementById("confirmCancelButton"),
  confirmDismissButton: document.getElementById("confirmDismissButton"),
  confirmApproveButton: document.getElementById("confirmApproveButton"),
  visionRagBackdrop: document.getElementById("visionRagBackdrop"),
  visionRagCloseButton: document.getElementById("visionRagCloseButton"),
  visionRagCancelButton: document.getElementById("visionRagCancelButton"),
  visionRagSaveButton: document.getElementById("visionRagSaveButton"),
  visionRagTitleInput: document.getElementById("visionRagTitleInput"),
  visionRagTextInput: document.getElementById("visionRagTextInput"),
  visionRagStatus: document.getElementById("visionRagStatus"),
  toastStack: document.getElementById("toastStack"),
  toastNotice: document.getElementById("toastNotice"),
  toastTitle: document.getElementById("toastTitle"),
  toastMessage: document.getElementById("toastMessage"),
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
  visionModelLibrary: document.getElementById("visionModelLibrary"),
  visionRuntimeSummary: document.getElementById("visionRuntimeSummary"),
  refreshVisionButton: document.getElementById("refreshVisionButton"),
  chatImagesEnabledToggle: document.getElementById("chatImagesEnabledToggle"),
  visionModelSelect: document.getElementById("visionModelSelect"),
  visionFallbackSelect: document.getElementById("visionFallbackSelect"),
  visionNumCtxInput: document.getElementById("visionNumCtxInput"),
  visionOcrAssistSelect: document.getElementById("visionOcrAssistSelect"),
  visionOcrLanguageInput: document.getElementById("visionOcrLanguageInput"),
  visionMaxImagesInput: document.getElementById("visionMaxImagesInput"),
  visionMaxFileMbInput: document.getElementById("visionMaxFileMbInput"),
  visionMaxTotalMbInput: document.getElementById("visionMaxTotalMbInput"),
  visionMaxMegapixelsInput: document.getElementById("visionMaxMegapixelsInput"),
  visionMaxSideInput: document.getElementById("visionMaxSideInput"),
  saveVisionSettingsButton: document.getElementById("saveVisionSettingsButton"),
  resetVisionSettingsButton: document.getElementById("resetVisionSettingsButton"),
  visionSettingsStatus: document.getElementById("visionSettingsStatus"),
  visionCacheSummary: document.getElementById("visionCacheSummary"),
  refreshVisionCacheButton: document.getElementById("refreshVisionCacheButton"),
  cleanupVisionOrphansButton: document.getElementById("cleanupVisionOrphansButton"),
  cleanupVisionCacheButton: document.getElementById("cleanupVisionCacheButton"),
  activeProfileSummary: document.getElementById("activeProfileSummary"),
  profileManagementSelect: document.getElementById("profileManagementSelect"),
  profileNameField: document.getElementById("profileNameField"),
  profileNameInput: document.getElementById("profileNameInput"),
  profileDescriptionInput: document.getElementById("profileDescriptionInput"),
  profileSystemPromptInput: document.getElementById("profileSystemPromptInput"),
  saveProfileSystemPromptButton: document.getElementById("saveProfileSystemPromptButton"),
  createProfileButton: document.getElementById("createProfileButton"),
  deleteProfileButton: document.getElementById("deleteProfileButton"),
  profileStatus: document.getElementById("profileStatus"),
  modelSettingsSummary: document.getElementById("modelSettingsSummary"),
  quickThinkingControl: document.getElementById("quickThinkingControl"),
  quickThinkingButton: document.getElementById("quickThinkingButton"),
  quickThinkingMenu: document.getElementById("quickThinkingMenu"),
  quickThinkingMobileControl: document.getElementById("quickThinkingMobileControl"),
  quickThinkingMobileButton: document.getElementById("quickThinkingMobileButton"),
  quickThinkingMobileMenu: document.getElementById("quickThinkingMobileMenu"),
  temperatureInput: document.getElementById("temperatureInput"),
  maxTokensInput: document.getElementById("maxTokensInput"),
  numCtxInput: document.getElementById("numCtxInput"),
  streamingEnabledToggle: document.getElementById("streamingEnabledToggle"),
  memTurnsInput: document.getElementById("memTurnsInput"),
  ollamaKeepAliveInput: document.getElementById("ollamaKeepAliveInput"),
  ollamaKeepAliveUnitSelect: document.getElementById("ollamaKeepAliveUnitSelect"),
  maxResidentTargetModelsSelect: document.getElementById("maxResidentTargetModelsSelect"),
  allowLightWithHeavyToggle: document.getElementById("allowLightWithHeavyToggle"),
  singleLargeTargetModelToggle: document.getElementById("singleLargeTargetModelToggle"),
  preloadManualSelectToggle: document.getElementById("preloadManualSelectToggle"),
  autoTargetKeepAliveInput: document.getElementById("autoTargetKeepAliveInput"),
  autoTargetKeepAliveUnitSelect: document.getElementById("autoTargetKeepAliveUnitSelect"),
  manualKeepAliveInput: document.getElementById("manualKeepAliveInput"),
  manualKeepAliveUnitSelect: document.getElementById("manualKeepAliveUnitSelect"),
  codeKeepAliveInput: document.getElementById("codeKeepAliveInput"),
  codeKeepAliveUnitSelect: document.getElementById("codeKeepAliveUnitSelect"),
  heavyKeepAliveInput: document.getElementById("heavyKeepAliveInput"),
  heavyKeepAliveUnitSelect: document.getElementById("heavyKeepAliveUnitSelect"),
  routerKeepAliveInput: document.getElementById("routerKeepAliveInput"),
  routerKeepAliveUnitSelect: document.getElementById("routerKeepAliveUnitSelect"),
  showRouterThinkingToggle: document.getElementById("showRouterThinkingToggle"),
  saveModelSettingsButton: document.getElementById("saveModelSettingsButton"),
  resetModelSettingsButton: document.getElementById("resetModelSettingsButton"),
  modelSettingsStatus: document.getElementById("modelSettingsStatus"),
  whisperModelSelect: document.getElementById("whisperModelSelect"),
  promptPresetSelect: document.getElementById("promptPresetSelect"),
  asrBeamSizeInput: document.getElementById("asrBeamSizeInput"),
  asrThreadsInput: document.getElementById("asrThreadsInput"),
  asrAnalysisPromptInput: document.getElementById("asrAnalysisPromptInput"),
  asrPipelineSettingsPanel: document.getElementById("asrPipelineSettingsPanel"),
  asrPipelineSettingsSummary: document.getElementById("asrPipelineSettingsSummary"),
  asrPipelineSettingsToggleButton: document.getElementById("asrPipelineSettingsToggleButton"),
  asrPipelineSettingsBody: document.getElementById("asrPipelineSettingsBody"),
  asrFullAnalysisEnabledToggle: document.getElementById("asrFullAnalysisEnabledToggle"),
  asrDiagnosticsEnabledToggle: document.getElementById("asrDiagnosticsEnabledToggle"),
  asrPipelineThinkSelect: document.getElementById("asrPipelineThinkSelect"),
  asrPipelineSettingsGrid: document.getElementById("asrPipelineSettingsGrid"),
  saveAsrPipelineSettingsButton: document.getElementById("saveAsrPipelineSettingsButton"),
  resetAsrPipelineSettingsButton: document.getElementById("resetAsrPipelineSettingsButton"),
  asrPipelineSettingsStatus: document.getElementById("asrPipelineSettingsStatus"),
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
  pluginsSummary: document.getElementById("pluginsSummary"),
  pluginsList: document.getElementById("pluginsList"),
  pluginsStatus: document.getElementById("pluginsStatus"),
  refreshPluginsButton: document.getElementById("refreshPluginsButton"),
  modelsDirInput: document.getElementById("modelsDirInput"),
  applyModelsDirButton: document.getElementById("applyModelsDirButton"),
  moveModelsDirButton: document.getElementById("moveModelsDirButton"),
  lanUrlValue: document.getElementById("lanUrlValue"),
  copyLanUrlFromSettingsButton: document.getElementById("copyLanUrlFromSettingsButton"),
  restartBackendButton: document.getElementById("restartBackendButton"),
  shutdownButton: document.getElementById("shutdownButton"),
  appRuntimeStatus: document.getElementById("appRuntimeStatus"),
  cleanupDatabaseButton: document.getElementById("cleanupDatabaseButton"),
  resetDatabaseButton: document.getElementById("resetDatabaseButton"),
  databaseStatus: document.getElementById("databaseStatus"),
  downloadList: document.getElementById("downloadList"),
  refreshModelTransferButton: document.getElementById("refreshModelTransferButton"),
  modelTransferList: document.getElementById("modelTransferList"),
  exportModelsButton: document.getElementById("exportModelsButton"),
  importModelsButton: document.getElementById("importModelsButton"),
  importModelsInput: document.getElementById("importModelsInput"),
  cancelModelTransferButton: document.getElementById("cancelModelTransferButton"),
  modelTransferStatus: document.getElementById("modelTransferStatus"),
};

const VOICE_RECORD_ICON = els.voiceRecordButton?.innerHTML || "";

const state = {
  profiles: [],
  activeProfileId: null,
  profileManagementMode: "edit",
  sessions: [],
  currentSessionId: null,
  sessionContextMenuSessionId: null,
  asrHistoryContextMenuTranscriptId: null,
  messages: [],
  messageAttachments: {},
  visionRagSourceMessageId: null,
  installedModels: [],
  recommendedModels: [],
  visionModels: [],
  utilityModels: [],
  downloads: [],
  modelDiagnostics: null,
  chatModelsError: null,
  visionCache: null,
  visionCacheBusy: false,
  selectedLlmModel: "",
  selectedChatWhisperModel: "medium",
  selectedWhisperModel: ASR_STUDIO_DEFAULT_MODEL,
  selectedPromptPreset: ASR_STUDIO_DEFAULT_PROMPT_PRESET,
  selectedAsrBeamSize: ASR_DEFAULT_BEAM_SIZE,
  selectedAsrThreads: ASR_DEFAULT_THREADS,
  selectedTtsProvider: "piper",
  selectedTtsVoiceId: "",
  selectedTtsSpeed: "1",
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
  chatTaskEventSource: null,
  chatTaskStreamAbort: null,
  chatTaskReplay: null,
  chatTypingStreams: new Map(),
  chatAttachments: [],
  isSpeaking: false,
  autoScrollPinned: true,
  messageScrollEndObserver: null,
  theme: "dark",
  sidebarOpen: readStored(STORAGE_KEYS.sidebarOpen, "true") !== "false",
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
  asrPipelineSettingsExpanded: readStored(STORAGE_KEYS.asrPipelineSettingsOpen, "") === "1",
  voiceModelMenuPosition: null,
  ragQuickMenuPosition: null,
  confirmResolver: null,
  confirmReturnFocus: null,
  toastTimer: null,
  lastToastKey: "",
  lastToastAt: 0,
  chatDropDepth: 0,
  asrToolDropDepth: 0,
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
  asrToolPipelineRun: null,
  asrToolPipelineBusy: false,
  asrToolPipelineAction: "",
  asrToolPipelinePreset: "",
  asrToolStopping: false,
  asrToolAnalysisMode: readStored(STORAGE_KEYS.asrAnalysisMode, ASR_ANALYSIS_MODE_DEFAULT),
  asrToolAnalysisModeMenuOpen: false,
  asrToolActiveTab: "text",
  asrToolTextSearch: "",
  asrToolHistorySearch: "",
  asrHistoryCollapsed: readStored(STORAGE_KEYS.asrHistoryCollapsed, "") === "1",
  ttsHistoryCollapsed: readStored(STORAGE_KEYS.ttsHistoryCollapsed, "1") === "1",
  ragStatus: null,
  ragBusy: false,
  pluginsState: {
    plugins: [],
    invalid_plugins: [],
    trusted_plugin_ids: [],
    message: "",
  },
  pluginsLoading: false,
  networkAddresses: [],
  networkAddressesLoading: false,
  networkAddressMenuPosition: null,
  activeSettingsTab: readStored(STORAGE_KEYS.settingsTab, "profile") || "profile",
  databaseMaintenanceBusy: false,
  appRuntimeBusy: false,
  modelTransferModels: [],
  modelTransferTaskId: null,
  modelTransferBusy: false,
  asrToolIsOpen: false,
  asrToolIsMinimized: false,
  asrToolBounds: null,
  asrToolDragSession: null,
  asrToolResizeSession: null,
  asrToolTaskId: null,
  asrToolStartController: null,
  asrToolPipelineController: null,
  asrToolIsTranscribing: false,
  asrToolLastFile: null,
  ttsToolSelectedRecordId: null,
  ttsToolSelectedRecord: null,
  ttsToolIsOpen: false,
  ttsToolIsMinimized: false,
  ttsToolBounds: null,
  ttsToolDragSession: null,
  ttsToolResizeSession: null,
  renderedCodeBlocks: [],
  appSelects: new Map(),
  appSelectSyncFrame: null,
  modelSettingsState: {
    effective: {},
    overrides: {},
    defaults: {},
  },
  asrPipelineSettingsState: {
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

function getModelId(item) {
  return String(item?.id || item?.name || "").trim();
}

function getModelTitle(item) {
  const id = getModelId(item);
  return String(item?.title || item?.label || id).trim();
}

function getModelDescription(item) {
  return String(item?.description || "").trim();
}

function getCatalogModels() {
  return (Array.isArray(state.recommendedModels) ? state.recommendedModels : [])
    .filter((item) => getModelId(item));
}

function getUtilityModels() {
  return (Array.isArray(state.utilityModels) ? state.utilityModels : [])
    .filter((item) => getModelId(item));
}

function getCatalogItemById(modelName) {
  const target = String(modelName || "").trim();
  return [...getCatalogModels(), ...getUtilityModels()].find((item) => getModelId(item) === target) || null;
}

function modelSupportsThinking(modelName) {
  const target = String(modelName || "").trim();
  if (!target) return false;
  if (target === AUTO_MODEL_ID) return true;
  const item = getCatalogItemById(target);
  const category = String(item?.category || "").toLowerCase();
  const description = String(item?.description || "").toLowerCase();
  if (category.includes("thinking") || description.includes("thinking") || description.includes("reasoning")) {
    return true;
  }
  return THINKING_MODEL_PATTERNS.some((pattern) => pattern.test(target));
}

function shouldShowThinkingToggleForModel(modelName) {
  const target = String(modelName || "").trim();
  if (!modelSupportsThinking(target)) return false;
  if (target !== AUTO_MODEL_ID) return true;
  const settings = getActiveProfilePreferences()?.settings || {};
  return Boolean(settings.show_router_thinking_toggle);
}

function normalizeOllamaThink(value, fallback = "auto") {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (normalized === "auto") return "auto";
  if (["on", "true", "1", "yes", "think"].includes(normalized)) return "on";
  if (["off", "false", "0", "no", "nothink"].includes(normalized)) return "off";
  return fallback;
}

function isRuntimeModelInstalled(item, installedByName = null) {
  const id = getModelId(item);
  return Boolean(item?.runtime_installed || item?.installed || (installedByName && installedByName.has(id)));
}

function getRuntimeModelState(item, installedByName = null) {
  const id = getModelId(item);
  const installed = isRuntimeModelInstalled(item, installedByName);
  if (item?.downloading) return "downloading";
  if (item?.active) return "active";
  if (installed) return "installed";
  if (item?.partial) return "partial";
  if (item?.configured) return "configured";
  return "missing";
}

function getRuntimeModelStatusLabel(item, installedByName = null) {
  const stateName = getRuntimeModelState(item, installedByName);
  return item?.status_label || {
    active: "Активна",
    installed: "Установлена",
    downloading: "Загружается",
    partial: "Недокачана",
    configured: "Не установлена",
    missing: "Отсутствует",
  }[stateName] || stateName;
}

function getModelActionLabel(item, installedByName = null) {
  if (isRuntimeModelInstalled(item, installedByName)) return "Выбрать";
  if (item?.partial) return "Продолжить загрузку";
  return "Скачать / докачать";
}

function getModelRuntimeNote(item, task = null, installedByName = null) {
  if (task?.message) return task.message;
  if (item?.active) return "Модель загружена в память Ollama и готова отвечать.";
  if (isRuntimeModelInstalled(item, installedByName)) {
    return item?.partial_blob_found
      ? "Модель зарегистрирована в project-scoped Ollama runtime; отдельно найден partial blob в одном из storage."
      : "Модель зарегистрирована в текущем Ollama runtime.";
  }
  if (item?.partial) return "Найден partial blob: загрузку нужно продолжить, пока модель не появится в ollama list.";
  if (item?.storage?.storage_present) {
    return "Файлы модели найдены в model storage, но текущий Ollama runtime не видит её через ollama list.";
  }
  return getModelDescription(item) || "Модель есть в каталоге, но отсутствует в текущем Ollama runtime.";
}

function getModelTooltip(item, { short = false } = {}) {
  const id = getModelId(item);
  const title = getModelTitle(item);
  const description = getModelDescription(item);
  if (short) {
    return description || `${item?.category || "model"} • ${item?.weight || "unknown"}`;
  }
  return [
    title,
    `ID: ${id}`,
    `Категория: ${item?.category || "-"}`,
    `Вес: ${item?.weight || "-"}`,
    `Рекомендована: ${item?.recommended ? "да" : "нет"}`,
    `Экспериментальная: ${item?.experimental ? "да" : "нет"}`,
    description,
  ].filter(Boolean).join("\n");
}

function getModelBadges(item) {
  const category = String(item?.category || "");
  const weight = String(item?.weight || "");
  const badges = [];
  if (item?.recommended) {
    badges.push({ label: "recommended", tone: "recommended" });
  }
  if (item?.experimental) {
    badges.push({ label: "experimental", tone: "experimental" });
  }
  if (item?.utility) {
    badges.push({ label: "utility", tone: "utility" });
  }
  if (weight === "heavy") {
    badges.push({ label: "heavy", tone: "heavy" });
  }
  if (category.includes("router")) {
    badges.push({ label: "router", tone: "router" });
  }
  if (category.includes("code")) {
    badges.push({ label: "code", tone: "code" });
  }
  return badges;
}

function renderModelBadges(item) {
  return getModelBadges(item)
    .map((badge) => `<span class="status-badge status-badge--${escapeHtml(badge.tone)}">${escapeHtml(badge.label)}</span>`)
    .join("");
}

function renderModelInfoIcon(item, className = "model-info-button") {
  const tooltip = getModelTooltip(item);
  return `<span class="${escapeHtml(className)}" role="img" aria-label="${escapeHtml(tooltip)}" data-tooltip="${escapeHtml(tooltip)}" data-model-help>?</span>`;
}

function renderModelInfoButton(item) {
  const tooltip = getModelTooltip(item);
  return `<button class="model-info-button" type="button" aria-label="${escapeHtml(tooltip)}" data-tooltip="${escapeHtml(tooltip)}" data-model-help>?</button>`;
}

let tooltipTimer = null;
let activeTooltipTarget = null;

function getTooltipNode() {
  let node = document.getElementById("appTooltip");
  if (!node) {
    node = document.createElement("div");
    node.id = "appTooltip";
    node.className = "app-tooltip";
    node.hidden = true;
    document.body.appendChild(node);
  }
  return node;
}

function clearTooltipTimer() {
  if (tooltipTimer) {
    window.clearTimeout(tooltipTimer);
    tooltipTimer = null;
  }
}

function positionTooltip(node, target) {
  const rect = target.getBoundingClientRect();
  const gap = 10;
  const margin = 10;
  const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
  const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
  const maxWidth = Math.min(340, Math.max(180, viewportWidth - margin * 2));
  node.style.maxWidth = `${maxWidth}px`;

  const tooltipRect = node.getBoundingClientRect();
  let left = rect.right + gap;
  let top = rect.top + rect.height / 2 - tooltipRect.height / 2;

  if (left + tooltipRect.width > viewportWidth - margin) {
    left = rect.left - tooltipRect.width - gap;
  }
  if (left < margin) {
    left = Math.min(viewportWidth - tooltipRect.width - margin, Math.max(margin, rect.left));
  }

  top = Math.max(margin, Math.min(top, viewportHeight - tooltipRect.height - margin));
  node.style.left = `${Math.round(left)}px`;
  node.style.top = `${Math.round(top)}px`;
}

function showTooltip(target) {
  const text = target?.dataset?.tooltip || "";
  if (!text) return;
  const node = getTooltipNode();
  node.textContent = text;
  node.hidden = false;
  node.classList.remove("app-tooltip--visible");
  positionTooltip(node, target);
  window.requestAnimationFrame(() => {
    node.classList.add("app-tooltip--visible");
  });
}

function scheduleTooltip(target) {
  clearTooltipTimer();
  activeTooltipTarget = target;
  tooltipTimer = window.setTimeout(() => {
    if (activeTooltipTarget === target) {
      showTooltip(target);
    }
  }, 250);
}

function hideTooltip() {
  clearTooltipTimer();
  activeTooltipTarget = null;
  const node = document.getElementById("appTooltip");
  if (!node) return;
  node.classList.remove("app-tooltip--visible");
  node.hidden = true;
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
  return formatMarkdownMessage(value, { registerCodeBlock: registerRenderedCodeBlock });
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

function normalizeTextForSpeech(value) {
  return String(value || "")
    .replace(/\r\n?/g, "\n")
    .replace(/```[a-zA-Z0-9_-]*\n?([\s\S]*?)```/g, "$1")
    .replace(/`([^`\n]+)`/g, "$1")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/^\s*>\s?/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, "$1")
    .replace(/\*\*([^*\n](?:[\s\S]*?[^*\n])?)\*\*/g, "$1")
    .replace(/__([^_\n](?:[\s\S]*?[^_\n])?)__/g, "$1")
    .replace(/(^|[\s(])[*_]([^*_\n]+)[*_](?=[\s).,!?:;]|$)/g, "$1$2")
    .replace(/<[^>]+>/g, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
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
  const installedChatNames = new Set(state.installedModels.map((item) => item.name));
  const chatCatalog = getCatalogModels();
  const utilityCatalog = getUtilityModels();
  const chatInstalled = [...utilityCatalog, ...chatCatalog].filter((item) => installedChatNames.has(getModelId(item))).length;
  const chatTotal = utilityCatalog.length + chatCatalog.length;
  const ollamaHost = state.modelDiagnostics?.ollama_host || state.modelDiagnostics?.base_url || "";
  const chatRuntimeLabel = ollamaHost ? ` • ${ollamaHost}` : "";
  const asrInstalled = state.asrModels.filter((item) => isWhisperItemReady(item)).length;
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
      metaText: `${chatInstalled} runtime • ${chatTotal} вариантов${chatRuntimeLabel}`,
    },
    {
      kind: "asr",
      open: state.libraryPanels.asr,
      toggle: els.asrLibraryToggle,
      panel: els.asrLibraryPanel,
      meta: els.asrLibraryMeta,
      metaText: `${asrInstalled} готово • ${asrTotal} моделей`,
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

function isActiveDownloadState(stateValue) {
  return ACTIVE_DOWNLOAD_STATES.has(String(stateValue || "").trim());
}

function getActiveChatDownload(modelName = "") {
  const target = String(modelName || "").trim();
  return (state.downloads || []).find((item) => (
    isActiveDownloadState(item.state) && (!target || item.model === target)
  )) || null;
}

function hasActiveDownload(modelName) {
  return Boolean(getActiveChatDownload(modelName));
}

function isMobileLayout() {
  return window.matchMedia(MOBILE_LAYOUT_QUERY).matches;
}

function isOverlayOpen(node) {
  return Boolean(node && node.hidden === false);
}

function syncMobileScrollLock() {
  const drawerOpen = els.sidebar?.classList.contains("sidebar--open") === true;
  const modalOpen = [
    els.settingsBackdrop,
    els.ocrBackdrop,
    els.ragBackdrop,
    els.confirmBackdrop,
    els.visionRagBackdrop,
  ].some(isOverlayOpen);
  const toolOpen = [
    els.asrToolWindow,
    els.ttsToolWindow,
  ].some(isOverlayOpen);
  document.body.classList.toggle("mobile-scroll-locked", isMobileLayout() && (drawerOpen || modalOpen || toolOpen));
}

function syncMessageScrollState() {
  if (!els.messageScroll) return;
  const remaining = els.messageScroll.scrollHeight - els.messageScroll.scrollTop - els.messageScroll.clientHeight;
  state.autoScrollPinned = remaining <= 96;
  if (els.scrollTopButton) {
    els.scrollTopButton.hidden = remaining <= 24;
  }
}

function observeMessageScrollEnd() {
  if (!els.messageScroll || !els.messageScrollEnd || !els.scrollTopButton) return;
  state.messageScrollEndObserver?.disconnect();
  state.messageScrollEndObserver = new IntersectionObserver(([entry]) => {
    const hasOverflow = els.messageScroll.scrollHeight > els.messageScroll.clientHeight + 1;
    const remaining = els.messageScroll.scrollHeight - els.messageScroll.scrollTop - els.messageScroll.clientHeight;
    els.scrollTopButton.hidden = !hasOverflow || (entry.isIntersecting && remaining <= 24) || remaining <= 24;
  }, {
    root: els.messageScroll,
    threshold: 0,
  });
  state.messageScrollEndObserver.observe(els.messageScrollEnd);
}

function scrollMessagesToBottom({ force = false } = {}) {
  if (!els.messageScroll) return;
  if (!force && !state.autoScrollPinned) return;
  requestAnimationFrame(() => {
    els.messageScroll?.scrollTo({ top: els.messageScroll.scrollHeight, behavior: "smooth" });
    syncMessageScrollState();
  });
}

function applySidebarOpenState() {
  const open = state.sidebarOpen !== false;
  document.querySelector(".app-shell")?.classList.toggle("app-shell--sidebar-closed", !open);
  els.toggleSidebarButton?.setAttribute("aria-expanded", els.sidebar?.classList.contains("sidebar--open") ? "true" : "false");
  if (els.sidebarCollapseButton) {
    els.sidebarCollapseButton.setAttribute("aria-expanded", open ? "true" : "false");
    els.sidebarCollapseButton.setAttribute("aria-label", open ? "Свернуть sidebar" : "Развернуть sidebar");
    const icon = els.sidebarCollapseButton.querySelector("span");
    if (icon) {
      icon.textContent = open ? "‹" : "›";
    }
  }
}

function setSidebarOpen(open) {
  state.sidebarOpen = Boolean(open);
  writeStored(STORAGE_KEYS.sidebarOpen, state.sidebarOpen ? "true" : "false");
  applySidebarOpenState();
}

function toggleSidebarCollapse() {
  setSidebarOpen(!state.sidebarOpen);
}

function applyAsrHistoryCollapsedState() {
  const collapsed = Boolean(state.asrHistoryCollapsed);
  const mobile = isMobileLayout();
  els.asrLayoutGrid?.classList.toggle("asr-layout-grid--history-collapsed", collapsed);
  if (els.asrHistoryReopenButton) {
    els.asrHistoryReopenButton.hidden = mobile || !collapsed;
  }
  if (!els.asrHistoryToggleButton) return;
  if (mobile) {
    els.asrHistoryToggleButton.setAttribute("aria-expanded", collapsed ? "false" : "true");
    els.asrHistoryToggleButton.setAttribute(
      "aria-label",
      collapsed ? "Показать базу транскрибаций" : "Скрыть базу транскрибаций",
    );
    els.asrHistoryToggleButton.title = collapsed ? "Показать базу транскрибаций" : "Скрыть базу транскрибаций";
    els.asrHistoryToggleButton.textContent = collapsed ? "More" : "Less";
    return;
  }
  els.asrHistoryToggleButton.setAttribute("aria-expanded", collapsed ? "false" : "true");
  els.asrHistoryToggleButton.setAttribute(
    "aria-label",
    collapsed ? "Развернуть базу транскрибаций" : "Свернуть базу транскрибаций",
  );
  els.asrHistoryToggleButton.title = collapsed ? "Развернуть базу транскрибаций" : "Свернуть базу транскрибаций";
  els.asrHistoryToggleButton.textContent = collapsed ? "▶" : "◀";
}

function setAsrHistoryCollapsed(collapsed) {
  state.asrHistoryCollapsed = Boolean(collapsed);
  writeStored(STORAGE_KEYS.asrHistoryCollapsed, state.asrHistoryCollapsed ? "1" : "");
  applyAsrHistoryCollapsedState();
}

function applyTtsHistoryCollapsedState() {
  const collapsed = Boolean(state.ttsHistoryCollapsed);
  const mobile = isMobileLayout();
  els.ttsToolWindow?.classList.toggle("tts-history-collapsed", mobile && collapsed);
  if (!els.ttsHistoryToggleButton) return;
  els.ttsHistoryToggleButton.setAttribute("aria-expanded", collapsed ? "false" : "true");
  els.ttsHistoryToggleButton.setAttribute(
    "aria-label",
    collapsed ? "Показать историю озвучки" : "Скрыть историю озвучки",
  );
  els.ttsHistoryToggleButton.title = collapsed ? "Показать историю озвучки" : "Скрыть историю озвучки";
  els.ttsHistoryToggleButton.textContent = collapsed ? "More" : "Less";
}

function setTtsHistoryCollapsed(collapsed) {
  state.ttsHistoryCollapsed = Boolean(collapsed);
  writeStored(STORAGE_KEYS.ttsHistoryCollapsed, state.ttsHistoryCollapsed ? "1" : "");
  applyTtsHistoryCollapsedState();
}

function normalizeTheme(value) {
  return value === "light" ? "light" : "dark";
}

function renderThemeToggle() {
  if (!els.themeToggleButton) return;
  const isLight = state.theme === "light";
  els.themeToggleButton.classList.toggle("theme-toggle-button--light", isLight);
  els.themeToggleButton.classList.toggle("theme-toggle-button--dark", !isLight);
  els.themeToggleButton.setAttribute("aria-pressed", isLight ? "true" : "false");
  els.themeToggleButton.setAttribute("aria-label", isLight ? "Включить тёмную тему" : "Включить светлую тему");
  els.themeToggleButton.title = isLight ? "Светлая тема включена" : "Тёмная тема включена";
}

function applyTheme(theme, { persist = true } = {}) {
  state.theme = normalizeTheme(theme);
  document.body.classList.toggle("theme-light", state.theme === "light");
  document.body.classList.toggle("theme-dark", state.theme !== "light");
  document.documentElement.style.colorScheme = state.theme === "light" ? "light" : "dark";
  if (persist) {
    writeStored(STORAGE_KEYS.theme, state.theme);
  }
  renderThemeToggle();
}

function initTheme() {
  applyTheme(readStored(STORAGE_KEYS.theme, "dark"), { persist: false });
}

function toggleTheme() {
  applyTheme(state.theme === "light" ? "dark" : "light");
}

function isTypingTarget(target) {
  if (!(target instanceof Element)) return false;
  return Boolean(target.closest("input, textarea, select, [contenteditable='true']"));
}

function toggleComposerMenu(forceState) {
  if (!els.composerMenu || !els.composerMenuButton) return;
  const nextState = typeof forceState === "boolean"
    ? forceState
    : els.composerMenu.hidden;
  els.composerMenu.hidden = !nextState;
  els.composerMenuButton.setAttribute("aria-expanded", nextState ? "true" : "false");
}

function appSelectLabel(select) {
  const selected = select?.selectedOptions?.[0];
  return selected?.textContent?.trim() || select?.options?.[0]?.textContent?.trim() || "Не выбрано";
}

function closeAppSelect(select = null) {
  const targets = select ? [select] : Array.from(state.appSelects.keys());
  targets.forEach((item) => {
    const entry = state.appSelects.get(item);
    if (!entry) return;
    entry.wrapper.classList.remove("app-select--open");
    entry.button.setAttribute("aria-expanded", "false");
    entry.menu.hidden = true;
  });
  hideTooltip();
}

function syncAppSelect(select) {
  const entry = state.appSelects.get(select);
  if (!entry) return;
  const disabled = Boolean(select.disabled);
  const selectedValue = String(select.value || "");
  entry.button.disabled = disabled;
  entry.button.setAttribute("aria-disabled", disabled ? "true" : "false");
  entry.value.textContent = appSelectLabel(select);
  entry.menu.innerHTML = Array.from(select.options || [])
    .filter((option) => !option.hidden)
    .map((option) => {
      const active = String(option.value) === selectedValue ? " app-select__option--active" : "";
      const help = option.dataset.help || "";
      const title = option.dataset.label || option.textContent || option.value;
      const helpMarkup = help
        ? `<span class="app-select__help" role="img" aria-label="${escapeHtml(help)}" data-tooltip="${escapeHtml(help)}" data-app-select-help>?</span>`
        : "";
      return `<button class="app-select__option${active}" type="button" role="option" aria-selected="${active ? "true" : "false"}" data-app-select-value="${escapeHtml(option.value)}"><span class="app-select__option-label">${escapeHtml(title)}</span>${helpMarkup}</button>`;
    })
    .join("");
}

function syncAllAppSelects() {
  state.appSelects.forEach((_, select) => syncAppSelect(select));
}

function queueSyncAppSelects() {
  if (state.appSelectSyncFrame) return;
  state.appSelectSyncFrame = window.requestAnimationFrame(() => {
    state.appSelectSyncFrame = null;
    syncAllAppSelects();
  });
}

function enhanceAppSelect(select) {
  if (!select || state.appSelects.has(select) || select.hidden) {
    return;
  }

  select.classList.add("app-select__native");
  select.setAttribute("aria-hidden", "true");
  select.tabIndex = -1;

  const wrapper = document.createElement("div");
  wrapper.className = "app-select";
  wrapper.dataset.appSelectFor = select.id || "";

  const button = document.createElement("button");
  button.className = "app-select__button";
  button.type = "button";
  button.setAttribute("aria-haspopup", "listbox");
  button.setAttribute("aria-expanded", "false");
  const labelText = select.closest(".field")?.querySelector(".field__label")?.textContent?.trim();
  if (labelText) {
    button.setAttribute("aria-label", labelText);
  }

  const value = document.createElement("span");
  value.className = "app-select__value";

  const caret = document.createElement("span");
  caret.className = "app-select__caret";
  caret.setAttribute("aria-hidden", "true");

  const menu = document.createElement("div");
  menu.className = "app-select__menu";
  menu.hidden = true;
  menu.setAttribute("role", "listbox");

  button.append(value, caret);
  wrapper.append(button, menu);
  select.insertAdjacentElement("afterend", wrapper);

  const observer = new MutationObserver(() => syncAppSelect(select));
  observer.observe(select, { attributes: true, childList: true, subtree: true, attributeFilter: ["disabled"] });

  state.appSelects.set(select, { wrapper, button, value, menu, observer });
  syncAppSelect(select);

  button.addEventListener("click", (event) => {
    event.stopPropagation();
    if (select.disabled) return;
    const willOpen = menu.hidden;
    closeAppSelect();
    wrapper.classList.toggle("app-select--open", willOpen);
    button.setAttribute("aria-expanded", willOpen ? "true" : "false");
    menu.hidden = !willOpen;
  });

  menu.addEventListener("click", (event) => {
    event.stopPropagation();
    if (event.target instanceof Element && event.target.closest("[data-app-select-help]")) {
      return;
    }
    const optionButton = event.target instanceof Element
      ? event.target.closest("[data-app-select-value]")
      : null;
    if (!optionButton) return;
    select.value = optionButton.dataset.appSelectValue || "";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    closeAppSelect(select);
    syncAppSelect(select);
  });
}

function initAppSelects() {
  document.querySelectorAll("select.field__control, select.quick-model-switch__control").forEach((select) => enhanceAppSelect(select));
  queueSyncAppSelects();
}

function getChatModelItems() {
  const installedByName = new Map(state.installedModels.map((item) => [item.name, item]));
  const catalog = getCatalogModels();
  const source = catalog.length
    ? catalog
    : state.installedModels.map((item) => ({ id: item.name, title: item.name, recommended: false }));
  const autoItem = {
    id: AUTO_MODEL_ID,
    name: AUTO_MODEL_ID,
    title: AUTO_MODEL_TITLE,
    category: "auto_router",
    weight: "utility",
    description: AUTO_MODEL_HELP,
    installed: null,
    recommended: null,
    task: null,
  };
  const calculatorItem = {
    id: LOCAL_CALCULATOR_MODEL_ID,
    name: LOCAL_CALCULATOR_MODEL_ID,
    title: LOCAL_CALCULATOR_TITLE,
    category: "local_calculator",
    weight: "utility",
    description: LOCAL_CALCULATOR_HELP,
    installed: null,
    recommended: null,
    task: null,
  };
  return [autoItem, calculatorItem, ...source.map((model) => {
    const name = getModelId(model);
    return {
      ...model,
      name,
      title: getModelTitle(model),
      installed: installedByName.get(name) || null,
      recommended: model,
      task: getActiveChatDownload(name),
    };
  })];
}

function describeChatModelItem(item) {
  if (item?.name === AUTO_MODEL_ID || getModelId(item) === AUTO_MODEL_ID) {
    return "router • qwen3:0.6b";
  }
  if (item?.name === LOCAL_CALCULATOR_MODEL_ID || getModelId(item) === LOCAL_CALCULATOR_MODEL_ID) {
    return "локальный расчёт • без LLM";
  }
  if (!item) {
    return "Загрузите модель в настройках";
  }
  if (item.task) {
    return item.task.message || `Загрузка • ${item.task.state || "running"}`;
  }
  if (item.installed) {
    const parts = ["Локальная модель"];
    if (item.installed.size_gb) {
      parts.push(`${item.installed.size_gb} GB`);
    }
    return parts.join(" • ");
  }
  if (item.recommended) {
    return `${item.recommended.category || "catalog"} • ${item.recommended.weight || "weight"} • не загружена`;
  }
  return "Не загружена";
}

function closeQuickModelMenu() {
  [
    { menu: els.quickModelMenu, button: els.quickModelButton },
    { menu: els.quickModelMobileMenu, button: els.quickModelMobileButton },
  ].forEach(({ menu, button }) => {
    if (menu) menu.hidden = true;
    if (button) button.setAttribute("aria-expanded", "false");
  });
  if (els.quickModelMobileMenu) {
    els.quickModelMobileMenu.style.position = "";
    els.quickModelMobileMenu.style.left = "";
    els.quickModelMobileMenu.style.right = "";
    els.quickModelMobileMenu.style.top = "";
    els.quickModelMobileMenu.style.transform = "";
    els.quickModelMobileMenu.style.visibility = "";
    els.quickModelMobileMenu.style.maxHeight = "";
    els.quickModelMobileMenu.style.maxWidth = "";
    els.quickModelMobileMenu.style.width = "";
  }
}

function syncQuickModelMobileMenuBounds() {
  if (!els.quickModelMobileMenu || !els.quickModelMobileButton) return;
  const viewportHeight = window.visualViewport?.height || window.innerHeight || 0;
  const viewportWidth = window.visualViewport?.width || window.innerWidth || 0;
  const viewportOffsetTop = window.visualViewport?.offsetTop || 0;
  const viewportOffsetLeft = window.visualViewport?.offsetLeft || 0;
  const buttonRect = els.quickModelMobileButton.getBoundingClientRect();
  const screenPadding = 12;
  const menuOffset = 8;
  const minMenuHeight = 160;
  const availableHeight = Math.floor(viewportOffsetTop + viewportHeight - buttonRect.bottom - menuOffset - screenPadding);
  const boundedHeight = Math.max(minMenuHeight, availableHeight);
  const maxWidth = Math.max(220, Math.floor(viewportWidth - screenPadding * 2));
  const minLeft = viewportOffsetLeft + screenPadding;
  const maxLeft = viewportOffsetLeft + viewportWidth - screenPadding;
  const buttonCenterX = buttonRect.left + (buttonRect.width / 2);
  els.quickModelMobileMenu.style.position = "fixed";
  els.quickModelMobileMenu.style.top = `${Math.round(buttonRect.bottom + menuOffset)}px`;
  els.quickModelMobileMenu.style.right = "auto";
  els.quickModelMobileMenu.style.left = `${Math.round(buttonCenterX)}px`;
  els.quickModelMobileMenu.style.transform = "translateX(-50%)";
  els.quickModelMobileMenu.style.width = "max-content";
  els.quickModelMobileMenu.style.maxWidth = `${maxWidth}px`;
  els.quickModelMobileMenu.style.maxHeight = `${boundedHeight}px`;
  els.quickModelMobileMenu.style.visibility = "hidden";
  const menuRect = els.quickModelMobileMenu.getBoundingClientRect();
  const menuWidth = Math.min(menuRect.width || maxWidth, maxWidth);
  let centeredX = buttonCenterX;
  centeredX = Math.min(centeredX, maxLeft - (menuWidth / 2));
  centeredX = Math.max(centeredX, minLeft + (menuWidth / 2));
  els.quickModelMobileMenu.style.left = `${Math.round(centeredX)}px`;
  els.quickModelMobileMenu.style.visibility = "visible";
}

function toggleQuickModelMenu(forceState, source = "desktop") {
  const target = source === "mobile"
    ? { menu: els.quickModelMobileMenu, button: els.quickModelMobileButton }
    : { menu: els.quickModelMenu, button: els.quickModelButton };
  if (!target.menu || !target.button) return;
  if (target.button.disabled) return;
  const nextState = typeof forceState === "boolean"
    ? forceState
    : target.menu.hidden;
  closeQuickModelMenu();
  target.menu.hidden = !nextState;
  target.button.setAttribute("aria-expanded", nextState ? "true" : "false");
  if (source === "mobile" && nextState) {
    syncQuickModelMobileMenuBounds();
    requestAnimationFrame(syncQuickModelMobileMenuBounds);
  }
}

function closeQuickThinkingMenu() {
  [
    { menu: els.quickThinkingMenu, button: els.quickThinkingButton },
    { menu: els.quickThinkingMobileMenu, button: els.quickThinkingMobileButton },
  ].forEach(({ menu, button }) => {
    if (menu) menu.hidden = true;
    if (button) button.setAttribute("aria-expanded", "false");
  });
}

function toggleQuickThinkingMenu(forceState, source = "desktop") {
  const target = source === "mobile"
    ? { menu: els.quickThinkingMobileMenu, button: els.quickThinkingMobileButton }
    : { menu: els.quickThinkingMenu, button: els.quickThinkingButton };
  if (!target.menu || !target.button) return;
  if (target.button.disabled) return;
  const nextState = typeof forceState === "boolean"
    ? forceState
    : target.menu.hidden;
  closeQuickThinkingMenu();
  target.menu.hidden = !nextState;
  target.button.setAttribute("aria-expanded", nextState ? "true" : "false");
}

function renderQuickModelPicker() {
  const items = getChatModelItems();
  const selectedName = state.selectedLlmModel || "";
  const selectedItem = items.find((item) => item.name === selectedName) || items[0] || null;
  const hasDesktopPicker = Boolean(els.quickModelButton && els.quickModelValue && els.quickModelMeta && els.quickModelMenu);
  const hasMobilePicker = Boolean(els.quickModelMobileButton && els.quickModelMobileMenu);
  if (!hasDesktopPicker && !hasMobilePicker) return;

  if (els.quickModelButton) {
    els.quickModelButton.disabled = !items.length;
  }
  if (els.quickModelMobileButton) {
    els.quickModelMobileButton.disabled = !items.length;
  }
  if (els.quickModelMobileControl) {
    els.quickModelMobileControl.hidden = false;
  }
  if (!items.length) {
    closeQuickModelMenu();
  }
  if (els.quickModelValue) {
    els.quickModelValue.textContent = selectedItem?.name || "Нет доступных моделей";
  }
  if (els.quickModelMeta) {
    els.quickModelMeta.textContent = selectedItem ? describeChatModelItem(selectedItem) : "Загрузите модель в настройках";
  }

  const thinkingValue = normalizeOllamaThink(
    els.quickThinkingControl?.dataset.thinkingMode ?? state.modelSettingsState?.effective?.ollama_think,
    "auto",
  );
  const thinkingOn = thinkingValue !== "off";
  const menuHtml = items.map((item) => {
    const active = item.name === selectedName;
    const thinkingSupported = shouldShowThinkingToggleForModel(item.name);
    const itemThinkingOn = active ? thinkingOn : false;
    return `
      <div class="quick-model-picker__item-shell${active ? " quick-model-picker__item-shell--active" : ""}">
        <button
          class="quick-model-picker__item${active ? " quick-model-picker__item--active" : ""}"
          type="button"
          role="menuitemradio"
          aria-checked="${active ? "true" : "false"}"
          data-quick-model="${escapeHtml(item.name)}"
        >
          <span class="quick-model-picker__item-name">${escapeHtml(item.title || item.name)}</span>
        </button>
        ${thinkingSupported ? `
          <label class="apple-switch quick-model-picker__thinking-toggle" title="Thinking">
            <input type="checkbox" data-quick-thinking-toggle data-quick-thinking-model="${escapeHtml(item.name)}" ${itemThinkingOn ? "checked" : ""} />
            <span class="apple-switch__track" aria-hidden="true"></span>
          </label>
        ` : ""}
      </div>
    `;
  }).join("");
  if (els.quickModelMenu) {
    els.quickModelMenu.innerHTML = menuHtml;
  }
  if (els.quickModelMobileMenu) {
    els.quickModelMobileMenu.innerHTML = menuHtml;
  }
}

function getWhisperItems() {
  return state.asrModels.length
    ? state.asrModels
    : WHISPER_MODELS.map((name) => ({ name, installed: false }));
}

function isWhisperItemReady(item) {
  if (!item) return false;
  if (Object.prototype.hasOwnProperty.call(item, "ready")) {
    return Boolean(item.ready);
  }
  if (Object.prototype.hasOwnProperty.call(item, "runtime_installed")) {
    return Boolean(item.installed && item.runtime_installed);
  }
  return Boolean(item.installed);
}

function getWhisperItemWarnings(item) {
  return Array.isArray(item?.warnings) ? item.warnings.filter(Boolean).map(String) : [];
}

function isWhisperModelInstalled(modelName) {
  const target = String(modelName || "").trim();
  if (!target) return false;
  const item = state.asrModels.find((entry) => entry.name === target);
  return isWhisperItemReady(item);
}

function normalizePromptPreset(promptPreset) {
  const preset = String(promptPreset || "").trim().toLowerCase();
  if (preset === "none") {
    return "auto";
  }
  return ASR_PROMPT_PRESETS.includes(preset) ? preset : ASR_STUDIO_DEFAULT_PROMPT_PRESET;
}

function normalizeAsrAnalysisLanguage(value) {
  const language = String(value || "").trim().toLowerCase();
  if (language === "none") {
    return ASR_ANALYSIS_LANGUAGE_DEFAULT;
  }
  return ASR_ANALYSIS_LANGUAGES.includes(language) ? language : ASR_ANALYSIS_LANGUAGE_DEFAULT;
}

function languageForPromptPreset(promptPreset) {
  const preset = normalizePromptPreset(promptPreset);
  if (preset === "ru" || preset === "en") {
    return preset;
  }
  return "auto";
}

function normalizeAsrBeamSize(value) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return ASR_DEFAULT_BEAM_SIZE;
  return Math.min(10, Math.max(1, parsed));
}

function normalizeAsrThreads(value) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return ASR_DEFAULT_THREADS;
  return Math.min(32, Math.max(0, parsed));
}

function getSelectedChatWhisperModel() {
  const items = getWhisperItems();
  const names = items.map((item) => item.name);
  if (!names.includes(state.selectedChatWhisperModel)) {
    state.selectedChatWhisperModel = state.selectedWhisperModel || names[0] || "medium";
  }
  return state.selectedChatWhisperModel || state.selectedWhisperModel || names[0] || "medium";
}

function closeVoiceModelMenu() {
  if (!els.voiceModelMenu) return;
  els.voiceModelMenu.hidden = true;
  els.voiceModelMenu.style.left = "";
  els.voiceModelMenu.style.top = "";
  state.voiceModelMenuPosition = null;
}

function positionVoiceModelMenu(clientX, clientY) {
  if (!els.voiceModelMenu || els.voiceModelMenu.hidden) return;
  const rect = els.voiceModelMenu.getBoundingClientRect();
  const padding = 12;
  const left = Math.max(padding, Math.min(clientX, window.innerWidth - rect.width - padding));
  const top = Math.max(padding, Math.min(clientY, window.innerHeight - rect.height - padding));
  els.voiceModelMenu.style.left = `${left}px`;
  els.voiceModelMenu.style.top = `${top}px`;
}

function renderVoiceModelMenu() {
  if (!els.voiceModelMenu) return;
  const items = getWhisperItems();
  const activeModel = getSelectedChatWhisperModel();
  const availabilityKnown = state.asrModels.length > 0;

  els.voiceModelMenu.innerHTML = [
    '<div class="voice-model-menu__header">Модель диктовки чата</div>',
    ...items.map((item) => {
      const active = item.name === activeModel;
      const meta = availabilityKnown
        ? (item.installed ? "Загружена" : "Не загружена")
        : "Проверяю наличие";
      return `
        <button
          class="voice-model-menu__item${active ? " voice-model-menu__item--active" : ""}"
          type="button"
          role="menuitemradio"
          aria-checked="${active ? "true" : "false"}"
          data-voice-model="${escapeHtml(item.name)}"
        >
          <span class="voice-model-menu__name">${escapeHtml(item.name)}</span>
          <span class="voice-model-menu__meta">${escapeHtml(meta)}</span>
        </button>
      `;
    }),
    '<div class="voice-model-menu__hint">Это влияет только на диктовку в чате. ASR Studio остаётся на своей модели.</div>',
  ].join("");

  if (!els.voiceModelMenu.hidden && state.voiceModelMenuPosition) {
    positionVoiceModelMenu(state.voiceModelMenuPosition.x, state.voiceModelMenuPosition.y);
  }
}

function openVoiceModelMenu({ clientX, clientY }) {
  if (!els.voiceModelMenu) return;
  if (state.isRecordingVoice || state.isVoiceTranscribing) {
    setFooter("Сначала остановите запись или распознавание, затем выберите модель.", "warning");
    return;
  }
  toggleComposerMenu(false);
  state.voiceModelMenuPosition = {
    x: Number.isFinite(clientX) ? clientX : 0,
    y: Number.isFinite(clientY) ? clientY : 0,
  };
  renderVoiceModelMenu();
  els.voiceModelMenu.hidden = false;
  positionVoiceModelMenu(state.voiceModelMenuPosition.x, state.voiceModelMenuPosition.y);
  if (!state.asrModels.length) {
    void loadWhisperModels({ silent: true });
  }
}

function renderVoiceRecordButton() {
  if (!els.voiceRecordButton) return;
  const isBusy = state.isVoiceTranscribing;
  const isRecording = state.isRecordingVoice;
  const selectedModel = getSelectedChatWhisperModel();
  const modelTitle = state.asrModels.length && !isWhisperModelInstalled(selectedModel)
    ? `${selectedModel} (не загружена)`
    : selectedModel;
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
  els.voiceRecordButton.setAttribute("aria-label", `Записать голос. Текущая модель диктовки: ${selectedModel}`);
  els.voiceRecordButton.title = `Записать голос. Модель диктовки: ${modelTitle}. ПКМ: выбрать модель.`;
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

function parseSsePayload(event) {
  try {
    return JSON.parse(event?.data || "{}");
  } catch {
    return {};
  }
}

function closeChatTaskEventSource(source = state.chatTaskEventSource) {
  if (!source) return;
  try {
    source.close();
  } catch {
    // Ignore close errors from browser EventSource implementations.
  }
  if (state.chatTaskEventSource === source) {
    state.chatTaskEventSource = null;
  }
}

function interruptChatTaskEventStream(message = "SSE-соединение закрыто.") {
  if (typeof state.chatTaskStreamAbort === "function") {
    state.chatTaskStreamAbort(message);
    return;
  }
  closeChatTaskEventSource();
  clearChatTaskReplay();
}

function chatTaskIdFrom(taskOrMessage) {
  return String(taskOrMessage?.task_id || taskOrMessage?.id || "").trim();
}

function findAssistantMessageForTask(taskOrMessage) {
  const taskId = chatTaskIdFrom(taskOrMessage);
  const assistantMessageId = String(taskOrMessage?.assistant_message_id || taskOrMessage?.id || "").trim();
  return state.messages.find((message) => {
    if (message?.role !== "assistant") return false;
    if (taskId && String(message.task_id || "") === taskId) return true;
    return Boolean(assistantMessageId && String(message.id || "") === assistantMessageId);
  }) || null;
}

function clearChatTaskReplay(taskId = "") {
  const target = String(taskId || "").trim();
  if (!state.chatTaskReplay) return;
  if (!target || state.chatTaskReplay.taskId === target) {
    state.chatTaskReplay = null;
  }
}

function prepareChatTaskReplay(task, baseContent = null) {
  const taskId = chatTaskIdFrom(task);
  if (!taskId) {
    state.chatTaskReplay = null;
    return;
  }
  const message = findAssistantMessageForTask(task);
  const content = baseContent === null ? String(message?.content || "") : String(baseContent || "");
  state.chatTaskReplay = {
    taskId,
    baseContent: content,
    replayedText: "",
    caughtUp: content.length === 0,
    lastSequence: 0,
  };
}

function normalizeChatDeltaSequence(sequence) {
  const numeric = Number(sequence);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
}

function consumeChatTaskDelta(task, text, sequence = null) {
  const taskId = chatTaskIdFrom(task);
  const delta = String(text || "");
  if (!delta) return "";
  const replay = state.chatTaskReplay;
  const deltaSequence = normalizeChatDeltaSequence(sequence);
  if (replay && replay.taskId === taskId && deltaSequence !== null) {
    if (deltaSequence <= (replay.lastSequence || 0)) {
      return null;
    }
    replay.lastSequence = deltaSequence;
  }
  if (!replay || replay.taskId !== taskId || replay.caughtUp) {
    return delta;
  }

  const previousReplay = replay.replayedText;
  const nextReplay = `${previousReplay}${delta}`;
  const baseContent = replay.baseContent || "";
  replay.replayedText = nextReplay;

  if (baseContent.startsWith(nextReplay)) {
    return null;
  }
  if (nextReplay.startsWith(baseContent)) {
    replay.caughtUp = true;
    const appendFrom = Math.max(0, baseContent.length - previousReplay.length);
    return delta.slice(appendFrom) || null;
  }

  // If persisted partial content was normalized unexpectedly, avoid duplicating old replayed chunks.
  replay.caughtUp = true;
  return null;
}

function chatTypingStreamKey(taskOrPayload) {
  return chatTaskIdFrom(taskOrPayload) || String(taskOrPayload?.assistant_message_id || "").trim();
}

function splitTypewriterChunk(text, { finalFlush = false } = {}) {
  const chars = Array.from(String(text || ""));
  if (!chars.length) return ["", ""];
  const maxChars = finalFlush ? STREAM_TYPEWRITER_FINAL_FLUSH_CHARS : STREAM_TYPEWRITER_MAX_CHARS;
  const backlogBoost = Math.ceil(chars.length / STREAM_TYPEWRITER_BACKLOG_STEP);
  const count = Math.max(
    STREAM_TYPEWRITER_MIN_CHARS,
    Math.min(maxChars, backlogBoost),
  );
  return [
    chars.slice(0, count).join(""),
    chars.slice(count).join(""),
  ];
}

function appendAssistantTypingDelta(stream, delta) {
  const text = String(delta || "");
  if (!text) return;
  updateAssistantMessageFromTask(stream.task, {
    ...stream.latestPayload,
    status: "streaming",
    delta: text,
  });
}

function stopChatTypingStream(key, { flush = false } = {}) {
  const stream = state.chatTypingStreams.get(key);
  if (!stream) return;
  if (stream.timer) {
    window.clearInterval(stream.timer);
  }
  if (flush && stream.pendingText) {
    appendAssistantTypingDelta(stream, stream.pendingText);
  }
  state.chatTypingStreams.delete(key);
}

function drainChatTypingStream(key) {
  const stream = state.chatTypingStreams.get(key);
  if (!stream) return;
  const [chunk, rest] = splitTypewriterChunk(stream.pendingText, { finalFlush: stream.finalFlush });
  stream.pendingText = rest;
  appendAssistantTypingDelta(stream, chunk);

  if (!stream.pendingText) {
    if (stream.timer) {
      window.clearInterval(stream.timer);
      stream.timer = null;
    }
    if (stream.onDrained) {
      const onDrained = stream.onDrained;
      state.chatTypingStreams.delete(key);
      onDrained();
    }
  }
}

function scheduleChatTypingStream(key) {
  const stream = state.chatTypingStreams.get(key);
  if (!stream || stream.timer) return;
  stream.timer = window.setInterval(() => drainChatTypingStream(key), STREAM_TYPEWRITER_INTERVAL_MS);
}

function queueAssistantTypingDelta(task, payload, delta) {
  const key = chatTypingStreamKey(task) || chatTypingStreamKey(payload);
  const text = String(delta || "");
  if (!key || !text) return;
  const existing = state.chatTypingStreams.get(key);
  const stream = existing || {
    task,
    latestPayload: {},
    pendingText: "",
    timer: null,
    onDrained: null,
    finalFlush: false,
  };
  stream.task = { ...stream.task, ...task };
  stream.latestPayload = { ...stream.latestPayload, ...payload, status: "streaming" };
  stream.pendingText = `${stream.pendingText || ""}${text}`;
  state.chatTypingStreams.set(key, stream);
  scheduleChatTypingStream(key);
}

function finishChatTypingStream(task, onDrained, { finalFlush = true } = {}) {
  const key = chatTypingStreamKey(task);
  const stream = key ? state.chatTypingStreams.get(key) : null;
  if (!stream || !stream.pendingText) {
    if (key) {
      stopChatTypingStream(key);
    }
    onDrained();
    return;
  }
  stream.onDrained = onDrained;
  stream.finalFlush = finalFlush;
  scheduleChatTypingStream(key);
}

function clearChatTypingStreams(taskOrId = "", { flush = false } = {}) {
  const key = typeof taskOrId === "string" ? String(taskOrId || "").trim() : chatTypingStreamKey(taskOrId);
  if (key) {
    stopChatTypingStream(key, { flush });
    return;
  }
  [...state.chatTypingStreams.keys()].forEach((itemKey) => stopChatTypingStream(itemKey, { flush }));
}

function normalizeMessageStatus(message) {
  const status = String(message?.status || "").trim().toLowerCase();
  if (MESSAGE_STATUSES.has(status)) return status;
  if (message?.role === "assistant" && message?._optimisticThinking) return "generating";
  return "completed";
}

function isAssistantMessageActive(message) {
  const status = normalizeMessageStatus(message);
  return message?.role === "assistant" && !MESSAGE_FINAL_STATUSES.has(status);
}

function assistantStatusMeta(status) {
  if (status === "streaming") {
    return { label: "Генерирует", text: "Генерирую дальше…" };
  }
  if (status === "failed") {
    return { label: "Ошибка", text: "Генерация ответа завершилась ошибкой." };
  }
  if (status === "cancelled") {
    return { label: "Остановлено", text: "Генерация ответа остановлена." };
  }
  if (status === "generating") {
    return { label: "Генерация", text: "Генерирую ответ..." };
  }
  return { label: "", text: "" };
}

function findMessageIndexById(messageId) {
  const target = String(messageId ?? "");
  if (!target) return -1;
  return state.messages.findIndex((message) => String(message?.id ?? "") === target);
}

function taskConversationId(taskOrPayload) {
  return taskOrPayload?.conversation_id || taskOrPayload?.session_id || state.currentSessionId || "";
}

function updateAssistantMessageFromTask(task, updates = {}) {
  const assistantMessageId = updates.assistant_message_id || task?.assistant_message_id;
  const conversationId = taskConversationId(updates) || taskConversationId(task);
  if (conversationId && state.currentSessionId && String(conversationId) !== String(state.currentSessionId)) {
    return;
  }

  let index = findMessageIndexById(assistantMessageId);
  if (index < 0 && assistantMessageId) {
    state.messages = [
      ...state.messages,
      {
        id: assistantMessageId,
        session_id: conversationId || state.currentSessionId,
        role: "assistant",
        content: "",
        status: "generating",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ];
    index = state.messages.length - 1;
  }
  if (index < 0) return;

  const current = state.messages[index] || {};
  const requestedStatus = String(updates.status || "").toLowerCase();
  const status = ["preparing", "analyzing", "loading_model"].includes(requestedStatus)
    ? "generating"
    : (updates.status || current.status || "generating");
  const nextContent = Object.prototype.hasOwnProperty.call(updates, "content")
    ? String(updates.content || "")
    : `${current.content || ""}${updates.delta || ""}`;
  const nextMessage = {
    ...current,
    status,
    content: nextContent,
    model: updates.model || current.model || task?.model_name || "",
    error: Object.prototype.hasOwnProperty.call(updates, "error") ? updates.error : current.error,
    task_id: task?.id || task?.task_id || current.task_id,
    is_partial: !MESSAGE_FINAL_STATUSES.has(String(status)),
    updated_at: new Date().toISOString(),
  };

  state.messages = state.messages.map((message, itemIndex) => (itemIndex === index ? nextMessage : message));
  renderMessages();
  if (state.autoScrollPinned) {
    scrollMessagesToBottom({ force: true });
  }
}

async function waitForChatTask(taskId, { timeoutMs = 300000 } = {}) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const task = await request(`/chat/tasks/${encodeURIComponent(taskId)}`);
    const taskState = String(task?.state || "");
    if (taskState === "completed" || taskState === "cancelled") {
      return task;
    }
    if (taskState === "error" || taskState === "failed") {
      throw new Error(task?.message || "Генерация ответа завершилась ошибкой.");
    }
    await new Promise((resolve) => window.setTimeout(resolve, 700));
  }
  throw new Error("Истекло время ожидания генерации ответа.");
}

function waitForChatTaskEvents(task, { timeoutMs = 300000, replayBaseContent = null } = {}) {
  const taskId = task?.id || task?.task_id || "";
  if (!taskId || typeof window.EventSource !== "function") {
    return Promise.reject(new Error("SSE недоступен в этом браузере."));
  }

  return new Promise((resolve, reject) => {
    interruptChatTaskEventStream("Открывается новое SSE-соединение.");
    prepareChatTaskReplay(task, replayBaseContent);
    const source = new window.EventSource(`/chat/tasks/${encodeURIComponent(taskId)}/events`);
    let settled = false;
    let terminalEventReceived = false;
    let timeoutId = null;

    const finish = (callback) => {
      if (settled) return;
      settled = true;
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      closeChatTaskEventSource(source);
      if (state.chatTaskStreamAbort === rejectStreamConnection) {
        state.chatTaskStreamAbort = null;
      }
      clearChatTaskReplay(taskId);
      clearChatTypingStreams(taskId);
      callback();
    };

    const rejectStreamConnection = (message) => {
      if (settled) return;
      const error = new Error(message || "SSE-соединение прервалось.");
      error.streamConnectionFailed = true;
      clearChatTypingStreams(task, { flush: true });
      finish(() => reject(error));
    };

    timeoutId = window.setTimeout(() => {
      rejectStreamConnection("Истекло время ожидания генерации ответа.");
    }, timeoutMs);

    state.chatTaskEventSource = source;
    state.chatTaskStreamAbort = rejectStreamConnection;

    source.addEventListener("status", (event) => {
      if (settled) return;
      const data = parseSsePayload(event);
      const status = String(data.status || "generating");
      updateAssistantMessageFromTask(task, {
        ...data,
        status,
      });
    });

    source.addEventListener("model_selected", (event) => {
      if (settled) return;
      const data = parseSsePayload(event);
      updateAssistantMessageFromTask(task, {
        ...data,
        model: data.model,
      });
    });

    source.addEventListener("delta", (event) => {
      if (settled) return;
      const data = parseSsePayload(event);
      const delta = consumeChatTaskDelta(task, data.text, data.sequence);
      if (delta === null) return;
      if (delta) {
        queueAssistantTypingDelta(task, data, delta);
      } else {
        updateAssistantMessageFromTask(task, {
          ...data,
          status: "streaming",
        });
      }
    });

    source.addEventListener("done", (event) => {
      if (settled) return;
      const data = parseSsePayload(event);
      terminalEventReceived = true;
      finishChatTypingStream(task, () => {
        updateAssistantMessageFromTask(task, {
          ...data,
          status: "completed",
        });
        finish(() => resolve({ ...task, ...data, state: "completed" }));
      });
    });

    source.addEventListener("cancelled", (event) => {
      if (settled) return;
      const data = parseSsePayload(event);
      terminalEventReceived = true;
      clearChatTypingStreams(task, { flush: true });
      updateAssistantMessageFromTask(task, {
        ...data,
        status: "cancelled",
      });
      finish(() => resolve({ ...task, ...data, state: "cancelled" }));
    });

    source.addEventListener("error", (event) => {
      if (settled) return;
      if (typeof event?.data !== "string") {
        return;
      }
      const data = parseSsePayload(event);
      terminalEventReceived = true;
      clearChatTypingStreams(task, { flush: true });
      updateAssistantMessageFromTask(task, {
        ...data,
        status: "failed",
        error: data.message || "Генерация ответа завершилась ошибкой.",
      });
      const error = new Error(data.message || "Генерация ответа завершилась ошибкой.");
      error.chatTaskFailed = true;
      finish(() => reject(error));
    });

    source.onerror = () => {
      if (settled) return;
      if (terminalEventReceived) return;
      rejectStreamConnection("SSE-соединение прервалось.");
    };
  });
}

function isFinalChatTaskState(taskState) {
  return ["completed", "failed", "error", "cancelled"].includes(String(taskState || "").toLowerCase());
}

function latestActiveAssistantMessageWithTask(messages = state.messages) {
  return [...(messages || [])]
    .reverse()
    .find((message) => message?.role === "assistant" && message?.task_id && isAssistantMessageActive(message)) || null;
}

function taskFromAssistantMessage(message) {
  const taskId = String(message?.task_id || "").trim();
  return {
    id: taskId,
    task_id: taskId,
    state: normalizeMessageStatus(message),
    session_id: message?.session_id || state.currentSessionId,
    conversation_id: message?.session_id || state.currentSessionId,
    assistant_message_id: message?.id,
    model_name: message?.model || state.selectedLlmModel || "",
    stream: activeProfileStreamingEnabled(),
  };
}

async function refreshCurrentSessionMessages({ sessionId = state.currentSessionId, scroll = false } = {}) {
  const targetSessionId = String(sessionId || "").trim();
  if (!targetSessionId) return false;
  const data = await request(`/sessions/${encodeURIComponent(targetSessionId)}/messages`);
  if (String(state.currentSessionId || "") !== targetSessionId) {
    return false;
  }
  state.messages = Array.isArray(data?.messages) ? data.messages : [];
  renderMessages();
  if (scroll) {
    scrollMessagesToBottom({ force: true });
  }
  return true;
}

async function recoverActiveChatTaskFromMessages() {
  const activeMessage = latestActiveAssistantMessageWithTask();
  const taskId = String(activeMessage?.task_id || "").trim();
  if (!activeMessage || !taskId) return;
  if (state.chatTaskId === taskId) return;

  const fallbackTask = taskFromAssistantMessage(activeMessage);
  const sessionId = activeMessage.session_id || state.currentSessionId;
  let task = fallbackTask;
  state.chatTaskId = taskId;
  state.isSending = true;
  updateSendButtonState();

  try {
    task = {
      ...fallbackTask,
      ...await request(`/chat/tasks/${encodeURIComponent(taskId)}`),
      assistant_message_id: activeMessage.id,
    };
    if (isFinalChatTaskState(task.state)) {
      await refreshCurrentSessionMessages({ sessionId, scroll: false });
      return;
    }

    let completedTask = null;
    const shouldUseSse = Boolean(task.stream && task.id);
    if (shouldUseSse) {
      try {
        completedTask = await waitForChatTaskEvents(task, {
          replayBaseContent: activeMessage.content || "",
        });
      } catch (streamError) {
        if (streamError?.chatTaskFailed) {
          throw streamError;
        }
        setFooter("Поток ответа прервался, жду финальный результат…", "warning");
        completedTask = await waitForChatTask(taskId);
      }
    } else {
      completedTask = await waitForChatTask(taskId);
    }

    await refreshCurrentSessionMessages({ sessionId, scroll: true });
    if (String(completedTask?.state || "") === "cancelled") {
      setFooter("Генерация ответа остановлена.", "warning");
    }
  } catch (error) {
    if ((error?.status || 0) === 404) {
      await refreshCurrentSessionMessages({ sessionId, scroll: false });
      setFooter("Генерация больше не активна: task не найден, сообщение помечено как ошибка.", "warning");
      return;
    }
    await refreshCurrentSessionMessages({ sessionId, scroll: false }).catch(() => false);
    setFooter(`Не удалось восстановить генерацию: ${error.message || error}`, "error");
  } finally {
    if (state.chatTaskId === taskId) {
      state.chatTaskId = null;
      state.isSending = false;
      closeChatTaskEventSource();
      clearChatTaskReplay(taskId);
      clearChatTypingStreams(taskId);
      updateSendButtonState();
    }
  }
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
    } catch {
      if ((error?.status || 0) !== 404) {
        setFooter(`Не удалось остановить генерацию: ${error.message || error}`, "error");
        return;
      }
    }
  }

  state.chatTaskId = null;
  state.chatTaskStartController = null;
  closeChatTaskEventSource();
  clearChatTaskReplay();
  clearChatTypingStreams(taskId, { flush: true });
  state.isSending = false;
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

const VOICE_TRANSCRIPTION_TIMEOUT_MS = 5 * 60 * 1000;
const FILE_TRANSCRIPTION_TIMEOUT_MS = 30 * 60 * 1000;
const MAX_TRANSCRIPTION_TIMEOUT_MS = 60 * 60 * 1000;

function transcriptionTimeoutForFile(file) {
  const sizeMb = Number(file?.size || 0) / (1024 * 1024);
  const sizeBudget = 10 * 60 * 1000 + sizeMb * 90 * 1000;
  return Math.min(MAX_TRANSCRIPTION_TIMEOUT_MS, Math.max(FILE_TRANSCRIPTION_TIMEOUT_MS, sizeBudget));
}

async function waitForVoiceTranscriptionTask(taskId, { timeoutMs = VOICE_TRANSCRIPTION_TIMEOUT_MS } = {}) {
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
  throw new Error("Истекло время ожидания транскрибации. Если это первый запуск модели, повторите проверку истории через минуту.");
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
    formData.append("model", getSelectedChatWhisperModel() || "medium");
    formData.append("prompt_preset", "auto");
    formData.append("language", "auto");
    formData.append("store_result", "false");

    const task = await request("/transcribe/tasks", {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
    state.voiceTranscriptionStartController = null;
    state.voiceTranscriptionTaskId = task?.id || null;

    const result = await waitForVoiceTranscriptionTask(task?.id || "", {
      timeoutMs: VOICE_TRANSCRIPTION_TIMEOUT_MS,
    });
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
  const nextHeight = Math.min(Math.max(els.promptInput.scrollHeight, 44), 132);
  els.promptInput.style.height = `${nextHeight}px`;
}

function updateSendButtonState() {
  if (!els.sendButton) return;
  const hasText = Boolean((els.promptInput?.value || "").trim());
  const hasReadyAttachments = state.chatAttachments.some((item) => item.status === "ready" && item.server?.id);
  const hasBlockedAttachments = state.chatAttachments.some((item) => item.status !== "ready");
  const selectedModel = String(state.selectedLlmModel || els.llmModelSelect?.value || "").trim();
  const selectedIsLocalCalculator = selectedModel === LOCAL_CALCULATOR_MODEL_ID;
  const hasInstalledChatModel = state.installedModels.length > 0 || selectedIsLocalCalculator;
  const selectedInstalled = Boolean(selectedModel) && (
    selectedModel === AUTO_MODEL_ID || selectedModel === LOCAL_CALCULATOR_MODEL_ID || state.installedModels.some((item) => item.name === selectedModel)
  );
  if (els.promptInput) {
    els.promptInput.disabled = false;
    els.promptInput.placeholder = !hasInstalledChatModel
      ? "Нет доступных моделей. Загрузите модель, чтобы отправлять сообщения."
      : (!selectedModel ? "Выберите модель, чтобы отправлять сообщения." : "Напишите сообщение…");
  }
  els.sendButton.disabled = state.isSending
    ? false
    : ((!hasText && !hasReadyAttachments) || hasBlockedAttachments || !selectedInstalled);
  els.sendButton.textContent = state.isSending ? "Стоп" : "Отправить";
  els.sendButton.classList.toggle("send-button--stopping", state.isSending);
  els.sendButton.setAttribute("aria-label", state.isSending ? "Остановить генерацию" : "Отправить сообщение");
}

function renderChatModelNotice() {
  if (!els.chatModelNotice) return;
  const selectedModel = String(state.selectedLlmModel || "").trim();
  const activeDownload = getActiveChatDownload(selectedModel) || getActiveChatDownload();
  const selectedIsLocalCalculator = selectedModel === LOCAL_CALCULATOR_MODEL_ID;
  const hasInstalledChatModel = state.installedModels.length > 0 || selectedIsLocalCalculator;
  const selectedInstalled = Boolean(selectedModel) && (
    selectedModel === AUTO_MODEL_ID || selectedModel === LOCAL_CALCULATOR_MODEL_ID || state.installedModels.some((item) => item.name === selectedModel)
  );
  const missing = !hasInstalledChatModel || !selectedModel || (Boolean(selectedModel) && !selectedInstalled);
  els.chatModelNotice.hidden = !missing;
  if (missing) {
    const title = els.chatModelNotice.querySelector("strong");
    const text = els.chatModelNotice.querySelector("span");
    if (activeDownload && (!selectedModel || !selectedInstalled)) {
      if (title) title.textContent = "Модель загружается.";
      if (text) text.textContent = activeDownload.message || "Прогресс показан в карточке загрузки. Чат станет доступен после установки модели.";
    } else if (!hasInstalledChatModel) {
      if (title) title.textContent = "Нет доступных моделей.";
      if (text) text.textContent = "Загрузите модель в настройках, чтобы отправлять сообщения в чат.";
    } else if (!selectedModel) {
      if (title) title.textContent = "Модель не выбрана.";
      if (text) text.textContent = "Выберите установленную модель в селекте или добавьте модель из каталога.";
    } else {
      if (title) title.textContent = "Модель не загружена.";
      if (text) text.textContent = "Выберите локальную модель или загрузите выбранную модель.";
    }
  }
  updateSendButtonState();
}

function setFooter(message = "", tone = "info") {
  if (els.footerStatus) {
    els.footerStatus.textContent = "";
    els.footerStatus.className = "footer-status";
  }
  if (!message) return;
  showToast(message, tone, {
    title: tone === "success" ? "Готово" : tone === "error" ? "Ошибка" : tone === "warning" ? "Внимание" : "Статус",
    duration: tone === "error" ? 4200 : tone === "warning" ? 3400 : 2800,
  });
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

function closeToast() {
  if (state.toastTimer) {
    window.clearTimeout(state.toastTimer);
    state.toastTimer = null;
  }
  els.toastStack?.querySelectorAll(".toast").forEach((toast) => toast.remove());
}

function showToast(message = "", tone = "info", { title = "Уведомление", duration = 2800 } = {}) {
  if (!els.toastStack || !message) return;
  const dedupeKey = `${tone}:${title}:${message}`;
  const now = Date.now();
  if (state.lastToastKey === dedupeKey && now - state.lastToastAt < 8000) return;
  state.lastToastKey = dedupeKey;
  state.lastToastAt = now;
  const toast = document.createElement("div");
  const normalizedTone = ["success", "warning", "error"].includes(tone) ? tone : "info";
  toast.className = `toast toast--${normalizedTone}`;
  toast.innerHTML = `
    <span class="toast__mark" aria-hidden="true"></span>
    <span class="toast__content">
      <strong class="toast__title">${escapeHtml(title)}</strong>
      <span class="toast__message">${escapeHtml(message)}</span>
    </span>
    <button class="toast__close" type="button" aria-label="Закрыть уведомление">×</button>
  `;
  const close = () => {
    toast.classList.add("toast--closing");
    window.setTimeout(() => toast.remove(), 180);
  };
  toast.querySelector(".toast__close")?.addEventListener("click", close);
  while (els.toastStack.children.length >= 2) {
    els.toastStack.firstElementChild?.remove();
  }
  els.toastStack.append(toast);
  window.setTimeout(close, Math.max(1200, Number(duration) || 2800));
}

function resolveConfirmDialog(approved = false) {
  if (!els.confirmBackdrop) return Boolean(approved);
  els.confirmBackdrop.hidden = true;
  syncMobileScrollLock();
  const resolver = state.confirmResolver;
  const returnFocus = state.confirmReturnFocus;
  state.confirmResolver = null;
  state.confirmReturnFocus = null;
  if (returnFocus && typeof returnFocus.focus === "function") {
    window.setTimeout(() => returnFocus.focus(), 0);
  }
  if (typeof resolver === "function") {
    resolver(Boolean(approved));
  }
  return Boolean(approved);
}

function openConfirmDialog({
  eyebrow = "Подтверждение",
  title = "Продолжить действие?",
  message = "Подтвердите действие.",
  confirmLabel = "Продолжить",
  cancelLabel = "Отмена",
  returnFocus = null,
} = {}) {
  if (!els.confirmBackdrop || !els.confirmTitle || !els.confirmMessage || !els.confirmApproveButton) {
    return Promise.resolve(false);
  }

  if (typeof state.confirmResolver === "function") {
    resolveConfirmDialog(false);
  }

  state.confirmReturnFocus = returnFocus || document.activeElement;
  els.confirmEyebrow.textContent = eyebrow;
  els.confirmTitle.textContent = title;
  els.confirmMessage.textContent = message;
  els.confirmCancelButton.textContent = cancelLabel;
  if (els.confirmDismissButton) {
    els.confirmDismissButton.textContent = cancelLabel;
  }
  els.confirmApproveButton.textContent = confirmLabel;
  els.confirmBackdrop.hidden = false;
  syncMobileScrollLock();

  return new Promise((resolve) => {
    state.confirmResolver = resolve;
    window.setTimeout(() => els.confirmApproveButton?.focus(), 0);
  });
}

function hasDirectoryInDataTransfer(dataTransfer) {
  const items = Array.from(dataTransfer?.items || []);
  return items.some((item) => {
    if (typeof item?.webkitGetAsEntry !== "function") return false;
    try {
      return Boolean(item.webkitGetAsEntry()?.isDirectory);
    } catch {
      return false;
    }
  });
}

function isFileDragEvent(event) {
  const types = Array.from(event?.dataTransfer?.types || []);
  return types.includes("Files");
}

function fileExtension(name = "") {
  const trimmed = String(name || "").trim().toLowerCase();
  const index = trimmed.lastIndexOf(".");
  return index >= 0 ? trimmed.slice(index + 1) : "";
}

function classifyFileKind(file) {
  const mimeType = String(file?.type || "").toLowerCase();
  const ext = fileExtension(file?.name || "");
  if (mimeType.startsWith("image/") || IMAGE_FILE_EXTENSIONS.has(ext)) {
    return "image";
  }
  if (mimeType.startsWith("audio/") || mimeType.startsWith("video/") || MEDIA_FILE_EXTENSIONS.has(ext)) {
    return "media";
  }
  return "other";
}

function classifyDraggedPayload(dataTransfer) {
  if (!dataTransfer) return "none";
  if (hasDirectoryInDataTransfer(dataTransfer)) return "directory";

  const files = Array.from(dataTransfer.files || []);
  if (files.length > 1) {
    return files.every((file) => classifyFileKind(file) === "image") ? "images" : "multiple";
  }
  if (files.length === 1) return classifyFileKind(files[0]);

  const fileItems = Array.from(dataTransfer.items || []).filter((item) => item.kind === "file");
  if (fileItems.length > 1) {
    return fileItems.every((item) => String(item?.type || "").toLowerCase().startsWith("image/"))
      ? "images"
      : "multiple";
  }
  if (!fileItems.length) return "none";
  const mimeType = String(fileItems[0]?.type || "").toLowerCase();
  if (mimeType.startsWith("image/")) return "image";
  if (mimeType.startsWith("audio/") || mimeType.startsWith("video/")) return "media";
  return "other";
}

function extractDroppedFile(dataTransfer) {
  if (!dataTransfer) {
    return { error: "unsupported" };
  }
  if (hasDirectoryInDataTransfer(dataTransfer)) {
    return { error: "unsupported" };
  }
  const files = Array.from(dataTransfer.files || []);
  if (files.length > 1) {
    return { error: "multiple" };
  }
  if (!files.length) {
    return { error: "unsupported" };
  }
  return { file: files[0] };
}

function getDropOverlayContent(zone, payloadKind) {
  if (zone === "chat") {
    if (payloadKind === "image" || payloadKind === "images") {
      return {
        tone: "accent",
        title: payloadKind === "images" ? "Добавить изображения в чат" : "Добавить изображение в чат",
        meta: "PNG, JPEG и WebP будут загружены локально и появятся над полем ввода.",
      };
    }
    if (payloadKind === "media") {
      return {
        tone: "accent",
        title: "Отпустите аудио или видео",
        meta: "После подтверждения файл откроется в ASR Studio для транскрибации.",
      };
    }
  }

  if (zone === "asr" && payloadKind === "media") {
    return {
      tone: "accent",
      title: "Отпустите файл для ASR Studio",
      meta: "После подтверждения будет запущена отдельная транскрибация.",
    };
  }

  if (payloadKind === "multiple") {
    return {
      tone: "warning",
      title: "Нельзя смешивать типы файлов",
      meta: "Перетащите несколько изображений либо один аудио/видеофайл.",
    };
  }

  return zone === "asr"
    ? {
        tone: "warning",
        title: "ASR Studio принимает только аудио и видео",
        meta: "Изображения и остальные типы файлов здесь пока не поддерживаются.",
      }
    : {
        tone: "warning",
        title: "Этот тип файла пока не поддерживается",
        meta: "Сейчас drag and drop в чате работает только для изображений, аудио и видео.",
      };
}

function renderDropOverlay(zone, payloadKind) {
  const overlay = zone === "asr" ? els.asrToolDropOverlay : els.chatDropOverlay;
  const title = zone === "asr" ? els.asrToolDropOverlayTitle : els.chatDropOverlayTitle;
  const meta = zone === "asr" ? els.asrToolDropOverlayMeta : els.chatDropOverlayMeta;
  if (!overlay || !title || !meta) return;
  const content = getDropOverlayContent(zone, payloadKind);
  overlay.dataset.tone = content.tone || "accent";
  title.textContent = content.title;
  meta.textContent = content.meta;
  overlay.hidden = false;
}

function clearDropOverlay(zone) {
  const overlay = zone === "asr" ? els.asrToolDropOverlay : els.chatDropOverlay;
  if (overlay) {
    overlay.hidden = true;
    delete overlay.dataset.tone;
  }
  if (zone === "asr") {
    state.asrToolDropDepth = 0;
  } else {
    state.chatDropDepth = 0;
  }
}

function clearAllDropOverlays() {
  clearDropOverlay("chat");
  clearDropOverlay("asr");
}

function handleDropZoneDragEnter(event, zone) {
  if (!isFileDragEvent(event)) return;
  event.preventDefault();
  if (zone === "asr") {
    state.asrToolDropDepth += 1;
  } else {
    state.chatDropDepth += 1;
  }
  renderDropOverlay(zone, classifyDraggedPayload(event.dataTransfer));
}

function handleDropZoneDragOver(event, zone) {
  if (!isFileDragEvent(event)) return;
  event.preventDefault();
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "copy";
  }
  renderDropOverlay(zone, classifyDraggedPayload(event.dataTransfer));
}

function handleDropZoneDragLeave(event, zone) {
  if (!isFileDragEvent(event)) return;
  event.preventDefault();
  if (zone === "asr") {
    state.asrToolDropDepth = Math.max(0, state.asrToolDropDepth - 1);
    if (!state.asrToolDropDepth) {
      clearDropOverlay("asr");
    }
    return;
  }
  state.chatDropDepth = Math.max(0, state.chatDropDepth - 1);
  if (!state.chatDropDepth) {
    clearDropOverlay("chat");
  }
}

function getActiveProfile() {
  return state.profiles.find((profile) => profile.id === state.activeProfileId) || null;
}

function getActiveProfilePreferences() {
  return getActiveProfile()?.preferences || {};
}

function activeProfileStreamingEnabled() {
  const preferences = getActiveProfilePreferences();
  const value = preferences?.settings?.streaming_enabled;
  return value === undefined || value === null ? true : Boolean(value);
}

function activeChatImageSettings() {
  const settings = getActiveProfilePreferences()?.settings || {};
  const maxImages = Number.parseInt(settings.max_images_per_message, 10);
  const maxFileBytes = Number.parseInt(settings.chat_image_max_file_bytes, 10);
  const maxTotalBytes = Number.parseInt(settings.chat_image_max_total_bytes, 10);
  return {
    enabled: settings.chat_images_enabled !== false,
    maxImages: Math.min(10, Math.max(1, Number.isFinite(maxImages) ? maxImages : 1)),
    maxFileBytes: Number.isFinite(maxFileBytes) && maxFileBytes > 0 ? maxFileBytes : 20 * 1024 * 1024,
    maxTotalBytes: Number.isFinite(maxTotalBytes) && maxTotalBytes > 0 ? maxTotalBytes : 40 * 1024 * 1024,
  };
}

function isSupportedChatImage(file) {
  const mimeType = String(file?.type || "").trim().toLowerCase();
  const extension = fileExtension(file?.name || "");
  return CHAT_IMAGE_MIME_TYPES.has(mimeType) || (!mimeType && CHAT_IMAGE_EXTENSIONS.has(extension));
}

function formatChatAttachmentBytes(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "";
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.ceil(bytes / 1024))} KB`;
  }
  return formatBytes(bytes);
}

function chatAttachmentStatusText(item) {
  if (item.status === "queued") return "Ожидает загрузки";
  if (item.status === "uploading") return "Загрузка…";
  if (item.status === "ready") {
    const size = formatChatAttachmentBytes(item.server?.size_bytes || item.file?.size);
    return size ? `Готово • ${size}` : "Готово";
  }
  if (item.status === "error") return item.error || "Не удалось загрузить";
  return "Подготовка…";
}

function renderChatAttachments() {
  if (!els.composerAttachments) return;
  els.composerAttachments.replaceChildren();
  els.composerAttachments.hidden = state.chatAttachments.length === 0;

  state.chatAttachments.forEach((item) => {
    const card = document.createElement("article");
    card.className = "composer-attachment";
    card.dataset.status = item.status;
    card.setAttribute("role", "listitem");

    const preview = document.createElement("img");
    preview.className = "composer-attachment__preview";
    preview.src = item.previewUrl || item.server?.thumbnail_url || "";
    preview.alt = "";

    const body = document.createElement("div");
    body.className = "composer-attachment__body";
    const name = document.createElement("span");
    name.className = "composer-attachment__name";
    name.textContent = item.file?.name || item.server?.original_name || "Изображение";
    name.title = name.textContent;
    const status = document.createElement("span");
    status.className = "composer-attachment__status";
    status.textContent = chatAttachmentStatusText(item);
    status.title = status.textContent;
    body.append(name, status);

    const remove = document.createElement("button");
    remove.className = "composer-attachment__remove";
    remove.type = "button";
    remove.dataset.chatAttachmentRemove = item.localId;
    remove.setAttribute("aria-label", `Удалить изображение ${name.textContent}`);
    remove.title = "Удалить изображение";
    remove.textContent = "×";
    remove.disabled = state.isSending;

    card.append(preview, body, remove);
    els.composerAttachments.append(card);
  });
  updateSendButtonState();
}

function releaseChatAttachmentPreview(item) {
  if (!item?.previewIsObjectUrl || !item.previewUrl) return;
  URL.revokeObjectURL(item.previewUrl);
  item.previewIsObjectUrl = false;
}

async function uploadChatAttachment(item) {
  if (!item || !state.chatAttachments.some((candidate) => candidate.localId === item.localId)) return;
  item.status = "uploading";
  const controller = new AbortController();
  item.controller = controller;
  renderChatAttachments();

  const formData = new FormData();
  formData.append("file", item.file, item.file.name || "clipboard-image");
  formData.append("profile_id", String(item.profileId));
  if (item.sessionId) {
    formData.append("session_id", item.sessionId);
  }

  try {
    const serverAttachment = await request("/chat/attachments", {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
    const current = state.chatAttachments.find((candidate) => candidate.localId === item.localId);
    if (!current || current.profileId !== state.activeProfileId) {
      await request(serverAttachment.media_url, { method: "DELETE" }).catch(() => {});
      return;
    }
    releaseChatAttachmentPreview(current);
    current.previewUrl = serverAttachment.thumbnail_url;
    current.server = serverAttachment;
    current.status = "ready";
    current.error = "";
  } catch (error) {
    const current = state.chatAttachments.find((candidate) => candidate.localId === item.localId);
    if (!current || isAbortError(error)) return;
    current.status = "error";
    current.error = error?.message || "Не удалось загрузить изображение";
    setFooter(`Изображение не загружено: ${current.error}`, "error");
  } finally {
    const current = state.chatAttachments.find((candidate) => candidate.localId === item.localId);
    if (current) {
      current.controller = null;
      renderChatAttachments();
    }
  }
}

async function addChatImageFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;
  if (!state.activeProfileId) {
    showToast("Сначала выберите профиль.", "warning");
    return;
  }

  const settings = activeChatImageSettings();
  if (!settings.enabled) {
    showToast("Изображения в чате отключены в настройках профиля.", "warning");
    return;
  }

  const accepted = [];
  let totalBytes = state.chatAttachments.reduce((sum, item) => sum + Number(item.file?.size || item.server?.size_bytes || 0), 0);
  let availableSlots = Math.max(0, settings.maxImages - state.chatAttachments.length);
  for (const file of files) {
    if (!availableSlots) {
      showToast(`Можно прикрепить не больше ${settings.maxImages} изображений.`, "warning");
      break;
    }
    if (!isSupportedChatImage(file)) {
      showToast(`${file.name || "Файл"}: поддерживаются только PNG, JPEG и WebP.`, "warning");
      continue;
    }
    if (Number(file.size || 0) > settings.maxFileBytes) {
      showToast(`${file.name || "Файл"} превышает лимит ${formatBytes(settings.maxFileBytes)}.`, "warning");
      continue;
    }
    if (totalBytes + Number(file.size || 0) > settings.maxTotalBytes) {
      showToast(`Общий размер изображений превышает ${formatBytes(settings.maxTotalBytes)}.`, "warning");
      break;
    }

    const item = {
      localId: globalThis.crypto?.randomUUID?.() || `chat-image-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      profileId: state.activeProfileId,
      sessionId: state.currentSessionId,
      file,
      previewUrl: URL.createObjectURL(file),
      previewIsObjectUrl: true,
      status: "queued",
      error: "",
      server: null,
      controller: null,
    };
    state.chatAttachments.push(item);
    accepted.push(item);
    totalBytes += Number(file.size || 0);
    availableSlots -= 1;
  }

  renderChatAttachments();
  await Promise.all(accepted.map((item) => uploadChatAttachment(item)));
}

async function removeChatAttachment(localId, { deleteRemote = true } = {}) {
  const index = state.chatAttachments.findIndex((item) => item.localId === localId);
  if (index < 0) return;
  const [item] = state.chatAttachments.splice(index, 1);
  item.controller?.abort();
  releaseChatAttachmentPreview(item);
  renderChatAttachments();
  if (deleteRemote && item.server?.media_url) {
    try {
      await request(item.server.media_url, { method: "DELETE" });
    } catch (error) {
      setFooter(`Не удалось удалить изображение из кэша: ${error.message || error}`, "error");
    }
  }
}

async function clearChatAttachments({ deleteRemote = true } = {}) {
  const items = [...state.chatAttachments];
  state.chatAttachments = [];
  items.forEach((item) => {
    item.controller?.abort();
    releaseChatAttachmentPreview(item);
  });
  renderChatAttachments();
  if (deleteRemote) {
    await Promise.all(items.map((item) => (
      item.server?.media_url
        ? request(item.server.media_url, { method: "DELETE" }).catch(() => {})
        : Promise.resolve()
    )));
  }
}

function asrFullAnalysisEnabled() {
  const preferences = getActiveProfilePreferences();
  return Boolean(preferences?.settings?.asr_full_analysis_enabled);
}

function asrDiagnosticsEnabled() {
  const preferences = getActiveProfilePreferences();
  return Boolean(preferences?.asr?.diagnostics_enabled);
}

function getAsrAnalysisModeConfig(modeId) {
  return ASR_ANALYSIS_MODES.find((mode) => mode.id === modeId) || ASR_ANALYSIS_MODES.find((mode) => mode.id === ASR_ANALYSIS_MODE_DEFAULT);
}

function normalizeAsrAnalysisMode(modeId) {
  const mode = getAsrAnalysisModeConfig(modeId);
  if (!mode) return ASR_ANALYSIS_MODE_DEFAULT;
  if (mode.requiresFullAnalysis && !asrFullAnalysisEnabled()) {
    return ASR_ANALYSIS_MODE_DEFAULT;
  }
  return mode.id;
}

function setAsrAnalysisModeMenuOpen(open) {
  state.asrToolAnalysisModeMenuOpen = Boolean(open);
  renderAsrAnalysisModeControl();
}

function setAsrAnalysisMode(modeId) {
  const mode = getAsrAnalysisModeConfig(modeId);
  if (!mode) return;
  if (mode.requiresFullAnalysis && !asrFullAnalysisEnabled()) {
    setInlineStatus(
      els.asrToolStatus,
      "Полный анализ отключён. Его можно включить в настройках ASR после предупреждения о нагрузке.",
      "warning",
    );
    openAsrPipelineSettings();
    return;
  }
  state.asrToolAnalysisMode = mode.id;
  state.asrToolAnalysisModeMenuOpen = false;
  writeStored(STORAGE_KEYS.asrAnalysisMode, mode.id);
  renderAsrAnalysisModeControl();
}

function applyActiveProfilePreferences() {
  const preferences = getActiveProfilePreferences();
  const whisperFallback = state.asrModels[0]?.name || "medium";
  const asrStudioFallback = state.asrModels.some((item) => item.name === ASR_STUDIO_DEFAULT_MODEL)
    ? ASR_STUDIO_DEFAULT_MODEL
    : (state.asrModels[0]?.name || ASR_STUDIO_DEFAULT_MODEL);
  const promptPreset = normalizePromptPreset(preferences?.asr?.prompt_preset);

  state.selectedChatWhisperModel = String(preferences?.chat?.dictation_model || "").trim() || whisperFallback;
  state.selectedWhisperModel = String(preferences?.asr?.studio_model || "").trim() || asrStudioFallback;
  state.selectedPromptPreset = promptPreset;
  state.selectedAsrBeamSize = normalizeAsrBeamSize(preferences?.asr?.beam_size ?? ASR_DEFAULT_BEAM_SIZE);
  state.selectedAsrThreads = normalizeAsrThreads(preferences?.asr?.threads ?? ASR_DEFAULT_THREADS);
  state.selectedTtsProvider = String(preferences?.tts?.provider || state.selectedTtsProvider || "piper").trim() || "piper";
  state.selectedTtsVoiceId = String(preferences?.tts?.voice_id || "").trim();
  state.selectedTtsSpeed = formatTtsSpeedLabel(preferences?.tts?.speed || state.selectedTtsSpeed || 1);

  renderRagButton();
  renderWhisperControls();
  renderTtsControls();
  renderVisionSettings();
}

function replaceProfileState(profile) {
  if (!profile?.id) return;
  state.profiles = state.profiles.map((item) => (item.id === profile.id ? profile : item));
}

function patchActiveProfileSettingsLocal(settingsPatch) {
  const profile = getActiveProfile();
  if (!profile || !settingsPatch || typeof settingsPatch !== "object") return null;
  const preferences = profile.preferences || {};
  const nextProfile = {
    ...profile,
    preferences: {
      ...preferences,
      settings: {
        ...(preferences.settings || {}),
        ...settingsPatch,
      },
    },
  };
  replaceProfileState(nextProfile);
  applyActiveProfilePreferences();
  renderModelSettings();
  return nextProfile;
}

function patchActiveProfileAsrLocal(asrPatch) {
  const profile = getActiveProfile();
  if (!profile || !asrPatch || typeof asrPatch !== "object") return null;
  const preferences = profile.preferences || {};
  const nextProfile = {
    ...profile,
    preferences: {
      ...preferences,
      asr: {
        ...(preferences.asr || {}),
        ...asrPatch,
      },
    },
  };
  replaceProfileState(nextProfile);
  applyActiveProfilePreferences();
  renderAsrPipelineSettings();
  return nextProfile;
}

async function saveActiveProfilePreferences(preferencesPatch) {
  if (!state.activeProfileId) {
    setFooter("Сначала выберите профиль.", "warning");
    return null;
  }

  try {
    const updatedProfile = await request(`/profiles/${encodeURIComponent(state.activeProfileId)}/preferences`, {
      method: "PATCH",
      body: preferencesPatch,
    });
    replaceProfileState(updatedProfile);
    renderProfileOptions();
    renderProfileManagement();
    if (updatedProfile?.id === state.activeProfileId) {
      applyActiveProfilePreferences();
    }
    return updatedProfile;
  } catch (error) {
    if (state.activeProfileId) {
      applyActiveProfilePreferences();
    }
    setFooter(`Не удалось сохранить настройки профиля: ${error.message || error}`, "error");
    return null;
  }
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
  const hasRunning = collectModelOperations().some((item) => isActiveDownloadState(item.state));
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
  if (!els.profileSelect) return;
  if (!state.profiles.length) {
    els.profileSelect.innerHTML = '<option value="">Нет профилей</option>';
    els.profileSelect.disabled = true;
    if (els.profileField) {
      els.profileField.hidden = false;
    }
    queueSyncAppSelects();
    return;
  }

  els.profileSelect.disabled = false;
  els.profileSelect.innerHTML = state.profiles
    .map((profile) => `<option value="${profile.id}">${escapeHtml(profile.name)}</option>`)
    .join("");

  if (state.activeProfileId) {
    els.profileSelect.value = String(state.activeProfileId);
  }

  if (els.profileField) {
    els.profileField.hidden = false;
  }
  queueSyncAppSelects();
}

function enterProfileCreateMode() {
  state.profileManagementMode = "create";
  if (els.profileNameInput) {
    els.profileNameInput.value = "";
  }
  if (els.profileDescriptionInput) {
    els.profileDescriptionInput.value = "";
  }
  if (els.profileSystemPromptInput) {
    els.profileSystemPromptInput.value = "";
  }
  renderProfileManagement();
}

function renderProfileManagement() {
  const activeProfile = getActiveProfile();
  const isCreateMode = state.profileManagementMode === "create";
  if (els.activeProfileSummary) {
    els.activeProfileSummary.textContent = isCreateMode ? "Создание нового профиля" : (activeProfile?.name || "Не выбран");
  }
  if (els.profileManagementSelect) {
    const options = state.profiles
      .map((profile) => `<option value="${profile.id}">${escapeHtml(profile.name)}</option>`)
      .join("");
    els.profileManagementSelect.innerHTML = `<option value="${CREATE_PROFILE_VALUE}">Создать новый профиль</option>${options}`;
    els.profileManagementSelect.value = isCreateMode ? CREATE_PROFILE_VALUE : String(state.activeProfileId || "");
  }
  if (els.profileNameField) {
    els.profileNameField.hidden = !isCreateMode;
  }
  if (els.profileDescriptionInput) {
    if (!isCreateMode && document.activeElement !== els.profileDescriptionInput) {
      els.profileDescriptionInput.value = activeProfile?.description || "";
    }
    els.profileDescriptionInput.disabled = !isCreateMode && !activeProfile;
  }
  if (els.profileSystemPromptInput) {
    const prompt = isCreateMode ? "" : (activeProfile?.preferences?.chat?.system_prompt || "");
    if (!isCreateMode && document.activeElement !== els.profileSystemPromptInput) {
      els.profileSystemPromptInput.value = prompt;
    }
    els.profileSystemPromptInput.disabled = !isCreateMode && !activeProfile;
  }
  if (els.createProfileButton) {
    els.createProfileButton.hidden = !isCreateMode;
    els.createProfileButton.disabled = !isCreateMode || !(els.profileNameInput?.value || "").trim();
  }
  if (els.saveProfileSystemPromptButton) {
    els.saveProfileSystemPromptButton.hidden = isCreateMode;
    els.saveProfileSystemPromptButton.disabled = isCreateMode || !activeProfile;
  }
  if (els.deleteProfileButton) {
    els.deleteProfileButton.hidden = isCreateMode;
    els.deleteProfileButton.disabled = isCreateMode || !activeProfile || state.profiles.length <= 1;
  }
  queueSyncAppSelects();
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

function closeSessionContextMenu() {
  state.sessionContextMenuSessionId = null;
  if (els.sessionContextMenu) {
    els.sessionContextMenu.hidden = true;
  }
}

function openSessionContextMenu(sessionId, clientX, clientY) {
  const session = state.sessions.find((item) => item.id === sessionId);
  if (!session || !els.sessionContextMenu) return;
  state.sessionContextMenuSessionId = sessionId;
  els.sessionContextMenu.hidden = false;

  const rect = els.sessionContextMenu.getBoundingClientRect();
  const margin = 10;
  const left = Math.min(Math.max(margin, clientX), window.innerWidth - rect.width - margin);
  const top = Math.min(Math.max(margin, clientY), window.innerHeight - rect.height - margin);
  els.sessionContextMenu.style.left = `${left}px`;
  els.sessionContextMenu.style.top = `${top}px`;
}

function closeAsrHistoryContextMenu() {
  state.asrHistoryContextMenuTranscriptId = null;
  if (els.asrHistoryContextMenu) {
    els.asrHistoryContextMenu.hidden = true;
  }
}

function openAsrHistoryContextMenu(transcriptId, clientX, clientY) {
  const targetId = Number(transcriptId || 0);
  const transcript = state.asrToolHistory.find((item) => Number(item.id) === targetId);
  if (!transcript || !els.asrHistoryContextMenu) return;
  state.asrHistoryContextMenuTranscriptId = targetId;
  els.asrHistoryContextMenu.hidden = false;

  const rect = els.asrHistoryContextMenu.getBoundingClientRect();
  const margin = 10;
  const left = Math.min(Math.max(margin, clientX), window.innerWidth - rect.width - margin);
  const top = Math.min(Math.max(margin, clientY), window.innerHeight - rect.height - margin);
  els.asrHistoryContextMenu.style.left = `${left}px`;
  els.asrHistoryContextMenu.style.top = `${top}px`;
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
    if (els.clearContextButton) {
      els.clearContextButton.hidden = false;
    }
    return;
  }

  els.contextStatus.textContent = "";
  els.contextStatus.hidden = true;
  if (els.clearContextButton) {
    els.clearContextButton.hidden = true;
  }
}

function renderTranscriptStrip() {
  renderContextSummary();
}

function visionSourceUserMessageForIndex(messageIndex) {
  for (let index = Number(messageIndex) - 1; index >= 0; index -= 1) {
    const message = state.messages[index];
    if (message?.role !== "user") continue;
    return (state.messageAttachments[String(message.id)] || []).length ? message : null;
  }
  return null;
}

function closeVisionRagDialog() {
  state.visionRagSourceMessageId = null;
  if (els.visionRagBackdrop) els.visionRagBackdrop.hidden = true;
  syncMobileScrollLock();
}

function openVisionRagDialog(messageIndex) {
  const index = Number(messageIndex);
  const assistantMessage = Number.isFinite(index) ? state.messages[index] : null;
  const sourceMessage = visionSourceUserMessageForIndex(index);
  if (!assistantMessage || !sourceMessage || !String(assistantMessage.content || "").trim()) {
    setFooter("Для этого ответа нет image-контекста для экспорта.", "warning");
    return;
  }
  state.visionRagSourceMessageId = Number(sourceMessage.id);
  if (els.visionRagTitleInput) {
    els.visionRagTitleInput.value = String(sourceMessage.content || "Vision context").trim().slice(0, 160);
  }
  if (els.visionRagTextInput) {
    els.visionRagTextInput.value = String(assistantMessage.content || "").trim();
  }
  setInlineStatus(els.visionRagStatus, "Проверьте и при необходимости отредактируйте производный текст.", "warning");
  if (els.visionRagBackdrop) els.visionRagBackdrop.hidden = false;
  syncMobileScrollLock();
  window.setTimeout(() => els.visionRagTextInput?.focus(), 0);
}

async function saveVisionContextToRag() {
  const messageId = Number(state.visionRagSourceMessageId || 0);
  const text = String(els.visionRagTextInput?.value || "").trim();
  if (!messageId || !state.activeProfileId || !state.currentSessionId || !text) {
    setInlineStatus(els.visionRagStatus, "Нужен непустой текст и активный чат.", "warning");
    return;
  }
  els.visionRagSaveButton.disabled = true;
  setInlineStatus(els.visionRagStatus, "Индексирую только текстовый контекст…", "warning");
  try {
    await request("/rag/vision-contexts", {
      method: "POST",
      body: {
        profile_id: state.activeProfileId,
        session_id: state.currentSessionId,
        message_id: messageId,
        title: String(els.visionRagTitleInput?.value || "").trim(),
        text,
      },
    });
    await loadRagStatus();
    closeVisionRagDialog();
    setFooter("Текстовый vision-контекст сохранён в RAG.", "success");
  } catch (error) {
    setInlineStatus(els.visionRagStatus, `Не удалось сохранить: ${error.message || error}`, "error");
  } finally {
    els.visionRagSaveButton.disabled = false;
  }
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
      const status = normalizeMessageStatus(message);
      const statusMeta = role === "assistant" ? assistantStatusMeta(status) : { label: "", text: "" };
      const content = String(message.content || "");
      const errorText = String(message.error || "").trim();
      const hasContent = Boolean(content.trim());
      const isActive = isAssistantMessageActive(message);
      const canCopy = role !== "user" && hasContent;
      const canExportVision = role === "assistant"
        && status === "completed"
        && hasContent
        && Boolean(visionSourceUserMessageForIndex(index));
      const body = (() => {
        if (role !== "assistant") return formatRichMessage(content);
        if (status === "failed") {
          return [
            hasContent ? formatRichMessage(content) : "",
            `<p class="message-status-text message-status-text--error">${escapeHtml(errorText || statusMeta.text)}</p>`,
          ].filter(Boolean).join("");
        }
        if (status === "cancelled") {
          return [
            hasContent ? formatRichMessage(content) : "",
            `<p class="message-status-text">${escapeHtml(statusMeta.text)}</p>`,
          ].filter(Boolean).join("");
        }
        if (!hasContent && status === "generating") {
          return `<p class="message-status-text">${escapeHtml(statusMeta.text)}</p>`;
        }
        if (isActive) {
          return [
            hasContent ? formatRichMessage(content) : `<p class="message-status-text">${escapeHtml(statusMeta.text)}</p>`,
            `<span class="message-streaming-indicator" aria-label="${escapeHtml(statusMeta.text)}"></span>`,
          ].join("");
        }
        return formatRichMessage(content);
      })();
      const attachments = role === "user"
        ? (state.messageAttachments[String(message.id)] || [])
        : [];
      const attachmentsMarkup = attachments.length
        ? `<div class="message-attachments" role="list" aria-label="Прикреплённые изображения">
            ${attachments.map((attachment) => `
              <a class="message-attachment" role="listitem" href="${escapeHtml(attachment.media_url || "")}" target="_blank" rel="noreferrer">
                <img src="${escapeHtml(attachment.thumbnail_url || "")}" alt="${escapeHtml(attachment.original_name || "Изображение")}" />
                <span>${escapeHtml(attachment.original_name || "Изображение")}</span>
              </a>
            `).join("")}
          </div>`
        : "";
      return `
        <div class="message-row message-row--${role} ${role === "assistant" ? `message-row--status-${escapeHtml(status)}` : ""}">
          <article class="message-card">
            <div class="message-card__top">
              <span class="message-card__author">${escapeHtml(author)}</span>
              <span class="message-card__top-meta">
                ${role === "assistant" && statusMeta.label ? `<span class="message-status-badge message-status-badge--${escapeHtml(status)}">${escapeHtml(statusMeta.label)}</span>` : ""}
                <span class="message-card__time">${escapeHtml(formatDateTime(message.created_at))}</span>
              </span>
            </div>
            ${attachmentsMarkup}
            <div class="message-card__body">${body}</div>
            ${canCopy || canExportVision || (role === "assistant" && status === "failed")
              ? `<div class="message-card__actions">
                  ${role === "assistant" && status === "failed" ? `<button class="message-copy-button" type="button" data-retry-message-index="${index}">Повторить</button>` : ""}
                  ${canExportVision ? `<button class="message-copy-button" type="button" data-vision-rag-index="${index}">В RAG</button>` : ""}
                  ${canCopy ? `<button class="message-copy-button" type="button" data-copy-index="${index}">Скопировать</button>` : ""}
                </div>`
              : ""}
          </article>
        </div>
      `;
    })
    .join("");
  requestAnimationFrame(() => {
    syncMessageScrollState();
    observeMessageScrollEnd();
  });
}

async function retryFailedAssistantMessage(messageIndex) {
  const index = Number(messageIndex);
  if (!Number.isFinite(index) || index < 0) return;
  let userMessage = null;
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    if (state.messages[cursor]?.role === "user" && String(state.messages[cursor]?.content || "").trim()) {
      userMessage = state.messages[cursor];
      break;
    }
  }
  if (!userMessage) {
    setFooter("Не нашёл исходное сообщение для повтора.", "warning");
    return;
  }
  await sendPromptText(userMessage.content, { clearInput: false });
}

function renderModelControls() {
  if (!els.llmModelSelect || !els.recommendedModels) return;

  const installedByName = new Map(state.installedModels.map((item) => [item.name, item]));
  const catalogItems = getCatalogModels().length
    ? getCatalogModels()
    : state.installedModels.map((item) => ({ id: item.name, title: item.name, recommended: false }));
  const utilityItems = getUtilityModels();
  const catalogIds = catalogItems.map((item) => getModelId(item)).filter(Boolean);
  const installedCatalogIds = catalogItems
    .filter((item) => isRuntimeModelInstalled(item, installedByName))
    .map((item) => getModelId(item));
  const optionIds = new Set([AUTO_MODEL_ID, LOCAL_CALCULATOR_MODEL_ID, ...catalogIds]);

  const optionsMarkup = catalogItems.length
    ? [
      '<option value="" hidden>Модель не выбрана</option>',
      `<option value="${AUTO_MODEL_ID}" data-label="${escapeHtml(AUTO_MODEL_TITLE)}" data-help="${escapeHtml(AUTO_MODEL_HELP)}">${escapeHtml(AUTO_MODEL_TITLE)}</option>`,
      `<option value="${LOCAL_CALCULATOR_MODEL_ID}" data-label="${escapeHtml(LOCAL_CALCULATOR_TITLE)}" data-help="${escapeHtml(LOCAL_CALCULATOR_HELP)}">${escapeHtml(LOCAL_CALCULATOR_TITLE)}</option>`,
      ...catalogItems.map((item) => {
        const id = getModelId(item);
        const title = getModelTitle(item);
        const help = getModelTooltip(item, { short: true });
        const installed = isRuntimeModelInstalled(item, installedByName);
        const suffix = installed ? "" : " (не загружена)";
        return `<option value="${escapeHtml(id)}" data-label="${escapeHtml(title)}" data-help="${escapeHtml(help)}" data-model-category="${escapeHtml(item.category || "")}" data-model-weight="${escapeHtml(item.weight || "")}">${escapeHtml(title + suffix)}</option>`;
      }),
    ].join("")
    : '<option value="">Нет доступных моделей</option>';

  [els.llmModelSelect, els.quickModelSelect].filter(Boolean).forEach((select) => {
    select.innerHTML = optionsMarkup;
    select.disabled = !catalogItems.length;
  });

  const preferredModel = state.selectedLlmModel || readStored(STORAGE_KEYS.llmModel, "");
  if (preferredModel && optionIds.has(preferredModel)) {
    els.llmModelSelect.value = preferredModel;
    if (els.quickModelSelect) {
      els.quickModelSelect.value = preferredModel;
    }
  } else if (!preferredModel && installedCatalogIds.length) {
    els.llmModelSelect.value = installedCatalogIds[0];
    if (els.quickModelSelect) {
      els.quickModelSelect.value = installedCatalogIds[0];
    }
    state.selectedLlmModel = installedCatalogIds[0];
    writeStored(STORAGE_KEYS.llmModel, installedCatalogIds[0]);
  } else {
    state.selectedLlmModel = "";
    writeStored(STORAGE_KEYS.llmModel, "");
    els.llmModelSelect.value = "";
    if (els.quickModelSelect) {
      els.quickModelSelect.value = "";
    }
  }

  renderQuickModelPicker();

  els.recommendedModels.innerHTML = [...utilityItems, ...catalogItems]
    .map((item) => {
      const id = getModelId(item);
      const installed = isRuntimeModelInstalled(item, installedByName);
      const selected = id === state.selectedLlmModel;
      const utility = Boolean(item.utility);
      const runtimeState = getRuntimeModelState(item, installedByName);
      const stateClass = ` chip-button--${runtimeState}`;
      const meta = [
        getRuntimeModelStatusLabel(item, installedByName),
        item.category,
        item.weight,
      ].filter(Boolean).join(" • ");
      return `<button class="chip-button${installed ? " chip-button--installed" : ""}${selected ? " chip-button--active" : ""}${stateClass}" type="button" data-recommended-model="${escapeHtml(id)}" data-utility-model="${utility ? "1" : "0"}" data-installed="${installed ? "1" : "0"}" data-model-state="${escapeHtml(runtimeState)}">
        <span class="chip-button__label">${escapeHtml(getModelTitle(item))}</span>
        <span class="chip-button__meta">${escapeHtml(meta)}</span>
        ${renderModelInfoIcon(item, "chip-button__help")}
      </button>`;
    })
    .join("");

  renderLibraryPanels();
  renderChatModelLibrary();
  renderChatModelNotice();
  renderQuickThinkingControl(state.modelSettingsState?.effective?.ollama_think);
  updateSendButtonState();
  queueSyncAppSelects();
}

async function applySelectedLlmModel(nextModel, { closeMenu = true } = {}) {
  const modelName = String(nextModel || "").trim();
  if (!modelName) return;

  state.selectedLlmModel = modelName;
  writeStored(STORAGE_KEYS.llmModel, state.selectedLlmModel);
  if (closeMenu) {
    closeQuickModelMenu();
  }

  [els.llmModelSelect, els.quickModelSelect].filter(Boolean).forEach((select) => {
    const hasOption = Array.from(select.options || []).some((option) => option.value === modelName);
    if (hasOption) {
      select.value = modelName;
    }
  });

  renderModelControls();
  renderContextSummary();
  renderModelSettings();
  if (state.currentSessionId && state.selectedLlmModel) {
    await updateCurrentSessionMeta({ model_name: state.selectedLlmModel });
  }
  await refreshModelSettings({ silent: true });
  await maybePreloadManualModel(modelName);
}

async function maybePreloadManualModel(modelName) {
  const target = String(modelName || "").trim();
  if (!target || target === AUTO_MODEL_ID || target === LOCAL_CALCULATOR_MODEL_ID || !state.activeProfileId) return;
  const settings = (getActiveProfilePreferences()?.settings || {});
  if (!settings.preload_model_on_manual_select) return;
  const installed = state.installedModels.some((item) => item.name === target);
  if (!installed) return;
  try {
    await request("/models/preload", {
      method: "POST",
      body: {
        model: target,
        profile_id: state.activeProfileId,
      },
    });
    setFooter(`Модель ${target} предварительно загружена в Ollama.`, "info");
  } catch (error) {
    setFooter(`Не удалось предварительно загрузить ${target}: ${error.message || error}`, "warning");
  }
}

function renderChatModelLibrary() {
  if (!els.chatModelLibrary) return;
  if (!state.libraryPanels.chat) {
    els.chatModelLibrary.innerHTML = "";
    return;
  }

  const installedByName = new Map(state.installedModels.map((item) => [item.name, item]));
  const catalogItems = [...getUtilityModels(), ...getCatalogModels()];

  if (!catalogItems.length) {
    els.chatModelLibrary.innerHTML = '<p class="subtle">Каталог Ollama-моделей пока пуст.</p>';
    return;
  }

  els.chatModelLibrary.innerHTML = catalogItems
    .map((item) => {
      const name = getModelId(item);
      const runtimeInfo = installedByName.get(name) || item.runtime || null;
      const runtimeInstalled = isRuntimeModelInstalled(item, installedByName);
      const selected = state.selectedLlmModel === name;
      const runtimeActive = Boolean(item.active || runtimeInfo?.active);
      const task = getActiveChatDownload(name);
      const utility = Boolean(item.utility);
      const runtimeState = task ? "downloading" : getRuntimeModelState(item, installedByName);
      const statusTone = {
        active: "active",
        installed: "success",
        downloading: "warning",
        partial: "warning",
        configured: "muted",
        missing: "muted",
      }[runtimeState] || "muted";
      const statusLabel = task ? (task.state || "running") : getRuntimeModelStatusLabel(item, installedByName);
      const statusBadge = `<span class="status-badge status-badge--${escapeHtml(statusTone)}">${escapeHtml(statusLabel)}</span>`;
      const meta = [
        `ID: ${name}`,
        `Runtime: ${runtimeInstalled ? "installed" : "missing"}`,
        item.category ? `Категория: ${item.category}` : null,
        item.weight ? `Вес: ${item.weight}` : null,
        runtimeInfo?.details?.quantization ? `Quant: ${runtimeInfo.details.quantization}` : null,
        runtimeInfo?.size_gb ? `${runtimeInfo.size_gb} GB` : null,
        item.storage?.storage_size_gb && !runtimeInstalled ? `Storage: ${item.storage.storage_size_gb} GB` : null,
        runtimeInfo?.modified_at ? formatDateTime(runtimeInfo.modified_at) : null,
      ].filter(Boolean).join(" • ");
      const note = getModelRuntimeNote(item, task, installedByName);
      return `
        <article class="model-card${runtimeInstalled ? " model-card--installed" : ""}${selected ? " model-card--active" : ""} model-card--${escapeHtml(runtimeState)}">
          <div class="model-card__head">
            <div>
              <h5 class="model-card__title">${escapeHtml(getModelTitle(item))}</h5>
              <p class="model-card__meta">${escapeHtml(meta || name)}</p>
            </div>
            <div class="model-card__badges">
              ${statusBadge}
              ${runtimeActive ? '<span class="status-badge status-badge--active">В памяти</span>' : ""}
              ${selected ? '<span class="status-badge status-badge--selected">Выбрана</span>' : ""}
              ${item.partial_blob_found && !item.partial ? '<span class="status-badge status-badge--warning">Partial blob</span>' : ""}
              ${item.configured ? '<span class="status-badge status-badge--configured">Configured</span>' : ""}
              ${item.missing ? '<span class="status-badge status-badge--missing">Missing</span>' : ""}
              ${renderModelBadges(item)}
            </div>
          </div>
          <p class="model-card__note">${escapeHtml(note)}</p>
          <div class="button-row">
            ${runtimeInstalled && !utility ? `<button class="button ${selected ? "button--primary" : "button--ghost"}" type="button" data-chat-model-action="select" data-chat-model="${escapeHtml(name)}">Выбрать</button>` : ""}
            ${runtimeInstalled ? "" : `<button class="button button--ghost" type="button" data-chat-model-action="download" data-chat-model="${escapeHtml(name)}">${escapeHtml(getModelActionLabel(item, installedByName))}</button>`}
            <button class="button button--ghost" type="button" data-chat-model-action="update" data-chat-model="${escapeHtml(name)}">Обновить</button>
            ${runtimeInstalled ? `<button class="button button--ghost" type="button" data-chat-model-action="delete" data-chat-model="${escapeHtml(name)}">Удалить</button>` : ""}
            ${renderModelInfoButton(item)}
          </div>
        </article>
      `;
    })
    .join("");
}

function visionSettingsValues() {
  const settings = getActiveProfilePreferences()?.settings || {};
  return {
    chat_images_enabled: settings.chat_images_enabled !== false,
    vision_model: String(settings.vision_model || "auto"),
    vision_num_ctx: Math.min(131072, Math.max(4096, Number(settings.vision_num_ctx) || 8192)),
    vision_fallback: String(settings.vision_fallback || "vision_context"),
    ocr_assist: String(settings.ocr_assist || "auto"),
    ocr_language: String(settings.ocr_language || ""),
    max_images_per_message: Math.min(10, Math.max(1, Number(settings.max_images_per_message) || 1)),
    chat_image_max_file_bytes: Number(settings.chat_image_max_file_bytes) || 20 * 1024 * 1024,
    chat_image_max_total_bytes: Number(settings.chat_image_max_total_bytes) || 40 * 1024 * 1024,
    chat_image_max_pixels: Number(settings.chat_image_max_pixels) || 16_000_000,
    chat_image_max_side: Number(settings.chat_image_max_side) || 4096,
  };
}

function renderVisionModelLibrary() {
  if (!els.visionModelLibrary) return;
  const installedByName = new Map(state.installedModels.map((item) => [item.name, item]));
  const selectedVisionModel = visionSettingsValues().vision_model;
  const models = Array.isArray(state.visionModels) ? state.visionModels : [];
  if (!models.length) {
    els.visionModelLibrary.innerHTML = '<p class="subtle">Vision-каталог недоступен.</p>';
    return;
  }
  els.visionModelLibrary.innerHTML = models.map((item) => {
    const name = getModelId(item);
    const runtimeInfo = installedByName.get(name) || item.runtime || null;
    const installed = isRuntimeModelInstalled(item, installedByName);
    const confirmed = Boolean(installed && item.capabilities_confirmed);
    const runtimeCapabilities = confirmed
      ? (runtimeInfo?.capabilities || item.capabilities || [])
      : [];
    const task = getActiveChatDownload(name);
    const selected = selectedVisionModel === name;
    const stateLabel = task
      ? String(task.state || "running")
      : (confirmed ? "Vision подтверждён" : installed ? "Capability не подтверждён" : "Не загружена");
    const tone = confirmed ? "success" : task ? "warning" : installed ? "warning" : "muted";
    const declared = Array.isArray(item.declared_capabilities) ? item.declared_capabilities.join(", ") : "text, vision";
    const runtime = runtimeCapabilities.length ? runtimeCapabilities.join(", ") : "не подтверждено";
    const size = runtimeInfo?.size_gb
      ? `${runtimeInfo.size_gb} GB runtime`
      : item.approx_size_gb ? `≈ ${item.approx_size_gb} GB` : "";
    return `
      <article class="model-card${installed ? " model-card--installed" : ""}${selected ? " model-card--active" : ""}">
        <div class="model-card__head">
          <div>
            <h5 class="model-card__title">${escapeHtml(getModelTitle(item))}</h5>
            <p class="model-card__meta">${escapeHtml([`ID: ${name}`, size, item.weight].filter(Boolean).join(" • "))}</p>
          </div>
          <div class="model-card__badges">
            <span class="status-badge status-badge--${tone}">${escapeHtml(stateLabel)}</span>
            ${selected ? '<span class="status-badge status-badge--selected">Основная</span>' : ""}
          </div>
        </div>
        <p class="model-card__note">${escapeHtml(item.description || "")}</p>
        <p class="model-card__meta">Declared: ${escapeHtml(declared)} • Runtime confirmed: ${escapeHtml(runtime)}</p>
        <div class="button-row">
          <button class="button ${selected ? "button--primary" : "button--ghost"}" type="button" data-vision-model-action="select" data-vision-model="${escapeHtml(name)}">Основная</button>
          ${installed ? "" : `<button class="button button--ghost" type="button" data-vision-model-action="download" data-vision-model="${escapeHtml(name)}">Загрузить</button>`}
          <button class="button button--ghost" type="button" data-vision-model-action="update" data-vision-model="${escapeHtml(name)}">Обновить</button>
          ${installed ? `<button class="button button--ghost" type="button" data-vision-model-action="delete" data-vision-model="${escapeHtml(name)}">Удалить</button>` : ""}
        </div>
      </article>
    `;
  }).join("");
}

function renderVisionSettings() {
  const values = visionSettingsValues();
  const profileDisabled = !state.activeProfileId;
  const installedVision = state.visionModels.filter((item) => item.runtime_installed);
  const confirmedVision = installedVision.filter((item) => item.capabilities_confirmed);
  if (els.visionRuntimeSummary) {
    els.visionRuntimeSummary.textContent = confirmedVision.length
      ? `Готово: ${confirmedVision.map((item) => getModelId(item)).join(", ")}`
      : installedVision.length
        ? "Модель найдена, но Ollama ещё не подтвердил vision capability."
        : "Vision-модели не установлены. Начните с Qwen2.5-VL 3B.";
  }
  if (els.chatImagesEnabledToggle) els.chatImagesEnabledToggle.checked = values.chat_images_enabled;
  if (els.visionModelSelect) els.visionModelSelect.value = values.vision_model;
  if (els.visionFallbackSelect) els.visionFallbackSelect.value = values.vision_fallback;
  if (els.visionNumCtxInput) els.visionNumCtxInput.value = String(values.vision_num_ctx);
  if (els.visionOcrAssistSelect) els.visionOcrAssistSelect.value = values.ocr_assist;
  if (els.visionOcrLanguageInput) els.visionOcrLanguageInput.value = values.ocr_language;
  if (els.visionMaxImagesInput) els.visionMaxImagesInput.value = String(values.max_images_per_message);
  if (els.visionMaxFileMbInput) els.visionMaxFileMbInput.value = String(Math.round(values.chat_image_max_file_bytes / 1024 / 1024));
  if (els.visionMaxTotalMbInput) els.visionMaxTotalMbInput.value = String(Math.round(values.chat_image_max_total_bytes / 1024 / 1024));
  if (els.visionMaxMegapixelsInput) els.visionMaxMegapixelsInput.value = String(Math.round(values.chat_image_max_pixels / 1_000_000));
  if (els.visionMaxSideInput) els.visionMaxSideInput.value = String(values.chat_image_max_side);
  [
    els.chatImagesEnabledToggle,
    els.visionModelSelect,
    els.visionFallbackSelect,
    els.visionNumCtxInput,
    els.visionOcrAssistSelect,
    els.visionOcrLanguageInput,
    els.visionMaxImagesInput,
    els.visionMaxFileMbInput,
    els.visionMaxTotalMbInput,
    els.visionMaxMegapixelsInput,
    els.visionMaxSideInput,
    els.saveVisionSettingsButton,
    els.resetVisionSettingsButton,
  ].filter(Boolean).forEach((control) => {
    control.disabled = profileDisabled;
  });
  if (els.visionCacheSummary) {
    const cache = state.visionCache;
    els.visionCacheSummary.textContent = cache
      ? `${cache.attachment_count || 0} файлов • ${formatBytes(cache.total_bytes || 0)} • active: ${cache.active_count || 0}`
      : "Нет данных";
  }
  [els.refreshVisionCacheButton, els.cleanupVisionOrphansButton, els.cleanupVisionCacheButton]
    .filter(Boolean)
    .forEach((button) => {
      button.disabled = profileDisabled || state.visionCacheBusy;
    });
  renderVisionModelLibrary();
  queueSyncAppSelects();
}

async function saveVisionSettingsFlow(settingsOverride = null) {
  if (!state.activeProfileId) return;
  const mb = 1024 * 1024;
  const settings = settingsOverride || {
    chat_images_enabled: Boolean(els.chatImagesEnabledToggle?.checked),
    vision_model: String(els.visionModelSelect?.value || "auto"),
    vision_num_ctx: Number(els.visionNumCtxInput?.value || 8192),
    vision_fallback: String(els.visionFallbackSelect?.value || "vision_context"),
    ocr_assist: String(els.visionOcrAssistSelect?.value || "auto"),
    ocr_language: String(els.visionOcrLanguageInput?.value || "").trim(),
    max_images_per_message: Number(els.visionMaxImagesInput?.value || 1),
    chat_image_max_file_bytes: Number(els.visionMaxFileMbInput?.value || 20) * mb,
    chat_image_max_total_bytes: Number(els.visionMaxTotalMbInput?.value || 40) * mb,
    chat_image_max_pixels: Number(els.visionMaxMegapixelsInput?.value || 16) * 1_000_000,
    chat_image_max_side: Number(els.visionMaxSideInput?.value || 4096),
  };
  setInlineStatus(els.visionSettingsStatus, "Сохраняю Vision-настройки…", "warning");
  const updated = await saveActiveProfilePreferences({ settings });
  if (!updated) {
    setInlineStatus(els.visionSettingsStatus, "Не удалось сохранить Vision-настройки.", "error");
    return;
  }
  renderVisionSettings();
  setInlineStatus(els.visionSettingsStatus, "Vision-настройки сохранены для активного профиля.", "success");
}

async function resetVisionSettingsFlow() {
  await saveVisionSettingsFlow({
    chat_images_enabled: true,
    vision_model: "auto",
    vision_num_ctx: 8192,
    vision_fallback: "vision_context",
    ocr_assist: "auto",
    ocr_language: "",
    max_images_per_message: 1,
    chat_image_max_file_bytes: 20 * 1024 * 1024,
    chat_image_max_total_bytes: 40 * 1024 * 1024,
    chat_image_max_pixels: 16_000_000,
    chat_image_max_side: 4096,
  });
}

async function loadVisionCache({ silent = false } = {}) {
  if (!state.activeProfileId) {
    state.visionCache = null;
    renderVisionSettings();
    return;
  }
  try {
    state.visionCache = await request(`/chat/attachments/cache?profile_id=${encodeURIComponent(state.activeProfileId)}`);
  } catch (error) {
    if (!silent) setInlineStatus(els.visionSettingsStatus, `Кэш недоступен: ${error.message || error}`, "error");
  } finally {
    renderVisionSettings();
  }
}

async function cleanupVisionCache(scope) {
  if (!state.activeProfileId || state.visionCacheBusy) return;
  const label = scope === "orphans" ? "orphan-файлы" : "весь image-кэш профиля";
  const approved = await openConfirmDialog({
    eyebrow: "Очистка Vision-кэша",
    title: `Удалить ${label}?`,
    message: scope === "orphans"
      ? "Будут удалены только непривязанные файлы старше 24 часов. Активные задачи будут пропущены."
      : "Будут удалены изображения из истории этого профиля. Активные задачи будут пропущены.",
    confirmLabel: "Удалить",
  });
  if (!approved) return;
  state.visionCacheBusy = true;
  renderVisionSettings();
  try {
    const result = await request("/chat/attachments/cleanup", {
      method: "POST",
      body: {
        scope,
        profile_id: state.activeProfileId,
        temporary_ttl_seconds: 24 * 60 * 60,
      },
    });
    await loadVisionCache({ silent: true });
    setInlineStatus(
      els.visionSettingsStatus,
      `Удалено: ${result.deleted_count || 0}, освобождено: ${formatBytes(result.deleted_bytes || 0)}, active skipped: ${result.skipped_active_count || 0}.`,
      "success",
    );
  } catch (error) {
    setInlineStatus(els.visionSettingsStatus, `Очистка не выполнена: ${error.message || error}`, "error");
  } finally {
    state.visionCacheBusy = false;
    renderVisionSettings();
  }
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
  const profileDisabled = !profile;
  const { effective = {}, overrides = {} } = state.modelSettingsState || {};
  const values = {
    temperature: overrides.temperature ?? effective.temperature ?? "",
    max_tokens: overrides.max_tokens ?? effective.max_tokens ?? "",
    num_ctx: overrides.num_ctx ?? effective.num_ctx ?? "",
    mem_turns: overrides.mem_turns ?? effective.mem_turns ?? "",
    streaming_enabled: activeProfileStreamingEnabled(),
    ollama_keep_alive: overrides.ollama_keep_alive ?? effective.ollama_keep_alive ?? defaultKeepAliveForModel(modelName),
    ollama_think: overrides.ollama_think ?? effective.ollama_think ?? "auto",
    max_resident_target_models: overrides.max_resident_target_models ?? effective.max_resident_target_models ?? RESIDENCY_DEFAULTS.max_resident_target_models,
    allow_light_with_heavy: overrides.allow_light_with_heavy ?? effective.allow_light_with_heavy ?? RESIDENCY_DEFAULTS.allow_light_with_heavy,
    single_large_target_model: overrides.single_large_target_model ?? effective.single_large_target_model ?? RESIDENCY_DEFAULTS.single_large_target_model,
    preload_model_on_manual_select: overrides.preload_model_on_manual_select ?? effective.preload_model_on_manual_select ?? RESIDENCY_DEFAULTS.preload_model_on_manual_select,
    auto_target_keep_alive: overrides.auto_target_keep_alive ?? effective.auto_target_keep_alive ?? RESIDENCY_DEFAULTS.auto_target_keep_alive,
    manual_keep_alive: overrides.manual_keep_alive ?? effective.manual_keep_alive ?? RESIDENCY_DEFAULTS.manual_keep_alive,
    code_model_keep_alive: overrides.code_model_keep_alive ?? effective.code_model_keep_alive ?? RESIDENCY_DEFAULTS.code_model_keep_alive,
    heavy_model_keep_alive: overrides.heavy_model_keep_alive ?? effective.heavy_model_keep_alive ?? RESIDENCY_DEFAULTS.heavy_model_keep_alive,
    router_keep_alive: overrides.router_keep_alive ?? effective.router_keep_alive ?? RESIDENCY_DEFAULTS.router_keep_alive,
    show_router_thinking_toggle: Boolean((getActiveProfilePreferences()?.settings || {}).show_router_thinking_toggle),
  };
  renderQuickThinkingControl(values.ollama_think);

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
    els.memTurnsInput.title = "Общая память диалога для активного профиля. Применяется ко всем chat-моделям, включая Auto.";
  }
  if (els.streamingEnabledToggle) {
    els.streamingEnabledToggle.disabled = profileDisabled;
    els.streamingEnabledToggle.checked = Boolean(values.streaming_enabled);
    els.streamingEnabledToggle.title = "Применяется только к финальной answer-модели. Auto-router не отдаёт token delta.";
  }
  if (els.ollamaKeepAliveInput) {
    const keepAlive = parseKeepAliveValue(values.ollama_keep_alive, defaultKeepAliveForModel(modelName));
    els.ollamaKeepAliveInput.disabled = disabled;
    els.ollamaKeepAliveInput.value = keepAlive.amount;
    els.ollamaKeepAliveInput.title = "Сколько Ollama держит модель в RAM/GPU после ответа. 0 секунд — выгружать сразу.";
  }
  if (els.ollamaKeepAliveUnitSelect) {
    const keepAlive = parseKeepAliveValue(values.ollama_keep_alive, defaultKeepAliveForModel(modelName));
    els.ollamaKeepAliveUnitSelect.disabled = disabled;
    els.ollamaKeepAliveUnitSelect.value = keepAlive.unit;
    queueSyncAppSelects();
  }
  if (els.maxResidentTargetModelsSelect) {
    els.maxResidentTargetModelsSelect.disabled = profileDisabled;
    els.maxResidentTargetModelsSelect.value = String(Math.max(1, Math.min(5, Number(values.max_resident_target_models) || RESIDENCY_DEFAULTS.max_resident_target_models)));
    els.maxResidentTargetModelsSelect.title = "Router qwen3:0.6b в этот лимит не входит.";
  }
  if (els.allowLightWithHeavyToggle) {
    els.allowLightWithHeavyToggle.disabled = profileDisabled;
    els.allowLightWithHeavyToggle.checked = Boolean(values.allow_light_with_heavy);
    els.allowLightWithHeavyToggle.title = "Если выключено, при запуске Mistral Nemo остальные target-модели выгружаются.";
  }
  if (els.singleLargeTargetModelToggle) {
    els.singleLargeTargetModelToggle.disabled = profileDisabled;
    els.singleLargeTargetModelToggle.checked = Boolean(values.single_large_target_model);
    els.singleLargeTargetModelToggle.title = "Если включено, LocalGPT не держит одновременно две medium/code/heavy target-модели.";
  }
  if (els.preloadManualSelectToggle) {
    els.preloadManualSelectToggle.disabled = profileDisabled;
    els.preloadManualSelectToggle.checked = Boolean(values.preload_model_on_manual_select);
    els.preloadManualSelectToggle.title = "Если включено, ручной выбор модели сразу загружает её в Ollama.";
  }
  if (els.showRouterThinkingToggle) {
    els.showRouterThinkingToggle.disabled = profileDisabled;
    els.showRouterThinkingToggle.checked = Boolean(values.show_router_thinking_toggle);
    els.showRouterThinkingToggle.title = "Показывать switch Thinking для Auto / Smart Router в верхнем меню выбора модели.";
  }
  setKeepAliveControl(
    els.autoTargetKeepAliveInput,
    els.autoTargetKeepAliveUnitSelect,
    values.auto_target_keep_alive,
    RESIDENCY_DEFAULTS.auto_target_keep_alive,
    profileDisabled,
  );
  setKeepAliveControl(
    els.manualKeepAliveInput,
    els.manualKeepAliveUnitSelect,
    values.manual_keep_alive,
    RESIDENCY_DEFAULTS.manual_keep_alive,
    profileDisabled,
  );
  setKeepAliveControl(
    els.codeKeepAliveInput,
    els.codeKeepAliveUnitSelect,
    values.code_model_keep_alive,
    RESIDENCY_DEFAULTS.code_model_keep_alive,
    profileDisabled,
  );
  setKeepAliveControl(
    els.heavyKeepAliveInput,
    els.heavyKeepAliveUnitSelect,
    values.heavy_model_keep_alive,
    RESIDENCY_DEFAULTS.heavy_model_keep_alive,
    profileDisabled,
  );
  setKeepAliveControl(
    els.routerKeepAliveInput,
    els.routerKeepAliveUnitSelect,
    values.router_keep_alive,
    RESIDENCY_DEFAULTS.router_keep_alive,
    profileDisabled,
  );
  if (els.saveModelSettingsButton) {
    els.saveModelSettingsButton.disabled = profileDisabled || !modelName;
  }
  if (els.resetModelSettingsButton) {
    els.resetModelSettingsButton.disabled = profileDisabled || !modelName;
  }
  renderQuickThinkingControl(values.ollama_think);
  renderQuickModelPicker();
  queueSyncAppSelects();
  renderAsrPipelineSettings();
}

function renderQuickThinkingControl(rawValue = null) {
  if (!els.quickThinkingControl || !els.quickThinkingButton || !els.quickThinkingMenu) return;
  const modelName = state.selectedLlmModel || els.llmModelSelect?.value || "";
  const supported = modelSupportsThinking(modelName);
  const normalized = normalizeOllamaThink(rawValue, "auto");
  const visibleValue = normalized === "off" ? "off" : "on";
  const disabled = !supported || !state.activeProfileId || !modelName;
  const hint = supported
    ? "Thinking влияет на скорость, CPU и полноту рассуждения для моделей, которые поддерживают этот режим."
    : "Выбранная модель не объявлена как thinking-capable; параметр не отправляется.";

  els.quickThinkingControl.dataset.thinkingMode = visibleValue;
  els.quickThinkingButton.disabled = disabled;
  els.quickThinkingButton.textContent = "Thinking";
  els.quickThinkingControl.hidden = true;
  els.quickThinkingControl.classList.toggle("thinking-mode-control--enabled", supported && visibleValue === "on");
  els.quickThinkingControl.classList.toggle("thinking-mode-control--disabled", !supported);
  els.quickThinkingControl.title = hint;

  if (els.quickThinkingMobileControl) {
    els.quickThinkingMobileControl.dataset.thinkingMode = visibleValue;
    els.quickThinkingMobileControl.hidden = true;
    els.quickThinkingMobileControl.title = hint;
  }
  if (els.quickThinkingMobileButton) {
    els.quickThinkingMobileButton.disabled = disabled;
    els.quickThinkingMobileButton.setAttribute("aria-label", `Thinking: ${visibleValue === "on" ? "включено" : "выключено"}`);
  }

  [els.quickThinkingMenu, els.quickThinkingMobileMenu].filter(Boolean).forEach((menu) => {
    menu.querySelectorAll("[data-thinking-mode]").forEach((button) => {
      const active = button.getAttribute("data-thinking-mode") === visibleValue;
      button.classList.toggle("thinking-mode-menu__item--active", active);
      button.setAttribute("aria-checked", active ? "true" : "false");
    });
  });

  if (disabled) {
    closeQuickThinkingMenu();
  }
}

function defaultKeepAliveForModel(modelName = "") {
  const target = String(modelName || "").trim();
  if (target === "qwen3:0.6b") return RESIDENCY_DEFAULTS.router_keep_alive;
  if (target === "mistral-nemo:12b") return RESIDENCY_DEFAULTS.heavy_model_keep_alive;
  if (["qwen2.5-coder:7b", "deepseek-coder:6.7b"].includes(target)) return RESIDENCY_DEFAULTS.code_model_keep_alive;
  return RESIDENCY_DEFAULTS.manual_keep_alive;
}

function parseKeepAliveValue(value, fallback = "1m") {
  const raw = String(value || fallback || "1m").trim().replace(",", ".");
  const match = raw.match(/^(\d+(?:\.\d+)?)\s*([smh])?$/i);
  if (!match) {
    return parseKeepAliveValue(fallback && fallback !== raw ? fallback : "1m", "1m");
  }
  const amount = Math.max(0, Number(match[1]));
  const unit = String(match[2] || "m").toLowerCase();
  return {
    amount: Number.isInteger(amount) ? String(amount) : String(amount).replace(/\.0+$/, ""),
    unit: ["s", "m", "h"].includes(unit) ? unit : "m",
  };
}

function collectKeepAliveValue() {
  return collectKeepAliveFromControl(els.ollamaKeepAliveInput, els.ollamaKeepAliveUnitSelect);
}

function setKeepAliveControl(input, unitSelect, value, fallback = "1m", disabled = false) {
  const keepAlive = parseKeepAliveValue(value, fallback);
  if (input) {
    input.disabled = disabled;
    input.value = keepAlive.amount;
  }
  if (unitSelect) {
    unitSelect.disabled = disabled;
    unitSelect.value = keepAlive.unit;
  }
}

function collectKeepAliveFromControl(input, unitSelect) {
  const rawAmount = String(input?.value || "").trim().replace(",", ".");
  if (!rawAmount) return null;
  const amount = Math.max(0, Number(rawAmount));
  if (!Number.isFinite(amount)) return null;
  const unit = ["s", "m", "h"].includes(unitSelect?.value)
    ? unitSelect.value
    : "m";
  if (amount === 0) return "0s";
  const normalizedAmount = Number.isInteger(amount) ? String(amount) : String(amount).replace(/\.0+$/, "");
  return `${normalizedAmount}${unit}`;
}

function collectResidencySettings() {
  const maxResident = Number.parseInt(els.maxResidentTargetModelsSelect?.value || "", 10);
  return {
    max_resident_target_models: Number.isFinite(maxResident) ? Math.max(1, Math.min(5, maxResident)) : RESIDENCY_DEFAULTS.max_resident_target_models,
    allow_light_with_heavy: Boolean(els.allowLightWithHeavyToggle?.checked),
    single_large_target_model: Boolean(els.singleLargeTargetModelToggle?.checked),
    preload_model_on_manual_select: Boolean(els.preloadManualSelectToggle?.checked),
    show_router_thinking_toggle: Boolean(els.showRouterThinkingToggle?.checked),
    auto_target_keep_alive: collectKeepAliveFromControl(els.autoTargetKeepAliveInput, els.autoTargetKeepAliveUnitSelect) || RESIDENCY_DEFAULTS.auto_target_keep_alive,
    manual_keep_alive: collectKeepAliveFromControl(els.manualKeepAliveInput, els.manualKeepAliveUnitSelect) || RESIDENCY_DEFAULTS.manual_keep_alive,
    code_model_keep_alive: collectKeepAliveFromControl(els.codeKeepAliveInput, els.codeKeepAliveUnitSelect) || RESIDENCY_DEFAULTS.code_model_keep_alive,
    heavy_model_keep_alive: collectKeepAliveFromControl(els.heavyKeepAliveInput, els.heavyKeepAliveUnitSelect) || RESIDENCY_DEFAULTS.heavy_model_keep_alive,
    router_keep_alive: collectKeepAliveFromControl(els.routerKeepAliveInput, els.routerKeepAliveUnitSelect) || RESIDENCY_DEFAULTS.router_keep_alive,
  };
}

function asrPipelineSourceObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function normalizeAsrPipelineStage(stageKey, value = {}) {
  const defaults = ASR_PIPELINE_DEFAULTS[stageKey] || {};
  const source = asrPipelineSourceObject(value);
  const temperature = Number(source.temperature ?? defaults.temperature ?? 0.2);
  const maxTokens = Number.parseInt(source.max_tokens ?? defaults.max_tokens ?? 1200, 10);
  return {
    enabled: source.enabled === undefined ? defaults.enabled !== false : Boolean(source.enabled),
    model: String(source.model || "").trim(),
    temperature: Number.isFinite(temperature) ? temperature : Number(defaults.temperature || 0.2),
    max_tokens: Number.isFinite(maxTokens) && maxTokens > 0
      ? maxTokens
      : Number.parseInt(defaults.max_tokens || 1200, 10),
  };
}

function getAsrPipelineStageSettings(stageKey) {
  const defaults = asrPipelineSourceObject(state.asrPipelineSettingsState?.defaults?.pipeline);
  const effective = asrPipelineSourceObject(state.asrPipelineSettingsState?.effective?.pipeline);
  const overrides = asrPipelineSourceObject(state.asrPipelineSettingsState?.overrides?.pipeline);
  return normalizeAsrPipelineStage(stageKey, {
    ...(ASR_PIPELINE_DEFAULTS[stageKey] || {}),
    ...asrPipelineSourceObject(defaults[stageKey]),
    ...asrPipelineSourceObject(effective[stageKey]),
    ...asrPipelineSourceObject(overrides[stageKey]),
  });
}

function pipelineModelOptionsHtml(selectedValue = "", stageKey = "", stageEnabled = true) {
  const selected = String(selectedValue || "").trim();
  const installedNames = new Set(state.installedModels.map((item) => String(item?.name || "").trim()).filter(Boolean));
  const stageRecommendation = ASR_PIPELINE_RECOMMENDATIONS[stageKey] || null;
  const fallbackLabel = stageRecommendation?.primary
    ? `Рекомендованная модель (${stageRecommendation.primary})`
    : "Модель по умолчанию";
  const options = [
    `<option value="${ASR_PIPELINE_DISABLED_VALUE}"${stageEnabled ? "" : " selected"}>Не использовать</option>`,
    `<option value=""${stageEnabled && !selected ? " selected" : ""}>${escapeHtml(fallbackLabel)}</option>`,
  ];

  if (stageEnabled && selected && !ASR_PIPELINE_MODEL_IDS.includes(selected)) {
    const legacyLabel = ASR_PIPELINE_LEGACY_MODEL_IDS.has(selected)
      ? `${selected} (legacy, замените)`
      : `${selected} (вне каталога)`;
    options.push(`<option value="${escapeHtml(selected)}" selected>${escapeHtml(legacyLabel)}</option>`);
  }

  ASR_PIPELINE_MODEL_CATALOG.forEach((item) => {
    const markers = [];
    if (item.id === stageRecommendation?.primary) {
      markers.push("реком.");
    }
    if (!installedNames.has(item.id)) {
      markers.push("не загружена");
    }
    if (item.id === "qwen3:4b") {
      markers.push("experimental");
    }
    if (item.category === "code" || item.id.includes("coder")) {
      markers.push("code");
    }
    const label = `${item.id}${markers.length ? ` (${markers.join(", ")})` : ""}`;
    options.push(
      `<option value="${escapeHtml(item.id)}"${stageEnabled && item.id === selected ? " selected" : ""}>${escapeHtml(label)}</option>`,
    );
  });

  return options.join("");
}

function pipelineStageRecommendationHtml(stageKey, selectedModel = "") {
  const recommendation = ASR_PIPELINE_RECOMMENDATIONS[stageKey];
  if (!recommendation) return "";
  const stageSettings = getAsrPipelineStageSettings(stageKey);
  if (stageSettings.enabled === false) {
    return `
      <p class="pipeline-stage-row__recommendation">
        <strong>Стадия выключена.</strong>
      </p>
    `;
  }
  const selected = String(selectedModel || "").trim();
  const legacyWarning = selected && !ASR_PIPELINE_MODEL_IDS.includes(selected)
    ? ` Сейчас выбрана ${ASR_PIPELINE_LEGACY_MODEL_IDS.has(selected) ? "legacy-модель" : "модель вне pipeline-каталога"} ${selected}; лучше заменить на ${recommendation.primary}.`
    : "";
  return `
    <p class="pipeline-stage-row__recommendation">
      <span>${escapeHtml(recommendation.primary)}</span> ${escapeHtml(recommendation.text)}${escapeHtml(legacyWarning)}
    </p>
  `;
}

function clearEnhancedSelectsIn(container) {
  if (!container) return;
  state.appSelects.forEach((entry, select) => {
    if (container.contains(select) || container.contains(entry.wrapper)) {
      entry.observer?.disconnect();
      state.appSelects.delete(select);
    }
  });
}

function renderAsrPipelineSettings() {
  const profile = getActiveProfile();
  const disabled = !profile;
  const expanded = Boolean(state.asrPipelineSettingsExpanded);

  if (els.asrPipelineSettingsPanel) {
    els.asrPipelineSettingsPanel.classList.toggle("pipeline-settings-panel--collapsed", !expanded);
  }
  if (els.asrPipelineSettingsBody) {
    els.asrPipelineSettingsBody.hidden = !expanded;
  }
  if (els.asrPipelineSettingsToggleButton) {
    els.asrPipelineSettingsToggleButton.setAttribute("aria-expanded", expanded ? "true" : "false");
    els.asrPipelineSettingsToggleButton.title = expanded ? "Свернуть настройки анализа" : "Развернуть настройки анализа";
    els.asrPipelineSettingsToggleButton.setAttribute(
      "aria-label",
      expanded ? "Свернуть настройки анализа" : "Развернуть настройки анализа",
    );
  }
  if (els.asrPipelineSettingsSummary) {
    els.asrPipelineSettingsSummary.textContent = profile
      ? `${profile.name} • ASR pipeline`
      : "Профиль не выбран";
  }
  if (els.saveAsrPipelineSettingsButton) {
    els.saveAsrPipelineSettingsButton.disabled = disabled;
  }
  if (els.resetAsrPipelineSettingsButton) {
    els.resetAsrPipelineSettingsButton.disabled = disabled;
  }
  if (els.asrFullAnalysisEnabledToggle) {
    els.asrFullAnalysisEnabledToggle.disabled = !profile;
    els.asrFullAnalysisEnabledToggle.checked = asrFullAnalysisEnabled();
  }
  if (els.asrDiagnosticsEnabledToggle) {
    els.asrDiagnosticsEnabledToggle.disabled = !profile;
    els.asrDiagnosticsEnabledToggle.checked = asrDiagnosticsEnabled();
  }
  if (els.asrPipelineThinkSelect) {
    const { effective = {}, overrides = {} } = state.asrPipelineSettingsState || {};
    const rawThink = overrides.ollama_think ?? effective.ollama_think ?? "off";
    els.asrPipelineThinkSelect.disabled = !profile;
    els.asrPipelineThinkSelect.value = normalizeOllamaThink(rawThink, "off");
    queueSyncAppSelects();
  }
  if (els.asrAnalysisPromptInput && document.activeElement !== els.asrAnalysisPromptInput) {
    els.asrAnalysisPromptInput.disabled = !profile;
    els.asrAnalysisPromptInput.value = String(getActiveProfilePreferences()?.asr?.analysis_prompt || "");
  }
  if (!els.asrPipelineSettingsGrid) return;

  clearEnhancedSelectsIn(els.asrPipelineSettingsGrid);
  els.asrPipelineSettingsGrid.innerHTML = ASR_PIPELINE_STAGES
    .map((stage) => {
      const settings = getAsrPipelineStageSettings(stage.key);
      const stageDisabled = settings.enabled === false;
      return `
        <article class="pipeline-stage-row">
          <div class="pipeline-stage-row__title">
            <strong>${escapeHtml(stage.label)}</strong>
            <span>${escapeHtml(stage.key)}</span>
          </div>
          <label class="field">
            <span class="field__label">Модель</span>
            <select class="field__control" data-asr-pipeline-stage="${escapeHtml(stage.key)}" data-asr-pipeline-field="model"${disabled ? " disabled" : ""}>
              ${pipelineModelOptionsHtml(settings.model, stage.key, !stageDisabled)}
            </select>
          </label>
          <label class="field">
            <span class="field__label">Temp</span>
            <input class="field__control" type="number" min="0" max="2" step="0.05" value="${escapeHtml(String(settings.temperature))}" data-asr-pipeline-stage="${escapeHtml(stage.key)}" data-asr-pipeline-field="temperature"${disabled || stageDisabled ? " disabled" : ""} />
          </label>
          <label class="field">
            <span class="field__label">Max tokens</span>
            <input class="field__control" type="number" min="1" step="1" value="${escapeHtml(String(settings.max_tokens))}" data-asr-pipeline-stage="${escapeHtml(stage.key)}" data-asr-pipeline-field="max_tokens"${disabled || stageDisabled ? " disabled" : ""} />
          </label>
          ${pipelineStageRecommendationHtml(stage.key, settings.model)}
        </article>
      `;
    })
    .join("");

  els.asrPipelineSettingsGrid
    .querySelectorAll("select.field__control")
    .forEach((select) => enhanceAppSelect(select));
  queueSyncAppSelects();
}

function setAsrPipelineSettingsExpanded(isExpanded, { render = true } = {}) {
  state.asrPipelineSettingsExpanded = Boolean(isExpanded);
  writeStored(STORAGE_KEYS.asrPipelineSettingsOpen, state.asrPipelineSettingsExpanded ? "1" : "");
  if (render) {
    renderAsrPipelineSettings();
  }
}

function getAsrPipelineControl(stageKey, field) {
  const controls = els.asrPipelineSettingsGrid?.querySelectorAll("[data-asr-pipeline-stage][data-asr-pipeline-field]") || [];
  return Array.from(controls).find((control) => (
    control.dataset.asrPipelineStage === stageKey && control.dataset.asrPipelineField === field
  )) || null;
}

function collectAsrPipelineSettingsFromControls() {
  return ASR_PIPELINE_STAGES.reduce((acc, stage) => {
    const current = getAsrPipelineStageSettings(stage.key);
    const modelControl = getAsrPipelineControl(stage.key, "model");
    const temperatureControl = getAsrPipelineControl(stage.key, "temperature");
    const maxTokensControl = getAsrPipelineControl(stage.key, "max_tokens");
    const temperature = parseOptionalNumber(temperatureControl?.value, "float");
    const maxTokens = parseOptionalNumber(maxTokensControl?.value, "int");
    const selectedModel = String(modelControl?.value ?? current.model ?? "").trim();
    const stageEnabled = selectedModel !== ASR_PIPELINE_DISABLED_VALUE;
    acc[stage.key] = {
      enabled: stageEnabled,
      model: stageEnabled ? selectedModel : String(current.model || ASR_PIPELINE_DEFAULTS[stage.key]?.model || "").trim(),
      temperature: temperature ?? current.temperature,
      max_tokens: maxTokens ?? current.max_tokens,
    };
    return acc;
  }, {});
}

function buildModelSettingsPayload(overrides = {}) {
  const existing = state.modelSettingsState?.overrides || {};
  const payload = {
    profile_id: state.activeProfileId,
    model_name: state.selectedLlmModel || els.llmModelSelect?.value || "",
  };
  MODEL_SETTINGS_OVERRIDE_KEYS.forEach((key) => {
    payload[key] = Object.prototype.hasOwnProperty.call(existing, key) ? existing[key] : null;
  });
  return { ...payload, ...overrides };
}

function renderWhisperControls() {
  if (!els.whisperModelSelect || !els.promptPresetSelect) return;
  const items = getWhisperItems();
  const names = items.map((item) => item.name);
  if (!names.includes(state.selectedWhisperModel)) {
    state.selectedWhisperModel = names.includes(ASR_STUDIO_DEFAULT_MODEL)
      ? ASR_STUDIO_DEFAULT_MODEL
      : (names[0] || ASR_STUDIO_DEFAULT_MODEL);
  }
  els.whisperModelSelect.innerHTML = names
    .map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`)
    .join("");
  els.whisperModelSelect.value = state.selectedWhisperModel;
  els.promptPresetSelect.value = normalizePromptPreset(state.selectedPromptPreset);
  if (els.asrBeamSizeInput) {
    els.asrBeamSizeInput.value = String(normalizeAsrBeamSize(state.selectedAsrBeamSize));
  }
  if (els.asrThreadsInput) {
    els.asrThreadsInput.value = String(normalizeAsrThreads(state.selectedAsrThreads));
  }
  if (els.asrAnalysisPromptInput && document.activeElement !== els.asrAnalysisPromptInput) {
    els.asrAnalysisPromptInput.value = String(getActiveProfilePreferences()?.asr?.analysis_prompt || "");
  }

  if (els.asrSettingsStatus) {
    const selectedItem = items.find((item) => item.name === state.selectedWhisperModel);
    const isInstalled = Boolean(selectedItem?.installed);
    const isReady = isWhisperItemReady(selectedItem);
    const warning = getWhisperItemWarnings(selectedItem)[0] || "";
    const analysisLanguage = normalizeAsrAnalysisLanguage(getActiveProfilePreferences()?.asr?.analysis_language);
    const asrProfileSummary = `язык/prompt ${normalizePromptPreset(state.selectedPromptPreset)}, язык анализа ${analysisLanguage}, beam ${normalizeAsrBeamSize(state.selectedAsrBeamSize)}, threads ${normalizeAsrThreads(state.selectedAsrThreads)}`;
    setInlineStatus(
      els.asrSettingsStatus,
      isReady
        ? `ASR Studio профиля использует модель ${state.selectedWhisperModel}; ${asrProfileSummary}.`
        : isInstalled
          ? `ASR-модель ${state.selectedWhisperModel} скачана, но runtime не готов. ${warning || "Нажмите «Проверить», чтобы доскачать и собрать недостающие файлы."}`
          : `Для ASR Studio профиля выбрана модель ${state.selectedWhisperModel}, но она ещё не загружена локально.`,
      isReady ? "success" : "warning",
    );
  }

  renderLibraryPanels();
  renderAsrModelLibrary();
  renderAsrTool();
  renderVoiceModelMenu();
  renderVoiceRecordButton();
  queueSyncAppSelects();
}

function renderAsrModelLibrary() {
  if (!els.asrModelLibrary) return;
  if (!state.libraryPanels.asr) {
    els.asrModelLibrary.innerHTML = "";
    return;
  }
  const items = getWhisperItems().map((item) => ({ repo_id: "", ...item }));

  els.asrModelLibrary.innerHTML = items
    .map((item) => {
      const active = state.selectedWhisperModel === item.name;
      const isInstalled = Boolean(item.installed);
      const isReady = isWhisperItemReady(item);
      const warnings = getWhisperItemWarnings(item);
      const task = item.active_task || state.asrDownloads.find((entry) => entry.model === item.name && ["pending", "running"].includes(entry.state));
      const update = state.asrUpdateChecks[item.name];
      let badge = '<span class="status-badge">Не загружена</span>';
      if (task) {
        const percent = typeof task.percent === "number" && task.percent > 0 ? ` ${Math.round(task.percent)}%` : "";
        badge = `<span class="status-badge status-badge--warning">${escapeHtml((task.state || "running") + percent)}</span>`;
      } else if (update?.status === "update_available") {
        badge = '<span class="status-badge status-badge--warning">Есть обновление</span>';
      } else if (isReady) {
        badge = '<span class="status-badge status-badge--success">Готова</span>';
      } else if (isInstalled) {
        badge = '<span class="status-badge status-badge--warning">Требует CLI</span>';
      }
      const meta = [
        item.repo_id || null,
        item.local_revision ? `rev ${String(item.local_revision).slice(0, 8)}` : null,
      ].filter(Boolean).join(" • ");
      const note = task?.message || update?.message || warnings[0] || (isReady ? "Whisper-модель готова к транскрибации." : "Нажмите «Проверить», чтобы скачать модель и собрать whisper-cli.");
      const downloadLabel = isReady ? "Обновить" : isInstalled ? "Дособрать" : "Загрузить";
      const forceDownload = isReady ? "1" : "0";
      return `
        <article class="model-card${isInstalled ? " model-card--installed" : ""}${active ? " model-card--active" : ""}">
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
            <button class="button button--ghost" type="button" data-asr-model-action="download" data-asr-model="${escapeHtml(item.name)}" data-asr-force="${forceDownload}">${downloadLabel}</button>
            <button class="button button--ghost" type="button" data-asr-model-action="check" data-asr-model="${escapeHtml(item.name)}">Проверить</button>
            ${isInstalled ? `<button class="button button--ghost" type="button" data-asr-model-action="delete" data-asr-model="${escapeHtml(item.name)}">Удалить</button>` : ""}
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
    queueSyncAppSelects();
    return;
  }

  const selectedExists = state.ttsVoices.some((voice) => voice.id === state.selectedTtsVoiceId);
  if (!selectedExists) {
    state.selectedTtsVoiceId = state.ttsVoices[0]?.id || "";
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
  queueSyncAppSelects();
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
  applyTtsHistoryCollapsedState();
  renderTtsToolHistory();
  queueSyncAppSelects();
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
  closeAsrHistoryContextMenu();
  if (!state.asrToolHistory.length) {
    els.asrToolHistoryList.innerHTML = '<p class="subtle">История транскрибаций пока пуста.</p>';
    return;
  }

  const selectedId = Number(state.asrToolSelectedTranscriptId || 0);
  const search = String(state.asrToolHistorySearch || "").trim().toLowerCase();
  const visibleHistory = search
    ? state.asrToolHistory.filter((item) => {
      const haystack = [
        item.name,
        item.summary,
        item.content,
        item.language,
        item.labels?.file_name,
      ].filter(Boolean).join("\n").toLowerCase();
      return haystack.includes(search);
    })
    : state.asrToolHistory;
  if (!visibleHistory.length) {
    els.asrToolHistoryList.innerHTML = '<p class="subtle">Ничего не найдено.</p>';
    return;
  }
  const prioritized = selectedId
    ? [
      ...visibleHistory.filter((item) => Number(item.id) === selectedId),
      ...visibleHistory.filter((item) => Number(item.id) !== selectedId),
    ]
    : [...visibleHistory];

  els.asrToolHistoryList.innerHTML = prioritized.slice(0, 6)
    .map((item) => {
      const active = Number(item.id) === selectedId ? " tool-history__item--active" : "";
      const meta = [
        item.language || null,
        formatDateTime(item.updated_at || item.created_at),
      ].filter(Boolean).join(" • ");
      const title = getAsrTranscriptTitle(item);
      const preview = stripRichTextToPlain(item.summary || item.content || "");
      return `
        <article class="tool-history__item${active}">
          <button class="tool-history__content" type="button" data-asr-history-id="${escapeHtml(item.id)}">
            <span class="tool-history__title">${escapeHtml(title || "Транскрипт")}</span>
            <span class="tool-history__meta">${escapeHtml(meta || "Транскрипт")}</span>
            <span class="tool-history__preview">${escapeHtml(preview || "Нет превью")}</span>
          </button>
          <button class="tool-history__delete" type="button" data-asr-history-delete-id="${escapeHtml(item.id)}" title="Удалить запись" aria-label="Удалить запись">×</button>
        </article>
      `;
    })
    .join("");
}

function getAsrActionLabel(action) {
  return {
    clean: "очистка",
    summary: "быстрое саммари",
    smart_summary: "умное саммари",
    tasks: "задачи",
    full: "полный анализ",
  }[action] || "обработка";
}

function getAsrActionStageKeys(action) {
  return {
    clean: ["cleaner"],
    summary: ["summary"],
    smart_summary: ["structurer", "summary"],
    tasks: ["segmenter", "structurer"],
    full: ["segmenter", "speaker_resolver", "structurer", "summary"],
  }[action] || ASR_PIPELINE_STAGES.map((stage) => stage.key);
}

function asrRunStageEnabled(run, stageKey) {
  const pipelineSettings = run?.used_settings?.pipeline;
  if (!pipelineSettings || typeof pipelineSettings !== "object") return true;
  const stageSettings = pipelineSettings[stageKey];
  return !stageSettings || stageSettings.enabled !== false;
}

function getAsrPipelineStagesForDisplay(run, activeAction) {
  const action = activeAction || run?.action || "";
  const routeStageKeys = new Set(getAsrActionStageKeys(action));
  const timings = run?.stage_timings && typeof run.stage_timings === "object" ? run.stage_timings : {};
  const warningText = Array.isArray(run?.warnings) ? run.warnings.join("\n") : "";
  return ASR_PIPELINE_STAGES.filter((stage) => {
    const belongsToRoute = routeStageKeys.has(stage.key);
    const hasResult = Boolean(timings[stage.key]) || warningText.includes(`${stage.key}_failed`);
    if (!belongsToRoute && !hasResult) return false;
    if (run && belongsToRoute && !asrRunStageEnabled(run, stage.key) && !hasResult) return false;
    if (!run && activeAction && belongsToRoute && getAsrPipelineStageSettings(stage.key).enabled === false) return false;
    return true;
  });
}

function renderAsrAnalysisModeControl() {
  const selectedId = normalizeAsrAnalysisMode(state.asrToolAnalysisMode);
  if (selectedId !== state.asrToolAnalysisMode) {
    state.asrToolAnalysisMode = selectedId;
    writeStored(STORAGE_KEYS.asrAnalysisMode, selectedId);
  }
  const selectedMode = getAsrAnalysisModeConfig(selectedId);
  const menuOpen = Boolean(state.asrToolAnalysisModeMenuOpen);

  const modeDescription = selectedMode?.description || "Выберите режим анализа транскрипции.";
  if (els.asrToolAnalysisModeLabel) {
    els.asrToolAnalysisModeLabel.textContent = selectedMode?.label || "Умное саммари";
  }
  if (els.asrToolAnalysisModeDescription) {
    els.asrToolAnalysisModeDescription.textContent = modeDescription;
  }
  if (els.asrToolAnalysisHelpButton) {
    els.asrToolAnalysisHelpButton.setAttribute("data-tooltip", modeDescription);
    els.asrToolAnalysisHelpButton.setAttribute("aria-label", modeDescription);
  }
  if (els.asrToolAnalysisModeButton) {
    const disabled = state.asrToolIsTranscribing || state.asrToolPipelineBusy || state.asrToolStopping || !state.activeProfileId;
    els.asrToolAnalysisModeButton.disabled = disabled;
    els.asrToolAnalysisModeButton.setAttribute("aria-expanded", menuOpen ? "true" : "false");
  }
  if (els.asrToolAnalysisModeMenu) {
    els.asrToolAnalysisModeMenu.hidden = !menuOpen;
    els.asrToolAnalysisModeMenu.innerHTML = ASR_ANALYSIS_MODES.map((mode) => {
      const active = mode.id === selectedId;
      const disabled = Boolean(mode.requiresFullAnalysis && !asrFullAnalysisEnabled());
      const description = disabled
        ? "Отключён в настройках ASR; включается только после предупреждения о нагрузке."
        : mode.description;
      return `
        <button class="asr-analysis-mode__option" type="button" role="menuitemradio"
          data-asr-analysis-mode="${escapeHtml(mode.id)}" aria-checked="${active ? "true" : "false"}"
          aria-disabled="${disabled ? "true" : "false"}"${disabled ? " tabindex=\"-1\"" : ""}>
          <span class="asr-analysis-mode__check" aria-hidden="true">${active ? "✓" : ""}</span>
          <span class="asr-analysis-mode__option-copy">
            <strong>${escapeHtml(mode.label)}</strong>
            <small>${escapeHtml(description)}</small>
          </span>
        </button>
      `;
    }).join("");
  }
  if (els.asrToolRunAnalysisButton) {
    const content = String(els.asrToolOutput?.value || "").trim();
    els.asrToolRunAnalysisButton.disabled = !content
      || !state.activeProfileId
      || state.asrToolIsTranscribing
      || state.asrToolPipelineBusy
      || state.asrToolStopping;
    const small = els.asrToolRunAnalysisButton.querySelector("small");
    if (small) {
      small.textContent = selectedMode ? selectedMode.label : "Использовать выбранный режим";
    }
  }
}

function getAsrStageStatus(stageKey, run) {
  const timings = run?.stage_timings && typeof run.stage_timings === "object" ? run.stage_timings : {};
  if (timings[stageKey]) return "completed";
  const warningText = Array.isArray(run?.warnings) ? run.warnings.join("\n") : "";
  if (warningText.includes(`${stageKey}_failed`)) return "error";
  return "pending";
}

function renderAsrPipelineSteps(run) {
  if (!els.asrToolPipelineSteps) return;
  const activeAction = state.asrToolPipelineBusy ? state.asrToolPipelineAction : "";
  const activePreset = state.asrToolPipelineBusy ? state.asrToolPipelinePreset : "";
  let hasActiveStage = false;
  const stages = getAsrPipelineStagesForDisplay(run, activeAction);
  const html = stages.map((stage) => {
    let status = getAsrStageStatus(stage.key, run);
    if (status === "pending" && activeAction && !hasActiveStage) {
      status = "active";
      hasActiveStage = true;
    }
    const icon = status === "completed" ? "✓" : status === "error" ? "!" : "•";
    return `
      <span class="pipeline-step pipeline-step--${escapeHtml(status)}">
        <span class="pipeline-step__icon" aria-hidden="true">${escapeHtml(icon)}</span>
        <span>${escapeHtml(stage.label)}</span>
      </span>
    `;
  }).join("");
  els.asrToolPipelineSteps.innerHTML = html;
  els.asrToolPipelineSteps.hidden = (!run && !activeAction && !activePreset) || !stages.length;
}

function getAsrTranscriptTitle(transcript) {
  if (!transcript) return "Файл не выбран";
  const labels = transcript.labels && typeof transcript.labels === "object" ? transcript.labels : {};
  return stripRichTextToPlain(labels.file_name || transcript.name || transcript.summary || "Транскрипт");
}

function getAsrTranscriptMeta(transcript) {
  if (!transcript) return "Загрузите аудио или видео для транскрибации";
  return [
    transcript.language || "Язык auto",
    formatDateTime(transcript.updated_at || transcript.created_at),
    state.asrToolPipelineRun ? "анализ готов" : "текст готов",
  ].filter(Boolean).join(" • ");
}

function getAsrWorkflowStatus(stepKey) {
  const hasOutput = Boolean((els.asrToolOutput?.value || "").trim());
  const hasRun = Boolean(state.asrToolPipelineRun);
  if (stepKey === "upload") {
    if (hasOutput || state.asrToolSelectedTranscript) return "completed";
    return state.asrToolIsTranscribing ? "completed" : "active";
  }
  if (stepKey === "transcribe") {
    if (state.asrToolIsTranscribing) return "active";
    return hasOutput ? "completed" : "pending";
  }
  if (stepKey === "analysis") {
    if (state.asrToolPipelineBusy) return "active";
    return hasRun ? "completed" : (hasOutput ? "active" : "pending");
  }
  if (stepKey === "export") {
    return hasRun ? "active" : "pending";
  }
  return "pending";
}

function renderAsrWorkflow() {
  document.querySelectorAll("[data-asr-workflow-step]").forEach((step) => {
    const status = getAsrWorkflowStatus(step.dataset.asrWorkflowStep || "");
    step.dataset.status = status;
    const index = step.querySelector(".asr-workflow__index");
    if (index) {
      index.textContent = status === "completed" ? "✓" : (step.dataset.asrWorkflowStep === "upload" ? "1"
        : step.dataset.asrWorkflowStep === "transcribe" ? "2"
          : step.dataset.asrWorkflowStep === "analysis" ? "3"
            : "4");
    }
    const sub = step.querySelector("small");
    if (sub) {
      const labels = {
        upload: status === "completed" ? "Файл загружен" : "Выберите файл",
        transcribe: state.asrToolIsTranscribing ? "В работе" : (status === "completed" ? "Готово" : "Ожидает файл"),
        analysis: state.asrToolPipelineBusy ? "В работе" : (status === "completed" ? "Готово" : "Выберите действие"),
        export: status === "active" ? "Можно сохранить" : "Сохраните результат",
      };
      sub.textContent = labels[step.dataset.asrWorkflowStep] || "";
    }
  });
}

function setAsrToolTab(tabName) {
  const allowed = new Set(["text", "summary", "tasks", "roles"]);
  state.asrToolActiveTab = allowed.has(tabName) ? tabName : "text";
  renderAsrTool();
}

function renderAsrTabs() {
  document.querySelectorAll("[data-asr-tab]").forEach((button) => {
    const active = button.dataset.asrTab === state.asrToolActiveTab;
    button.classList.toggle("asr-tab--active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });
  document.querySelectorAll("[data-asr-tab-panel]").forEach((panel) => {
    panel.classList.toggle("asr-tab-panel--active", panel.dataset.asrTabPanel === state.asrToolActiveTab);
  });
}

function formatAsrTasksOutput(run) {
  const structured = run?.structured_json;
  if (!structured || typeof structured !== "object" || Array.isArray(structured)) {
    return "Задачи появятся после анализа транскрипта.";
  }
  const parts = [];
  [
    ["Задачи", structured.tasks, "tasks"],
    ["Предложения / варианты", structured.proposals || structured.solutions],
    ["Подтверждённые решения", structured.decisions],
    ["Риски", structured.risks],
    ["Открытые вопросы", structured.open_questions],
    ["Следующие действия", structured.next_steps],
  ].forEach(([title, value, kind]) => {
    const block = formatStructuredSection(title, value, kind);
    if (block) parts.push(block);
  });
  return parts.join("\n\n").trim() || "В анализе нет выделенных задач.";
}

function formatAsrRolesOutput(run) {
  const mapping = Array.isArray(run?.speaker_mapping) ? run.speaker_mapping : [];
  if (!mapping.length) return "";
  return mapping.map((item) => {
    const speaker = item.speaker || "Unknown speaker";
    const confidence = typeof item.confidence === "number" ? `, уверенность ${Math.round(item.confidence * 100)}%` : "";
    return `#${item.segment_id}: ${speaker}${confidence}\n${stripRichTextToPlain(item.text || "")}`;
  }).join("\n\n");
}

function getAsrToolSelectedContent() {
  const run = state.asrToolPipelineRun;
  if (state.asrToolActiveTab === "text") {
    return String(els.asrToolOutput?.value || "").trim();
  }
  if (state.asrToolActiveTab === "tasks") {
    const text = formatAsrTasksOutput(run);
    return text.startsWith("Задачи появятся") ? "" : text;
  }
  if (state.asrToolActiveTab === "roles") {
    return formatAsrRolesOutput(run);
  }
  return formatAsrPipelineRun(run);
}

function renderAsrFileCard() {
  if (els.asrToolFileTitle) {
    els.asrToolFileTitle.textContent = getAsrTranscriptTitle(state.asrToolSelectedTranscript);
  }
  if (els.asrToolFileMeta) {
    els.asrToolFileMeta.textContent = getAsrTranscriptMeta(state.asrToolSelectedTranscript);
  }
}

function applyAsrTextSearch() {
  const query = String(els.asrToolSearchInput?.value || "").trim();
  if (!query) return;
  if (state.asrToolActiveTab === "text") {
    const textarea = els.asrToolOutput;
    if (!textarea) return;
    const haystack = textarea.value.toLowerCase();
    const index = haystack.indexOf(query.toLowerCase());
    if (index >= 0) {
      textarea.focus();
      textarea.setSelectionRange(index, index + query.length);
    }
    return;
  }
  const content = getAsrToolSelectedContent().toLowerCase();
  const found = content.includes(query.toLowerCase());
  setInlineStatus(
    els.asrToolStatus,
    found ? "Совпадение найдено в текущем результате." : "В текущем результате совпадений нет.",
    found ? "success" : "warning",
  );
  if (found) {
    els.asrToolPipelineOutput?.scrollIntoView({ block: "nearest" });
  }
}

function downloadAsrToolText() {
  const text = getAsrToolSelectedContent() || String(els.asrToolOutput?.value || "").trim();
  if (!text) {
    setInlineStatus(els.asrToolStatus, "Нет текста для скачивания.", "warning");
    return;
  }
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  const title = getAsrTranscriptTitle(state.asrToolSelectedTranscript).replace(/[^\p{L}\p{N}_-]+/gu, "_").slice(0, 80) || "transcript";
  const url = URL.createObjectURL(blob);
  link.href = url;
  link.download = `${title}.txt`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function retranscribeAsrToolFile() {
  if (!state.asrToolLastFile) {
    setInlineStatus(els.asrToolStatus, "Исходный файл доступен только в текущей сессии. Выберите файл заново.", "warning");
    return;
  }
  await runAsrToolTranscription(state.asrToolLastFile);
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
  const selectedContent = getAsrToolSelectedContent();

  if (els.asrToolModelSelect) {
    const items = getWhisperItems();
    const names = items.map((item) => item.name);
    els.asrToolModelSelect.innerHTML = names
      .map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`)
      .join("");
    els.asrToolModelSelect.value = names.includes(state.selectedWhisperModel)
      ? state.selectedWhisperModel
      : (names.includes(ASR_STUDIO_DEFAULT_MODEL) ? ASR_STUDIO_DEFAULT_MODEL : (names[0] || ASR_STUDIO_DEFAULT_MODEL));
  }

  if (els.asrToolPromptPresetSelect) {
    els.asrToolPromptPresetSelect.value = normalizePromptPreset(state.selectedPromptPreset);
  }
  if (els.asrToolAnalysisLanguageSelect) {
    els.asrToolAnalysisLanguageSelect.value = normalizeAsrAnalysisLanguage(getActiveProfilePreferences()?.asr?.analysis_language);
    els.asrToolAnalysisLanguageSelect.disabled = state.asrToolIsTranscribing || state.asrToolPipelineBusy || state.asrToolStopping || !state.activeProfileId;
  }

  renderAsrAnalysisModeControl();

  if (els.asrToolChooseFileButton) {
    els.asrToolChooseFileButton.disabled = state.asrToolIsTranscribing || state.asrToolStopping || !state.activeProfileId;
    els.asrToolChooseFileButton.textContent = state.asrToolIsTranscribing ? "Транскрибация…" : "Выбрать файл";
  }
  if (els.asrToolPipelineSettingsButton) {
    els.asrToolPipelineSettingsButton.disabled = !state.activeProfileId;
  }
  if (els.asrToolRefreshHistoryButton) {
    els.asrToolRefreshHistoryButton.disabled = state.asrToolIsTranscribing || state.asrToolStopping || !state.activeProfileId;
  }
  if (els.asrToolStopButton) {
    const canStop = state.asrToolIsTranscribing || state.asrToolPipelineBusy || state.asrToolTaskId || state.asrToolStartController || state.asrToolPipelineController;
    els.asrToolStopButton.disabled = !canStop || state.asrToolStopping;
    els.asrToolStopButton.textContent = state.asrToolStopping ? "Останавливаю…" : "Остановить";
  }
  if (els.asrToolInsertPromptButton) {
    els.asrToolInsertPromptButton.disabled = !selectedContent;
  }
  if (els.asrToolSendButton) {
    els.asrToolSendButton.disabled = !formatAsrPipelineRun(state.asrToolPipelineRun) || state.isSending;
  }
  if (els.asrToolFullAnalysisButton) {
    const fullEnabled = asrFullAnalysisEnabled();
    els.asrToolFullAnalysisButton.hidden = !fullEnabled;
    els.asrToolFullAnalysisButton.title = fullEnabled
      ? "Запускает все стадии pipeline и может заметно нагревать Mac."
      : "Полный анализ отключён в настройках ASR.";
  }
  if (els.asrToolRolesButton) {
    const rolesAvailable = asrFullAnalysisEnabled() || Boolean(state.asrToolPipelineRun?.speaker_mapping?.length);
    els.asrToolRolesButton.hidden = !rolesAvailable;
    els.asrToolRolesButton.title = rolesAvailable
      ? "Открыть роли участников."
      : "Роли требуют полного анализа; включите его в настройках ASR.";
  }
  [
    els.asrToolCleanButton,
    els.asrToolSummaryButton,
    els.asrToolTasksButton,
    els.asrToolRolesButton,
    els.asrToolFullAnalysisButton,
  ].filter(Boolean).forEach((button) => {
    button.disabled = !hasOutput || !state.activeProfileId || state.asrToolIsTranscribing || state.asrToolPipelineBusy || state.asrToolStopping;
  });
  if (els.asrToolOpenAnalysisButton) {
    els.asrToolOpenAnalysisButton.disabled = !hasOutput && !state.asrToolPipelineRun;
  }
  if (els.asrToolDownloadButton) {
    els.asrToolDownloadButton.disabled = !selectedContent && !hasOutput;
  }
  if (els.asrToolRetranscribeButton) {
    els.asrToolRetranscribeButton.disabled = !state.asrToolLastFile || state.asrToolIsTranscribing || state.asrToolStopping;
  }
  if (els.asrToolSaveContextButton) {
    els.asrToolSaveContextButton.disabled = !state.asrToolPipelineRun || !state.activeProfileId;
  }
  if (els.asrToolCopyButton) {
    els.asrToolCopyButton.disabled = !selectedContent && !hasOutput;
  }
  if (els.asrToolSaveSpeakersButton) {
    els.asrToolSaveSpeakersButton.disabled = !state.asrToolPipelineRun || state.asrToolPipelineBusy || state.asrToolStopping;
  }
  if (els.asrToolRegenerateSummaryButton) {
    els.asrToolRegenerateSummaryButton.disabled = !state.asrToolPipelineRun || state.asrToolPipelineBusy || state.asrToolStopping;
  }
  if (els.asrToolSaveButton) {
    els.asrToolSaveButton.disabled = !hasOutput || !state.activeProfileId || state.asrToolIsTranscribing || state.asrToolStopping;
  }
  if (els.asrToolClearButton) {
    els.asrToolClearButton.disabled = !hasOutput && !hasSelectedTranscript;
  }
  if (els.asrToolDeleteButton) {
    els.asrToolDeleteButton.disabled = !hasSelectedTranscript || state.asrToolIsTranscribing || state.asrToolStopping;
  }
  if (els.asrToolClearHistoryButton) {
    els.asrToolClearHistoryButton.disabled = !historyCount || state.asrToolIsTranscribing || state.asrToolStopping;
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
  if (els.asrToolPipelinePanel && els.asrToolPipelineOutput && els.asrToolPipelineMeta) {
    const run = state.asrToolPipelineRun;
    const text = formatAsrPipelineRun(run);
    const busyText = state.asrToolPipelineBusy ? "Обработка выполняется..." : "";
    const emptyText = state.asrToolActiveTab === "summary" ? "Саммари появится после анализа транскрипта." : "";
    const outputText = text || busyText || emptyText;
    els.asrToolPipelinePanel.hidden = !outputText;
    els.asrToolPipelineOutput.dataset.plainText = outputText;
    els.asrToolPipelineOutput.innerHTML = renderAsrMarkdownOutput(outputText, emptyText);
    els.asrToolPipelineMeta.textContent = run
      ? `${run.preset || "balanced"} • ${getAsrActionLabel(run.action || "full")} • ${formatDateTime(run.updated_at || run.created_at)}`
      : (state.asrToolPipelineBusy
        ? `${state.asrToolPipelinePreset || "balanced"} • ${getAsrActionLabel(state.asrToolPipelineAction || "full")}`
        : "");
    renderAsrPipelineSteps(run);
    renderAsrSpeakerEditor(run);
  }
  if (els.asrToolTasksOutput) {
    const tasksText = formatAsrTasksOutput(state.asrToolPipelineRun);
    els.asrToolTasksOutput.dataset.plainText = tasksText;
    els.asrToolTasksOutput.innerHTML = renderAsrMarkdownOutput(tasksText, "Задачи появятся после анализа транскрипта.");
  }

  renderAsrToolHistory();
  renderAsrFileCard();
  renderAsrWorkflow();
  renderAsrTabs();
  queueSyncAppSelects();
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
    state.asrToolPipelineRun = null;
    if (els.asrToolOutput) {
      els.asrToolOutput.value = transcript.content || "";
    }
    try {
      const latestRun = await request(`/transcripts/${encodeURIComponent(target)}/pipeline/latest`);
      state.asrToolPipelineRun = latestRun || null;
    } catch {
      state.asrToolPipelineRun = null;
    }
    setInlineStatus(els.asrToolStatus, "Транскрипт загружен. Можно редактировать и отправить в чат.", "success");
    setAsrHistoryCollapsed(true);
    renderAsrTool();
    if (!isMobileLayout()) {
      requestAnimationFrame(() => els.asrToolOutput?.focus({ preventScroll: true }));
    }
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
  els.asrToolWindow.classList.add("tool-window--fullscreen");
  syncMobileScrollLock();
  if (!els.asrToolWindow.classList.contains("tool-window--fullscreen")) {
    setAsrToolWindowBounds();
  }
  setInlineStatus(
    els.asrToolStatus,
    state.asrToolSelectedTranscript
      ? "Транскрипт загружен. Можно редактировать и отправить в чат."
      : "Выберите аудио или видео для транскрибации.",
    state.asrToolSelectedTranscript ? "success" : "warning",
  );
  renderAsrTool();
  await loadAsrToolHistory({ silent: true });
  if (focusText && !isMobileLayout()) {
    try {
      els.asrToolOutput?.focus({ preventScroll: true });
    } catch {
      els.asrToolOutput?.focus();
    }
  }
  renderToolDock();
}

function closeAsrTool() {
  if (!els.asrToolWindow) return;
  stopAsrToolDrag();
  stopAsrToolResize();
  clearDropOverlay("asr");
  state.asrToolIsOpen = false;
  state.asrToolIsMinimized = false;
  els.asrToolWindow.hidden = true;
  els.asrToolWindow.classList.remove("tool-window--fullscreen");
  syncMobileScrollLock();
  renderToolDock();
}

function minimizeAsrTool() {
  if (!els.asrToolWindow) return;
  stopAsrToolDrag();
  stopAsrToolResize();
  clearDropOverlay("asr");
  state.asrToolIsOpen = false;
  state.asrToolIsMinimized = true;
  els.asrToolWindow.hidden = true;
  els.asrToolWindow.classList.remove("tool-window--fullscreen");
  syncMobileScrollLock();
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
  if (!file) return false;
  if (state.asrToolIsTranscribing) {
    setInlineStatus(els.asrToolStatus, "ASR Studio уже обрабатывает другой файл.", "warning");
    setFooter("ASR Studio уже обрабатывает другой файл.", "warning");
    return false;
  }
  if (!state.activeProfileId) {
    setInlineStatus(els.asrToolStatus, "Сначала выберите профиль.", "warning");
    return false;
  }

  state.asrToolIsTranscribing = true;
  state.asrToolLastFile = file;
  renderAsrTool();
  setInlineStatus(els.asrToolStatus, `Транскрибирую ${file.name}…`, "warning");
  setFooter(`ASR Studio: транскрибация ${file.name}…`);

  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("profile_id", String(state.activeProfileId));
    formData.append("model", state.selectedWhisperModel || ASR_STUDIO_DEFAULT_MODEL);
    formData.append("prompt_preset", normalizePromptPreset(state.selectedPromptPreset));
    formData.append("language", languageForPromptPreset(state.selectedPromptPreset));
    formData.append("beam_size", String(normalizeAsrBeamSize(state.selectedAsrBeamSize)));
    formData.append("threads", String(normalizeAsrThreads(state.selectedAsrThreads)));
    formData.append("store_result", "true");
    formData.append("origin", ASR_TOOL_ORIGIN);

    const controller = new AbortController();
    state.asrToolStartController = controller;
    const task = await request("/transcribe/tasks", { method: "POST", body: formData, signal: controller.signal });
    state.asrToolStartController = null;
    state.asrToolTaskId = task?.id || null;

    const result = await waitForVoiceTranscriptionTask(task?.id || "", {
      timeoutMs: transcriptionTimeoutForFile(file),
    });
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
    return true;
  } catch (error) {
    if (!isAbortError(error)) {
      setInlineStatus(els.asrToolStatus, `Ошибка транскрибации: ${error.message || error}`, "error");
      setFooter(`Ошибка ASR Studio: ${error.message || error}`, "error");
    }
    return false;
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

async function stopAsrToolProcessing() {
  if (state.asrToolStopping) return;
  const hasLocalWork = state.asrToolIsTranscribing || state.asrToolPipelineBusy || state.asrToolTaskId || state.asrToolStartController || state.asrToolPipelineController;
  if (!hasLocalWork) {
    setInlineStatus(els.asrToolStatus, "Активных процессов ASR Studio нет.", "warning");
    return;
  }

  state.asrToolStopping = true;
  renderAsrTool();
  setInlineStatus(els.asrToolStatus, "Останавливаю ASR Studio…", "warning");
  setFooter("Останавливаю ASR Studio…", "warning");

  try {
    state.asrToolStartController?.abort();
    state.asrToolPipelineController?.abort();
    if (state.asrToolTaskId) {
      try {
        await request(`/transcribe/tasks/${encodeURIComponent(state.asrToolTaskId)}/cancel`, {
          method: "POST",
          body: {},
        });
      } catch (error) {
        if ((error?.status || 0) !== 404) throw error;
      }
    }
    await request("/asr/stop", { method: "POST", body: {} });
    state.asrToolTaskId = null;
    state.asrToolStartController = null;
    state.asrToolPipelineController = null;
    state.asrToolIsTranscribing = false;
    state.asrToolPipelineBusy = false;
    state.asrToolPipelineAction = "";
    state.asrToolPipelinePreset = "";
    setInlineStatus(els.asrToolStatus, "ASR Studio остановлена. Если модель уже была внутри текущего LLM-вызова, дождитесь освобождения Ollama.", "warning");
    setFooter("ASR Studio остановлена.", "warning");
  } catch (error) {
    setInlineStatus(els.asrToolStatus, `Не удалось остановить ASR Studio: ${error.message || error}`, "error");
    setFooter(`Не удалось остановить ASR Studio: ${error.message || error}`, "error");
  } finally {
    state.asrToolStopping = false;
    renderAsrTool();
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
    renderAsrTool();
    return transcript;
  } catch (error) {
    setInlineStatus(els.asrToolStatus, `Не удалось сохранить транскрипт: ${error.message || error}`, "error");
    setFooter(`Не удалось сохранить транскрипт: ${error.message || error}`, "error");
  }
}

function clearAsrToolEditor() {
  state.asrToolSelectedTranscriptId = null;
  state.asrToolSelectedTranscript = null;
  state.asrToolPipelineRun = null;
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
  await deleteAsrToolTranscript(state.asrToolSelectedTranscriptId, { clearIfSelected: true });
}

async function deleteAsrToolTranscript(transcriptId, { clearIfSelected = false } = {}) {
  const targetId = Number(transcriptId || 0);
  if (!Number.isFinite(targetId) || targetId <= 0) return;
  if (!window.confirm("Удалить выбранную запись транскрибации?")) return;

  try {
    await request(`/transcripts/${encodeURIComponent(targetId)}`, { method: "DELETE" });
    if (clearIfSelected || Number(state.asrToolSelectedTranscriptId || 0) === targetId) {
      clearAsrToolEditor();
    }
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
  const text = getAsrToolSelectedContent();
  if (!text) {
    setInlineStatus(els.asrToolStatus, "Нет выбранного содержимого для вставки.", "warning");
    return;
  }
  insertPromptText(text, { append: true });
  setInlineStatus(els.asrToolStatus, "Выбранное содержимое вставлено в поле ввода.", "success");
  setFooter("ASR содержимое вставлено в поле ввода.", "success");
}

async function sendAsrToolTextToChat() {
  const text = getAsrToolChatPayload();
  if (!text) {
    setInlineStatus(els.asrToolStatus, "Сначала обработайте транскрипт.", "warning");
    return;
  }
  await sendPromptText(text, { clearInput: false });
}

function normalizeStructuredItems(value) {
  if (Array.isArray(value)) return value;
  if (typeof value === "string") {
    const normalized = value.trim();
    if (normalized && !["не указано", "не зафиксировано", "requires clarification"].includes(normalized.toLowerCase())) {
      return [normalized];
    }
  }
  return [];
}

function formatStructuredItem(item) {
  if (typeof item === "string") {
    return isEmptyStructuredValue(item) ? "" : item;
  }
  if (!item || typeof item !== "object") {
    return "";
  }
  const title = item.task || item.title || item.name || item.text || item.value || "";
  const details = [
    item.responsible && item.responsible !== "не указано" ? `ответственный: ${item.responsible}` : "",
    item.status && item.status !== "не указано" ? `статус: ${item.status}` : "",
    item.deadline && item.deadline !== "не указано" ? `срок: ${item.deadline}` : "",
  ].filter(Boolean);
  return [title, details.length ? `(${details.join(", ")})` : ""].filter(Boolean).join(" ");
}

function isEmptyStructuredValue(value) {
  const text = String(value || "").trim().toLowerCase();
  return !text || [
    "no specific agreement found",
    "not specified",
    "none",
    "n/a",
    "не указано",
    "не зафиксировано",
  ].includes(text);
}

function formatTaskItem(item) {
  if (typeof item === "string") {
    return isEmptyStructuredValue(item) ? "" : `- ${item}`;
  }
  if (!item || typeof item !== "object") {
    return "";
  }
  const task = item.task || item.title || item.name || item.text || "";
  if (isEmptyStructuredValue(task)) return "";
  const lines = [`- ${task}`];
  const context = item.context || item.details || item.description || item.evidence || "";
  if (!isEmptyStructuredValue(context)) {
    lines.push(`  Контекст: ${context}`);
  }
  const responsible = item.responsible || item.owner || "";
  if (!isEmptyStructuredValue(responsible)) {
    lines.push(`  Ответственный: ${responsible}`);
  }
  const status = item.status || "";
  if (!isEmptyStructuredValue(status)) {
    lines.push(`  Статус: ${status}`);
  }
  const deadline = item.deadline || "";
  if (!isEmptyStructuredValue(deadline)) {
    lines.push(`  Срок: ${deadline}`);
  }
  return lines.join("\n");
}

function formatStructuredSection(title, value, kind = "") {
  const items = normalizeStructuredItems(value).map(formatStructuredItem).filter(Boolean);
  if (!items.length) return "";
  if (kind === "tasks") {
    const taskItems = normalizeStructuredItems(value).map(formatTaskItem).filter(Boolean);
    if (!taskItems.length) return "";
    return [`## ${title}`, ...taskItems].join("\n");
  }
  return [`## ${title}`, ...items.map((item) => `- ${item}`)].join("\n");
}

function formatStructuredData(structured) {
  if (!structured || typeof structured !== "object" || Array.isArray(structured)) {
    return "";
  }
  const parts = [];
  const topic = structured.topic || structured.theme;
  if (topic) {
    parts.push(`## Тема\n${topic}`);
  }
  if (structured.summary) {
    parts.push(`## Суть\n${structured.summary}`);
  }
  [
    ["Подтверждённые решения", structured.decisions],
    ["Предложения / варианты", structured.proposals || structured.solutions],
    ["Договорённости", structured.agreements],
    ["Задачи", structured.tasks, "tasks"],
    ["Риски", structured.risks],
    ["Открытые вопросы", structured.open_questions],
    ["Следующие действия", structured.next_steps],
    ["Ответственные", structured.owners || structured.responsible],
    ["Сроки", structured.deadlines || structured.schedules],
  ].forEach(([title, value, kind]) => {
    const block = formatStructuredSection(title, value, kind);
    if (block) parts.push(block);
  });
  return parts.join("\n\n").trim();
}

function formatAsrPipelineRun(run) {
  if (!run) return "";
  const parts = [];
  if (run.summary) {
    return normalizeAsrDisplayMarkdown(run.summary);
  } else if (run.structured_json) {
    const formatted = formatStructuredData(run.structured_json);
    parts.push(formatted || `Структурированные данные:\n${JSON.stringify(run.structured_json, null, 2)}`);
  }
  if (!parts.length && run.cleaned_transcript) {
    parts.push(run.cleaned_transcript);
  }
  return normalizeAsrDisplayMarkdown(parts.join("\n\n"));
}

function normalizeAsrDisplayMarkdown(value) {
  return String(value || "")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .filter((line) => !/^\s*-{3,}\s*$/.test(line))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function renderAsrMarkdownOutput(value, emptyText = "") {
  const text = normalizeAsrDisplayMarkdown(value);
  if (!text) {
    return emptyText ? `<p class="subtle">${escapeHtml(emptyText)}</p>` : "";
  }
  return formatRichMessage(text);
}

function renderAsrSpeakerEditor(run) {
  if (!els.asrToolSpeakerEditor) return;
  const mapping = Array.isArray(run?.speaker_mapping) ? run.speaker_mapping : [];
  if (!mapping.length) {
    els.asrToolSpeakerEditor.innerHTML = '<p class="subtle">Роли появятся после анализа транскрипта.</p>';
    if (els.asrToolSpeakerPanel) {
      els.asrToolSpeakerPanel.hidden = false;
    }
    return;
  }
  if (els.asrToolSpeakerPanel) {
    els.asrToolSpeakerPanel.hidden = false;
  }
  els.asrToolSpeakerEditor.innerHTML = mapping.slice(0, 24).map((item) => {
    const segmentId = item.segment_id;
    const speaker = item.speaker || "Unknown speaker";
    const confidence = typeof item.confidence === "number" ? ` • ${Math.round(item.confidence * 100)}%` : "";
    const uncertain = item.uncertain ? " • неуверенно" : "";
    const text = stripRichTextToPlain(item.text || "").slice(0, 700);
    return `
      <label class="speaker-editor__row">
        <span class="speaker-editor__meta">#${escapeHtml(segmentId)}${escapeHtml(confidence)}${escapeHtml(uncertain)}</span>
        <input class="field__control" data-speaker-segment="${escapeHtml(segmentId)}" value="${escapeHtml(speaker)}" aria-label="Говорящий в сегменте ${escapeHtml(segmentId)}" />
        <span class="speaker-editor__text">${escapeHtml(text)}</span>
      </label>
    `;
  }).join("");
}

function getAsrToolChatPayload() {
  return formatAsrPipelineRun(state.asrToolPipelineRun);
}

async function ensureAsrToolTranscriptSaved() {
  if (state.asrToolSelectedTranscriptId) {
    const content = String(els.asrToolOutput?.value || "").trim();
    if (content && content !== String(state.asrToolSelectedTranscript?.content || "")) {
      return saveAsrToolTranscript();
    }
    return state.asrToolSelectedTranscript;
  }
  return saveAsrToolTranscript();
}

async function runSelectedAsrAnalysisMode() {
  const mode = getAsrAnalysisModeConfig(normalizeAsrAnalysisMode(state.asrToolAnalysisMode));
  if (!mode) return;
  if (mode.requiresFullAnalysis && !confirmAsrFullAnalysisRisk()) return;
  setAsrToolTab(mode.tab || "summary");
  await runAsrPipelineAction(mode.action, mode.preset);
}

async function runAsrPipelineAction(action, preset = "balanced") {
  if (state.asrToolPipelineBusy) return;
  if (action === "full" && !asrFullAnalysisEnabled()) {
    setInlineStatus(
      els.asrToolStatus,
      "Полный анализ отключён. Его можно включить в настройках ASR после предупреждения о нагрузке.",
      "warning",
    );
    openAsrPipelineSettings();
    return;
  }
  const content = String(els.asrToolOutput?.value || "").trim();
  if (!content) {
    setInlineStatus(els.asrToolStatus, "Нет текста для обработки.", "warning");
    return;
  }
  const transcript = await ensureAsrToolTranscriptSaved();
  if (!transcript?.id) return;

  state.asrToolPipelineBusy = true;
  state.asrToolPipelineAction = action;
  state.asrToolPipelinePreset = preset;
  const controller = new AbortController();
  state.asrToolPipelineController = controller;
  renderAsrTool();
  setInlineStatus(els.asrToolStatus, "Идёт обработка транскрипта…", "warning");
  try {
    const run = await request(`/transcripts/${encodeURIComponent(transcript.id)}/pipeline`, {
      method: "POST",
      body: { action, preset, model_name: ASR_PIPELINE_SETTINGS_MODEL_ID },
      signal: controller.signal,
    });
    state.asrToolPipelineRun = run;
    if (action === "clean" && run?.cleaned_transcript && els.asrToolOutput) {
      els.asrToolOutput.value = run.cleaned_transcript;
    }
    try {
      state.asrToolSelectedTranscript = await request(`/transcripts/${encodeURIComponent(transcript.id)}`);
      state.asrToolSelectedTranscriptId = state.asrToolSelectedTranscript?.id || transcript.id;
      await loadAsrToolHistory({ silent: true });
    } catch {
      // Pipeline result is still usable even if the history refresh failed.
    }
    setInlineStatus(els.asrToolStatus, "Обработка готова.", "success");
    setFooter("ASR обработка готова.", "success");
  } catch (error) {
    if (isAbortError(error)) {
      setInlineStatus(els.asrToolStatus, "ASR обработка остановлена.", "warning");
      setFooter("ASR обработка остановлена.", "warning");
    } else if (error?.code === "asr_full_analysis_disabled") {
      setInlineStatus(els.asrToolStatus, "Полный анализ отключён в настройках ASR.", "warning");
      setFooter("Полный анализ ASR отключён.", "warning");
      openAsrPipelineSettings();
    } else if (error?.code === "asr_summary_stage_disabled") {
      setInlineStatus(els.asrToolStatus, "Стадия саммари выключена в настройках ASR. Включите её или выберите другой маршрут.", "warning");
      setFooter("ASR summary выключено в настройках стадий.", "warning");
      openAsrPipelineSettings();
    } else {
      setInlineStatus(els.asrToolStatus, `Ошибка обработки: ${error.message || error}`, "error");
      setFooter(`Ошибка ASR обработки: ${error.message || error}`, "error");
    }
  } finally {
    state.asrToolPipelineBusy = false;
    state.asrToolPipelineAction = "";
    state.asrToolPipelinePreset = "";
    if (state.asrToolPipelineController === controller) {
      state.asrToolPipelineController = null;
    }
    renderAsrTool();
  }
}

async function saveAsrPipelineAsContext() {
  const text = getAsrToolChatPayload();
  if (!text || !state.activeProfileId) return;
  try {
    const transcript = await request("/transcripts", {
      method: "POST",
      body: {
        profile_id: state.activeProfileId,
        session_id: state.currentSessionId || undefined,
        name: "ASR обработанный контекст",
        content: text,
        labels: { origin: "asr_context", source_run_id: state.asrToolPipelineRun?.id || null },
      },
    });
    state.latestTranscript = transcript;
    renderTranscriptStrip();
    renderContextSummary();
    const ragIndex = transcript?.rag_index || null;
    const ragWasEnabled = activeProfileRagEnabled();
    if (!ragWasEnabled) {
      await toggleRagForActiveProfile(true, { notify: false });
    }
    await loadRagStatus({ silent: true });
    const chunks = Number(ragIndex?.chunks_indexed || 0);
    const ragNote = chunks ? ` RAG chunks: ${chunks}.` : "";
    const enabledNote = ragWasEnabled ? "" : " RAG включён.";
    setInlineStatus(els.asrToolStatus, `Контекст сохранён и проиндексирован.${ragNote}${enabledNote}`, "success");
    setFooter(`ASR контекст сохранён, подключён к чату и добавлен в RAG.${enabledNote}`, "success");
    return transcript;
  } catch (error) {
    setInlineStatus(els.asrToolStatus, `Не удалось сохранить контекст: ${error.message || error}`, "error");
  }
}

async function copyAsrToolText() {
  const text = getAsrToolSelectedContent() || String(els.asrToolOutput?.value || "").trim();
  if (!text) return;
  try {
    await copyText(text);
    setInlineStatus(els.asrToolStatus, "Текст скопирован.", "success");
  } catch {
    setInlineStatus(els.asrToolStatus, "Не удалось скопировать текст.", "error");
  }
}

async function saveAsrSpeakerOverrides() {
  const run = state.asrToolPipelineRun;
  const transcriptId = state.asrToolSelectedTranscriptId;
  if (!run?.id || !transcriptId || !els.asrToolSpeakerEditor) return;
  const overrides = {};
  els.asrToolSpeakerEditor.querySelectorAll("[data-speaker-segment]").forEach((input) => {
    const segmentId = input.dataset.speakerSegment;
    const value = String(input.value || "").trim();
    if (segmentId && value) {
      overrides[segmentId] = value;
    }
  });
  state.asrToolPipelineBusy = true;
  renderAsrTool();
  try {
    const updated = await request(
      `/transcripts/${encodeURIComponent(transcriptId)}/pipeline/${encodeURIComponent(run.id)}/speakers`,
      { method: "PATCH", body: { overrides } },
    );
    state.asrToolPipelineRun = updated;
    setInlineStatus(els.asrToolStatus, "Роли сохранены.", "success");
  } catch (error) {
    setInlineStatus(els.asrToolStatus, `Не удалось сохранить роли: ${error.message || error}`, "error");
  } finally {
    state.asrToolPipelineBusy = false;
    renderAsrTool();
  }
}

async function regenerateAsrSummary() {
  const run = state.asrToolPipelineRun;
  const transcriptId = state.asrToolSelectedTranscriptId;
  if (!run?.id || !transcriptId) return;
  state.asrToolPipelineBusy = true;
  state.asrToolPipelineAction = "summary";
  state.asrToolPipelinePreset = run.preset || "balanced";
  const controller = new AbortController();
  state.asrToolPipelineController = controller;
  renderAsrTool();
  try {
    const updated = await request(
      `/transcripts/${encodeURIComponent(transcriptId)}/pipeline/${encodeURIComponent(run.id)}/summary`,
      { method: "POST", body: { save_memory: true }, signal: controller.signal },
    );
    state.asrToolPipelineRun = updated;
    try {
      state.asrToolSelectedTranscript = await request(`/transcripts/${encodeURIComponent(transcriptId)}`);
      await loadAsrToolHistory({ silent: true });
    } catch {
      // Summary was regenerated; stale history title is non-blocking.
    }
    setInlineStatus(els.asrToolStatus, "Саммари пересобрано с учётом ролей.", "success");
  } catch (error) {
    if (isAbortError(error)) {
      setInlineStatus(els.asrToolStatus, "Пересборка саммари остановлена.", "warning");
    } else {
      setInlineStatus(els.asrToolStatus, `Не удалось пересобрать саммари: ${error.message || error}`, "error");
    }
  } finally {
    state.asrToolPipelineBusy = false;
    state.asrToolPipelineAction = "";
    state.asrToolPipelinePreset = "";
    if (state.asrToolPipelineController === controller) {
      state.asrToolPipelineController = null;
    }
    renderAsrTool();
  }
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
  syncMobileScrollLock();
  renderOcrEditor();
}

function closeOcrEditor() {
  if (!els.ocrBackdrop) return;
  els.ocrBackdrop.hidden = true;
  syncMobileScrollLock();
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
  if (!file) return false;
  if (state.ocrBusy) {
    setInlineStatus(els.ocrStatus, "OCR уже обрабатывает другое изображение.", "warning");
    setFooter("OCR уже обрабатывает другое изображение.", "warning");
    return false;
  }
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
    return true;
  } catch (error) {
    if (error?.code === "ocr_empty_result") {
      setInlineStatus(els.ocrStatus, "OCR не нашёл текст на изображении.", "warning");
      setFooter("OCR не нашёл текст на изображении.", "warning");
      renderOcrEditor();
      return false;
    }
    setInlineStatus(els.ocrStatus, `Ошибка OCR: ${error.message || error}`, "error");
    setFooter(`Ошибка OCR: ${error.message || error}`, "error");
    return false;
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

async function handleChatDroppedFile(file) {
  const fileKind = classifyFileKind(file);
  if (fileKind === "image") {
    await addChatImageFiles([file]);
    return;
  }

  if (fileKind === "media") {
    const approved = await openConfirmDialog({
      eyebrow: "Drag & Drop",
      title: "Открыть ASR Studio",
      message: "Для аудио и видео сейчас доступна только транскрибация в ASR Studio.",
      confirmLabel: "Открыть ASR Studio",
      cancelLabel: "Отмена",
      returnFocus: els.promptInput,
    });
    if (!approved) {
      showToast("Действие отменено пользователем.", "warning");
      return;
    }
    await openAsrTool({ focusText: false });
    await runAsrToolTranscription(file);
    return;
  }

  showToast("Этот тип файла пока не поддерживается.", "warning");
}

async function handleAsrToolDroppedFile(file) {
  if (classifyFileKind(file) !== "media") {
    showToast("Этот тип файла пока не поддерживается.", "warning");
    return;
  }

  const approved = await openConfirmDialog({
    eyebrow: "ASR Studio",
    title: "Запустить транскрибацию?",
    message: "Будет запущена транскрибация в ASR Studio.",
    confirmLabel: "Транскрибировать",
    cancelLabel: "Отмена",
    returnFocus: els.asrToolOutput,
  });
  if (!approved) {
    showToast("Действие отменено пользователем.", "warning");
    return;
  }
  await runAsrToolTranscription(file);
}

async function handleDroppedDataTransfer(zone, dataTransfer) {
  if (zone === "chat" && !hasDirectoryInDataTransfer(dataTransfer)) {
    const files = Array.from(dataTransfer?.files || []);
    if (files.length > 1 && files.every((file) => classifyFileKind(file) === "image")) {
      await addChatImageFiles(files);
      return;
    }
  }
  const { file, error } = extractDroppedFile(dataTransfer);
  if (error === "multiple") {
    showToast("Перетащите несколько изображений либо один аудио/видеофайл.", "warning");
    return;
  }
  if (!file) {
    showToast("Этот тип файла пока не поддерживается.", "warning");
    return;
  }

  if (zone === "asr") {
    await handleAsrToolDroppedFile(file);
    return;
  }
  await handleChatDroppedFile(file);
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
    if (isMobileLayout()) {
      setTtsHistoryCollapsed(true);
    }
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
    els.ttsToolText.value = normalizeTextForSpeech(message.content || "");
  }
  setInlineStatus(els.ttsToolStatus, "Последний ответ подставлен в Voice Studio.", "success");
  renderTtsTool();
  return true;
}

async function openTtsTool({ focusText = false } = {}) {
  if (!els.ttsToolWindow) return;
  setTtsHistoryCollapsed(true);
  state.ttsToolIsOpen = true;
  state.ttsToolIsMinimized = false;
  els.ttsToolWindow.hidden = false;
  syncMobileScrollLock();
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

  if (focusText && !isMobileLayout()) {
    try {
      els.ttsToolText?.focus({ preventScroll: true });
    } catch {
      els.ttsToolText?.focus();
    }
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
  syncMobileScrollLock();
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
  syncMobileScrollLock();
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
  const text = normalizeTextForSpeech(els.ttsToolText?.value || "");
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
  if (els.ttsToolText && els.ttsToolText.value !== text) {
    els.ttsToolText.value = text;
  }
  if (voiceId !== state.selectedTtsVoiceId) {
    state.selectedTtsVoiceId = voiceId;
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
      const downloaded = (item.downloaded_bytes || item.completed) ? formatBytes(item.downloaded_bytes || item.completed) : "";
      const total = (item.total_bytes || item.total) ? formatBytes(item.total_bytes || item.total) : "";
      const transfer = downloaded && total ? ` • ${downloaded} / ${total}` : downloaded ? ` • ${downloaded}` : "";
      const canCancel = item.source === "chat" && isActiveDownloadState(item.state);
      const sourceLabel = item.source === "asr" ? "ASR" : item.source === "tts" ? "TTS" : "CHAT";
      const outputTail = Array.isArray(item.output_tail) && item.output_tail.length
        ? `<pre class="download-card__log">${escapeHtml(item.output_tail.slice(-4).join("\n"))}</pre>`
        : "";
      return `
        <article class="download-card">
          <div class="download-card__top">
            <strong>${escapeHtml(item.model || item.voice_key || "модель")}</strong>
            <span class="subtle">${escapeHtml(sourceLabel)} • ${escapeHtml(item.state || "")}</span>
          </div>
          <div class="download-progress"><div class="download-progress__bar" style="width:${percent}%;"></div></div>
          <div class="subtle">${escapeHtml(item.message || "Ожидание")}${escapeHtml(eta)}${escapeHtml(transfer)}</div>
          ${outputTail}
          ${canCancel ? `<div class="button-row"><button class="button button--ghost" type="button" data-cancel-download="${escapeHtml(item.task_id || "")}">Остановить</button></div>` : ""}
        </article>
      `;
    })
    .join("");
}

function normalizeNetworkAddressItems(items) {
  if (!Array.isArray(items)) return [];
  return items
    .map((item, index) => {
      const rawUrl = String(item?.url || "").trim();
      if (!rawUrl || rawUrl.includes("<") || rawUrl.includes(">")) return null;
      try {
        const parsed = new URL(rawUrl);
        if (!["http:", "https:"].includes(parsed.protocol)) return null;
      } catch {
        return null;
      }
      return {
        id: String(item?.id || item?.provider_id || `address-${index}`),
        provider_id: String(item?.provider_id || item?.id || `address-${index}`),
        label: String(item?.label || item?.provider_id || "Address"),
        url: rawUrl,
        detail: String(item?.detail || item?.security_note || ""),
        copyable: item?.copyable !== false,
        priority: Number.isFinite(Number(item?.priority)) ? Number(item.priority) : 100,
      };
    })
    .filter((item) => item && item.copyable)
    .sort((a, b) => (a.priority - b.priority) || a.label.localeCompare(b.label));
}

function availableNetworkAddresses() {
  return Array.isArray(state.networkAddresses) ? state.networkAddresses : [];
}

function closeNetworkAddressMenu() {
  if (!els.networkAddressMenu) return;
  els.networkAddressMenu.hidden = true;
  els.networkAddressMenu.style.left = "";
  els.networkAddressMenu.style.top = "";
  state.networkAddressMenuPosition = null;
  els.copyLanUrlButton?.setAttribute("aria-expanded", "false");
}

function positionNetworkAddressMenu(clientX, clientY) {
  if (!els.networkAddressMenu || els.networkAddressMenu.hidden) return;
  const rect = els.networkAddressMenu.getBoundingClientRect();
  const padding = 12;
  const left = Math.max(padding, Math.min(clientX, window.innerWidth - rect.width - padding));
  const top = Math.max(padding, Math.min(clientY, window.innerHeight - rect.height - padding));
  els.networkAddressMenu.style.left = `${left}px`;
  els.networkAddressMenu.style.top = `${top}px`;
}

function renderNetworkAddressMenu() {
  if (!els.networkAddressMenu) return;
  const items = availableNetworkAddresses();
  els.networkAddressMenu.innerHTML = [
    '<div class="network-address-menu__header">Адрес доступа</div>',
    ...items.map((item, index) => `
      <button class="network-address-menu__item" type="button" role="menuitem" data-network-address-index="${index}">
        <span>
          <strong>${escapeHtml(item.label)}</strong>
          ${item.detail ? `<small>${escapeHtml(item.detail)}</small>` : ""}
        </span>
        <code>${escapeHtml(item.url)}</code>
      </button>
    `),
  ].join("");
  if (!els.networkAddressMenu.hidden && state.networkAddressMenuPosition) {
    positionNetworkAddressMenu(state.networkAddressMenuPosition.x, state.networkAddressMenuPosition.y);
  }
}

function renderLanUrl() {
  const value = state.lanUrl || "Недоступно";
  const addresses = availableNetworkAddresses();
  const topbarDisabled = state.networkAddressesLoading || !addresses.length;
  if (els.lanUrlValue) {
    els.lanUrlValue.textContent = value;
  }
  if (els.copyLanUrlButton) {
    els.copyLanUrlButton.disabled = topbarDisabled;
    els.copyLanUrlButton.setAttribute("aria-expanded", els.networkAddressMenu?.hidden === false ? "true" : "false");
    if (addresses.length > 1) {
      els.copyLanUrlButton.title = "Выбрать адрес доступа";
      els.copyLanUrlButton.setAttribute("aria-label", "Выбрать адрес доступа");
    } else if (addresses.length === 1) {
      els.copyLanUrlButton.title = `Скопировать ${addresses[0].label} URL`;
      els.copyLanUrlButton.setAttribute("aria-label", `Скопировать ${addresses[0].label} URL`);
    } else {
      els.copyLanUrlButton.title = "Адрес доступа недоступен";
      els.copyLanUrlButton.setAttribute("aria-label", "Адрес доступа недоступен");
    }
  }
  if (els.copyLanUrlFromSettingsButton) {
    els.copyLanUrlFromSettingsButton.disabled = !state.lanUrl;
  }
  renderNetworkAddressMenu();
}

function pluginStatusLabel(plugin) {
  if (!plugin?.trusted) return "Detected, not trusted";
  if (plugin?.enabled && plugin?.effective_enabled) return "Enabled";
  return "Disabled";
}

function pluginStatusClass(plugin) {
  if (!plugin?.trusted) return "plugin-status--untrusted";
  if (plugin?.enabled && plugin?.effective_enabled) return "plugin-status--enabled";
  return "plugin-status--disabled";
}

function renderPluginPills(items, emptyText = "none", extraClass = "") {
  if (!Array.isArray(items) || !items.length) {
    return `<span class="plugin-pill plugin-pill--muted">${escapeHtml(emptyText)}</span>`;
  }
  return items
    .map((item) => `<span class="plugin-pill ${extraClass}">${escapeHtml(item)}</span>`)
    .join("");
}

function pluginDocUrl(plugin, doc) {
  const pluginId = String(plugin?.id || "").trim();
  const path = String(doc?.path || "").trim();
  if (!pluginId || !path) return "";
  if (doc?.url) return String(doc.url);
  const encodedPath = path.split("/").map((part) => encodeURIComponent(part)).join("/");
  return `/plugins/${encodeURIComponent(pluginId)}/docs/${encodedPath}`;
}

function renderPluginDocs(plugin) {
  const docs = Array.isArray(plugin?.docs_status) ? plugin.docs_status : [];
  if (!docs.length) {
    return '<span class="plugin-pill plugin-pill--muted">no docs</span>';
  }
  return docs
    .map((doc) => {
      const available = doc?.available === true;
      const className = available ? "plugin-pill" : "plugin-pill plugin-pill--muted";
      const suffix = available ? "" : " (missing)";
      const label = `${doc?.path || "doc"}${suffix}`;
      const url = pluginDocUrl(plugin, doc);
      if (available && url) {
        return `<a class="${className} plugin-doc-link" href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(label)}</a>`;
      }
      return `<span class="${className}">${escapeHtml(label)}</span>`;
    })
    .join("");
}

function renderPluginSecurityWarnings(plugin) {
  const warnings = Array.isArray(plugin?.security_warnings)
    ? plugin.security_warnings
    : Array.isArray(plugin?.handler_status?.security_warnings)
      ? plugin.handler_status.security_warnings
      : [];
  if (!warnings.length) return "";
  return `<div class="plugin-warning">Security warnings: ${renderPluginPills(warnings, "none", "plugin-pill--danger")}</div>`;
}

function renderPluginHandlerStatus(plugin) {
  const handler = plugin?.handler_status;
  if (!handler || typeof handler !== "object") return "";
  const command = handler.manual_command || handler.manual_command_template || "";
  const cliState = handler.cli_available ? "tailscale CLI found" : "tailscale CLI not found";
  const serveState = handler.serve_localgpt_detected
    ? "LocalGPT Serve active"
    : handler.serve_active
      ? "Serve active for another target"
      : "Serve not detected";
  const message = handler.message ? `<span>${escapeHtml(handler.message)}</span>` : "";
  return `
    <div class="plugin-runtime">
      <div class="plugin-runtime__row">
        <span>${escapeHtml(cliState)}</span>
        <span>${escapeHtml(serveState)}</span>
      </div>
      ${command ? `<code>${escapeHtml(command)}</code>` : ""}
      ${message}
    </div>
  `;
}

function renderPluginCard(plugin) {
  const id = String(plugin?.id || "");
  const trusted = plugin?.trusted === true;
  const disabled = state.pluginsLoading || !trusted;
  const checked = trusted && plugin?.enabled === true;
  const dangerous = Array.isArray(plugin?.dangerous_permissions) ? plugin.dangerous_permissions : [];
  const warning = dangerous.length
    ? `<div class="plugin-warning">Dangerous permissions: ${renderPluginPills(dangerous, "none", "plugin-pill--danger")}</div>`
    : "";
  const trustNote = trusted
    ? "Trusted backend handler available."
    : "Detected, but not trusted. Execution unavailable.";
  const securityWarnings = renderPluginSecurityWarnings(plugin);
  const handlerStatus = trusted ? renderPluginHandlerStatus(plugin) : "";

  return `
    <article class="plugin-card" data-plugin-id="${escapeHtml(id)}">
      <div class="plugin-card__main">
        <div class="plugin-card__title-row">
          <div>
            <strong>${escapeHtml(plugin?.name || id || "Plugin")}</strong>
            <span>${escapeHtml(plugin?.id || "unknown")} • ${escapeHtml(plugin?.type || "unknown")} • v${escapeHtml(plugin?.version || "0")}</span>
          </div>
          <span class="plugin-status ${pluginStatusClass(plugin)}">${escapeHtml(pluginStatusLabel(plugin))}</span>
        </div>
        <p>${escapeHtml(plugin?.description || "")}</p>
        <div class="plugin-meta-row">
          <span class="plugin-meta-row__label">Permissions</span>
          <span>${renderPluginPills(plugin?.permissions, "none")}</span>
        </div>
        ${warning}
        ${securityWarnings}
        <div class="plugin-meta-row">
          <span class="plugin-meta-row__label">Docs</span>
          <span>${renderPluginDocs(plugin)}</span>
        </div>
        ${handlerStatus}
        <p class="plugin-note">${escapeHtml(plugin?.security_note || trustNote)}</p>
      </div>
      <label class="field field--checkbox plugin-toggle">
        <input type="checkbox" data-plugin-toggle="${escapeHtml(id)}" ${checked ? "checked" : ""} ${disabled ? "disabled" : ""} />
        <span>${checked ? "Enabled" : "Disabled"}</span>
      </label>
    </article>
  `;
}

function renderInvalidPluginCard(plugin) {
  const errors = Array.isArray(plugin?.errors) ? plugin.errors : ["Invalid plugin manifest"];
  return `
    <article class="plugin-card plugin-card--invalid">
      <div class="plugin-card__main">
        <div class="plugin-card__title-row">
          <div>
            <strong>${escapeHtml(plugin?.plugin_dir || "Invalid plugin")}</strong>
            <span>${escapeHtml(plugin?.manifest_path || "plugin.json")}</span>
          </div>
          <span class="plugin-status plugin-status--invalid">Invalid</span>
        </div>
        <div class="plugin-warning">${renderPluginPills(errors, "invalid", "plugin-pill--danger")}</div>
      </div>
    </article>
  `;
}

function renderPlugins() {
  const plugins = Array.isArray(state.pluginsState?.plugins) ? state.pluginsState.plugins : [];
  const invalidPlugins = Array.isArray(state.pluginsState?.invalid_plugins) ? state.pluginsState.invalid_plugins : [];
  const trustedIds = Array.isArray(state.pluginsState?.trusted_plugin_ids) ? state.pluginsState.trusted_plugin_ids : [];
  const enabledCount = plugins.filter((plugin) => plugin?.effective_enabled).length;

  if (els.refreshPluginsButton) {
    els.refreshPluginsButton.disabled = state.pluginsLoading;
    els.refreshPluginsButton.textContent = state.pluginsLoading ? "Обновление…" : "Обновить";
  }

  if (els.pluginsSummary) {
    els.pluginsSummary.innerHTML = `
      <span>Installed: <strong>${plugins.length}</strong></span>
      <span>Enabled: <strong>${enabledCount}</strong></span>
      <span>Trusted ids: <strong>${escapeHtml(trustedIds.join(", ") || "none")}</strong></span>
    `;
  }

  if (!els.pluginsList) return;
  if (state.pluginsLoading && !plugins.length && !invalidPlugins.length) {
    els.pluginsList.innerHTML = '<p class="subtle">Загружаю plugins registry…</p>';
    return;
  }

  if (!plugins.length && !invalidPlugins.length) {
    els.pluginsList.innerHTML = `
      <div class="plugins-empty">
        <strong>No plugins installed.</strong>
        <span>${escapeHtml(state.pluginsState?.message || "Add a plugin folder to plugins/ to make it appear here.")}</span>
      </div>
    `;
    return;
  }

  els.pluginsList.innerHTML = [
    ...plugins.map(renderPluginCard),
    ...invalidPlugins.map(renderInvalidPluginCard),
  ].join("");
}

function renderDatabaseMaintenance() {
  const busy = Boolean(state.databaseMaintenanceBusy);
  if (els.cleanupDatabaseButton) {
    els.cleanupDatabaseButton.disabled = busy;
    els.cleanupDatabaseButton.textContent = busy ? "Очистка…" : "Очистить мусор";
  }
  if (els.resetDatabaseButton) {
    els.resetDatabaseButton.disabled = busy;
    els.resetDatabaseButton.textContent = busy ? "Очистка…" : "Полная очистка";
  }
}

function renderAppRuntimeMaintenance() {
  const busy = Boolean(state.appRuntimeBusy);
  if (els.restartBackendButton) {
    els.restartBackendButton.disabled = busy;
    els.restartBackendButton.textContent = busy ? "Перезапуск…" : "Перезапустить backend";
  }
  if (els.shutdownButton) {
    els.shutdownButton.disabled = busy;
    els.shutdownButton.textContent = busy ? "Остановка…" : "Остановить приложение";
  }
}

function renderModelTransfer() {
  if (!els.modelTransferList) return;
  const models = state.modelTransferModels || [];
  els.modelTransferList.innerHTML = models.length
    ? models.map((item) => `
        <label class="model-transfer__item">
          <input type="checkbox" data-model-transfer-id="${escapeHtml(item.id)}" ${item.selectable ? "checked" : "disabled"} />
          <span><strong>${escapeHtml(item.model_id)}</strong><br><small>${escapeHtml(item.family)}${item.reason ? ` • ${escapeHtml(item.reason)}` : ""}</small></span>
          <span>${formatBytes(item.size || 0)}</span>
        </label>`).join("")
    : '<p class="subtle">Готовые локальные модели не найдены.</p>';
  if (els.exportModelsButton) els.exportModelsButton.disabled = state.modelTransferBusy || !models.some((item) => item.selectable);
  if (els.importModelsButton) els.importModelsButton.disabled = state.modelTransferBusy;
  if (els.refreshModelTransferButton) els.refreshModelTransferButton.disabled = state.modelTransferBusy;
  if (els.cancelModelTransferButton) els.cancelModelTransferButton.hidden = !state.modelTransferTaskId;
}

async function loadModelTransferPreview() {
  setInlineStatus(els.modelTransferStatus, "Проверяю локальные модели…", "warning");
  try {
    const data = await request("/model-transfer/export-preview");
    state.modelTransferModels = data.models || [];
    renderModelTransfer();
    setInlineStatus(els.modelTransferStatus, `Готово моделей: ${data.complete_count || 0}. Общий уникальный размер: ${formatBytes(data.total_unique_size || 0)}.`, "success");
  } catch (error) {
    setInlineStatus(els.modelTransferStatus, `Не удалось получить модели: ${error.message || error}`, "error");
  }
}

async function pollModelTransferTask(taskId) {
  const task = await request(`/model-transfer/tasks/${encodeURIComponent(taskId)}`);
  if (task.status === "running") {
    setInlineStatus(els.modelTransferStatus, `Упаковка: ${task.processed_files || 0}/${task.total_files || "?"} файлов, ${formatBytes(task.processed_bytes || 0)}.`, "warning");
    window.setTimeout(() => void pollModelTransferTask(taskId), 500);
    return;
  }
  state.modelTransferBusy = false;
  state.modelTransferTaskId = null;
  renderModelTransfer();
  if (task.status === "completed") {
    setInlineStatus(els.modelTransferStatus, "Bundle готов. Начинаю скачивание…", "success");
    window.location.assign(`/model-transfer/exports/${encodeURIComponent(taskId)}/download`);
  } else {
    setInlineStatus(els.modelTransferStatus, task.status === "cancelled" ? "Экспорт отменён." : `Ошибка экспорта: ${task.error_code || "unknown"}`, "error");
  }
}

async function startModelExport() {
  const selected = Array.from(els.modelTransferList?.querySelectorAll("[data-model-transfer-id]:checked") || [])
    .map((input) => input.getAttribute("data-model-transfer-id"));
  if (!selected.length) {
    setInlineStatus(els.modelTransferStatus, "Выберите хотя бы одну готовую модель.", "warning");
    return;
  }
  state.modelTransferBusy = true;
  renderModelTransfer();
  try {
    const task = await request("/model-transfer/exports", { method: "POST", body: { models: selected } });
    state.modelTransferTaskId = task.task_id;
    renderModelTransfer();
    await pollModelTransferTask(task.task_id);
  } catch (error) {
    state.modelTransferBusy = false;
    renderModelTransfer();
    setInlineStatus(els.modelTransferStatus, `Не удалось начать экспорт: ${error.message || error}`, "error");
  }
}

async function inspectModelImport(file) {
  const form = new FormData();
  form.append("bundle", file);
  state.modelTransferBusy = true;
  renderModelTransfer();
  setInlineStatus(els.modelTransferStatus, `Проверяю ${file.name}…`, "warning");
  try {
    const result = await request("/model-transfer/import-inspect", { method: "POST", body: form });
    setInlineStatus(els.modelTransferStatus, `Bundle исправен: ${result.models?.length || 0} моделей, ${formatBytes(result.total_size || 0)}. Ожидается подтверждение.`, "success");
    const approved = await openConfirmDialog({
      eyebrow: "Импорт моделей",
      title: `Импортировать ${result.models?.length || 0} моделей?`,
      message: `LocalGPT повторно проверит bundle и добавит файлы в текущие пути моделей. Существующие отличающиеся файлы не будут заменены.`,
      confirmLabel: "Импортировать",
      cancelLabel: "Отмена",
      returnFocus: els.importModelsButton,
    });
    if (!approved) {
      await request(`/model-transfer/uploads/${encodeURIComponent(result.upload_id)}`, { method: "DELETE" });
      setInlineStatus(els.modelTransferStatus, "Импорт отменён до изменения хранилища.", "warning");
      return;
    }
    setInlineStatus(els.modelTransferStatus, "Повторно проверяю и импортирую модели…", "warning");
    const applied = await request("/model-transfer/imports", { method: "POST", body: { upload_id: result.upload_id } });
    setInlineStatus(els.modelTransferStatus, `Импорт завершён: добавлено файлов ${applied.published_files || 0}, идентичных пропущено ${applied.skipped_files || 0}.`, "success");
    await Promise.all([
      loadModels({ silent: true }),
      loadWhisperModels({ silent: true }),
      loadTtsSettings({ silent: true }),
      loadModelTransferPreview(),
    ]);
  } catch (error) {
    setInlineStatus(els.modelTransferStatus, `Bundle не принят: ${error.message || error}`, "error");
  } finally {
    state.modelTransferBusy = false;
    if (els.importModelsInput) els.importModelsInput.value = "";
    renderModelTransfer();
  }
}

function setSettingsTab(tabName, { persist = true, render = true } = {}) {
  const allowed = new Set(["profile", "models", "vision", "asr", "tts", "plugins", "system"]);
  const next = allowed.has(tabName) ? tabName : "profile";
  state.activeSettingsTab = next;
  if (persist) {
    writeStored(STORAGE_KEYS.settingsTab, next);
  }
  if (render) {
    renderSettingsTabs();
    if (isMobileLayout() && isOverlayOpen(els.settingsBackdrop)) {
      els.settingsBackdrop?.querySelector(".settings-panel__content")?.scrollTo({ top: 0, left: 0, behavior: "smooth" });
    }
  }
}

function renderSettingsTabs() {
  const active = state.activeSettingsTab || "profile";
  let activeButton = null;
  document.querySelectorAll("[data-settings-tab]").forEach((button) => {
    const selected = button.getAttribute("data-settings-tab") === active;
    button.classList.toggle("settings-tab--active", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
    button.setAttribute("tabindex", selected ? "0" : "-1");
    if (selected) {
      activeButton = button;
    }
  });
  document.querySelectorAll("[data-settings-tab-panel]").forEach((panel) => {
    panel.hidden = panel.getAttribute("data-settings-tab-panel") !== active;
  });
  if (activeButton && isMobileLayout() && isOverlayOpen(els.settingsBackdrop)) {
    requestAnimationFrame(() => {
      activeButton.scrollIntoView({ block: "nearest", inline: "center" });
    });
  }
}

function renderSettings() {
  renderSettingsTabs();
  renderProfileOptions();
  renderProfileManagement();
  renderSessionList();
  renderLibraryPanels();
  renderModelControls();
  renderModelSettings();
  renderVisionSettings();
  renderWhisperControls();
  renderTtsControls();
  renderDownloads();
  renderLanUrl();
  renderPlugins();
  renderDatabaseMaintenance();
  renderAppRuntimeMaintenance();
  renderModelTransfer();

  if (els.modelsDirInput && !els.modelsDirInput.value && state.modelsDir) {
    els.modelsDirInput.value = state.modelsDir;
  }
}

function applyCurrentSessionMeta() {
  const session = state.sessions.find((item) => item.id === state.currentSessionId);
  const title = session?.title || "Новый чат";
  state.selectedLlmModel = session?.model_name || state.selectedLlmModel || "";
  writeStored(STORAGE_KEYS.llmModel, state.selectedLlmModel || "");
  if (els.chatTitle) {
    els.chatTitle.textContent = title;
  }
  renderQuickModelPicker();
  renderContextSummary();
  renderSettings();
  void refreshModelSettings({ silent: true });
  void refreshAsrPipelineSettings({ silent: true });
}

function openSidebar() {
  if (!isMobileLayout() || !els.sidebar || !els.sidebarBackdrop) return;
  els.sidebar.classList.add("sidebar--open");
  els.sidebarBackdrop.hidden = false;
  els.toggleSidebarButton?.setAttribute("aria-expanded", "true");
  syncMobileScrollLock();
}

function closeSidebar() {
  if (!els.sidebar || !els.sidebarBackdrop) return;
  els.sidebar.classList.remove("sidebar--open");
  els.sidebarBackdrop.hidden = true;
  els.toggleSidebarButton?.setAttribute("aria-expanded", "false");
  syncMobileScrollLock();
}

function toggleMobileSidebar() {
  if (!isMobileLayout()) return;
  if (els.sidebar?.classList.contains("sidebar--open")) {
    closeSidebar();
    return;
  }
  openSidebar();
}

function openSettings() {
  if (!els.settingsBackdrop) return;
  els.settingsBackdrop.hidden = false;
  syncMobileScrollLock();
  renderSettings();
  void refreshModelSettings({ silent: true });
  void refreshAsrPipelineSettings({ silent: true });
  void loadWhisperModels({ silent: true });
  void loadTtsSettings({ silent: true });
  void loadTtsLibrary({ silent: true });
  void loadPlugins({ silent: true });
  void loadVisionCache({ silent: true });
}

function openAsrPipelineSettings() {
  setSettingsTab("asr", { render: false });
  setAsrPipelineSettingsExpanded(true, { render: false });
  openSettings();
  window.setTimeout(() => {
    els.asrPipelineSettingsPanel?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, 80);
}

function closeSettings() {
  if (!els.settingsBackdrop) return;
  els.settingsBackdrop.hidden = true;
  syncMobileScrollLock();
}

function activeProfileRagEnabled() {
  const preferences = getActiveProfilePreferences();
  const value = preferences?.settings?.rag_enabled;
  if (typeof value === "string") {
    return value.trim().toLowerCase() === "true";
  }
  return value === true || value === 1;
}

function renderRagButton() {
  if (!els.openRagButton) return;
  const enabled = activeProfileRagEnabled();
  els.openRagButton.classList.toggle("rag-status-button--on", enabled);
  els.openRagButton.setAttribute("aria-pressed", enabled ? "true" : "false");
  els.openRagButton.setAttribute("aria-label", enabled ? "Открыть RAG, включён" : "Открыть RAG, выключен");
  els.openRagButton.title = enabled ? "RAG включён для активного профиля" : "RAG выключен для активного профиля";
}

function closeRagQuickMenu() {
  if (!els.ragQuickMenu) return;
  els.ragQuickMenu.hidden = true;
  els.ragQuickMenu.style.left = "";
  els.ragQuickMenu.style.top = "";
  state.ragQuickMenuPosition = null;
}

function positionRagQuickMenu(clientX, clientY) {
  if (!els.ragQuickMenu || els.ragQuickMenu.hidden) return;
  const rect = els.ragQuickMenu.getBoundingClientRect();
  const padding = 12;
  const left = Math.max(padding, Math.min(clientX, window.innerWidth - rect.width - padding));
  const top = Math.max(padding, Math.min(clientY, window.innerHeight - rect.height - padding));
  els.ragQuickMenu.style.left = `${left}px`;
  els.ragQuickMenu.style.top = `${top}px`;
}

function renderRagQuickMenu() {
  renderRagButton();
  if (!els.ragQuickEnabledToggle) return;
  els.ragQuickEnabledToggle.disabled = !state.activeProfileId;
  els.ragQuickEnabledToggle.checked = activeProfileRagEnabled();
  if (!els.ragQuickMenu?.hidden && state.ragQuickMenuPosition) {
    positionRagQuickMenu(state.ragQuickMenuPosition.x, state.ragQuickMenuPosition.y);
  }
}

function renderRagPanel() {
  const status = state.ragStatus || {};
  renderRagButton();
  if (els.ragSourceDirValue) {
    els.ragSourceDirValue.textContent = status.source_dir || "rag_sources";
  }
  if (els.ragEnabledToggle) {
    els.ragEnabledToggle.disabled = !state.activeProfileId || state.ragBusy;
    els.ragEnabledToggle.checked = activeProfileRagEnabled();
  }
  [els.ragAddFilesButton, els.ragIngestButton, els.ragForceIngestButton, els.ragRefreshButton, els.ragCopyPathButton]
    .filter(Boolean)
    .forEach((button) => {
      button.disabled = state.ragBusy || (!state.activeProfileId && button !== els.ragRefreshButton && button !== els.ragCopyPathButton);
    });
  if (els.ragIngestButton) {
    els.ragIngestButton.textContent = state.ragBusy ? "Индексация…" : "Индексировать";
  }
  if (els.ragStatusText) {
    const stats = status.stats || {};
    const contextCount = Array.isArray(status.contexts) ? status.contexts.length : 0;
    els.ragStatusText.textContent = state.ragBusy
      ? "RAG обновляется…"
      : `Файлов: ${status.file_count ?? 0} • контекстов: ${contextCount} • документов: ${stats.documents ?? 0} • chunks: ${stats.chunks ?? 0} • embeddings: ${stats.embeddings ?? 0}`;
  }
  if (els.ragFileList) {
    const files = Array.isArray(status.files) ? status.files : [];
    const contexts = Array.isArray(status.contexts) ? status.contexts : [];
    const contextMarkup = contexts.length
      ? [
        '<p class="rag-file-list__section">Контекст</p>',
        ...contexts.slice(0, 100).map((item) => {
          const sourceId = String(item?.source_id || "").trim();
          const title = String(item?.title || sourceId || "ASR context").trim();
          return `
            <div class="rag-file-list__item">
              <span>${escapeHtml(title)}</span>
              <button class="rag-file-list__delete" type="button" data-rag-delete-context="${escapeHtml(sourceId)}" aria-label="Удалить ${escapeHtml(title)}">✕</button>
            </div>
          `;
        }),
      ].join("")
      : "";
    const fileMarkup = files.length
      ? [
        '<p class="rag-file-list__section">Файлы</p>',
        ...files.slice(0, 100).map((file) => `
        <div class="rag-file-list__item">
          <span>${escapeHtml(file)}</span>
          <button class="rag-file-list__delete" type="button" data-rag-delete-file="${escapeHtml(file)}" aria-label="Удалить ${escapeHtml(file)}">✕</button>
        </div>
      `),
      ].join("")
      : "";
    els.ragFileList.innerHTML = contextMarkup || fileMarkup
      ? `${contextMarkup}${fileMarkup}`
      : '<p class="subtle">Для активного профиля RAG-источников нет. Добавьте файлы или сохраните ASR результат как контекст.</p>';
  }
}

async function loadRagStatus({ silent = false } = {}) {
  try {
    const query = state.activeProfileId ? `?profile_id=${encodeURIComponent(state.activeProfileId)}` : "";
    state.ragStatus = await request(`/rag/status${query}`);
    renderRagPanel();
  } catch (error) {
    if (!silent) {
      setFooter(`Не удалось загрузить статус RAG: ${error.message || error}`, "error");
    }
  }
}

async function openRagPanel() {
  if (!els.ragBackdrop) return;
  closeRagQuickMenu();
  els.ragBackdrop.hidden = false;
  syncMobileScrollLock();
  renderRagPanel();
  await loadRagStatus({ silent: true });
}

function closeRagPanel() {
  if (!els.ragBackdrop) return;
  els.ragBackdrop.hidden = true;
  syncMobileScrollLock();
}

function openRagQuickMenu() {
  if (!els.ragQuickMenu) return;
  closeRagPanel();
  closeNetworkAddressMenu();
  closeQuickModelMenu();
  closeVoiceModelMenu();
  toggleComposerMenu(false);
  const buttonRect = els.openRagButton?.getBoundingClientRect();
  state.ragQuickMenuPosition = {
    x: Math.round(buttonRect?.left || 12),
    y: Math.round((buttonRect?.bottom || 0) + 10),
  };
  renderRagQuickMenu();
  els.ragQuickMenu.hidden = false;
  positionRagQuickMenu(state.ragQuickMenuPosition.x, state.ragQuickMenuPosition.y);
  window.setTimeout(() => els.ragQuickEnabledToggle?.focus(), 0);
}

async function ingestRagSources(force = false) {
  if (!state.activeProfileId) {
    setFooter("Сначала выберите профиль для RAG.", "warning");
    return;
  }
  state.ragBusy = true;
  renderRagPanel();
  try {
    const result = await request("/rag/ingest", {
      method: "POST",
      body: { profile_id: state.activeProfileId, force },
    });
    state.ragStatus = {
      ...(state.ragStatus || {}),
      source_dir: result.source_dir,
      supported_suffixes: result.supported_suffixes,
      stats: result.stats,
    };
    await loadRagStatus({ silent: true });
    const errorCount = Array.isArray(result.errors) ? result.errors.length : 0;
    setFooter(
      `RAG индекс готов: файлов ${result.indexed}, chunks ${result.chunks_indexed}${errorCount ? `, ошибок ${errorCount}` : ""}.`,
      errorCount ? "warning" : "success",
    );
  } catch (error) {
    setFooter(`Не удалось индексировать RAG: ${error.message || error}`, "error");
  } finally {
    state.ragBusy = false;
    renderRagPanel();
  }
}

async function uploadRagFiles(files) {
  const selectedFiles = Array.from(files || []);
  if (!selectedFiles.length) return;
  if (!state.activeProfileId) {
    setFooter("Сначала выберите профиль для RAG.", "warning");
    return;
  }
  const formData = new FormData();
  selectedFiles.forEach((file) => formData.append("files", file));
  state.ragBusy = true;
  renderRagPanel();
  try {
    const result = await request(`/rag/files?profile_id=${encodeURIComponent(state.activeProfileId)}`, {
      method: "POST",
      body: formData,
    });
    state.ragStatus = result?.status || state.ragStatus;
    await loadRagStatus({ silent: true });
    const savedCount = Array.isArray(result?.saved) ? result.saved.length : 0;
    const errorCount = Array.isArray(result?.errors) ? result.errors.length : 0;
    setFooter(
      `RAG: добавлено файлов ${savedCount}${errorCount ? `, ошибок ${errorCount}` : ""}. Теперь можно индексировать.`,
      errorCount ? "warning" : "success",
    );
  } catch (error) {
    setFooter(`Не удалось добавить RAG-файлы: ${error.message || error}`, "error");
  } finally {
    state.ragBusy = false;
    renderRagPanel();
    if (els.ragFileInput) {
      els.ragFileInput.value = "";
    }
  }
}

async function deleteRagFile(sourceId, returnFocus = null) {
  const target = String(sourceId || "").trim();
  if (!target || !state.activeProfileId) return;
  const approved = await openConfirmDialog({
    eyebrow: "RAG",
    title: "Удалить RAG-файл?",
    message: `Файл «${target}» будет удалён из папки активного профиля и из индекса.`,
    confirmLabel: "Удалить",
    cancelLabel: "Отмена",
    returnFocus,
  });
  if (!approved) return;
  state.ragBusy = true;
  renderRagPanel();
  try {
    const query = new URLSearchParams({ profile_id: String(state.activeProfileId), path: target });
    const result = await request(`/rag/files?${query.toString()}`, { method: "DELETE" });
    state.ragStatus = result?.status || state.ragStatus;
    await loadRagStatus({ silent: true });
    const deleted = Array.isArray(result?.deleted) ? result.deleted : [target];
    setFooter(`RAG: удалено файлов ${deleted.length}.`, "success");
  } catch (error) {
    setFooter(`Не удалось удалить RAG-файл: ${error.message || error}`, "error");
  } finally {
    state.ragBusy = false;
    renderRagPanel();
  }
}

async function deleteRagContext(sourceId, returnFocus = null) {
  const target = String(sourceId || "").trim();
  if (!target || !state.activeProfileId) return;
  const approved = await openConfirmDialog({
    eyebrow: "RAG",
    title: "Удалить контекст?",
    message: "ASR context будет удалён из RAG-индекса и из подключённых transcript/context записей.",
    confirmLabel: "Удалить",
    cancelLabel: "Отмена",
    returnFocus,
  });
  if (!approved) return;
  state.ragBusy = true;
  renderRagPanel();
  try {
    const query = new URLSearchParams({ profile_id: String(state.activeProfileId), source_id: target });
    const result = await request(`/rag/contexts?${query.toString()}`, { method: "DELETE" });
    state.ragStatus = result?.status || state.ragStatus;
    await loadRagStatus({ silent: true });
    if (state.latestTranscript?.id && target === `transcript:${state.latestTranscript.id}`) {
      state.latestTranscript = null;
      renderTranscriptStrip();
      renderContextSummary();
    }
    setFooter("RAG: контекст удалён.", "success");
  } catch (error) {
    setFooter(`Не удалось удалить RAG-контекст: ${error.message || error}`, "error");
  } finally {
    state.ragBusy = false;
    renderRagPanel();
  }
}

async function toggleRagForActiveProfile(enabled, { notify = true } = {}) {
  const updated = await saveActiveProfilePreferences({ settings: { rag_enabled: Boolean(enabled) } });
  if (updated) {
    renderRagPanel();
    renderRagQuickMenu();
    if (notify) {
      setFooter(
        enabled
          ? "RAG включён: локальный контекст будет подмешиваться в каждый chat prompt активного профиля."
          : "RAG выключен: локальные документы не будут использоваться в chat prompt.",
        "success",
      );
    }
  } else {
    renderRagPanel();
    renderRagQuickMenu();
  }
}

async function copyText(value) {
  if (!value) return;
  await navigator.clipboard.writeText(value);
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
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
    await loadNetworkAddresses({ silent: true });
  } catch (error) {
    state.serverHealthy = false;
    state.lanUrl = fallbackLanUrl();
    state.networkAddresses = [];
    setHealthBadge("Нет связи", "error");
    renderLanUrl();
    if (!silent) {
      setFooter(`Сервер недоступен: ${error.message || error}`, "error");
    }
  }
}

async function loadNetworkAddresses({ silent = false } = {}) {
  state.networkAddressesLoading = true;
  renderLanUrl();
  try {
    const data = await request("/plugins/network-addresses");
    state.networkAddresses = normalizeNetworkAddressItems(data?.items);
    if (!state.networkAddresses.length) {
      closeNetworkAddressMenu();
    }
  } catch (error) {
    state.networkAddresses = [];
    closeNetworkAddressMenu();
    if (!silent) {
      setFooter(`Не удалось загрузить адреса доступа: ${error.message || error}`, "error");
    }
  } finally {
    state.networkAddressesLoading = false;
    renderLanUrl();
  }
}

async function loadPlugins({ silent = false } = {}) {
  state.pluginsLoading = true;
  renderPlugins();
  try {
    const data = await request("/plugins");
    state.pluginsState = {
      plugins: Array.isArray(data?.plugins) ? data.plugins : [],
      invalid_plugins: Array.isArray(data?.invalid_plugins) ? data.invalid_plugins : [],
      trusted_plugin_ids: Array.isArray(data?.trusted_plugin_ids) ? data.trusted_plugin_ids : [],
      message: data?.message || "",
    };
    if (!silent) {
      const count = state.pluginsState.plugins.length + state.pluginsState.invalid_plugins.length;
      setInlineStatus(els.pluginsStatus, count ? "Plugins registry обновлён." : "Plugins не установлены.", "success");
    }
  } catch (error) {
    if (!silent) {
      setInlineStatus(els.pluginsStatus, `Не удалось загрузить plugins: ${error.message || error}`, "error");
    }
  } finally {
    state.pluginsLoading = false;
    renderPlugins();
  }
}

async function setPluginEnabled(pluginId, enabled) {
  const id = String(pluginId || "").trim();
  if (!id || state.pluginsLoading) return;

  state.pluginsLoading = true;
  renderPlugins();
  setInlineStatus(els.pluginsStatus, enabled ? "Включаю plugin…" : "Отключаю plugin…", "warning");

  try {
    const data = await request(`/plugins/${encodeURIComponent(id)}/enabled`, {
      method: "POST",
      body: { enabled: Boolean(enabled) },
    });
    state.pluginsState = {
      plugins: Array.isArray(data?.plugins) ? data.plugins : [],
      invalid_plugins: Array.isArray(data?.invalid_plugins) ? data.invalid_plugins : [],
      trusted_plugin_ids: Array.isArray(data?.trusted_plugin_ids) ? data.trusted_plugin_ids : [],
      message: data?.message || "",
    };
    setInlineStatus(els.pluginsStatus, enabled ? "Plugin включён." : "Plugin отключён.", "success");
    setFooter(enabled ? "Plugin включён." : "Plugin отключён.", "success");
    await loadNetworkAddresses({ silent: true });
  } catch (error) {
    setInlineStatus(els.pluginsStatus, `Не удалось изменить plugin: ${error.message || error}`, "error");
    setFooter(`Plugin: ${error.message || error}`, "error");
    await loadPlugins({ silent: true });
  } finally {
    state.pluginsLoading = false;
    renderPlugins();
  }
}

async function loadModels({ silent = false } = {}) {
  try {
    const data = await request("/models");
    state.installedModels = Array.isArray(data?.installed) ? data.installed : [];
    state.recommendedModels = Array.isArray(data?.catalog)
      ? data.catalog
      : (Array.isArray(data?.recommended) ? data.recommended : []);
    state.utilityModels = Array.isArray(data?.utility) ? data.utility : [];
    state.visionModels = Array.isArray(data?.vision_catalog) ? data.vision_catalog : [];
    state.downloads = Array.isArray(data?.downloads) ? data.downloads : [];
    state.modelDiagnostics = data?.diagnostics || null;
    state.chatModelsError = data?.error || null;
    const savedModel = readStored(STORAGE_KEYS.llmModel, "");
    const installedModelNames = new Set(state.installedModels.map((item) => item.name));
    const isSelectableNow = (modelName) => (
      modelName === AUTO_MODEL_ID || modelName === LOCAL_CALCULATOR_MODEL_ID || installedModelNames.has(modelName)
    );
    const catalogIds = new Set(getCatalogModels().map((item) => getModelId(item)));
    catalogIds.add(AUTO_MODEL_ID);
    catalogIds.add(LOCAL_CALCULATOR_MODEL_ID);
    const installedCatalogModel = getCatalogModels().find((item) => (
      state.installedModels.some((installed) => installed.name === getModelId(item))
    ));
    if (state.selectedLlmModel && !catalogIds.has(state.selectedLlmModel)) {
      state.selectedLlmModel = "";
    }
    if (state.selectedLlmModel && !isSelectableNow(state.selectedLlmModel)) {
      state.selectedLlmModel = "";
    }
    if (!state.selectedLlmModel) {
      state.selectedLlmModel = savedModel && catalogIds.has(savedModel) && isSelectableNow(savedModel)
        ? savedModel
        : getModelId(installedCatalogModel) || "";
    }
    if (!state.selectedLlmModel) {
      writeStored(STORAGE_KEYS.llmModel, "");
    } else {
      writeStored(STORAGE_KEYS.llmModel, state.selectedLlmModel);
    }
    renderModelControls();
    renderVisionSettings();
    renderDownloads();
    void refreshModelSettings({ silent: true });
    syncDownloadsPolling();
  } catch (error) {
    state.chatModelsError = error.message || String(error);
    renderChatModelNotice();
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
    if (state.activeProfileId) {
      applyActiveProfilePreferences();
    } else if (!state.selectedWhisperModel) {
      state.selectedWhisperModel = data?.studio_default || ASR_STUDIO_DEFAULT_MODEL;
      state.selectedChatWhisperModel = data?.default || state.asrModels[0]?.name || "medium";
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
    state.ttsSpeedOptions = Array.isArray(health?.speed_options) && health.speed_options.length
      ? health.speed_options.map((item) => Number(item)).filter(Number.isFinite)
      : [...DEFAULT_TTS_SPEED_OPTIONS];
    if (!state.ttsSpeedOptions.some((item) => formatTtsSpeedLabel(item) === formatTtsSpeedLabel(state.selectedTtsSpeed))) {
      state.selectedTtsSpeed = formatTtsSpeedLabel(state.ttsSpeedOptions[0] || 1);
    }
    state.ttsVoices = Array.isArray(voicesData?.items) ? voicesData.items : [];
    if (state.activeProfileId) {
      applyActiveProfilePreferences();
    }
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

async function refreshAsrPipelineSettings({ silent = false } = {}) {
  if (!state.activeProfileId) {
    state.asrPipelineSettingsState = { effective: {}, overrides: {}, defaults: {} };
    renderAsrPipelineSettings();
    if (!silent) {
      setInlineStatus(els.asrPipelineSettingsStatus, "Выберите профиль.", "warning");
    }
    return;
  }

  try {
    const data = await request(`/model_settings?profile_id=${encodeURIComponent(state.activeProfileId)}&model_name=${encodeURIComponent(ASR_PIPELINE_SETTINGS_MODEL_ID)}`);
    state.asrPipelineSettingsState = data || { effective: {}, overrides: {}, defaults: {} };
    renderAsrPipelineSettings();
    if (!silent) {
      setInlineStatus(els.asrPipelineSettingsStatus, "Настройки анализа загружены.", "success");
    }
  } catch (error) {
    if (!silent) {
      setInlineStatus(els.asrPipelineSettingsStatus, `Не удалось загрузить настройки анализа: ${error.message || error}`, "error");
    }
  }
}

async function openSession(sessionId) {
  if (state.currentSessionId !== (sessionId || null) && state.chatAttachments.length) {
    await clearChatAttachments({ deleteRemote: true });
  }
  state.currentSessionId = sessionId || null;
  writeStored(STORAGE_KEYS.activeSessionId, state.currentSessionId || "");

  if (!sessionId) {
    state.messages = [];
    state.messageAttachments = {};
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
    const [messagesData, transcriptsData, attachmentsData] = await Promise.all([
      request(`/sessions/${encodeURIComponent(sessionId)}/messages`),
      request(`/transcripts?profile_id=${encodeURIComponent(state.activeProfileId)}&session_id=${encodeURIComponent(sessionId)}`),
      request(`/chat/attachments?profile_id=${encodeURIComponent(state.activeProfileId)}&session_id=${encodeURIComponent(sessionId)}`),
    ]);

    state.messages = Array.isArray(messagesData?.messages) ? messagesData.messages : [];
    state.messageAttachments = (Array.isArray(attachmentsData?.attachments) ? attachmentsData.attachments : [])
      .reduce((groups, attachment) => {
        const key = String(attachment?.message_id ?? "");
        if (!key) return groups;
        groups[key] = [...(groups[key] || []), attachment];
        return groups;
      }, {});
    const transcripts = Array.isArray(transcriptsData?.transcripts) ? transcriptsData.transcripts : [];
    state.latestTranscript = transcripts[0] || null;
    renderMessages();
    renderTranscriptStrip();
    scrollMessagesToBottom({ force: true });
    void recoverActiveChatTaskFromMessages();
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
  if (state.activeProfileId && state.activeProfileId !== (profileId || null) && state.chatAttachments.length) {
    await clearChatAttachments({ deleteRemote: true });
  }
  state.activeProfileId = profileId || null;
  state.profileManagementMode = "edit";
  writeStored(STORAGE_KEYS.activeProfileId, state.activeProfileId || "");
  state.asrToolSelectedTranscriptId = null;
  state.asrToolSelectedTranscript = null;
  state.asrToolHistory = [];
  state.ragStatus = null;
  applyActiveProfilePreferences();
  renderProfileOptions();
  renderProfileManagement();
  await loadSessions({ preferredSessionId });
  await loadAsrToolHistory({ silent: true });
  await loadRagStatus({ silent: true });
  await refreshModelSettings({ silent: true });
  await refreshAsrPipelineSettings({ silent: true });
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
    const memTurnsValue = parseOptionalNumber(els.memTurnsInput?.value, "int");
    const residencySettings = collectResidencySettings();
    const currentResidentLimit = Number(
      state.modelSettingsState?.overrides?.max_resident_target_models
      ?? state.modelSettingsState?.effective?.max_resident_target_models
      ?? RESIDENCY_DEFAULTS.max_resident_target_models,
    );
    if (
      residencySettings.max_resident_target_models >= 4
      && residencySettings.max_resident_target_models !== currentResidentLimit
    ) {
      const approved = await openConfirmDialog({
        eyebrow: "Ollama memory",
        title: "Высокий лимит моделей в памяти",
        message: "Вы выбрали высокий лимит моделей в памяти.\n\nНа Mac с 16 GB RAM это может привести к повышенному расходу памяти, swap, нагреву, замедлению системы и долгой выгрузке моделей из Ollama.\n\nРекомендуемое значение для MBP M1 Pro 16GB: 2 модели.\n\nПродолжить?",
        confirmLabel: "Подтвердить",
        cancelLabel: "Отмена",
        returnFocus: els.maxResidentTargetModelsSelect,
      });
      if (!approved) {
        if (els.maxResidentTargetModelsSelect) {
          els.maxResidentTargetModelsSelect.value = String(currentResidentLimit || RESIDENCY_DEFAULTS.max_resident_target_models);
          queueSyncAppSelects();
        }
        setInlineStatus(els.modelSettingsStatus, "Высокий лимит не сохранён.", "warning");
        return;
      }
    }
    const memTurnsWarning = memTurnsValue && memTurnsValue > 12
      ? "Большое значение памяти увеличивает размер prompt, замедляет ответы и может ухудшить качество. Для длинных диалогов лучше использовать summary memory."
      : "";
    if (memTurnsWarning) {
      setInlineStatus(
        els.modelSettingsStatus,
        memTurnsWarning,
        "warning",
      );
    }
    const data = await request("/model_settings", {
      method: "POST",
      body: buildModelSettingsPayload({
        temperature: parseOptionalNumber(els.temperatureInput?.value, "float"),
        max_tokens: parseOptionalNumber(els.maxTokensInput?.value, "int"),
        num_ctx: parseOptionalNumber(els.numCtxInput?.value, "int"),
        ollama_keep_alive: collectKeepAliveValue(),
        ollama_think: modelSupportsThinking(modelName)
          ? normalizeOllamaThink(els.quickThinkingControl?.dataset.thinkingMode, "on")
          : null,
      }),
    });
    state.modelSettingsState = data || state.modelSettingsState;
    const profileSettingsPatch = {
      ...residencySettings,
      streaming_enabled: Boolean(els.streamingEnabledToggle?.checked),
    };
    if (memTurnsValue !== null) {
      profileSettingsPatch.mem_turns = memTurnsValue;
    }
    if (Object.keys(profileSettingsPatch).length) {
      const updatedProfile = await saveActiveProfilePreferences({ settings: profileSettingsPatch });
      if (!updatedProfile) {
        throw new Error("не удалось сохранить настройки профиля");
      }
    }
    await refreshModelSettings({ silent: true });
    setInlineStatus(
      els.modelSettingsStatus,
      memTurnsWarning ? `Настройки сохранены. ${memTurnsWarning}` : "Настройки сохранены.",
      memTurnsWarning ? "warning" : "success",
    );
  } catch (error) {
    setInlineStatus(els.modelSettingsStatus, `Не удалось сохранить настройки: ${error.message || error}`, "error");
  }
}

async function saveStreamingPreferenceFlow() {
  if (!els.streamingEnabledToggle || !state.activeProfileId) return;
  const checked = Boolean(els.streamingEnabledToggle.checked);
  const previous = activeProfileStreamingEnabled();

  patchActiveProfileSettingsLocal({ streaming_enabled: checked });
  els.streamingEnabledToggle.disabled = true;
  setInlineStatus(
    els.modelSettingsStatus,
    checked ? "Стриминг ответов включается…" : "Стриминг ответов выключается…",
    "warning",
  );

  const updatedProfile = await saveActiveProfilePreferences({ settings: { streaming_enabled: checked } });
  if (!updatedProfile) {
    patchActiveProfileSettingsLocal({ streaming_enabled: previous });
    setInlineStatus(els.modelSettingsStatus, "Не удалось сохранить настройку стриминга.", "error");
    return;
  }

  setInlineStatus(
    els.modelSettingsStatus,
    checked ? "Стриминг ответов включён. Следующее сообщение пойдёт через SSE." : "Стриминг ответов выключен. Следующее сообщение дождётся полного ответа.",
    "success",
  );
  renderModelSettings();
}

async function saveShowRouterThinkingToggleFlow() {
  if (!els.showRouterThinkingToggle || !state.activeProfileId) return;
  const checked = Boolean(els.showRouterThinkingToggle.checked);
  const previous = Boolean((getActiveProfilePreferences()?.settings || {}).show_router_thinking_toggle);

  patchActiveProfileSettingsLocal({ show_router_thinking_toggle: checked });
  renderQuickModelPicker();
  setInlineStatus(
    els.modelSettingsStatus,
    checked
      ? "Thinking для Auto / Smart Router будет показан в меню выбора модели."
      : "Thinking для Auto / Smart Router скрыт из меню выбора модели.",
    "warning",
  );

  const updatedProfile = await saveActiveProfilePreferences({ settings: { show_router_thinking_toggle: checked } });
  if (!updatedProfile) {
    patchActiveProfileSettingsLocal({ show_router_thinking_toggle: previous });
    renderQuickModelPicker();
    setInlineStatus(els.modelSettingsStatus, "Не удалось сохранить настройку router Thinking.", "error");
    return;
  }

  renderQuickModelPicker();
  setInlineStatus(
    els.modelSettingsStatus,
    checked
      ? "Router Thinking будет отображаться в верхнем меню."
      : "Router Thinking скрыт из верхнего меню.",
    "success",
  );
}

async function saveQuickThinkingModeFlow() {
  const modelName = state.selectedLlmModel || els.llmModelSelect?.value || "";
  if (!state.activeProfileId || !modelName || !modelSupportsThinking(modelName)) {
    renderQuickThinkingControl(state.modelSettingsState?.effective?.ollama_think);
    return;
  }
  const nextMode = normalizeOllamaThink(els.quickThinkingControl?.dataset.thinkingMode, "on");
  try {
    const data = await request("/model_settings", {
      method: "POST",
      body: buildModelSettingsPayload({ ollama_think: nextMode }),
    });
    state.modelSettingsState = data || state.modelSettingsState;
    renderModelSettings();
    setFooter(`Thinking ${nextMode === "off" ? "выключен" : "включён"} для текущей модели.`, "success");
  } catch (error) {
    renderModelSettings();
    setFooter(`Не удалось сохранить Thinking: ${error.message || error}`, "error");
  }
}

async function saveAsrPipelineSettingsFlow() {
  if (!state.activeProfileId) {
    setInlineStatus(els.asrPipelineSettingsStatus, "Нет активного профиля.", "warning");
    return;
  }

  try {
    const data = await request("/model_settings", {
      method: "POST",
      body: {
        profile_id: state.activeProfileId,
        model_name: ASR_PIPELINE_SETTINGS_MODEL_ID,
        ollama_think: normalizeOllamaThink(els.asrPipelineThinkSelect?.value, "off"),
        pipeline: collectAsrPipelineSettingsFromControls(),
      },
    });
    state.asrPipelineSettingsState = data || state.asrPipelineSettingsState;
    renderAsrPipelineSettings();
    setInlineStatus(els.asrPipelineSettingsStatus, "Настройки анализа сохранены.", "success");
  } catch (error) {
    setInlineStatus(els.asrPipelineSettingsStatus, `Не удалось сохранить анализ: ${error.message || error}`, "error");
  }
}

async function resetAsrPipelineSettingsFlow() {
  if (!state.activeProfileId) {
    setInlineStatus(els.asrPipelineSettingsStatus, "Нет активного профиля.", "warning");
    return;
  }

  try {
    const data = await request("/model_settings/reset_to_defaults", {
      method: "POST",
      body: {
        profile_id: state.activeProfileId,
        model_name: ASR_PIPELINE_SETTINGS_MODEL_ID,
      },
    });
    state.asrPipelineSettingsState = data || state.asrPipelineSettingsState;
    renderAsrPipelineSettings();
    setInlineStatus(els.asrPipelineSettingsStatus, "Настройки стадий сброшены к рекомендациям.", "success");
  } catch (error) {
    setInlineStatus(els.asrPipelineSettingsStatus, `Не удалось сбросить стадии: ${error.message || error}`, "error");
  }
}

function confirmAsrFullAnalysisRisk() {
  return window.confirm(`${ASR_FULL_ANALYSIS_WARNING}\n\nПродолжить?`);
}

async function saveAsrFullAnalysisPreferenceFlow() {
  if (!els.asrFullAnalysisEnabledToggle || !state.activeProfileId) return;
  const checked = Boolean(els.asrFullAnalysisEnabledToggle.checked);
  const previous = asrFullAnalysisEnabled();

  if (checked && !previous && !confirmAsrFullAnalysisRisk()) {
    els.asrFullAnalysisEnabledToggle.checked = false;
    return;
  }

  patchActiveProfileSettingsLocal({ asr_full_analysis_enabled: checked });
  els.asrFullAnalysisEnabledToggle.disabled = true;
  setInlineStatus(
    els.asrPipelineSettingsStatus,
    checked ? "Включаю полный анализ ASR…" : "Отключаю полный анализ ASR…",
    "warning",
  );

  const updatedProfile = await saveActiveProfilePreferences({ settings: { asr_full_analysis_enabled: checked } });
  if (!updatedProfile) {
    patchActiveProfileSettingsLocal({ asr_full_analysis_enabled: previous });
    setInlineStatus(els.asrPipelineSettingsStatus, "Не удалось сохранить настройку полного анализа.", "error");
    renderAsrPipelineSettings();
    renderAsrTool();
    return;
  }

  setInlineStatus(
    els.asrPipelineSettingsStatus,
    checked
      ? "Полный анализ включён для этого профиля. Используйте осторожно: он запускает все стадии."
      : "Полный анализ отключён. Саммари работает в облегчённом режиме.",
    "success",
  );
  renderAsrPipelineSettings();
  renderAsrTool();
}

async function saveAsrDiagnosticsPreferenceFlow() {
  if (!els.asrDiagnosticsEnabledToggle || !state.activeProfileId) return;
  const checked = Boolean(els.asrDiagnosticsEnabledToggle.checked);
  const previous = asrDiagnosticsEnabled();

  patchActiveProfileAsrLocal({ diagnostics_enabled: checked });
  els.asrDiagnosticsEnabledToggle.disabled = true;
  setInlineStatus(
    els.asrPipelineSettingsStatus,
    checked ? "Включаю ASR-логи…" : "Выключаю ASR-логи и удаляю папку diagnostics…",
    "warning",
  );

  const updatedProfile = await saveActiveProfilePreferences({ asr: { diagnostics_enabled: checked } });
  if (!updatedProfile) {
    patchActiveProfileAsrLocal({ diagnostics_enabled: previous });
    setInlineStatus(els.asrPipelineSettingsStatus, "Не удалось сохранить настройку ASR-логов.", "error");
    renderAsrPipelineSettings();
    return;
  }

  setInlineStatus(
    els.asrPipelineSettingsStatus,
    checked
      ? "ASR-логи включены. Диагностика pipeline будет записываться в папку профиля."
      : "ASR-логи выключены. Папка diagnostics для профиля удалена.",
    "success",
  );
  renderAsrPipelineSettings();
}

async function resetModelSettingsFlow() {
  const modelName = state.selectedLlmModel || els.llmModelSelect?.value || "";
  if (!state.activeProfileId || !modelName) {
    setInlineStatus(els.modelSettingsStatus, "Нет активного профиля или модели.", "warning");
    return;
  }

  try {
    const defaultMemTurns = parseOptionalNumber(state.modelSettingsState?.defaults?.mem_turns, "int") || 6;
    const defaultStreamingEnabled = state.modelSettingsState?.defaults?.streaming_enabled !== false;
    const data = await request("/model_settings/reset_to_defaults", {
      method: "POST",
      body: {
        profile_id: state.activeProfileId,
        model_name: modelName,
      },
    });
    state.modelSettingsState = data || state.modelSettingsState;
    await saveActiveProfilePreferences({
      settings: {
        mem_turns: defaultMemTurns,
        streaming_enabled: defaultStreamingEnabled,
        ...RESIDENCY_DEFAULTS,
        show_router_thinking_toggle: false,
      },
    });
    await refreshModelSettings({ silent: true });
    setInlineStatus(els.modelSettingsStatus, "Настройки модели, память диалога и resident-политика сброшены.", "success");
  } catch (error) {
    setInlineStatus(els.modelSettingsStatus, `Не удалось сбросить настройки: ${error.message || error}`, "error");
  }
}

async function saveProfileSystemPromptFlow() {
  if (!state.activeProfileId) {
    setInlineStatus(els.profileStatus, "Сначала выберите профиль.", "warning");
    return;
  }
  if (state.profileManagementMode === "create") {
    setInlineStatus(els.profileStatus, "Сначала создайте профиль или выберите существующий.", "warning");
    return;
  }
  const systemPrompt = String(els.profileSystemPromptInput?.value || "").trim();
  const description = String(els.profileDescriptionInput?.value || "").trim();
  try {
    const updatedProfile = await request(`/profiles/${encodeURIComponent(state.activeProfileId)}`, {
      method: "PATCH",
      body: {
        description: description || null,
        system_prompt: systemPrompt,
      },
    });
    replaceProfileState(updatedProfile);
    renderProfileOptions();
    renderProfileManagement();
    applyActiveProfilePreferences();
    setInlineStatus(els.profileStatus, "Профиль сохранён.", "success");
  } catch (error) {
    setInlineStatus(els.profileStatus, `Не удалось сохранить профиль: ${error.message || error}`, "error");
  }
}

async function createProfileFlow() {
  if (state.profileManagementMode !== "create") {
    enterProfileCreateMode();
    return;
  }
  const name = (els.profileNameInput?.value || "").trim();
  const description = (els.profileDescriptionInput?.value || "").trim();
  const systemPrompt = (els.profileSystemPromptInput?.value || "").trim();
  if (!name) {
    setInlineStatus(els.profileStatus, "Введите название профиля.", "warning");
    renderProfileManagement();
    return;
  }

  try {
    const profile = await request("/profiles", {
      method: "POST",
      body: {
        name,
        description: description || null,
        system_prompt: systemPrompt || null,
      },
    });
    state.profiles = [...state.profiles, profile];
    state.profileManagementMode = "edit";
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
    model_name: String(state.selectedLlmModel || "").trim(),
  };

  const session = await request("/sessions", { method: "POST", body: payload });
  await loadSessions({ preferredSessionId: session.id });
  return session.id;
}

async function ensureModelInstalled(modelName) {
  const target = String(modelName || "").trim();
  if (!target) {
    setFooter("Модель не выбрана. Выберите модель и повторите отправку.", "warning");
    return false;
  }
  if (target === AUTO_MODEL_ID) {
    return true;
  }
  if (target === LOCAL_CALCULATOR_MODEL_ID) {
    return true;
  }
  if (state.installedModels.some((item) => item.name === target)) {
    return true;
  }
  setFooter("Модель не загружена. Загрузите модель и повторите отправку.", "warning");
  return false;
}

async function sendPromptText(
  rawQuery,
  { clearInput = false, attachmentIds = [], consumeComposerAttachments = false } = {},
) {
  const normalizedAttachmentIds = Array.from(new Set(
    (Array.isArray(attachmentIds) ? attachmentIds : []).map((item) => String(item || "").trim()).filter(Boolean),
  ));
  const query = String(rawQuery || "").trim()
    || (normalizedAttachmentIds.length ? "Проанализируй прикреплённое изображение." : "");
  if (state.isSending) {
    await cancelCurrentChatGeneration();
    return;
  }
  if (!query) return;
  if (!state.activeProfileId) {
    setFooter("Сначала выберите профиль.", "warning");
    return;
  }

  const selectedModel = String(state.selectedLlmModel || els.llmModelSelect?.value || "").trim();
  const modelAvailable = await ensureModelInstalled(selectedModel);
  if (!modelAvailable) {
    return;
  }

  state.isSending = true;
  state.chatTaskId = null;
  const controller = new AbortController();
  state.chatTaskStartController = controller;
  updateSendButtonState();
  renderChatAttachments();
  if (clearInput && els.promptInput) {
    els.promptInput.value = "";
    autoResizePrompt();
    updateSendButtonState();
  }

  let activeTaskId = "";
  try {
    const payload = {
      query,
      profile_id: state.activeProfileId,
      model: selectedModel,
      model_name: selectedModel,
      stream: activeProfileStreamingEnabled(),
    };
    if (normalizedAttachmentIds.length) {
      payload.attachment_ids = normalizedAttachmentIds;
    }

    if (state.currentSessionId) {
      payload.session_id = state.currentSessionId;
    }

    const task = await request("/chat/tasks", { method: "POST", body: payload, signal: controller.signal });
    if (consumeComposerAttachments && normalizedAttachmentIds.length) {
      await clearChatAttachments({ deleteRemote: false });
    }
    activeTaskId = task?.id || task?.task_id || "";
    state.chatTaskStartController = null;
    state.chatTaskId = task?.id || null;
    const nextSessionId = task?.session_id || state.currentSessionId;
    state.selectedLlmModel = selectedModel === AUTO_MODEL_ID ? AUTO_MODEL_ID : (task?.model_name || selectedModel);
    writeStored(STORAGE_KEYS.llmModel, state.selectedLlmModel || "");

    if (nextSessionId) {
      await loadSessions({ preferredSessionId: nextSessionId });
    }

    if (String(task?.state || "") === "completed") {
      return;
    }

    let completedTask = null;
    const shouldUseSse = Boolean(payload.stream && task?.id);
    if (shouldUseSse) {
      try {
        completedTask = await waitForChatTaskEvents(task);
      } catch (streamError) {
        if (streamError?.chatTaskFailed) {
          throw streamError;
        }
        setFooter("Поток ответа прервался, жду финальный результат…", "warning");
        completedTask = await waitForChatTask(task?.id || "");
      }
    } else {
      completedTask = await waitForChatTask(task?.id || "");
    }
    state.chatTaskId = null;

    if (String(completedTask?.state || "") === "cancelled") {
      if (nextSessionId) {
        await loadSessions({
          preferredSessionId: String(state.currentSessionId || "") === String(nextSessionId) ? nextSessionId : null,
        });
      }
      setFooter("Генерация ответа остановлена.", "warning");
      return;
    }

    if (nextSessionId) {
      await loadSessions({
        preferredSessionId: String(state.currentSessionId || "") === String(nextSessionId) ? nextSessionId : null,
      });
    }
  } catch (error) {
    if (isAbortError(error)) {
      setFooter("Генерация ответа остановлена.", "warning");
      return;
    }
    if (state.currentSessionId) {
      await loadSessions({ preferredSessionId: state.currentSessionId });
    }
    setFooter(`Ошибка чата: ${error.message || error}`, "error");
  } finally {
    state.chatTaskId = null;
    state.chatTaskStartController = null;
    closeChatTaskEventSource();
    clearChatTaskReplay();
    clearChatTypingStreams(activeTaskId);
    state.isSending = false;
    updateSendButtonState();
    renderChatAttachments();
    scrollMessagesToBottom({ force: true });
  }
}

async function sendCurrentPrompt() {
  const query = (els.promptInput?.value || "").trim();
  const attachmentIds = state.chatAttachments
    .filter((item) => item.status === "ready" && item.server?.id)
    .map((item) => item.server.id);
  await sendPromptText(query, {
    clearInput: true,
    attachmentIds,
    consumeComposerAttachments: true,
  });
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
    formData.append("model", getSelectedChatWhisperModel() || "small");
    formData.append("prompt_preset", normalizePromptPreset(state.selectedPromptPreset));
    formData.append("language", languageForPromptPreset(state.selectedPromptPreset));
    formData.append("beam_size", String(normalizeAsrBeamSize(state.selectedAsrBeamSize)));
    formData.append("threads", String(normalizeAsrThreads(state.selectedAsrThreads)));

    formData.append("store_result", "true");

    const task = await request("/transcribe/tasks", { method: "POST", body: formData });
    const data = await waitForVoiceTranscriptionTask(task?.id || "", {
      timeoutMs: transcriptionTimeoutForFile(file),
    });
    if (data?.cancelled) {
      setFooter("Транскрибация остановлена.", "warning");
      return;
    }
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

async function startModelDownload(modelName, { mode = "download" } = {}) {
  const target = (modelName || "").trim();
  if (!target) {
    setFooter("Укажите модель Ollama для загрузки.", "warning");
    return;
  }
  if (hasActiveDownload(target)) {
    renderDownloads();
    return;
  }

  const isUpdate = mode === "update";
  const confirmed = await openConfirmDialog({
    eyebrow: isUpdate ? "Обновление модели" : "Загрузка модели",
    title: isUpdate ? "Обновить модель?" : "Загрузить модель?",
    message: `Будет запущен ollama pull для модели: ${target}`,
    confirmLabel: isUpdate ? "Обновить" : "Загрузить",
  });
  if (!confirmed) return;

  try {
    await request("/models/pull", { method: "POST", body: { model: target } });
    await loadModels({ silent: true });
    renderSettings();
  } catch (error) {
    setFooter(`Не удалось запустить ${isUpdate ? "обновление" : "загрузку"} модели: ${error.message || error}`, "error");
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
    setFooter(`${force ? "Обновление" : "Подготовка"} ASR-модели ${target} запущена.`, "success");
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
    if (result?.prepare_required) {
      setFooter(result?.message || `ASR-модель ${target} требует подготовки. Запускаю загрузку/сборку.`, "warning");
      await prepareAsrModel(target, { force: false });
      return;
    }
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

async function renameSessionById(sessionId) {
  const session = state.sessions.find((item) => item.id === sessionId);
  if (!session) return;
  const currentTitle = session.title || "Новый чат";
  const nextTitle = window.prompt("Новое название чата", currentTitle);
  if (nextTitle === null) return;
  const title = nextTitle.trim();
  if (!title) {
    setFooter("Название чата не может быть пустым.", "warning");
    return;
  }
  if (title === currentTitle) return;

  try {
    const updated = await request(`/sessions/${encodeURIComponent(sessionId)}`, {
      method: "PATCH",
      body: { title },
    });
    state.sessions = state.sessions.map((item) => (item.id === updated.id ? updated : item));
    renderSessionList();
    if (updated.id === state.currentSessionId) {
      applyCurrentSessionMeta();
    }
    setFooter("Чат переименован.", "success");
  } catch (error) {
    setFooter(`Не удалось переименовать чат: ${error.message || error}`, "error");
  }
}

async function renameAsrToolTranscriptById(transcriptId) {
  const targetId = Number(transcriptId || 0);
  if (!Number.isFinite(targetId) || targetId <= 0) return;
  const transcript = state.asrToolHistory.find((item) => Number(item.id) === targetId)
    || (state.asrToolSelectedTranscript && Number(state.asrToolSelectedTranscript.id) === targetId
      ? state.asrToolSelectedTranscript
      : null);
  if (!transcript) return;

  const currentTitle = getAsrTranscriptTitle(transcript);
  const nextTitle = window.prompt("Новое название транскрибации", currentTitle);
  if (nextTitle === null) return;
  const title = nextTitle.trim();
  if (!title) {
    setFooter("Название транскрибации не может быть пустым.", "warning");
    return;
  }
  if (title === currentTitle) return;

  try {
    const updated = await request(`/transcripts/${encodeURIComponent(targetId)}`, {
      method: "PATCH",
      body: { name: title },
    });
    state.asrToolHistory = state.asrToolHistory.map((item) => (
      Number(item.id) === targetId ? { ...item, ...updated } : item
    ));
    if (Number(state.asrToolSelectedTranscriptId || 0) === targetId) {
      state.asrToolSelectedTranscript = { ...(state.asrToolSelectedTranscript || {}), ...updated };
    }
    renderAsrTool();
    setFooter("Транскрибация переименована.", "success");
  } catch (error) {
    setFooter(`Не удалось переименовать транскрибацию: ${error.message || error}`, "error");
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

async function deleteCurrentContext() {
  const transcriptId = state.latestTranscript?.id;
  if (!transcriptId) return;
  const approved = await openConfirmDialog({
    eyebrow: "Context",
    title: "Удалить подключённый context?",
    message: "Запись transcript/context будет удалена из базы для текущего чата.",
    confirmLabel: "Удалить",
    cancelLabel: "Отмена",
    returnFocus: els.clearContextButton,
  });
  if (!approved) return;
  try {
    await request(`/transcripts/${encodeURIComponent(transcriptId)}`, { method: "DELETE" });
    state.latestTranscript = null;
    renderTranscriptStrip();
    renderContextSummary();
    setFooter("Подключённый context удалён.", "success");
  } catch (error) {
    setFooter(`Не удалось удалить context: ${error.message || error}`, "error");
  }
}

async function copyLanUrlOnly() {
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

async function copyNetworkAddressItem(item) {
  if (!item?.url) {
    setFooter("Адрес доступа пока недоступен.", "warning");
    return;
  }
  try {
    await copyText(item.url);
    setFooter(`${item.label || "Адрес"} URL скопирован.`, "success");
  } catch {
    setFooter("Не удалось скопировать адрес доступа.", "error");
  }
}

function openNetworkAddressMenu() {
  if (!els.networkAddressMenu || !els.copyLanUrlButton) return;
  const items = availableNetworkAddresses();
  if (items.length < 2) return;
  closeRagQuickMenu();
  closeQuickModelMenu();
  closeVoiceModelMenu();
  toggleComposerMenu(false);
  const rect = els.copyLanUrlButton.getBoundingClientRect();
  state.networkAddressMenuPosition = {
    x: Math.round(rect.left),
    y: Math.round(rect.bottom + 10),
  };
  renderNetworkAddressMenu();
  els.networkAddressMenu.hidden = false;
  els.copyLanUrlButton.setAttribute("aria-expanded", "true");
  positionNetworkAddressMenu(state.networkAddressMenuPosition.x, state.networkAddressMenuPosition.y);
  window.setTimeout(() => {
    els.networkAddressMenu?.querySelector("[data-network-address-index]")?.focus();
  }, 0);
}

async function copyNetworkAddress() {
  await loadNetworkAddresses({ silent: true });
  const items = availableNetworkAddresses();
  if (!items.length) {
    setFooter("Адрес доступа пока недоступен.", "warning");
    return;
  }
  if (items.length === 1) {
    await copyNetworkAddressItem(items[0]);
    return;
  }
  openNetworkAddressMenu();
}

function isExpectedShutdownError(error) {
  const raw = String(error?.message || error || "").toLowerCase();
  return raw.includes("failed to fetch")
    || raw.includes("load failed")
    || raw.includes("networkerror")
    || raw.includes("network request failed")
    || raw.includes("the network connection was lost");
}

async function waitForBackendRestart() {
  await sleep(900);
  for (let attempt = 0; attempt < 24; attempt += 1) {
    try {
      await request("/health");
      await loadHealth({ silent: true });
      return true;
    } catch {
      state.serverHealthy = false;
      setHealthBadge("Перезапуск…", "warning");
    }
    await sleep(500);
  }
  return false;
}

async function restartBackendRuntime() {
  const approved = await openConfirmDialog({
    eyebrow: "Приложение",
    title: "Перезапустить backend?",
    message: "Backend LocalGPT будет перезапущен. Текущие генерации, транскрибации и TTS-задачи будут остановлены. Страница попробует восстановить соединение автоматически.",
    confirmLabel: "Перезапустить",
    cancelLabel: "Отмена",
    returnFocus: els.restartBackendButton,
  });
  if (!approved) return;

  state.appRuntimeBusy = true;
  renderAppRuntimeMaintenance();
  setInlineStatus(els.appRuntimeStatus, "Перезапуск backend…", "warning");
  setFooter("Перезапуск backend…", "warning");
  setHealthBadge("Перезапуск…", "warning");

  try {
    await request("/runtime/restart", { method: "POST", body: {} });
  } catch (error) {
    if (!isExpectedShutdownError(error)) {
      setInlineStatus(els.appRuntimeStatus, `Не удалось запустить перезапуск: ${error.message || error}`, "error");
      setFooter(`Не удалось перезапустить backend: ${error.message || error}`, "error");
      state.appRuntimeBusy = false;
      renderAppRuntimeMaintenance();
      return;
    }
  }

  const ok = await waitForBackendRestart();
  state.appRuntimeBusy = false;
  renderAppRuntimeMaintenance();
  if (ok) {
    setInlineStatus(els.appRuntimeStatus, "Backend перезапущен.", "success");
    setFooter("Backend перезапущен.", "success");
    await Promise.all([
      loadModels({ silent: true }),
      loadWhisperModels({ silent: true }),
      loadTtsSettings({ silent: true }),
      loadProfiles(),
    ]);
    return;
  }
  setInlineStatus(els.appRuntimeStatus, "Backend не ответил после перезапуска. Проверьте launcher или терминал.", "error");
  setFooter("Backend не ответил после перезапуска.", "error");
}

async function shutdownRuntime() {
  const approved = await openConfirmDialog({
    eyebrow: "Приложение",
    title: "Остановить приложение?",
    message: "Backend и Caddy будут остановлены. После этого текущая страница потеряет связь с API; для нового старта понадобится launcher или ручной запуск.",
    confirmLabel: "Остановить",
    cancelLabel: "Отмена",
    returnFocus: els.shutdownButton,
  });
  if (!approved) return;

  state.appRuntimeBusy = true;
  renderAppRuntimeMaintenance();
  setInlineStatus(els.appRuntimeStatus, "Остановка приложения…", "warning");
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
    setInlineStatus(els.appRuntimeStatus, `Не удалось остановить: ${error.message || error}`, "error");
    state.appRuntimeBusy = false;
    renderAppRuntimeMaintenance();
  }
}

function formatDatabaseDeleted(result, emptyMessage = "Удалять нечего.") {
  const labels = {
    profiles: "профилей",
    chat_sessions: "чатов",
    chat_messages: "сообщений",
    transcripts: "транскриптов",
    transcript_pipeline_runs: "pipeline-запусков",
    session_summaries: "summary",
    source_documents: "документов индекса",
    document_chunks: "chunks",
    document_embeddings: "embeddings",
    model_settings: "настроек моделей",
  };
  const deleted = result?.deleted && typeof result.deleted === "object" ? result.deleted : {};
  const parts = Object.entries(deleted)
    .map(([key, value]) => [labels[key] || key, Number(value) || 0])
    .filter(([, value]) => value > 0)
    .map(([label, value]) => `${label}: ${value}`);
  return parts.length ? `Удалено: ${parts.join(" • ")}.` : emptyMessage;
}

function clearClientDatabaseState() {
  writeStored(STORAGE_KEYS.activeProfileId, "");
  writeStored(STORAGE_KEYS.activeSessionId, "");
  state.activeProfileId = null;
  state.currentSessionId = null;
  state.sessions = [];
  state.messages = [];
  state.latestTranscript = null;
  state.asrToolHistory = [];
  state.asrToolSelectedTranscriptId = null;
  state.asrToolSelectedTranscript = null;
  state.asrToolPipelineRun = null;
  state.ragStatus = null;
  renderSessionList();
  renderMessages();
  renderContextSummary();
  renderAsrTool();
  renderRagPanel();
}

async function cleanupDatabaseGarbage() {
  const approved = await openConfirmDialog({
    eyebrow: "База данных",
    title: "Очистить мусор БД?",
    message: "Будут удалены осиротевшие записи после удалённых чатов. ASR Studio записи и ручные RAG-файлы сохраняются.",
    confirmLabel: "Очистить",
    returnFocus: els.cleanupDatabaseButton,
  });
  if (!approved) return;

  state.databaseMaintenanceBusy = true;
  renderDatabaseMaintenance();
  setInlineStatus(els.databaseStatus, "Очистка БД…", "warning");

  try {
    const result = await request("/database/cleanup", { method: "POST", body: { vacuum: true } });
    setInlineStatus(els.databaseStatus, formatDatabaseDeleted(result, "Мусор не найден."), "success");
    setFooter("Очистка БД завершена.", "success");
    await Promise.all([
      loadSessions({ preferredSessionId: state.currentSessionId }),
      loadAsrToolHistory({ silent: true }),
      loadRagStatus({ silent: true }),
    ]);
  } catch (error) {
    setInlineStatus(els.databaseStatus, `Ошибка очистки БД: ${error.message || error}`, "error");
    setFooter(`Не удалось очистить БД: ${error.message || error}`, "error");
  } finally {
    state.databaseMaintenanceBusy = false;
    renderDatabaseMaintenance();
  }
}

async function resetDatabaseFully() {
  const approved = await openConfirmDialog({
    eyebrow: "База данных",
    title: "Полностью очистить БД?",
    message: "Будут удалены все профили, чаты, сообщения, транскрипты, RAG-индекс и профильные RAG-папки. Загруженные модели не удаляются.",
    confirmLabel: "Полная очистка",
    returnFocus: els.resetDatabaseButton,
  });
  if (!approved) return;

  state.databaseMaintenanceBusy = true;
  renderDatabaseMaintenance();
  setInlineStatus(els.databaseStatus, "Полная очистка БД…", "warning");

  try {
    const result = await request("/database/reset", {
      method: "POST",
      body: { confirm: "RESET_DATABASE", vacuum: true },
    });
    clearClientDatabaseState();
    await loadProfiles();
    await Promise.all([
      loadModels({ silent: true }),
      loadRagStatus({ silent: true }),
      loadAsrToolHistory({ silent: true }),
    ]);
    setInlineStatus(els.databaseStatus, `${formatDatabaseDeleted(result)} Создан новый профиль Default.`, "success");
    setFooter("БД полностью очищена. Локальные модели не удалялись.", "success");
  } catch (error) {
    setInlineStatus(els.databaseStatus, `Ошибка полной очистки: ${error.message || error}`, "error");
    setFooter(`Не удалось полностью очистить БД: ${error.message || error}`, "error");
  } finally {
    state.databaseMaintenanceBusy = false;
    renderDatabaseMaintenance();
  }
}

function bindEvents() {
  els.toggleSidebarButton?.addEventListener("click", () => toggleMobileSidebar());
  els.sidebarBackdrop?.addEventListener("click", () => closeSidebar());
  els.sidebarCollapseButton?.addEventListener("click", () => toggleSidebarCollapse());
  els.newChatButton?.addEventListener("click", async () => {
    state.currentSessionId = null;
    writeStored(STORAGE_KEYS.activeSessionId, "");
    await openSession(null);
    closeSidebar();
  });

  els.sessionList?.addEventListener("click", async (event) => {
    closeSessionContextMenu();
    closeAsrHistoryContextMenu();
    const target = event.target instanceof Element ? event.target : null;
    const openButton = target?.closest("[data-action='open']");
    const deleteButton = target?.closest("[data-action='delete']");
    const card = target?.closest("[data-session-id]");

    if (deleteButton) {
      await deleteSessionById(deleteButton.dataset.sessionId);
      return;
    }

    const sessionId = openButton?.dataset.sessionId || card?.dataset.sessionId;
    if (sessionId) {
      await openSession(sessionId);
      closeSidebar();
    }
  });
  els.sessionList?.addEventListener("contextmenu", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const card = target?.closest("[data-session-id]");
    const sessionId = card?.dataset.sessionId;
    if (!sessionId) return;
    event.preventDefault();
    openSessionContextMenu(sessionId, event.clientX, event.clientY);
  });
  els.renameSessionMenuItem?.addEventListener("click", async () => {
    const sessionId = state.sessionContextMenuSessionId;
    closeSessionContextMenu();
    if (sessionId) {
      await renameSessionById(sessionId);
    }
  });
  els.renameAsrTranscriptMenuItem?.addEventListener("click", async () => {
    const transcriptId = state.asrHistoryContextMenuTranscriptId;
    closeAsrHistoryContextMenu();
    if (transcriptId) {
      await renameAsrToolTranscriptById(transcriptId);
    }
  });

  els.profileSelect?.addEventListener("change", async () => {
    const nextId = Number(els.profileSelect.value);
    if (Number.isFinite(nextId)) {
      await setActiveProfile(nextId);
    }
  });
  els.profileManagementSelect?.addEventListener("change", async () => {
    const value = els.profileManagementSelect.value;
    if (value === CREATE_PROFILE_VALUE) {
      enterProfileCreateMode();
      setInlineStatus(els.profileStatus, "", "neutral");
      return;
    }
    const nextId = Number(value);
    if (Number.isFinite(nextId)) {
      await setActiveProfile(nextId);
    }
  });
  els.profileNameInput?.addEventListener("input", () => renderProfileManagement());

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
      if (!state.isSending && !els.sendButton?.disabled) {
        sendCurrentPrompt();
      }
    }
  });
  els.promptInput?.addEventListener("paste", async (event) => {
    const clipboard = event.clipboardData;
    const imageFiles = Array.from(clipboard?.items || [])
      .filter((item) => item.kind === "file" && String(item.type || "").toLowerCase().startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter(Boolean);
    if (!imageFiles.length) return;
    if (!String(clipboard?.getData("text/plain") || "")) {
      event.preventDefault();
    }
    await addChatImageFiles(imageFiles);
  });

  els.voiceRecordButton?.addEventListener("click", async () => {
    toggleComposerMenu(false);
    closeVoiceModelMenu();
    await toggleVoiceRecording();
  });
  els.voiceRecordButton?.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    openVoiceModelMenu({ clientX: event.clientX, clientY: event.clientY });
  });
  els.voiceModelMenu?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-voice-model]");
    if (!button) return;
    const modelName = button.dataset.voiceModel || "";
    if (!modelName) return;
    const updated = await saveActiveProfilePreferences({ chat: { dictation_model: modelName } });
    if (!updated) return;
    closeVoiceModelMenu();
    if (state.asrModels.length && !isWhisperModelInstalled(modelName)) {
      setFooter(`Для профиля выбрана модель диктовки ${modelName}, но она ещё не готова локально.`, "warning");
      return;
    }
    setFooter(`Модель диктовки профиля: ${modelName}`, "success");
  });

  els.messageScroll?.addEventListener("scroll", () => {
    syncMessageScrollState();
  });

  els.chatShell?.addEventListener("dragenter", (event) => {
    handleDropZoneDragEnter(event, "chat");
  });
  els.chatShell?.addEventListener("dragover", (event) => {
    handleDropZoneDragOver(event, "chat");
  });
  els.chatShell?.addEventListener("dragleave", (event) => {
    handleDropZoneDragLeave(event, "chat");
  });
  els.chatShell?.addEventListener("drop", async (event) => {
    if (!isFileDragEvent(event)) return;
    event.preventDefault();
    clearDropOverlay("chat");
    toggleComposerMenu(false);
    closeQuickModelMenu();
    closeVoiceModelMenu();
    await handleDroppedDataTransfer("chat", event.dataTransfer);
  });

  els.scrollTopButton?.addEventListener("click", () => {
    scrollMessagesToBottom({ force: true });
  });

  els.composerMenuButton?.addEventListener("click", () => {
    toggleComposerMenu();
  });

  els.imageMenuItem?.addEventListener("click", () => {
    toggleComposerMenu(false);
    els.chatImageInput?.click();
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
  els.chatImageInput?.addEventListener("change", async () => {
    const files = Array.from(els.chatImageInput.files || []);
    if (files.length) {
      await addChatImageFiles(files);
    }
    els.chatImageInput.value = "";
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
  els.composerAttachments?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-chat-attachment-remove]");
    if (!button || button.disabled) return;
    await removeChatAttachment(button.dataset.chatAttachmentRemove || "");
    els.promptInput?.focus();
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

    const retryButton = event.target.closest("[data-retry-message-index]");
    if (retryButton) {
      await retryFailedAssistantMessage(retryButton.dataset.retryMessageIndex);
      return;
    }

    const visionRagButton = event.target.closest("[data-vision-rag-index]");
    if (visionRagButton) {
      openVisionRagDialog(visionRagButton.dataset.visionRagIndex);
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

  const openRagQuickFromPointer = (event) => {
    event.preventDefault();
    event.stopPropagation();
    openRagQuickMenu();
  };
  els.openSettingsButton?.addEventListener("click", () => openSettings());
  els.openRagButton?.addEventListener("click", async () => openRagPanel());
  els.openRagButton?.addEventListener("mousedown", (event) => {
    if (event.button === 2) {
      openRagQuickFromPointer(event);
    }
  });
  els.openRagButton?.addEventListener("contextmenu", openRagQuickFromPointer);
  els.themeToggleButton?.addEventListener("click", () => toggleTheme());
  els.chatModelNoticeSettingsButton?.addEventListener("click", () => openSettings());
  els.closeSettingsButton?.addEventListener("click", () => closeSettings());
  els.settingsTabList?.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-settings-tab]") : null;
    if (!button) return;
    setSettingsTab(button.getAttribute("data-settings-tab") || "profile");
  });
  els.settingsBackdrop?.addEventListener("click", (event) => {
    if (event.target === els.settingsBackdrop) {
      closeSettings();
    }
  });
  els.closeRagButton?.addEventListener("click", () => closeRagPanel());
  els.ragBackdrop?.addEventListener("click", (event) => {
    if (event.target === els.ragBackdrop) {
      closeRagPanel();
    }
  });
  els.ragQuickEnabledToggle?.addEventListener("change", async () => {
    await toggleRagForActiveProfile(Boolean(els.ragQuickEnabledToggle.checked), { notify: false });
  });
  els.ragRefreshButton?.addEventListener("click", async () => {
    await loadRagStatus();
    setFooter("RAG: список файлов и статистика обновлены.", "success");
  });
  els.ragAddFilesButton?.addEventListener("click", () => {
    els.ragFileInput?.click();
  });
  els.ragFileInput?.addEventListener("change", async () => {
    await uploadRagFiles(els.ragFileInput.files);
  });
  els.ragIngestButton?.addEventListener("click", async () => ingestRagSources(true));
  els.ragForceIngestButton?.addEventListener("click", async () => ingestRagSources(true));
  els.ragCopyPathButton?.addEventListener("click", async () => {
    await copyText(state.ragStatus?.source_dir || "rag_sources");
    setFooter("Путь RAG скопирован.", "success");
  });
  els.ragEnabledToggle?.addEventListener("change", async () => {
    await toggleRagForActiveProfile(Boolean(els.ragEnabledToggle.checked));
  });
  els.ragFileList?.addEventListener("click", async (event) => {
    const fileButton = event.target.closest("[data-rag-delete-file]");
    if (fileButton) {
      await deleteRagFile(fileButton.dataset.ragDeleteFile, fileButton);
      return;
    }
    const contextButton = event.target.closest("[data-rag-delete-context]");
    if (contextButton) {
      await deleteRagContext(contextButton.dataset.ragDeleteContext, contextButton);
    }
  });
  els.confirmCancelButton?.addEventListener("click", () => {
    resolveConfirmDialog(false);
  });
  els.confirmDismissButton?.addEventListener("click", () => {
    resolveConfirmDialog(false);
  });
  els.confirmApproveButton?.addEventListener("click", () => {
    resolveConfirmDialog(true);
  });
  els.confirmBackdrop?.addEventListener("click", (event) => {
    if (event.target === els.confirmBackdrop) {
      resolveConfirmDialog(false);
    }
  });
  els.visionRagCloseButton?.addEventListener("click", closeVisionRagDialog);
  els.visionRagCancelButton?.addEventListener("click", closeVisionRagDialog);
  els.visionRagSaveButton?.addEventListener("click", saveVisionContextToRag);
  els.visionRagBackdrop?.addEventListener("click", (event) => {
    if (event.target === els.visionRagBackdrop) closeVisionRagDialog();
  });

  els.copyLanUrlButton?.addEventListener("click", async () => copyNetworkAddress());
  els.clearContextButton?.addEventListener("click", async () => deleteCurrentContext());
  els.copyLanUrlFromSettingsButton?.addEventListener("click", async () => copyLanUrlOnly());
  els.networkAddressMenu?.addEventListener("click", async (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-network-address-index]") : null;
    if (!button) return;
    const index = Number(button.getAttribute("data-network-address-index"));
    const item = Number.isFinite(index) ? availableNetworkAddresses()[index] : null;
    closeNetworkAddressMenu();
    await copyNetworkAddressItem(item);
  });
  els.refreshPluginsButton?.addEventListener("click", async () => loadPlugins());
  els.pluginsList?.addEventListener("change", async (event) => {
    const input = event.target instanceof Element ? event.target.closest("[data-plugin-toggle]") : null;
    if (!(input instanceof HTMLInputElement)) return;
    await setPluginEnabled(input.getAttribute("data-plugin-toggle"), Boolean(input.checked));
  });
  els.restartBackendButton?.addEventListener("click", async () => restartBackendRuntime());
  els.shutdownButton?.addEventListener("click", async () => shutdownRuntime());
  els.cleanupDatabaseButton?.addEventListener("click", async () => cleanupDatabaseGarbage());
  els.resetDatabaseButton?.addEventListener("click", async () => resetDatabaseFully());
  els.createProfileButton?.addEventListener("click", async () => createProfileFlow());
  els.saveProfileSystemPromptButton?.addEventListener("click", async () => saveProfileSystemPromptFlow());
  els.deleteProfileButton?.addEventListener("click", async () => deleteCurrentProfileFlow());
  els.saveModelSettingsButton?.addEventListener("click", async () => saveModelSettingsFlow());
  els.resetModelSettingsButton?.addEventListener("click", async () => resetModelSettingsFlow());
  els.streamingEnabledToggle?.addEventListener("change", async () => saveStreamingPreferenceFlow());
  els.showRouterThinkingToggle?.addEventListener("change", async () => saveShowRouterThinkingToggleFlow());
  els.quickThinkingButton?.addEventListener("click", () => {
    closeQuickModelMenu();
    closeVoiceModelMenu();
    toggleQuickThinkingMenu(undefined, "desktop");
  });
  els.quickThinkingMobileButton?.addEventListener("click", () => {
    closeQuickModelMenu();
    closeVoiceModelMenu();
    toggleQuickThinkingMenu(undefined, "mobile");
  });
  const handleQuickThinkingMenuClick = async (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-thinking-mode]") : null;
    if (!(button instanceof HTMLElement)) return;
    const nextMode = normalizeOllamaThink(button.dataset.thinkingMode, "on");
    if (!els.quickThinkingControl) return;
    closeQuickThinkingMenu();
    els.quickThinkingControl.dataset.thinkingMode = nextMode === "off" ? "off" : "on";
    if (els.quickThinkingMobileControl) {
      els.quickThinkingMobileControl.dataset.thinkingMode = nextMode === "off" ? "off" : "on";
    }
    renderQuickThinkingControl(nextMode);
    await saveQuickThinkingModeFlow();
  };
  els.quickThinkingMenu?.addEventListener("click", handleQuickThinkingMenuClick);
  els.quickThinkingMobileMenu?.addEventListener("click", handleQuickThinkingMenuClick);
  els.saveAsrPipelineSettingsButton?.addEventListener("click", async () => saveAsrPipelineSettingsFlow());
  els.resetAsrPipelineSettingsButton?.addEventListener("click", async () => resetAsrPipelineSettingsFlow());
  els.asrFullAnalysisEnabledToggle?.addEventListener("change", async () => saveAsrFullAnalysisPreferenceFlow());
  els.asrDiagnosticsEnabledToggle?.addEventListener("change", async () => saveAsrDiagnosticsPreferenceFlow());
  els.asrPipelineSettingsToggleButton?.addEventListener("click", () => {
    setAsrPipelineSettingsExpanded(!state.asrPipelineSettingsExpanded);
  });
  els.asrPipelineSettingsGrid?.addEventListener("change", (event) => {
    const control = event.target instanceof Element ? event.target.closest("[data-asr-pipeline-field='model']") : null;
    if (!(control instanceof HTMLSelectElement)) return;
    const row = control.closest(".pipeline-stage-row");
    const disabledStage = control.value === ASR_PIPELINE_DISABLED_VALUE;
    row?.querySelectorAll("[data-asr-pipeline-field='temperature'], [data-asr-pipeline-field='max_tokens']").forEach((input) => {
      input.disabled = disabledStage;
    });
  });

  els.llmModelSelect?.addEventListener("change", async () => {
    await applySelectedLlmModel(els.llmModelSelect.value || "");
  });

  els.quickModelButton?.addEventListener("click", () => {
    toggleComposerMenu(false);
    closeQuickThinkingMenu();
    closeVoiceModelMenu();
    toggleQuickModelMenu(undefined, "desktop");
  });

  els.quickModelMobileButton?.addEventListener("click", () => {
    toggleComposerMenu(false);
    closeQuickThinkingMenu();
    closeVoiceModelMenu();
    toggleQuickModelMenu(undefined, "mobile");
  });

  const handleQuickModelMenuClick = async (event) => {
    if (event.target instanceof Element && event.target.closest("[data-model-help]")) {
      return;
    }
    const button = event.target instanceof Element ? event.target.closest("[data-quick-model]") : null;
    if (!button) return;
    const modelName = button.dataset.quickModel || "";
    if (!modelName) return;
    closeQuickModelMenu();
    await applySelectedLlmModel(modelName);
  };
  const handleQuickModelMenuChange = async (event) => {
    const input = event.target instanceof Element ? event.target.closest("[data-quick-thinking-toggle]") : null;
    if (!(input instanceof HTMLInputElement)) return;
    const modelName = String(input.dataset.quickThinkingModel || "").trim();
    if (!modelName) return;
    if (state.selectedLlmModel !== modelName) {
      await applySelectedLlmModel(modelName, { closeMenu: false });
    }
    const nextMode = input.checked ? "on" : "off";
    if (els.quickThinkingControl) {
      els.quickThinkingControl.dataset.thinkingMode = nextMode;
    }
    if (els.quickThinkingMobileControl) {
      els.quickThinkingMobileControl.dataset.thinkingMode = nextMode;
    }
    renderQuickThinkingControl(nextMode);
    renderQuickModelPicker();
    await saveQuickThinkingModeFlow();
    renderQuickModelPicker();
  };
  els.quickModelMenu?.addEventListener("click", handleQuickModelMenuClick);
  els.quickModelMobileMenu?.addEventListener("click", handleQuickModelMenuClick);
  els.quickModelMenu?.addEventListener("change", handleQuickModelMenuChange);
  els.quickModelMobileMenu?.addEventListener("change", handleQuickModelMenuChange);

  els.quickModelSelect?.addEventListener("change", async () => {
    await applySelectedLlmModel(els.quickModelSelect.value || "");
  });

  els.whisperModelSelect?.addEventListener("change", async () => {
    const modelName = els.whisperModelSelect.value || "small";
    const updated = await saveActiveProfilePreferences({ asr: { studio_model: modelName } });
    if (!updated) return;
    if (state.asrModels.length && !isWhisperModelInstalled(modelName)) {
      setFooter(`Для профиля выбрана ASR-модель ${modelName}, но она ещё не готова локально.`, "warning");
      return;
    }
    setFooter(`Профиль обновлён: ASR Studio использует ${modelName}`, "success");
  });

  els.promptPresetSelect?.addEventListener("change", async () => {
    const promptPreset = normalizePromptPreset(els.promptPresetSelect.value);
    const updated = await saveActiveProfilePreferences({ asr: { prompt_preset: promptPreset } });
    if (!updated) return;
    setFooter(`Профиль обновлён: ASR язык/prompt ${promptPreset}`, "success");
  });

  els.asrBeamSizeInput?.addEventListener("change", async () => {
    const beamSize = normalizeAsrBeamSize(els.asrBeamSizeInput.value);
    els.asrBeamSizeInput.value = String(beamSize);
    const updated = await saveActiveProfilePreferences({ asr: { beam_size: beamSize } });
    if (!updated) return;
    setFooter(`Профиль обновлён: ASR beam ${beamSize}`, "success");
  });

  els.asrThreadsInput?.addEventListener("change", async () => {
    const threads = normalizeAsrThreads(els.asrThreadsInput.value);
    els.asrThreadsInput.value = String(threads);
    const updated = await saveActiveProfilePreferences({ asr: { threads } });
    if (!updated) return;
    setFooter(`Профиль обновлён: ASR threads ${threads}`, "success");
  });

  els.asrAnalysisPromptInput?.addEventListener("change", async () => {
    const analysisPrompt = String(els.asrAnalysisPromptInput.value || "").trim();
    els.asrAnalysisPromptInput.value = analysisPrompt;
    const updated = await saveActiveProfilePreferences({ asr: { analysis_prompt: analysisPrompt } });
    if (!updated) return;
    setFooter(analysisPrompt ? "Профиль обновлён: ASR контекст анализа сохранён." : "Профиль обновлён: ASR контекст анализа очищен.", "success");
  });

  els.ttsVoiceSelect?.addEventListener("change", async () => {
    const voiceId = els.ttsVoiceSelect.value || "";
    const updated = await saveActiveProfilePreferences({ tts: { voice_id: voiceId } });
    if (!updated) return;
    setFooter(`Профиль обновлён: TTS-голос ${voiceId || "не выбран"}`, "success");
  });

  els.asrToolCloseButton?.addEventListener("click", () => closeAsrTool());
  els.asrToolMinimizeButton?.addEventListener("click", () => minimizeAsrTool());
  els.asrToolFullscreenButton?.addEventListener("click", () => toggleAsrToolFullscreen());
  els.asrToolHeader?.addEventListener("mousedown", (event) => {
    startAsrToolDrag(event);
  });
  els.asrToolWindow?.addEventListener("dragenter", (event) => {
    handleDropZoneDragEnter(event, "asr");
  });
  els.asrToolWindow?.addEventListener("dragover", (event) => {
    handleDropZoneDragOver(event, "asr");
  });
  els.asrToolWindow?.addEventListener("dragleave", (event) => {
    handleDropZoneDragLeave(event, "asr");
  });
  els.asrToolWindow?.addEventListener("drop", async (event) => {
    if (!isFileDragEvent(event)) return;
    event.preventDefault();
    clearDropOverlay("asr");
    await handleDroppedDataTransfer("asr", event.dataTransfer);
  });
  els.asrToolResizeHandle?.addEventListener("mousedown", (event) => {
    startAsrToolResize(event);
  });
  els.asrToolModelSelect?.addEventListener("change", async () => {
    const modelName = els.asrToolModelSelect.value || ASR_STUDIO_DEFAULT_MODEL;
    const updated = await saveActiveProfilePreferences({ asr: { studio_model: modelName } });
    if (!updated) return;
    if (state.asrModels.length && !isWhisperModelInstalled(modelName)) {
      setFooter(`Для профиля выбрана ASR-модель ${modelName}, но она ещё не готова локально.`, "warning");
      return;
    }
    setFooter(`Профиль обновлён: ASR Studio использует ${modelName}`, "success");
  });
  els.asrToolPromptPresetSelect?.addEventListener("change", async () => {
    const promptPreset = normalizePromptPreset(els.asrToolPromptPresetSelect.value);
    const updated = await saveActiveProfilePreferences({ asr: { prompt_preset: promptPreset } });
    if (!updated) return;
    setFooter(`Профиль обновлён: ASR язык/prompt ${promptPreset}`, "success");
  });
  els.asrToolAnalysisLanguageSelect?.addEventListener("change", async () => {
    const analysisLanguage = normalizeAsrAnalysisLanguage(els.asrToolAnalysisLanguageSelect.value);
    els.asrToolAnalysisLanguageSelect.value = analysisLanguage;
    const updated = await saveActiveProfilePreferences({ asr: { analysis_language: analysisLanguage } });
    if (!updated) return;
    const label = analysisLanguage === "auto" ? "авто" : analysisLanguage;
    setFooter(`Профиль обновлён: язык summary ${label}`, "success");
  });
  els.asrToolOutput?.addEventListener("input", () => {
    state.asrToolPipelineRun = null;
    renderAsrTool();
  });
  els.asrToolSearchInput?.addEventListener("input", () => {
    state.asrToolTextSearch = els.asrToolSearchInput.value || "";
    applyAsrTextSearch();
  });
  els.asrToolHistorySearchInput?.addEventListener("input", () => {
    state.asrToolHistorySearch = els.asrToolHistorySearchInput.value || "";
    renderAsrToolHistory();
  });
  els.asrHistoryToggleButton?.addEventListener("click", () => {
    setAsrHistoryCollapsed(!state.asrHistoryCollapsed);
  });
  els.asrHistoryReopenButton?.addEventListener("click", () => {
    setAsrHistoryCollapsed(false);
  });
  document.querySelectorAll("[data-asr-tab]").forEach((button) => {
    button.addEventListener("click", () => setAsrToolTab(button.dataset.asrTab || "text"));
  });
  els.asrToolFileCard?.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest("button")) return;
    els.asrToolOutput?.focus({ preventScroll: true });
  });
  els.asrToolFileCard?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      els.asrToolOutput?.focus({ preventScroll: true });
    }
  });
  els.asrToolRetranscribeButton?.addEventListener("click", async () => {
    await retranscribeAsrToolFile();
  });
  els.asrToolChooseFileButton?.addEventListener("click", () => {
    els.asrToolFileInput?.click();
  });
  els.asrToolPipelineSettingsButton?.addEventListener("click", () => openAsrPipelineSettings());
  els.asrToolStopButton?.addEventListener("click", async () => {
    await stopAsrToolProcessing();
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
  els.asrToolAnalysisModeButton?.addEventListener("click", (event) => {
    event.preventDefault();
    setAsrAnalysisModeMenuOpen(!state.asrToolAnalysisModeMenuOpen);
  });
  els.asrToolAnalysisModeMenu?.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-asr-analysis-mode]") : null;
    if (!button) return;
    event.preventDefault();
    if (button.getAttribute("aria-disabled") === "true") {
      setAsrAnalysisMode(button.dataset.asrAnalysisMode);
      return;
    }
    setAsrAnalysisMode(button.dataset.asrAnalysisMode);
  });
  els.asrToolRunAnalysisButton?.addEventListener("click", async () => {
    await runSelectedAsrAnalysisMode();
  });
  els.asrToolCleanButton?.addEventListener("click", async () => {
    setAsrToolTab("text");
    await runAsrPipelineAction("clean", "fast");
  });
  els.asrToolSummaryButton?.addEventListener("click", async () => {
    setAsrToolTab("summary");
    await runAsrPipelineAction("summary", "balanced");
  });
  els.asrToolTasksButton?.addEventListener("click", async () => {
    setAsrToolTab("tasks");
    await runAsrPipelineAction("tasks", "balanced");
  });
  els.asrToolRolesButton?.addEventListener("click", async () => {
    setAsrToolTab("roles");
    if (!state.asrToolPipelineRun?.speaker_mapping?.length) {
      if (!asrFullAnalysisEnabled()) {
        setInlineStatus(
          els.asrToolStatus,
          "Определение ролей требует полного анализа. Включите его в настройках ASR, если готовы к повышенной нагрузке.",
          "warning",
        );
        openAsrPipelineSettings();
        return;
      }
      if (!confirmAsrFullAnalysisRisk()) return;
      await runAsrPipelineAction("full", "balanced");
    }
  });
  els.asrToolFullAnalysisButton?.addEventListener("click", async () => {
    setAsrToolTab("summary");
    if (!confirmAsrFullAnalysisRisk()) return;
    await runAsrPipelineAction("full", "balanced");
  });
  els.asrToolInsertPromptButton?.addEventListener("click", () => {
    insertAsrToolIntoPrompt();
  });
  els.asrToolOpenAnalysisButton?.addEventListener("click", () => {
    setAsrToolTab(state.asrToolPipelineRun?.structured_json ? "tasks" : "summary");
  });
  els.asrToolDownloadButton?.addEventListener("click", () => {
    downloadAsrToolText();
  });
  els.asrToolSendButton?.addEventListener("click", async () => {
    await sendAsrToolTextToChat();
  });
  els.asrToolSaveContextButton?.addEventListener("click", async () => {
    await saveAsrPipelineAsContext();
  });
  els.asrToolCopyButton?.addEventListener("click", async () => {
    await copyAsrToolText();
  });
  els.asrToolSaveSpeakersButton?.addEventListener("click", async () => {
    await saveAsrSpeakerOverrides();
  });
  els.asrToolRegenerateSummaryButton?.addEventListener("click", async () => {
    await regenerateAsrSummary();
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
    closeAsrHistoryContextMenu();
    const deleteButton = event.target instanceof Element ? event.target.closest("[data-asr-history-delete-id]") : null;
    if (deleteButton) {
      event.preventDefault();
      event.stopPropagation();
      await deleteAsrToolTranscript(deleteButton.dataset.asrHistoryDeleteId);
      return;
    }
    const button = event.target instanceof Element ? event.target.closest("[data-asr-history-id]") : null;
    if (!button) return;
    await selectAsrToolTranscript(button.dataset.asrHistoryId);
  });
  els.asrToolHistoryList?.addEventListener("contextmenu", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const deleteButton = target?.closest("[data-asr-history-delete-id]");
    if (deleteButton) return;
    const button = target?.closest("[data-asr-history-id]");
    const transcriptId = button?.getAttribute("data-asr-history-id");
    if (!transcriptId) return;
    event.preventDefault();
    openAsrHistoryContextMenu(transcriptId, event.clientX, event.clientY);
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
  els.ttsToolVoiceSelect?.addEventListener("change", async () => {
    const voiceId = els.ttsToolVoiceSelect.value || "";
    const updated = await saveActiveProfilePreferences({ tts: { voice_id: voiceId } });
    if (!updated) return;
    setFooter(`Профиль обновлён: TTS-голос ${voiceId || "не выбран"}`, "success");
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
    const nextSpeed = formatTtsSpeedLabel(els.ttsToolSpeedSelect.value || 1);
    const updated = await saveActiveProfilePreferences({ tts: { speed: nextSpeed } });
    if (!updated) return;
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
  els.ttsHistoryToggleButton?.addEventListener("click", () => {
    setTtsHistoryCollapsed(!state.ttsHistoryCollapsed);
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
    if (event.target instanceof Element && event.target.closest("[data-model-help]")) {
      return;
    }
    const button = event.target.closest("[data-recommended-model]");
    if (!button) return;
    const modelName = button.dataset.recommendedModel || "";
    const isUtility = button.dataset.utilityModel === "1";
    const isInstalled = state.installedModels.some((item) => item.name === modelName);
    if (isUtility) {
      if (!isInstalled) {
        await startModelDownload(modelName);
        return;
      }
      setFooter(`${button.querySelector(".chip-button__label")?.textContent || modelName} используется как служебная router-модель. Для чата выберите Auto / Smart Router.`, "info");
      return;
    }
    if (isInstalled) {
      await applySelectedLlmModel(modelName);
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
      await applySelectedLlmModel(modelName);
      return;
    }
    if (action === "download") {
      await startModelDownload(modelName);
      return;
    }
    if (action === "update") {
      await startModelDownload(modelName, { mode: "update" });
      return;
    }
    if (action === "delete") {
      await deleteCurrentModel(modelName);
    }
  });

  els.visionModelLibrary?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-vision-model-action]");
    if (!button) return;
    const action = button.dataset.visionModelAction || "";
    const modelName = button.dataset.visionModel || "";
    if (!modelName) return;
    if (action === "select") {
      await saveVisionSettingsFlow({
        ...visionSettingsValues(),
        vision_model: modelName,
      });
      return;
    }
    if (action === "download") {
      await startModelDownload(modelName);
      return;
    }
    if (action === "update") {
      await startModelDownload(modelName, { mode: "update" });
      return;
    }
    if (action === "delete") {
      await deleteCurrentModel(modelName);
    }
  });
  els.refreshVisionButton?.addEventListener("click", async () => {
    await loadModels();
    await loadVisionCache({ silent: true });
    setInlineStatus(els.visionSettingsStatus, "Vision runtime и каталог обновлены.", "success");
  });
  els.saveVisionSettingsButton?.addEventListener("click", () => saveVisionSettingsFlow());
  els.resetVisionSettingsButton?.addEventListener("click", resetVisionSettingsFlow);
  els.refreshVisionCacheButton?.addEventListener("click", () => loadVisionCache());
  els.cleanupVisionOrphansButton?.addEventListener("click", () => cleanupVisionCache("orphans"));
  els.cleanupVisionCacheButton?.addEventListener("click", () => cleanupVisionCache("profile"));

  els.asrModelLibrary?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-asr-model-action]");
    if (!button) return;
    const action = button.dataset.asrModelAction || "";
    const modelName = button.dataset.asrModel || "";
    if (!modelName) return;
    if (action === "select") {
      const updated = await saveActiveProfilePreferences({ asr: { studio_model: modelName } });
      if (!updated) return;
      if (state.asrModels.length && !isWhisperModelInstalled(modelName)) {
        setFooter(`Для профиля выбрана ASR-модель ${modelName}, но она ещё не готова локально.`, "warning");
        return;
      }
      setFooter(`Профиль обновлён: ASR Studio использует ${modelName}`, "success");
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
      const updated = await saveActiveProfilePreferences({ tts: { voice_id: voiceId } });
      if (!updated) return;
      setFooter(`Профиль обновлён: TTS-голос ${voiceId}`, "success");
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

  els.refreshModelTransferButton?.addEventListener("click", () => void loadModelTransferPreview());
  els.exportModelsButton?.addEventListener("click", () => void startModelExport());
  els.importModelsButton?.addEventListener("click", () => els.importModelsInput?.click());
  els.importModelsInput?.addEventListener("change", () => {
    const file = els.importModelsInput?.files?.[0];
    if (file) void inspectModelImport(file);
  });
  els.cancelModelTransferButton?.addEventListener("click", async () => {
    if (state.modelTransferTaskId) {
      await request(`/model-transfer/tasks/${encodeURIComponent(state.modelTransferTaskId)}/cancel`, { method: "POST" });
    }
  });

  document.addEventListener("pointerover", (event) => {
    const target = event.target instanceof Element ? event.target.closest("[data-tooltip]") : null;
    if (!target || target === activeTooltipTarget) return;
    scheduleTooltip(target);
  });

  document.addEventListener("pointerout", (event) => {
    const target = event.target instanceof Element ? event.target.closest("[data-tooltip]") : null;
    if (!target) return;
    if (event.relatedTarget instanceof Node && target.contains(event.relatedTarget)) return;
    hideTooltip();
  });

  document.addEventListener("focusin", (event) => {
    const target = event.target instanceof Element ? event.target.closest("[data-tooltip]") : null;
    if (!target) return;
    scheduleTooltip(target);
  });

  document.addEventListener("focusout", (event) => {
    const target = event.target instanceof Element ? event.target.closest("[data-tooltip]") : null;
    if (target) {
      hideTooltip();
    }
  });

  document.addEventListener("scroll", hideTooltip, true);

  window.addEventListener("keydown", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "b" && !event.altKey && !isTypingTarget(target)) {
      event.preventDefault();
      toggleSidebarCollapse();
      return;
    }
    if (event.key === "Escape") {
      hideTooltip();
      if (state.asrToolAnalysisModeMenuOpen) {
        setAsrAnalysisModeMenuOpen(false);
        return;
      }
      const appSelectOpen = Array.from(state.appSelects.values()).some((entry) => entry.wrapper.classList.contains("app-select--open"));
      if (appSelectOpen) {
        closeAppSelect();
        return;
      }
      closeSessionContextMenu();
      closeAsrHistoryContextMenu();
      if (!els.confirmBackdrop?.hidden) {
        resolveConfirmDialog(false);
        return;
      }
      if (!els.visionRagBackdrop?.hidden) {
        closeVisionRagDialog();
        return;
      }
      if (!els.ragQuickMenu?.hidden) {
        closeRagQuickMenu();
        return;
      }
      if (!els.networkAddressMenu?.hidden) {
        closeNetworkAddressMenu();
        return;
      }
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
      closeQuickModelMenu();
      closeQuickThinkingMenu();
      closeVoiceModelMenu();
      closeAppSelect();
    }
  });

  window.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const insideComposerMenu = target?.closest("#composerMenu") || target?.closest("#composerMenuButton");
    const insideQuickModelMenu = target?.closest("#quickModelMenu")
      || target?.closest("#quickModelButton")
      || target?.closest("#quickModelMobileMenu")
      || target?.closest("#quickModelMobileButton");
    const insideQuickThinkingMenu = target?.closest("#quickThinkingMenu")
      || target?.closest("#quickThinkingButton")
      || target?.closest("#quickThinkingMobileMenu")
      || target?.closest("#quickThinkingMobileButton");
    const insideVoiceMenu = target?.closest("#voiceModelMenu") || target?.closest("#voiceRecordButton");
    const insideRagQuickMenu = target?.closest("#ragQuickMenu") || target?.closest("#openRagButton");
    const insideNetworkAddressMenu = target?.closest("#networkAddressMenu") || target?.closest("#copyLanUrlButton");
    const insideSessionContextMenu = target?.closest("#sessionContextMenu");
    const insideAsrHistoryContextMenu = target?.closest("#asrHistoryContextMenu");
    const insideAppSelect = target?.closest(".app-select");
    const insideAsrAnalysisMode = target?.closest("#asrToolAnalysisModeControl");
    if (!insideSessionContextMenu) {
      closeSessionContextMenu();
    }
    if (!insideAsrHistoryContextMenu) {
      closeAsrHistoryContextMenu();
    }
    if (els.composerMenu && els.composerMenuButton && !insideComposerMenu) {
      toggleComposerMenu(false);
    }
    if (!insideQuickModelMenu) {
      closeQuickModelMenu();
    }
    if (!insideQuickThinkingMenu) {
      closeQuickThinkingMenu();
    }
    if (!insideVoiceMenu) {
      closeVoiceModelMenu();
    }
    if (!insideRagQuickMenu) {
      closeRagQuickMenu();
    }
    if (!insideNetworkAddressMenu) {
      closeNetworkAddressMenu();
    }
    if (!insideAppSelect) {
      closeAppSelect();
    }
    if (!insideAsrAnalysisMode && state.asrToolAnalysisModeMenuOpen) {
      setAsrAnalysisModeMenuOpen(false);
    }
  });

  window.addEventListener("contextmenu", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const insideVoiceMenu = target?.closest("#voiceModelMenu") || target?.closest("#voiceRecordButton");
    const insideQuickModelMenu = target?.closest("#quickModelMenu")
      || target?.closest("#quickModelButton")
      || target?.closest("#quickModelMobileMenu")
      || target?.closest("#quickModelMobileButton");
    const insideQuickThinkingMenu = target?.closest("#quickThinkingMenu")
      || target?.closest("#quickThinkingButton")
      || target?.closest("#quickThinkingMobileMenu")
      || target?.closest("#quickThinkingMobileButton");
    const insideRagQuickMenu = target?.closest("#ragQuickMenu") || target?.closest("#openRagButton");
    const insideNetworkAddressMenu = target?.closest("#networkAddressMenu") || target?.closest("#copyLanUrlButton");
    const insideSessionContextMenu = target?.closest("#sessionContextMenu") || target?.closest("[data-session-id]");
    const insideAsrHistoryContextMenu = target?.closest("#asrHistoryContextMenu") || target?.closest("[data-asr-history-id]");
    const insideAppSelect = target?.closest(".app-select");
    if (!insideSessionContextMenu) {
      closeSessionContextMenu();
    }
    if (!insideAsrHistoryContextMenu) {
      closeAsrHistoryContextMenu();
    }
    if (!insideQuickModelMenu) {
      closeQuickModelMenu();
    }
    if (!insideQuickThinkingMenu) {
      closeQuickThinkingMenu();
    }
    if (!insideVoiceMenu) {
      closeVoiceModelMenu();
    }
    if (!insideRagQuickMenu) {
      closeRagQuickMenu();
    }
    if (!insideNetworkAddressMenu) {
      closeNetworkAddressMenu();
    }
    if (!insideAppSelect) {
      closeAppSelect();
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
    closeQuickModelMenu();
    closeVoiceModelMenu();
    closeRagQuickMenu();
    closeNetworkAddressMenu();
    closeAppSelect();
    closeSessionContextMenu();
    closeAsrHistoryContextMenu();
    applyAsrHistoryCollapsedState();
    applyTtsHistoryCollapsedState();
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
    clearAllDropOverlays();
    syncMobileScrollLock();
  });

  window.addEventListener("dragend", () => {
    clearAllDropOverlays();
  });

  window.addEventListener("drop", () => {
    clearAllDropOverlays();
  });

  window.addEventListener("pagehide", () => {
    interruptChatTaskEventStream("SSE-соединение закрыто при скрытии страницы.");
  });
}

async function bootstrap() {
  initTheme();
  applySidebarOpenState();
  applyAsrHistoryCollapsedState();
  initAppSelects();
  renderWhisperControls();
  renderTtsControls();
  renderAsrTool();
  renderOcrEditor();
  renderToolDock();
  renderVoiceRecordButton();
  renderQuickModelPicker();
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
