export const SAVED_SEARCHES_KEY = "kafundo_saved_searches";
export const PENDING_SAVED_SEARCH_KEY = "kafundo_pending_saved_search";
export const MATCH_STORAGE_KEY = "kafundo_match_state";
export const FAVORITE_DEVICES_KEY = "kafundo_favorite_devices";
export const DEVICES_VIEW_MODE_KEY = "kafundo_devices_view_modes";
export const DEVICE_PIPELINE_KEY = "kafundo_device_pipeline";
export const USER_PREFERENCES_KEY = "kafundo_user_preferences";
const WORKSPACE_MIGRATION_KEY = "kafundo_workspace_api_migrated";
const WORKSPACE_MATCH_SYNC_KEY = "kafundo_workspace_match_synced_at";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface SavedSearchFilters {
  q: string;
  countries: string[];
  deviceTypes: string[];
  sectors: string[];
  statuses: string[];
  closingSoon: string;
  hasCloseDate?: boolean;
  sortBy: string;
}

export interface SavedSearch {
  id: string;
  name: string;
  title: string;
  path: string;
  filters: SavedSearchFilters;
  resultCount: number | null;
  savedAt: string;
}

export interface FavoriteDevice {
  id: string;
  title: string;
  organism: string;
  country: string;
  region: string | null;
  deviceType: string;
  status: string;
  closeDate: string | null;
  amountMax: number | null;
  currency: string;
  sourceUrl: string;
  savedAt: string;
}

export type DevicesViewMode = "split" | "cards" | "table";

export type DevicePipelineStatus =
  | "a_etudier"
  | "interessant"
  | "candidature_en_cours"
  | "soumis"
  | "refuse"
  | "non_pertinent";

export type DevicePipelinePriority = "faible" | "moyenne" | "haute";

export interface PipelineDocument {
  id: string;
  name: string;
  url?: string | null;
  doc_type: string; // "url" | "note" | "brouillon"
  note?: string | null;
  added_at: string;
}

export interface UserPreferences {
  defaultViewMode: DevicesViewMode;
  emailDigest: boolean;
  productTips: boolean;
  onboardingCompleted?: boolean;
  onboardingProfile?: string | null;
  onboardingCountries?: string[];
  onboardingSectors?: string[];
  onboardingDeviceTypes?: string[];
}

export interface DevicePipelineEntry {
  id: string;
  title: string;
  organism: string;
  country: string;
  region: string | null;
  deviceType: string;
  status: string;
  closeDate: string | null;
  amountMax: number | null;
  currency: string;
  sourceUrl: string;
  pipelineStatus: DevicePipelineStatus;
  priority: DevicePipelinePriority;
  reminderDate: string | null;
  matchProjectId: string | null;
  note: string;
  documents: PipelineDocument[];
  updatedAt: string;
}

interface PendingSavedSearch {
  search: SavedSearch;
  mode: "open" | "edit";
}

export interface MatchWorkspaceSnapshot {
  id?: string | null;
  fileName: string | null;
  fileSize: number | null;
  total: number;
  updatedAt: string | null;
  topMatches: Array<{
    id: string;
    title: string;
    country: string;
    deviceType: string;
    matchScore: number;
  }>;
}

function isBrowser() {
  return typeof window !== "undefined";
}

function emitWorkspaceUpdate() {
  if (!isBrowser()) return;
  window.dispatchEvent(new CustomEvent("kafundo:workspace-update"));
}

function getToken(): string | null {
  if (!isBrowser()) return null;
  return localStorage.getItem("kafundo_token");
}

async function workspaceFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  if (!token) {
    throw new Error("Utilisateur non connecte.");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    throw new Error(`Workspace API ${response.status}`);
  }

  if (response.status === 204) {
    return null as T;
  }

  return response.json();
}

function safeSetJson(key: string, value: unknown) {
  if (!isBrowser()) return;
  localStorage.setItem(key, JSON.stringify(value));
}

function normalizeSavedSearch(item: any): SavedSearch {
  return {
    id: String(item.id),
    name: String(item.name || "Recherche sauvegardee"),
    title: String(item.title || "Opportunités"),
    path: String(item.path || "/devices"),
    filters: (item.filters || {}) as SavedSearchFilters,
    resultCount: item.result_count ?? null,
    savedAt: String(item.updated_at || item.created_at || new Date().toISOString()),
  };
}

function normalizeFavorite(item: any): FavoriteDevice {
  const snapshot = item.snapshot || {};
  return {
    id: String(snapshot.id || item.device_id),
    title: String(snapshot.title || "Opportunité sauvegardée"),
    organism: String(snapshot.organism || ""),
    country: String(snapshot.country || ""),
    region: snapshot.region ?? null,
    deviceType: String(snapshot.deviceType || snapshot.device_type || "autre"),
    status: String(snapshot.status || "open"),
    closeDate: snapshot.closeDate ?? snapshot.close_date ?? null,
    amountMax: snapshot.amountMax ?? snapshot.amount_max ?? null,
    currency: String(snapshot.currency || "EUR"),
    sourceUrl: String(snapshot.sourceUrl || snapshot.source_url || ""),
    savedAt: String(snapshot.savedAt || item.created_at || new Date().toISOString()),
  };
}

function normalizePipeline(item: any): DevicePipelineEntry {
  const snapshot = item.snapshot || {};
  const priority = String(item.priority || snapshot.priority || "moyenne");
  return {
    id: String(snapshot.id || item.device_id),
    title: String(snapshot.title || "Opportunité suivie"),
    organism: String(snapshot.organism || ""),
    country: String(snapshot.country || ""),
    region: snapshot.region ?? null,
    deviceType: String(snapshot.deviceType || snapshot.device_type || "autre"),
    status: String(snapshot.status || "open"),
    closeDate: snapshot.closeDate ?? snapshot.close_date ?? null,
    amountMax: snapshot.amountMax ?? snapshot.amount_max ?? null,
    currency: String(snapshot.currency || "EUR"),
    sourceUrl: String(snapshot.sourceUrl || snapshot.source_url || ""),
    pipelineStatus: String(item.pipeline_status || snapshot.pipelineStatus || "a_etudier") as DevicePipelineStatus,
    priority: (["faible", "moyenne", "haute"].includes(priority) ? priority : "moyenne") as DevicePipelinePriority,
    reminderDate: item.reminder_date ?? snapshot.reminderDate ?? snapshot.reminder_date ?? null,
    matchProjectId: item.match_project_id ? String(item.match_project_id) : snapshot.matchProjectId ?? snapshot.match_project_id ?? null,
    note: String(item.note || snapshot.note || ""),
    documents: Array.isArray(item.documents) ? item.documents : [],
    updatedAt: String(item.updated_at || snapshot.updatedAt || new Date().toISOString()),
  };
}

function savedSearchPayload(search: SavedSearch) {
  return {
    id: search.id,
    name: search.name,
    title: search.title,
    path: search.path,
    filters: search.filters,
    result_count: search.resultCount,
  };
}

function favoritePayload(device: FavoriteDevice) {
  return {
    device_id: device.id,
    snapshot: device,
  };
}

function pipelinePayload(entry: DevicePipelineEntry) {
  return {
    device_id: entry.id,
    pipeline_status: entry.pipelineStatus,
    priority: entry.priority,
    reminder_date: entry.reminderDate,
    match_project_id: entry.matchProjectId,
    note: entry.note,
    documents: entry.documents ?? [],
    snapshot: entry,
  };
}

async function upsertRemoteSavedSearch(search: SavedSearch) {
  await workspaceFetch("/api/v1/workspace/saved-searches", {
    method: "POST",
    body: JSON.stringify(savedSearchPayload(search)),
  });
}

async function deleteRemoteSavedSearch(searchId: string) {
  await workspaceFetch(`/api/v1/workspace/saved-searches/${searchId}`, { method: "DELETE" });
}

async function upsertRemoteFavorite(device: FavoriteDevice) {
  await workspaceFetch("/api/v1/workspace/favorites", {
    method: "POST",
    body: JSON.stringify(favoritePayload(device)),
  });
}

async function deleteRemoteFavorite(deviceId: string) {
  await workspaceFetch(`/api/v1/workspace/favorites/${deviceId}`, { method: "DELETE" });
}

async function upsertRemotePipeline(entry: DevicePipelineEntry) {
  await workspaceFetch("/api/v1/workspace/pipeline", {
    method: "POST",
    body: JSON.stringify(pipelinePayload(entry)),
  });
}

async function deleteRemotePipeline(deviceId: string) {
  await workspaceFetch(`/api/v1/workspace/pipeline/${deviceId}`, { method: "DELETE" });
}

async function saveRemotePreferences(preferences: UserPreferences) {
  await workspaceFetch("/api/v1/workspace/preferences", {
    method: "PUT",
    body: JSON.stringify({ preferences }),
  });
}

async function saveRemoteMatchSnapshot(snapshot: MatchWorkspaceSnapshot) {
  await workspaceFetch("/api/v1/workspace/match-projects", {
    method: "POST",
    body: JSON.stringify({
      file_name: snapshot.fileName,
      file_size: snapshot.fileSize,
      result: {
        total: snapshot.total,
        matches: snapshot.topMatches.map((item) => ({
          id: item.id,
          title: item.title,
          country: item.country,
          device_type: item.deviceType,
          match_score: item.matchScore,
        })),
      },
    }),
  });
}

export async function syncWorkspace() {
  if (!isBrowser() || !getToken()) return false;

  await migrateLocalWorkspaceToApi();

  const snapshot = await workspaceFetch<any>("/api/v1/workspace");
  safeSetJson(SAVED_SEARCHES_KEY, (snapshot.saved_searches || []).map(normalizeSavedSearch));
  safeSetJson(FAVORITE_DEVICES_KEY, (snapshot.favorites || []).map(normalizeFavorite));
  safeSetJson(DEVICE_PIPELINE_KEY, (snapshot.pipeline || []).map(normalizePipeline));

  if (snapshot.preferences?.preferences) {
    safeSetJson(USER_PREFERENCES_KEY, snapshot.preferences.preferences);
  }

  const latestMatch = Array.isArray(snapshot.match_projects) ? snapshot.match_projects[0] : null;
  if (latestMatch) {
    safeSetJson(MATCH_STORAGE_KEY, {
      id: latestMatch.id ?? null,
      fileName: latestMatch.file_name ?? null,
      fileSize: latestMatch.file_size ?? null,
      result: latestMatch.result || { total: 0, matches: [] },
      updatedAt: latestMatch.updated_at || latestMatch.created_at || null,
    });
  }

  emitWorkspaceUpdate();
  return true;
}

export async function migrateLocalWorkspaceToApi() {
  if (!isBrowser() || !getToken()) return false;
  if (localStorage.getItem(WORKSPACE_MIGRATION_KEY) === "1") return false;

  const tasks: Array<Promise<unknown>> = [
    ...listSavedSearches().map(upsertRemoteSavedSearch),
    ...listFavoriteDevices().map(upsertRemoteFavorite),
    ...listPipelineDevices().map(upsertRemotePipeline),
  ];

  if (localStorage.getItem(USER_PREFERENCES_KEY)) {
    tasks.push(saveRemotePreferences(getUserPreferences()));
  }

  await Promise.allSettled(tasks);

  const latestMatch = readLatestMatchSnapshot();
  if (latestMatch?.updatedAt && localStorage.getItem(WORKSPACE_MATCH_SYNC_KEY) !== latestMatch.updatedAt) {
    await saveRemoteMatchSnapshot(latestMatch).catch(() => undefined);
    localStorage.setItem(WORKSPACE_MATCH_SYNC_KEY, latestMatch.updatedAt);
  }

  localStorage.setItem(WORKSPACE_MIGRATION_KEY, "1");
  return true;
}

export function listSavedSearches(): SavedSearch[] {
  if (!isBrowser()) return [];

  try {
    const raw = localStorage.getItem(SAVED_SEARCHES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveSearch(search: SavedSearch) {
  if (!isBrowser()) return;

  const existing = listSavedSearches().filter((item) => item.id !== search.id);
  const next = [search, ...existing].slice(0, 20);
  localStorage.setItem(SAVED_SEARCHES_KEY, JSON.stringify(next));
  emitWorkspaceUpdate();
  void upsertRemoteSavedSearch(search).catch(() => undefined);
}

export function deleteSavedSearch(searchId: string) {
  if (!isBrowser()) return;
  const next = listSavedSearches().filter((item) => item.id !== searchId);
  localStorage.setItem(SAVED_SEARCHES_KEY, JSON.stringify(next));
  emitWorkspaceUpdate();
  void deleteRemoteSavedSearch(searchId).catch(() => undefined);
}

export function queueSavedSearch(search: SavedSearch, mode: "open" | "edit" = "open") {
  if (!isBrowser()) return;
  localStorage.setItem(PENDING_SAVED_SEARCH_KEY, JSON.stringify({ search, mode } satisfies PendingSavedSearch));
}

export function consumePendingSavedSearch(pathname: string): PendingSavedSearch | null {
  if (!isBrowser()) return null;

  try {
    const raw = localStorage.getItem(PENDING_SAVED_SEARCH_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PendingSavedSearch;
    if (parsed.search.path !== pathname) return null;
    localStorage.removeItem(PENDING_SAVED_SEARCH_KEY);
    return parsed;
  } catch {
    localStorage.removeItem(PENDING_SAVED_SEARCH_KEY);
    return null;
  }
}

export function readLatestMatchSnapshot(): MatchWorkspaceSnapshot | null {
  if (!isBrowser()) return null;

  try {
    const raw = localStorage.getItem(MATCH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as any;
    const matches = Array.isArray(parsed?.result?.matches) ? parsed.result.matches : [];
    return {
      id: parsed?.id ?? null,
      fileName: parsed?.fileName ?? null,
      fileSize: parsed?.fileSize ?? null,
      total: Number(parsed?.result?.total ?? matches.length ?? 0),
      updatedAt: parsed?.updatedAt ?? null,
      topMatches: matches.slice(0, 3).map((item: any) => ({
        id: String(item.id),
        title: String(item.title ?? ""),
        country: String(item.country ?? ""),
        deviceType: String(item.device_type ?? ""),
        matchScore: Number(item.match_score ?? 0),
      })),
    };
  } catch {
    return null;
  }
}

export function listFavoriteDevices(): FavoriteDevice[] {
  if (!isBrowser()) return [];

  try {
    const raw = localStorage.getItem(FAVORITE_DEVICES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function isFavoriteDevice(deviceId: string): boolean {
  return listFavoriteDevices().some((item) => item.id === deviceId);
}

export function toggleFavoriteDevice(device: Omit<FavoriteDevice, "savedAt">): boolean {
  if (!isBrowser()) return false;

  const existing = listFavoriteDevices();
  const isAlreadyFavorite = existing.some((item) => item.id === device.id);
  const next = isAlreadyFavorite
    ? existing.filter((item) => item.id !== device.id)
    : [{ ...device, savedAt: new Date().toISOString() }, ...existing].slice(0, 50);

  localStorage.setItem(FAVORITE_DEVICES_KEY, JSON.stringify(next));
  emitWorkspaceUpdate();
  if (isAlreadyFavorite) {
    void deleteRemoteFavorite(device.id).catch(() => undefined);
  } else {
    void upsertRemoteFavorite(next[0]).catch(() => undefined);
  }
  return !isAlreadyFavorite;
}

export function removeFavoriteDevice(deviceId: string) {
  if (!isBrowser()) return;
  const next = listFavoriteDevices().filter((item) => item.id !== deviceId);
  localStorage.setItem(FAVORITE_DEVICES_KEY, JSON.stringify(next));
  emitWorkspaceUpdate();
  void deleteRemoteFavorite(deviceId).catch(() => undefined);
}

export function getSavedViewMode(pathname: string): DevicesViewMode | null {
  if (!isBrowser()) return null;

  try {
    const raw = localStorage.getItem(DEVICES_VIEW_MODE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Record<string, DevicesViewMode>;
    return parsed[pathname] || null;
  } catch {
    return null;
  }
}

export function setSavedViewMode(pathname: string, mode: DevicesViewMode) {
  if (!isBrowser()) return;

  try {
    const raw = localStorage.getItem(DEVICES_VIEW_MODE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Record<string, DevicesViewMode>) : {};
    parsed[pathname] = mode;
    localStorage.setItem(DEVICES_VIEW_MODE_KEY, JSON.stringify(parsed));
  } catch {
    localStorage.setItem(DEVICES_VIEW_MODE_KEY, JSON.stringify({ [pathname]: mode }));
  }
}

export function listPipelineDevices(): DevicePipelineEntry[] {
  if (!isBrowser()) return [];

  try {
    const raw = localStorage.getItem(DEVICE_PIPELINE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.map((item) => {
      const status = String(item.pipelineStatus || "a_etudier");
      const priority = String(item.priority || "moyenne");
      return {
        ...item,
        pipelineStatus: (["a_etudier", "interessant", "candidature_en_cours", "soumis", "refuse", "non_pertinent"].includes(status)
          ? status
          : "a_etudier") as DevicePipelineStatus,
        priority: (["faible", "moyenne", "haute"].includes(priority) ? priority : "moyenne") as DevicePipelinePriority,
        reminderDate: item.reminderDate ?? null,
        matchProjectId: item.matchProjectId ?? null,
        documents: Array.isArray(item.documents) ? item.documents : [],
        updatedAt: item.updatedAt || new Date().toISOString(),
      };
    });
  } catch {
    return [];
  }
}

export function getPipelineDevice(deviceId: string): DevicePipelineEntry | null {
  return listPipelineDevices().find((item) => item.id === deviceId) || null;
}

export function savePipelineDevice(entry: Omit<DevicePipelineEntry, "updatedAt">) {
  if (!isBrowser()) return;

  const existing = listPipelineDevices().filter((item) => item.id !== entry.id);
  const next = [{ ...entry, updatedAt: new Date().toISOString() }, ...existing].slice(0, 200);
  localStorage.setItem(DEVICE_PIPELINE_KEY, JSON.stringify(next));
  emitWorkspaceUpdate();
  void upsertRemotePipeline(next[0]).catch(() => undefined);
}

export function removePipelineDevice(deviceId: string) {
  if (!isBrowser()) return;
  const next = listPipelineDevices().filter((item) => item.id !== deviceId);
  localStorage.setItem(DEVICE_PIPELINE_KEY, JSON.stringify(next));
  emitWorkspaceUpdate();
  void deleteRemotePipeline(deviceId).catch(() => undefined);
}

export function getUserPreferences(): UserPreferences {
  const fallback: UserPreferences = {
    defaultViewMode: "cards",
    emailDigest: true,
    productTips: true,
  };

  if (!isBrowser()) return fallback;

  try {
    const raw = localStorage.getItem(USER_PREFERENCES_KEY);
    if (!raw) return fallback;
    return { ...fallback, ...(JSON.parse(raw) as Partial<UserPreferences>) };
  } catch {
    return fallback;
  }
}

export function saveUserPreferences(preferences: UserPreferences) {
  if (!isBrowser()) return;
  localStorage.setItem(USER_PREFERENCES_KEY, JSON.stringify(preferences));
  emitWorkspaceUpdate();
  void saveRemotePreferences(preferences).catch(() => undefined);
}

// ─── Pipeline document helpers ─────────────────────────────────────────────

export async function addPipelineDocument(
  deviceId: string,
  doc: { name: string; url?: string | null; doc_type?: string; note?: string | null }
): Promise<PipelineDocument> {
  // Backend returns the full pipeline response; extract the newly added document (last one)
  const pipelineResp = await workspaceFetch<any>(`/api/v1/workspace/pipeline/${deviceId}/documents`, {
    method: "POST",
    body: JSON.stringify({
      name: doc.name,
      url: doc.url ?? null,
      doc_type: doc.doc_type ?? "url",
      note: doc.note ?? null,
    }),
  });
  const docs: PipelineDocument[] = Array.isArray(pipelineResp.documents) ? pipelineResp.documents : [];
  const added = docs.find((d) => d.name === doc.name) ?? docs[docs.length - 1];
  if (!added) throw new Error("Document introuvable dans la réponse");
  return added;
}

export async function removePipelineDocument(deviceId: string, docId: string): Promise<void> {
  // Backend returns updated pipeline response; we ignore the body
  await workspaceFetch<any>(`/api/v1/workspace/pipeline/${deviceId}/documents/${docId}`, {
    method: "DELETE",
  });
}

// ─── Team view ────────────────────────────────────────────────────────────

export interface TeamMemberPipelineItem {
  device_id: string;
  pipeline_status: string;
  priority: string;
  note: string;
  documents_count: number;
  snapshot: Record<string, any>;
  updated_at: string | null;
}

export interface TeamMember {
  user_id: string;
  full_name: string | null;
  email: string;
  role: string;
  pipeline: TeamMemberPipelineItem[];
}

export interface TeamView {
  organization_id: string | null;
  organization_name: string | null;
  members: TeamMember[];
}

export async function fetchTeamView(): Promise<TeamView> {
  return workspaceFetch<TeamView>("/api/v1/workspace/team");
}

// ─── Activity feed ────────────────────────────────────────────────────────

export interface ActivityItem {
  id: string;
  activity_type: string;
  label: string;
  description: string;
  device_id: string | null;
  device_title: string | null;
  user_id: string | null;
  user_name: string | null;
  occurred_at: string;
}

export interface ActivityFeed {
  items: ActivityItem[];
  total: number;
}

export async function fetchActivityFeed(limit = 20): Promise<ActivityFeed> {
  return workspaceFetch<ActivityFeed>(`/api/v1/workspace/activity?limit=${limit}`);
}

// ─── Reporting décisionnel ────────────────────────────────────────────────────

export interface PipelineReporting {
  total: number;
  active: number;
  by_status: Record<string, number>;
  submitted: number;
  refused: number;
  non_pertinent: number;
  submission_rate: number;
  refusal_rate: number;
  total_amount_detected: number;
  pipeline_count: number;
  team_stats: {
    member_count: number;
    total_tracked: number;
    total_submitted: number;
  } | null;
}

export async function fetchReporting(): Promise<PipelineReporting> {
  return workspaceFetch<PipelineReporting>("/api/v1/workspace/reporting");
}
