export type AppRole = "admin" | "editor" | "reader";

export interface StoredUser {
  id?: string;
  email?: string;
  full_name?: string | null;
  name?: string | null;
  role?: AppRole;
  platform_role?: "super_admin" | "member";
  default_organization_id?: string | null;
}

function getStoredUser(): StoredUser | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = localStorage.getItem("finveille_user");
    if (!raw) return null;
    return JSON.parse(raw) as StoredUser;
  } catch {
    return null;
  }
}

export function getCurrentRole(): AppRole {
  return getStoredUser()?.role || "reader";
}

export function isAdminRole(role: AppRole): boolean {
  return role === "admin";
}

export function isStaffRole(role: AppRole): boolean {
  return role === "admin" || role === "editor";
}

/** Access to the super admin cockpit. */
export function canAccessAdmin(role: AppRole): boolean {
  return isAdminRole(role);
}

/** Access to operational source management. */
export function canManageSources(role: AppRole): boolean {
  return isStaffRole(role);
}

export function canCreateDevices(role: AppRole): boolean {
  return isStaffRole(role);
}

export function canModerateDevices(role: AppRole): boolean {
  return isStaffRole(role);
}
