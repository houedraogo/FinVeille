const SENSITIVE_KEYS = [
  "kafundo_token", "kafundo_user", "kafundo_user_role",
  "kafundo_onboarding_completed", "kafundo_financing_scope",
  "kafundo_saved_searches", "kafundo_pending_saved_search",
  "kafundo_match_state", "kafundo_favorite_devices",
  "kafundo_devices_view_modes", "kafundo_device_pipeline",
  "kafundo_user_preferences", "kafundo_workspace_api_migrated",
  "kafundo_workspace_match_synced_at",
];

const WORKSPACE_KEYS = SENSITIVE_KEYS.filter((key) =>
  !["kafundo_token", "kafundo_user", "kafundo_user_role", "kafundo_onboarding_completed"].includes(key),
);

export function clearTenantWorkspaceData() {
  if (typeof window === "undefined") return;
  WORKSPACE_KEYS.forEach((key) => localStorage.removeItem(key));
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith("kafundo_match_state:")) localStorage.removeItem(key);
  }
  for (const key of Object.keys(sessionStorage)) {
    if (key.startsWith("kafundo_")) sessionStorage.removeItem(key);
  }
}

export function clearSensitiveBrowserData() {
  if (typeof window === "undefined") return;
  SENSITIVE_KEYS.forEach((key) => localStorage.removeItem(key));
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith("kafundo_match_state:") || key.startsWith("kafundo_device_filters:")) {
      localStorage.removeItem(key);
    }
  }
  for (const key of Object.keys(sessionStorage)) {
    if (key.startsWith("kafundo_")) sessionStorage.removeItem(key);
  }
}

export function scopedMatchStorageKey(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const user = JSON.parse(localStorage.getItem("kafundo_user") || "null");
    if (!user?.id) return null;
    return `kafundo_match_state:${user.id}:${user.default_organization_id || "personal"}`;
  } catch {
    return null;
  }
}
