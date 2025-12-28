import { fetchRoles } from "./api.js";
import { elements, state } from "./app-state.js";
import { getSavedRole, setSavedRole } from "./storage.js";

const ROLE_FALLBACK = "free";
let onRoleChanged = null;

function renderRoleOptions(roles) {
  if (!elements.roleSelect) return;
  elements.roleSelect.innerHTML = roles
    .map((role) => `<option value="${role.key}">${role.label}</option>`)
    .join("");
}

function updateTooltip(roleKey) {
  if (!elements.roleTooltip) return;
  const found = state.roles.find((item) => item.key === roleKey);
  elements.roleTooltip.textContent = found?.description || "";
}

export function setCurrentRole(roleKey, { persist = true, silent = false } = {}) {
  const normalized = roleKey && state.roles.some((r) => r.key === roleKey) ? roleKey : ROLE_FALLBACK;
  state.currentRole = normalized;
  if (elements.roleSelect && elements.roleSelect.value !== normalized) {
    elements.roleSelect.value = normalized;
  }
  updateTooltip(normalized);
  if (persist) {
    setSavedRole(normalized);
  }
  if (!silent && typeof onRoleChanged === "function") {
    onRoleChanged(normalized);
  }
}

export async function initRoles({ onChange } = {}) {
  onRoleChanged = onChange || null;
  try {
    const data = await fetchRoles();
    state.roles = Array.isArray(data?.roles) ? data.roles : [];
    if (!state.roles.length) {
      state.roles = [
        { key: "free", label: "Свободное общение", description: "Дружелюбные короткие ответы" },
        { key: "hr", label: "HR", description: "Исходный HR-промпт" },
      ];
    }
    renderRoleOptions(state.roles);
    const savedRole = getSavedRole(state.currentRole || ROLE_FALLBACK);
    setCurrentRole(savedRole, { persist: false, silent: true });
  } catch (error) {
    state.roles = [];
    renderRoleOptions([]);
  }

  if (elements.roleSelect) {
    elements.roleSelect.addEventListener("change", (event) => {
      const nextRole = event.target.value;
      setCurrentRole(nextRole, { persist: true });
    });
  }
}
