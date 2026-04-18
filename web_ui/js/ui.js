import { elements, tabButtons, tabPanels } from "./app-state.js";
import { deleteHistoryEntry, loadHistory, saveHistory } from "./storage.js";

function renderHistory() {
  if (!elements.historyList) return;
  const history = loadHistory();
  if (!history.length) {
    elements.historyList.innerHTML = '<p class="muted">История пуста.</p>';
    return;
  }
  elements.historyList.innerHTML = history
    .map(
      (item) => `
        <div class="history-row" data-ts="${item.ts}">
          <div class="history-row__meta">
            <div class="history-row__question">${item.q}</div>
            <div class="history-row__answer muted">${item.a}</div>
          </div>
          <button class="warn" data-action="delete">Удалить</button>
        </div>
      `,
    )
    .join("");
}

function bindHistory() {
  elements.btnHistory?.addEventListener("click", () => {
    renderHistory();
    elements.overlay?.classList.add("overlay--visible");
  });
  elements.btnCloseModal?.addEventListener("click", () => {
    elements.overlay?.classList.remove("overlay--visible");
  });
  elements.overlay?.addEventListener("click", (event) => {
    if (event.target === elements.overlay) {
      elements.overlay.classList.remove("overlay--visible");
    }
  });
  elements.historyList?.addEventListener("click", (event) => {
    const row = event.target.closest("[data-ts]");
    if (!row) return;
    const ts = Number(row.dataset.ts);
    const action = event.target.closest("[data-action]")?.dataset?.action;
    if (action === "delete") {
      deleteHistoryEntry(ts);
      renderHistory();
    }
  });
  elements.btnClearStorage?.addEventListener("click", () => {
    saveHistory([]);
    renderHistory();
  });
}

function bindSettingsOverlay() {
  elements.btnSettings?.addEventListener("click", () => {
    elements.settingsOverlay?.classList.add("overlay--visible");
  });
  elements.btnCloseSettings?.addEventListener("click", () => {
    elements.settingsOverlay?.classList.remove("overlay--visible");
  });
  elements.settingsOverlay?.addEventListener("click", (event) => {
    if (event.target === elements.settingsOverlay) {
      elements.settingsOverlay.classList.remove("overlay--visible");
    }
  });
}

function bindHelp() {
  elements.btnHelp?.addEventListener("click", () => {
    elements.helpOverlay?.classList.add("overlay--visible");
  });
  elements.btnCloseHelp?.addEventListener("click", () => {
    elements.helpOverlay?.classList.remove("overlay--visible");
  });
  elements.helpOverlay?.addEventListener("click", (event) => {
    if (event.target === elements.helpOverlay) {
      elements.helpOverlay.classList.remove("overlay--visible");
    }
  });
}

function bindTabs() {
  const switchTab = (targetId) => {
    tabButtons.forEach((btn) => {
      const isActive = btn.dataset.tabTarget === targetId;
      btn.classList.toggle("is-active", isActive);
      btn.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    tabPanels.forEach((panel) => {
      const shouldShow = panel.dataset.panel === targetId;
      panel.classList.toggle("is-active", shouldShow);
      panel.hidden = !shouldShow;
    });
  };
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tabTarget));
  });
}

export function initUi() {
  bindHistory();
  bindSettingsOverlay();
  bindHelp();
  bindTabs();
}
