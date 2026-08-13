import { fetchSessionCriteria, saveSessionCriteria } from "./api.js";
import { sanitizeHTML } from "./timeline.js";

const DEFAULT_MAX_CRITERIA = 200;
const EMPTY_HINT =
  'Критерии не выбраны. Откройте «Транскрибация и дополнительные настройки», чтобы добавить или загрузить критерии.';

function normalizeCriterion(value) {
  if (typeof value !== "string") {
    value = value == null ? "" : String(value);
  }
  return value
    .replace(/[\u200b\u200c\u200d]/g, "")
    .trim()
    .replace(/^[-•*0-9\)\].]+\s*/u, "")
    .replace(/\s+/g, " ")
    .trim();
}

function applyTone(statusNode, tone) {
  if (!statusNode) return;
  statusNode.classList.remove("status--error", "status--success", "status--warning");
  if (tone === "error") {
    statusNode.classList.add("status--error");
  } else if (tone === "success") {
    statusNode.classList.add("status--success");
  } else if (tone === "warning") {
    statusNode.classList.add("status--warning");
  }
}

export class CriteriaManager {
  constructor({ listEl, statusEl, maxItems = DEFAULT_MAX_CRITERIA } = {}) {
    this.listEl = listEl;
    this.statusEl = statusEl;
    this.maxItems = maxItems;
    this.criteria = [];
    this.busy = false;
    this.sessionId = null;
    this.profileId = null;
  }

  updateStatus(message, tone = "info") {
    if (!this.statusEl) return;
    this.statusEl.textContent = message || "";
    applyTone(this.statusEl, tone);
  }

  renderCriteria(list = this.criteria) {
    if (!this.listEl) return;
    const items = Array.isArray(list) ? list : [];
    if (!items.length) {
      this.listEl.innerHTML = `<li class="criteria-empty muted">${EMPTY_HINT}</li>`;
      return;
    }

    const html = items
      .map(
        (item, index) => `
          <li>
            <span class="criteria-index">${index + 1}.</span>
            <span class="criteria-text">${sanitizeHTML(item)}</span>
            <button
              class="secondary criteria-remove"
              type="button"
              data-action="remove-criterion"
              data-index="${index}"
              title="Удалить критерий"
              aria-label="Удалить критерий"
            >
              Удалить
            </button>
          </li>
        `,
      )
      .join("");

    this.listEl.innerHTML = html;
  }

  async persistToBackend() {
    if (!this.sessionId) return;
    try {
      await saveSessionCriteria(this.sessionId, this.profileId, { criteria: this.criteria });
    } catch (error) {
      this.updateStatus(`❌ Не удалось сохранить критерии: ${error?.message || error}`, "error");
    }
  }

  async setContext(sessionId, profileId) {
    this.sessionId = sessionId || null;
    this.profileId = profileId || null;
    await this.loadFromSession(this.sessionId);
  }

  async setCriteria(list, { persist = true, source = "" } = {}) {
    const seen = new Set();
    const items = [];
    (Array.isArray(list) ? list : []).forEach((value) => {
      const normalized = normalizeCriterion(value);
      if (!normalized) return;
      const key = normalized.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      if (items.length < this.maxItems) {
        items.push(normalized);
      }
    });

    this.criteria = items;
    this.renderCriteria(this.criteria);
    if (persist) {
      this.persistToBackend();
    }

    if (this.criteria.length) {
      const suffix = source ? ` • источник: ${source}` : "";
      this.updateStatus(`Критериев: ${this.criteria.length}${suffix}`, "success");
    } else {
      this.updateStatus(EMPTY_HINT);
    }
  }

  async loadFromSession(sessionId) {
    if (!sessionId) {
      this.criteria = [];
      this.renderCriteria();
      this.updateStatus(EMPTY_HINT);
      return;
    }
    this.busy = true;
    this.updateStatus("Загружаю критерии…");
    try {
      const data = await fetchSessionCriteria(sessionId, profileId);
      const items = Array.isArray(data?.criteria) ? data.criteria : [];
      await this.setCriteria(items, { persist: false, source: "session" });
      if (!items.length) {
        this.updateStatus(EMPTY_HINT);
      }
    } catch (error) {
      this.updateStatus(`❌ Не удалось загрузить критерии: ${error?.message || error}`, "error");
    } finally {
      this.busy = false;
    }
  }

  getCriteria() {
    return this.criteria;
  }

  clear() {
    this.criteria = [];
    this.renderCriteria();
    this.updateStatus(EMPTY_HINT);
    this.persistToBackend();
  }

  removeCriterion(index) {
    const idx = Number(index);
    if (!Number.isInteger(idx) || idx < 0 || idx >= this.criteria.length) {
      return false;
    }

    this.criteria = this.criteria.filter((_, itemIndex) => itemIndex !== idx);
    this.renderCriteria();
    this.persistToBackend();

    if (this.criteria.length) {
      this.updateStatus(`Критериев: ${this.criteria.length}`, "success");
    } else {
      this.updateStatus(EMPTY_HINT);
    }

    return true;
  }

  addManualCriterion(value) {
    const normalized = normalizeCriterion(value);
    if (!normalized) {
      this.updateStatus("Введите текст критерия перед сохранением.", "error");
      return false;
    }

    const lower = normalized.toLowerCase();
    if (this.criteria.some((item) => item.toLowerCase() === lower)) {
      this.updateStatus("Такой критерий уже есть в списке.", "warning");
      return false;
    }

    if (this.criteria.length >= this.maxItems) {
      this.updateStatus(`Нельзя добавить больше ${this.maxItems} критериев.`, "error");
      return false;
    }

    this.criteria = [...this.criteria, normalized];
    this.renderCriteria();
    this.persistToBackend();
    this.updateStatus(`Критериев: ${this.criteria.length} • источник: вручную`, "success");
    return true;
  }

  parseGoogleSheetInput(raw) {
    const value = (raw || "").trim();
    if (!value) return null;
    try {
      const url = new URL(value);
      if (url.hostname.includes("docs.google.com")) {
        const idMatch = url.pathname.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
        const gidMatch =
          url.searchParams.get("gid") || url.hash.match(/gid=(\d+)/)?.[1] || "";
        if (idMatch) {
          return { sheetId: idMatch[1], gid: gidMatch };
        }
      }
    } catch (error) {
      // noop
    }

    const idMatch = value.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
    if (idMatch) {
      const gidMatch = value.match(/gid=(\d+)/);
      return { sheetId: idMatch[1], gid: gidMatch ? gidMatch[1] : "" };
    }

    return { sheetId: value, gid: "" };
  }

  async requestFromBackend({ apiBase, sessionId, profileId, file, googleSheetId, googleGid, rawText }) {
    if (this.busy) return;
    this.busy = true;
    this.updateStatus("Загружаю критерии…");
    try {
      const fd = new FormData();
      const sid = sessionId || this.sessionId || "";
      fd.append("session_id", sid);
      const pid = profileId || this.profileId || 0;
      if (pid) {
        fd.append("profile_id", pid);
      }
      if (file) {
        fd.append("file", file, file.name || "criteria");
      }
      if (googleSheetId) {
        fd.append("google_sheet_id", googleSheetId);
      }
      if (googleGid) {
        fd.append("google_gid", googleGid);
      }
      if (rawText) {
        fd.append("raw_text", rawText);
      }

      const response = await fetch(`${apiBase}/criteria/parse`, {
        method: "POST",
        body: fd,
      });

      let data = null;
      try {
        data = await response.json();
      } catch (error) {
        data = null;
      }

      if (!response.ok) {
        const detail = data?.detail;
        const message =
          typeof detail === "string"
            ? detail
            : detail?.message || `HTTP ${response.status}`;
        throw new Error(message);
      }

      const criteria = Array.isArray(data?.criteria) ? data.criteria : [];
      const rawSource = typeof data?.source === "string" ? data.source : "backend";
      const source =
        {
          "file:csv": "CSV",
          "file:xlsx": "XLSX",
          google_sheets: "Google Sheets",
          text: "контекст",
        }[rawSource] || (rawSource === "backend" ? "" : rawSource);

      this.setCriteria(criteria, { source });
    } catch (error) {
      const message = error?.message || "Не удалось загрузить критерии";
      this.updateStatus(`❌ ${message}`, "error");
      throw error;
    } finally {
      this.busy = false;
    }
  }
}
