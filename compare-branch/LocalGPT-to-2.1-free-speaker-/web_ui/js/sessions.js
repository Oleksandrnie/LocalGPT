import {
  createProfile,
  createSession,
  deleteProfile,
  deleteSession,
  fetchProfiles,
  fetchSessions,
} from "./api.js";
import { elements, state, updateStatus } from "./app-state.js";
import {
  getLastChatSessionId,
  getLastProfileId,
  setLastChatSessionId,
  setLastProfileId,
  getSidebarPreference,
  setSidebarPreference,
  getSavedLlmModel,
} from "./storage.js";

let onSessionChanged = null;
let onProfileChanged = null;

function profileButtonLabel(profileId) {
  const found = state.profileList.find((p) => p.id === profileId);
  return found?.name || "Профиль";
}

function renderProfiles() {
  if (!elements.profileList) return;
  const html = state.profileList
    .map(
      (profile) => `
      <div class="profile-list__item" data-id="${profile.id}">
        <div class="profile-list__meta">
          <strong>${profile.name}</strong>
          ${profile.description ? `<span class="muted">${profile.description}</span>` : ""}
        </div>
        <div class="profile-list__actions">
          <button class="secondary" data-action="select">Выбрать</button>
          <button class="warn" data-action="delete">Удалить</button>
        </div>
      </div>
    `,
    )
    .join("");
  elements.profileList.innerHTML = html || '<p class="muted">Пока нет профилей.</p>';
  if (elements.profileLabel) {
    elements.profileLabel.textContent = profileButtonLabel(state.activeProfileId);
  }
  if (elements.profileTitle) {
    elements.profileTitle.textContent = "Сессии профиля";
  }
}

function renderSessions() {
  if (!elements.sessionList) return;
  const html = state.sessionList
    .map(
      (session) => `
        <div class="session-item ${session.id === state.currentSessionId ? "session-item--active" : ""}" data-id="${session.id
        }">
          <div class="session-item__meta">
            <span class="session-item__title">${session.title}</span>
            <span class="muted">${session.model_name || ""}${session.role ? ` • роль: ${session.role}` : ""
        }</span>
          </div>
          <div class="session-item__actions">
            <button class="secondary" data-action="open">Открыть</button>
            <button class="warn" data-action="delete">Удалить</button>
          </div>
        </div>
      `,
    )
    .join("");
  elements.sessionList.innerHTML = html || '<p class="muted">Нет диалогов.</p>';
  if (elements.profileTitle) {
    elements.profileTitle.textContent = profileButtonLabel(state.activeProfileId);
  }
}

export function applySidebarState(collapsed, { persist = true } = {}) {
  const sidebar = document.getElementById("sidebar");
  const workspace = document.querySelector(".workspace-grid");
  if (!sidebar) return;
  const shouldCollapse = Boolean(collapsed);
  sidebar.classList.toggle("sidebar-collapsed", shouldCollapse);
  if (workspace) {
    workspace.classList.toggle("is-collapsed", shouldCollapse);
  }
  if (elements.btnToggleSidebar) {
    elements.btnToggleSidebar.textContent = shouldCollapse ? "▶" : "◀";
    elements.btnToggleSidebar.title = shouldCollapse ? "Развернуть список" : "Свернуть список";
    elements.btnToggleSidebar.setAttribute("aria-expanded", shouldCollapse ? "false" : "true");
  }
  if (persist) {
    setSidebarPreference(shouldCollapse);
  }
}

export function toggleSidebar(force) {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;
  const collapsed = sidebar.classList.contains("sidebar-collapsed");
  const next = typeof force === "boolean" ? force : !collapsed;
  applySidebarState(next);
}

export function restoreSidebarState() {
  const preferred = getSidebarPreference(false);
  const autoCollapse = window.matchMedia("(max-width: 960px)").matches;
  applySidebarState(preferred || autoCollapse, { persist: false });
}

export async function loadProfiles() {
  try {
    const data = await fetchProfiles();
    state.profileList = Array.isArray(data?.profiles) ? data.profiles : [];
    renderProfiles();
    const storedProfile = getLastProfileId() || state.profileList[0]?.id || null;
    if (storedProfile) {
      await setActiveProfile(storedProfile);
    }
  } catch (error) {
    updateStatus(elements.healthStatus, `Ошибка загрузки профилей: ${error.message || error}`, "error");
  }
}

export async function setActiveProfile(profileId) {
  state.activeProfileId = profileId;
  setLastProfileId(profileId);
  renderProfiles();
  if (typeof onProfileChanged === "function") {
    onProfileChanged(profileId);
  }
  await loadSessions(profileId);
}

export async function loadSessions(profileId) {
  if (!profileId) return;
  try {
    const data = await fetchSessions(profileId);
    state.sessionList = Array.isArray(data?.sessions) ? data.sessions : [];
    renderSessions();
    const storedSession = state.currentSessionId || getLastChatSessionId();
    const fallback = state.sessionList[0]?.id || null;
    const nextSession = state.sessionList.find((item) => item.id === storedSession)?.id || fallback;
    await setActiveSession(nextSession, { silent: true });
    if (typeof onSessionChanged === "function") {
      onSessionChanged(nextSession || null);
    }
  } catch (error) {
    updateStatus(elements.healthStatus, `Ошибка загрузки сессий: ${error.message || error}`, "error");
  }
}

export async function setActiveSession(sessionId, { silent = false } = {}) {
  state.currentSessionId = sessionId || null;
  setLastChatSessionId(sessionId || null);
  renderSessions();
  if (!silent && typeof onSessionChanged === "function") {
    onSessionChanged(sessionId || null);
  }
}

export function bindSessionListEvents() {
  elements.sessionList?.addEventListener("click", async (event) => {
    const row = event.target.closest(".session-item");
    if (!row) return;
    const sessionId = row.dataset.id;
    const action = event.target.closest("[data-action]")?.dataset?.action;
    if (action === "delete") {
      const confirmed = window.confirm("Удалить диалог и историю сообщений?");
      if (!confirmed) return;
      try {
        await deleteSession(sessionId);
        state.sessionList = state.sessionList.filter((item) => item.id !== sessionId);
        renderSessions();
        const next = state.sessionList[0]?.id || null;
        await setActiveSession(next);
      } catch (error) {
        updateStatus(elements.healthStatus, `Не удалось удалить сессию: ${error.message || error}`, "error");
      }
      return;
    }
    await setActiveSession(sessionId);
  });
}

export function bindProfileModal() {
  elements.btnProfile?.addEventListener("click", () => {
    elements.profileOverlay?.classList.add("overlay--visible");
  });
  elements.btnCloseProfileModal?.addEventListener("click", () => {
    elements.profileOverlay?.classList.remove("overlay--visible");
  });
  elements.profileOverlay?.addEventListener("click", (event) => {
    if (event.target === elements.profileOverlay) {
      elements.profileOverlay.classList.remove("overlay--visible");
    }
  });
  elements.btnModalNewProfile?.addEventListener("click", async () => {
    const name = window.prompt("Название профиля", "Новый профиль")?.trim();
    if (!name) return;
    try {
      const profile = await createProfile({ name });
      state.profileList = [...state.profileList, profile];
      renderProfiles();
      await setActiveProfile(profile.id);
    } catch (error) {
      updateStatus(elements.healthStatus, `Не удалось создать профиль: ${error.message || error}`, "error");
    }
  });
  elements.profileList?.addEventListener("click", async (event) => {
    const row = event.target.closest("[data-id]");
    if (!row) return;
    const profileId = Number(row.dataset.id);
    const action = event.target.closest("[data-action]")?.dataset?.action;
    if (!Number.isFinite(profileId)) return;
    if (action === "select") {
      await setActiveProfile(profileId);
      elements.profileOverlay?.classList.remove("overlay--visible");
      return;
    }
    if (action === "delete") {
      const confirmed = window.confirm("Удалить профиль и все связанные данные?");
      if (!confirmed) return;
      try {
        await deleteProfile(profileId);
        state.profileList = state.profileList.filter((p) => p.id !== profileId);
        renderProfiles();
        const nextProfile = state.profileList[0]?.id || null;
        await setActiveProfile(nextProfile);
      } catch (error) {
        updateStatus(elements.healthStatus, `Не удалось удалить профиль: ${error.message || error}`, "error");
      }
    }
  });
}

export function bindSidebarControls() {
  elements.btnToggleSidebar?.addEventListener("click", () => toggleSidebar());
  elements.btnSidebarHeader?.addEventListener("click", () => toggleSidebar());
  const sidebarMq = window.matchMedia("(max-width: 960px)");
  const handler = (event) => {
    if (event.matches) {
      applySidebarState(true, { persist: false });
      return;
    }
    const preferred = getSidebarPreference(false);
    applySidebarState(preferred, { persist: false });
  };
  if (typeof sidebarMq.addEventListener === "function") {
    sidebarMq.addEventListener("change", handler);
  } else if (typeof sidebarMq.addListener === "function") {
    sidebarMq.addListener(handler);
  }

  window.addEventListener("keydown", (event) => {
    const meta = event.metaKey || event.ctrlKey;
    if (meta && event.key.toLowerCase() === "b") {
      event.preventDefault();
      toggleSidebar();
    }
  });
}

export async function createSessionFlow(defaultModel) {
  if (!state.activeProfileId) {
    updateStatus(elements.healthStatus, "Сначала выберите профиль", "warning");
    return;
  }
  const title = window.prompt("Название нового диалога", "Новый диалог")?.trim() || "Новый диалог";
  try {
    const payload = {
      profile_id: state.activeProfileId,
      title,
      model_name: defaultModel || "",
    };
    const session = await createSession(payload);
    state.sessionList = [session, ...state.sessionList.filter((s) => s.id !== session.id)];
    renderSessions();
    await setActiveSession(session.id);
  } catch (error) {
    updateStatus(elements.healthStatus, `Не удалось создать сессию: ${error.message || error}`, "error");
  }
}

export function initSessions({ onSessionChange, onProfileChange } = {}) {
  onSessionChanged = onSessionChange || null;
  onProfileChanged = onProfileChange || null;
  bindProfileModal();
  bindSessionListEvents();
  bindSidebarControls();
  elements.btnNewSession?.addEventListener("click", () =>
    createSessionFlow(state.currentSessionModel || getSavedLlmModel()),
  );
  restoreSidebarState();
}
