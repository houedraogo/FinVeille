export type AppRole = "admin" | "editor" | "reader";

export function getCurrentRole(): AppRole {
  if (typeof window === "undefined") return "reader";
  try {
    const raw = localStorage.getItem("finveille_user");
    if (!raw) return "reader";
    const user = JSON.parse(raw);
    return (user.role as AppRole) || "reader";
  } catch {
    return "reader";
  }
}

/** Accès au panneau d'administration */
export function canAccessAdmin(role: AppRole): boolean {
  return role === "admin";
}

/** Accès à la gestion des sources */
export function canManageSources(role: AppRole): boolean {
  return role === "admin" || role === "editor";
}
