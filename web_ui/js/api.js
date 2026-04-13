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
  const code =
    typeof detail === "string"
      ? parsed?.code
      : detail?.code || parsed?.code;

  const error = new Error(message);
  error.status = response.status;
  error.code = code || null;
  error.payload = parsed;
  throw error;
}

async function apiGet(path) {
  const response = await fetch(path);
  return handleResponse(response);
}

async function apiPost(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse(response);
}

async function apiDelete(path) {
  const response = await fetch(path, { method: "DELETE" });
  return handleResponse(response);
}

export function fetchHealth() {
  return apiGet("/tts/health");
}

export function listVoices() {
  return apiGet("/tts/voices");
}

export function generateSpeech(payload) {
  return apiPost("/tts/generate", payload);
}

export function processSpeed(payload) {
  return apiPost("/tts/process-speed", payload);
}

export function listHistory() {
  return apiGet("/tts/history");
}

export function getHistoryItem(id) {
  return apiGet(`/tts/history/${encodeURIComponent(id)}`);
}

export function deleteHistoryItem(id) {
  return apiDelete(`/tts/history/${encodeURIComponent(id)}`);
}
