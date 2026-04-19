const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("finveille_token");
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Erreur réseau" }));
    if (response.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("finveille_token");
      }
      throw new Error("Session expirée. Veuillez vous reconnecter.");
    }
    const detail =
      typeof error.detail === "string"
        ? error.detail
        : error.detail?.message
          ? error.detail.message
          : Array.isArray(error.detail)
            ? error.detail.map((item: any) => item.msg).join(", ")
            : null;
    throw new Error(detail || `HTTP ${response.status}`);
  }

  // 204 No Content (typique pour les DELETE) → retourner null
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return null as T;
  }

  return response.json();
}

// Auth
export const auth = {
  login: (email: string, password: string) =>
    apiFetch<{ access_token: string; user: any }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  googleLogin: (credential: string) =>
    apiFetch<{ access_token: string; user: any }>("/api/v1/auth/google", {
      method: "POST",
      body: JSON.stringify({ credential }),
    }),
  me: () => apiFetch("/api/v1/auth/me"),
  context: () => apiFetch("/api/v1/me/context"),
};

// Organizations
export const organizations = {
  current: () => apiFetch<any>("/api/v1/organizations/current"),
  create: (name: string) => apiFetch<any>("/api/v1/organizations", {
    method: "POST",
    body: JSON.stringify({ name }),
  }),
  invite: (data: { email: string; role: string; organization_id?: string }) =>
    apiFetch<any>("/api/v1/organizations/invite", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  acceptInvitation: (token: string) =>
    apiFetch<any>(`/api/v1/organizations/invitations/${token}/accept`, { method: "POST" }),
};

// Billing
export const billing = {
  plans: () => apiFetch<any[]>("/api/v1/billing/plans"),
  subscription: () => apiFetch<any>("/api/v1/billing/subscription"),
  checkout: (planSlug: string) =>
    apiFetch<any>("/api/v1/billing/checkout", {
      method: "POST",
      body: JSON.stringify({ plan_slug: planSlug }),
    }),
  portal: () => apiFetch<any>("/api/v1/billing/portal", { method: "POST" }),
};

// Security / RGPD
export const security = {
  forgotPassword: (email: string) =>
    apiFetch<any>("/api/v1/security/password/forgot", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, newPassword: string) =>
    apiFetch<any>("/api/v1/security/password/reset", {
      method: "POST",
      body: JSON.stringify({ token, new_password: newPassword }),
    }),
  createDataExport: () => apiFetch<any>("/api/v1/security/data-export", { method: "POST" }),
  requestDeletion: (reason?: string) =>
    apiFetch<any>("/api/v1/security/deletion-request", {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
};

// Devices
export const devices = {
  list: (params: Record<string, string | string[] | number | boolean | undefined> = {}) => {
    const qs = buildQueryString(params);
    return apiFetch<any>(`/api/v1/devices/?${qs}`);
  },
  get: (id: string) => apiFetch<any>(`/api/v1/devices/${id}`),
  stats: () => apiFetch<any>("/api/v1/devices/stats"),
  create: (data: any) => apiFetch("/api/v1/devices/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: any) =>
    apiFetch(`/api/v1/devices/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  validate: (id: string) => apiFetch(`/api/v1/devices/${id}/validate`, { method: "POST" }),
  reject: (id: string) => apiFetch(`/api/v1/devices/${id}/reject`, { method: "POST" }),
  delete: (id: string) => apiFetch<void>(`/api/v1/devices/${id}`, { method: "DELETE" }),
  bulkAction: (ids: string[], action: string, tags?: string[]) =>
    apiFetch<{ action: string; processed: number; failed: number; errors: string[] }>(
      "/api/v1/devices/bulk",
      { method: "POST", body: JSON.stringify({ ids, action, tags }) },
    ),
  history: (id: string) => apiFetch<any[]>(`/api/v1/devices/${id}/history`),
  scrape: (id: string) => apiFetch<any>(`/api/v1/devices/${id}/scrape`, { method: "POST" }),
  exportCsv: (params: Record<string, string | string[] | number | undefined> = {}) => {
    const qs = buildQueryString(params);
    return `${API_BASE}/api/v1/devices/export/csv?${qs}`;
  },
  exportExcel: (params: Record<string, string | string[] | number | undefined> = {}) => {
    const qs = buildQueryString(params);
    return `${API_BASE}/api/v1/devices/export/excel?${qs}`;
  },
};

// Dashboard
export const dashboard = {
  get: () => apiFetch<any>("/api/v1/dashboard/"),
};

// Sources
export const sources = {
  list: (params: Record<string, string | boolean | number | undefined> = {}) => {
    const qs = buildQueryString(params);
    return apiFetch<any[]>(`/api/v1/sources/?${qs}`);
  },
  test: (data: any) => apiFetch<any>("/api/v1/sources/test", { method: "POST", body: JSON.stringify(data) }),
  get: (id: string) => apiFetch<any>(`/api/v1/sources/${id}`),
  stats: () => apiFetch<any>("/api/v1/sources/stats"),
  create: (data: any) => apiFetch("/api/v1/sources/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: any) =>
    apiFetch(`/api/v1/sources/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  collect: (id: string) => apiFetch(`/api/v1/sources/${id}/collect`, { method: "POST" }),
  logs: (id: string) => apiFetch<any[]>(`/api/v1/sources/${id}/logs`),
  delete: (id: string) => apiFetch<void>(`/api/v1/sources/${id}`, { method: "DELETE" }),
};

// Alerts
export const alerts = {
  list: () => apiFetch<any[]>("/api/v1/alerts/"),
  get: (id: string) => apiFetch<any>(`/api/v1/alerts/${id}`),
  create: (data: any) => apiFetch("/api/v1/alerts/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: any) =>
    apiFetch(`/api/v1/alerts/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  delete: (id: string) => apiFetch<void>(`/api/v1/alerts/${id}`, { method: "DELETE" }),
  preview: (id: string) => apiFetch<any>(`/api/v1/alerts/${id}/preview`),
};

// Admin
export const admin = {
  quality: () => apiFetch<any>("/api/v1/admin/quality"),
  fixExpired: () => apiFetch("/api/v1/admin/quality/fix-expired", { method: "POST" }),
  pending: (page = 1) => apiFetch<any>(`/api/v1/admin/pending?page=${page}`),
  users: () => apiFetch<any[]>("/api/v1/admin/users"),
  organizations: () => apiFetch<any[]>("/api/v1/admin/organizations"),
  operations: () => apiFetch<any>("/api/v1/admin/operations"),
  collectAll: () => apiFetch("/api/v1/admin/collect/all", { method: "POST" }),
  emailStatus: () => apiFetch<any>("/api/v1/admin/email/status"),
  testEmail: () => apiFetch<any>("/api/v1/admin/email/test", { method: "POST" }),
  enrich: (batchSize = 50) => apiFetch<any>(`/api/v1/admin/enrich?batch_size=${batchSize}`, { method: "POST" }),
  dedup: () => apiFetch<any>("/api/v1/admin/dedup"),
  dedupMergeAll: () => apiFetch<any>("/api/v1/admin/dedup/merge", { method: "POST" }),
  dedupMergeGroup: (canonicalId: string, duplicateIds: string[]) =>
    apiFetch<any>("/api/v1/admin/dedup/merge-group", {
      method: "POST",
      body: JSON.stringify({ canonical_id: canonicalId, duplicate_ids: duplicateIds }),
    }),
};

function buildQueryString(params: Record<string, unknown>): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      value.forEach((v) => qs.append(key, String(v)));
    } else {
      qs.append(key, String(value));
    }
  }
  return qs.toString();
}
