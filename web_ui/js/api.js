import { API_BASE } from "./storage.js";

async function handleResponse(response) {
  if (response.ok) {
    const text = await response.text();
    return text ? JSON.parse(text) : {};
  }
  let detail = response.statusText;
  try {
    const data = await response.json();
    detail = data?.detail || JSON.stringify(data);
  } catch (error) {
    // noop
  }
  const error = new Error(detail || `HTTP ${response.status}`);
  error.status = response.status;
  error.detail = detail;
  throw error;
}

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: "GET" });
  return handleResponse(res);
}

export async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  return handleResponse(res);
}

export async function apiPost(path, body, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: options.signal,
  });
  return handleResponse(res);
}

export async function apiPatch(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse(res);
}

export async function apiUpload(path, formData) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
  });
  return handleResponse(res);
}

// Meta
export const fetchHealth = () => apiGet("/health");
export const fetchRoles = () => apiGet("/roles");
export const fetchStoragePaths = () => apiGet("/storage/paths");
export const updateStoragePaths = (payload) => apiPost("/storage/paths", payload);

// Profiles & sessions
export const fetchProfiles = () => apiGet("/profiles");
export const createProfile = (payload) => apiPost("/profiles", payload);
export const deleteProfile = (id) => apiDelete(`/profiles/${id}`);
export const fetchSessions = (profileId) => apiGet(`/sessions?profile_id=${encodeURIComponent(profileId)}`);
export const createSession = (payload) => apiPost("/sessions", payload);
export const updateSession = (id, payload) => apiPatch(`/sessions/${id}`, payload);
export const deleteSession = (id) => apiDelete(`/sessions/${id}`);
export const fetchSessionMessages = (id, limit) =>
  apiGet(`/sessions/${encodeURIComponent(id)}/messages${limit ? `?limit=${limit}` : ""}`);
export const fetchSessionCriteria = (id) => apiGet(`/sessions/${encodeURIComponent(id)}/criteria`);
export const saveSessionCriteria = (id, payload) => apiPost(`/sessions/${encodeURIComponent(id)}/criteria`, payload);

// Model settings
export const fetchModelSettings = (profileId, modelName) =>
  apiGet(`/model_settings?profile_id=${encodeURIComponent(profileId)}&model_name=${encodeURIComponent(modelName)}`);
export const saveModelSettings = (payload) => apiPost("/model_settings", payload);
export const resetModelSettings = (payload) => apiPost("/model_settings/reset_to_defaults", payload);

// Models
export const listModels = () => apiGet("/models");
export const pullModel = (payload) => apiPost("/models/pull", payload);
export const pullStatus = (taskId) => apiGet(`/models/pull/${encodeURIComponent(taskId)}`);
export const pullStatuses = () => apiGet("/models/downloads");
export const cancelPull = (taskId) => apiPost(`/models/pull/${encodeURIComponent(taskId)}/cancel`);
export const deleteModelApi = (modelName) => apiDelete(`/models/${encodeURIComponent(modelName)}`);
export const pausePull = (taskId) => apiPost(`/models/pull/${encodeURIComponent(taskId)}/pause`, {});
export const resumePull = (taskId) => apiPost(`/models/pull/${encodeURIComponent(taskId)}/resume`, {});

// Chat & transcripts
export const sendChat = (payload, options = {}) => apiPost("/chat", payload, options);
export const resetChatSession = (payload) => apiPost("/session/reset", payload);
export const transcribeFile = (formData) => apiUpload("/transcribe", formData);
export const parseCriteria = (formData) => apiUpload("/criteria/parse", formData);

export const listTranscripts = (profileId, sessionId) => {
  const params = new URLSearchParams({ profile_id: profileId });
  if (sessionId) params.append("session_id", sessionId);
  return apiGet(`/transcripts?${params.toString()}`);
};
export const createTranscript = (payload) => apiPost("/transcripts", payload);
export const updateTranscriptApi = (id, payload) => apiPatch(`/transcripts/${id}`, payload);
export const deleteTranscriptApi = (id) => apiDelete(`/transcripts/${id}`);
