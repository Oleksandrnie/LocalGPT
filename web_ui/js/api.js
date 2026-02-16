import { API_BASE } from "./storage.js";

async function handleResponse(response) {
  const raw = await response.text();
  let parsed = {};
  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = { message: raw };
    }
  }
  if (response.ok) {
    return parsed;
  }

  const detail = parsed?.detail;
  const message =
    typeof detail === "string"
      ? detail
      : detail?.message || parsed?.message || `HTTP ${response.status}`;

  const error = new Error(message);
  error.status = response.status;
  error.payload = parsed;
  throw error;
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`);
  return handleResponse(response);
}

async function apiPost(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse(response);
}

async function apiPatch(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse(response);
}

export function fetchHealth() {
  return apiGet("/health");
}

export function fetchWhisperModels() {
  return apiGet("/whisper/models");
}

export function startWhisperModelPrepare(model) {
  return apiPost("/whisper/models/prepare", { model });
}

export function fetchWhisperModelPrepare(taskId) {
  return apiGet(`/whisper/models/prepare/${encodeURIComponent(taskId)}`);
}

export async function transcribeFile(file, model, sourceType = "upload") {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("model", model);
  formData.append("source_type", sourceType);

  const response = await fetch(`${API_BASE}/transcribe`, {
    method: "POST",
    body: formData,
  });
  return handleResponse(response);
}

export function listTranscripts() {
  return apiGet("/transcripts");
}

export function getTranscript(id) {
  return apiGet(`/transcripts/${encodeURIComponent(id)}`);
}

export function createTranscript(payload) {
  return apiPost("/transcripts", payload);
}

export function updateTranscript(id, payload) {
  return apiPatch(`/transcripts/${encodeURIComponent(id)}`, payload);
}
