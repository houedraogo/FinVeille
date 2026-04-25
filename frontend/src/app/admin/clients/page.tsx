"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  Crown,
  Filter,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  Users,
  X,
} from "lucide-react";
import clsx from "clsx";

import AppLayout from "@/components/AppLayout";
import RoleGate from "@/components/RoleGate";
import { admin, billing } from "@/lib/api";
import { formatDateRelative } from "@/lib/utils";

const METRIC_LABELS: Record<string, string> = {
  users: "utilisateurs",
  alerts: "alertes",
  saved_searches: "recherches",
  pipeline_projects: "suivi",
};

const PLAN_COLORS: Record<string, string> = {
  free: "bg-slate-100 text-slate-600",
  starter: "bg-blue-50 text-blue-700",
  pro: "bg-violet-50 text-violet-700",
  team: "bg-emerald-50 text-emerald-700",
  expert: "bg-amber-50 text-amber-700",
  enterprise: "bg-rose-50 text-rose-700",
};

function usageText(org: any) {
  return Object.entries(org.usage || {})
    .map(([key, value]) => `${METRIC_LABELS[key] || key}: ${Number(value || 0)}/${org.limits?.[key] ?? "∞"}`)
    .join(" · ");
}

export default function AdminClientsPage() {
  const [operations, setOperations] = useState<any>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "paid" | "free" | "limited" | "inactive">("all");
  const [query, setQuery] = useState("");

  // Plan assignment modal
  const [assignTarget, setAssignTarget] = useState<any | null>(null);
  const [assignSlug, setAssignSlug] = useState("");
  const [assignLoading, setAssignLoading] = useState(false);
  const [assignMsg, setAssignMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  // Delete confirmation modal
  const [deleteTarget, setDeleteTarget] = useState<any | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Feedback global
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [ops, plansData] = await Promise.all([admin.operations(), billing.plans()]);
      setOperations(ops);
      setPlans(plansData || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const organizations: any[] = operations?.organizations || [];

  const filtered = useMemo(() => {
    return organizations.filter((org: any) => {
      if (filter === "paid" && org.plan_slug === "free") return false;
      if (filter === "free" && org.plan_slug !== "free") return false;
      if (filter === "limited" && !org.limits_reached?.length) return false;
      if (filter === "inactive" && org.status === "active") return false;
      const needle = query.trim().toLowerCase();
      if (!needle) return true;
      return [org.name, org.slug, org.billing_email, org.owners?.[0]?.email]
        .filter(Boolean)
        .some((value: string) => value.toLowerCase().includes(needle));
    });
  }, [filter, organizations, query]);

  /* ── Handlers ── */

  const openAssign = (org: any) => {
    setAssignTarget(org);
    setAssignSlug(org.plan_slug || "free");
    setAssignMsg(null);
  };

  const handleAssignPlan = async () => {
    if (!assignTarget || !assignSlug) return;
    setAssignLoading(true);
    setAssignMsg(null);
    try {
      await admin.assignPlan(assignTarget.id, assignSlug);
      const planName = plans.find((p) => p.slug === assignSlug)?.name || assignSlug;
      setAssignMsg({ type: "ok", text: `Plan "${planName}" attribué avec succès.` });
      // Mettre à jour localement sans rechargement
      setOperations((prev: any) => ({
        ...prev,
        organizations: prev.organizations.map((o: any) =>
          o.id === assignTarget.id
            ? { ...o, plan_slug: assignSlug, plan: planName }
            : o
        ),
      }));
      setTimeout(() => { setAssignTarget(null); setAssignMsg(null); }, 1400);
    } catch (e: any) {
      setAssignMsg({ type: "err", text: e.message || "Erreur lors de l'attribution." });
    } finally {
      setAssignLoading(false);
    }
  };

  const handleDeleteUser = async () => {
    const ownerId = deleteTarget?.owners?.[0]?.id;
    const ownerEmail = deleteTarget?.owners?.[0]?.email;
    if (!ownerId) return;
    setDeleteLoading(true);
    try {
      await admin.deleteUser(ownerId);
      setFeedback({ type: "success", text: `Compte "${ownerEmail}" désactivé avec succès.` });
      // Retirer l'org de la liste (ou la marquer inactive)
      setOperations((prev: any) => ({
        ...prev,
        organizations: prev.organizations.filter((o: any) => o.id !== deleteTarget.id),
      }));
      setDeleteTarget(null);
    } catch (e: any) {
      setFeedback({ type: "error", text: e.message || "Erreur lors de la suppression." });
      setDeleteTarget(null);
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <RoleGate allow={["admin"]} title="Clients réservé" message="Cette page est réservée au super admin." backHref="/admin/workspace">
      <AppLayout>
        {/* Header */}
        <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-primary-600">Super admin</p>
            <h1 className="mt-1 text-2xl font-bold text-slate-950">Clients</h1>
            <p className="mt-2 text-sm text-slate-500">
              Organisations, plans, propriétaires, usage et limites. Attribuez un abonnement ou désactivez un compte.
            </p>
          </div>
          <button onClick={load} disabled={loading} className="btn-secondary text-xs">
            <RefreshCw className={clsx("h-3.5 w-3.5", loading && "animate-spin")} />
            Actualiser
          </button>
        </div>

        {/* Feedback global */}
        {feedback && (
          <div className={clsx(
            "mb-4 flex items-center justify-between rounded-2xl border px-4 py-3 text-sm",
            feedback.type === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-red-200 bg-red-50 text-red-800"
          )}>
            <span>{feedback.text}</span>
            <button onClick={() => setFeedback(null)} className="ml-4 opacity-60 hover:opacity-100">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Barre recherche + filtres */}
        <div className="mb-4 rounded-[26px] border border-slate-200 bg-white p-4 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative max-w-md flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="input pl-9"
                placeholder="Rechercher client, owner, email…"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {[
                ["all", "Tous"],
                ["paid", "Payants"],
                ["free", "Gratuits"],
                ["limited", "Limites atteintes"],
                ["inactive", "Inactifs"],
              ].map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setFilter(key as any)}
                  className={clsx(
                    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                    filter === key
                      ? "border-primary-600 bg-primary-600 text-white"
                      : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-primary-50"
                  )}
                >
                  <Filter className="h-3 w-3" />
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Tableau */}
        <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
          <div className="grid grid-cols-[1.3fr_0.7fr_1.1fr_0.8fr_1.2fr_0.7fr_auto] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
            <span>Organisation</span>
            <span>Plan</span>
            <span>Propriétaire</span>
            <span>Stripe</span>
            <span>Usage</span>
            <span>Création</span>
            <span>Actions</span>
          </div>

          <div className="divide-y divide-slate-100">
            {loading ? (
              <div className="flex items-center justify-center py-14 text-sm text-slate-400">
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Chargement clients…
              </div>
            ) : filtered.length === 0 ? (
              <p className="py-12 text-center text-sm text-slate-400">Aucun client ne correspond au filtre.</p>
            ) : (
              filtered.map((org: any) => {
                const owner = org.owners?.[0];
                return (
                  <div
                    key={org.id}
                    className="grid grid-cols-[1.3fr_0.7fr_1.1fr_0.8fr_1.2fr_0.7fr_auto] gap-3 px-4 py-4 text-sm transition-colors hover:bg-slate-50/60"
                  >
                    {/* Org */}
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-slate-950">{org.name}</p>
                      <p className="truncate text-xs text-slate-400">{org.slug}</p>
                    </div>

                    {/* Plan */}
                    <div>
                      <span className={clsx(
                        "rounded-full px-2.5 py-1 text-xs font-medium",
                        PLAN_COLORS[org.plan_slug] || "bg-slate-100 text-slate-600"
                      )}>
                        {org.plan || org.plan_slug || "Free"}
                      </span>
                      {org.subscription_status && (
                        <p className="mt-1 text-[10px] text-slate-400">{org.subscription_status}</p>
                      )}
                    </div>

                    {/* Propriétaire */}
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-800">
                        {owner?.full_name || owner?.email || "Non renseigné"}
                      </p>
                      <p className="truncate text-xs text-slate-400">
                        {owner?.email || org.billing_email || "Email absent"}
                      </p>
                    </div>

                    {/* Stripe */}
                    <div>
                      <p className="truncate text-xs text-slate-500">{org.stripe_customer_id || "Aucun"}</p>
                      <p className="mt-1 truncate text-xs text-slate-400">
                        {org.stripe_subscription_id || "Sans abonnement"}
                      </p>
                    </div>

                    {/* Usage */}
                    <div>
                      <p className="line-clamp-2 text-xs leading-5 text-slate-600">{usageText(org)}</p>
                      {org.limits_reached?.length > 0 && (
                        <p className="mt-1 inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                          <AlertTriangle className="h-3 w-3" />
                          Limite atteinte
                        </p>
                      )}
                    </div>

                    {/* Date */}
                    <div className="text-xs text-slate-500">
                      {org.created_at ? formatDateRelative(org.created_at) : "N/A"}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1.5">
                      {/* Voir le détail */}
                      <Link
                        href={`/admin/clients/${org.id}`}
                        className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-colors hover:border-primary-300 hover:text-primary-700"
                        title="Voir le détail"
                      >
                        <ArrowRight className="h-3.5 w-3.5" />
                      </Link>

                      {/* Attribuer un plan */}
                      <button
                        type="button"
                        onClick={() => openAssign(org)}
                        className="flex h-8 w-8 items-center justify-center rounded-lg border border-primary-200 bg-primary-50 text-primary-700 transition-colors hover:bg-primary-100"
                        title="Attribuer un abonnement"
                      >
                        <Crown className="h-3.5 w-3.5" />
                      </button>

                      {/* Désactiver l'utilisateur */}
                      {owner && (
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(org)}
                          className="flex h-8 w-8 items-center justify-center rounded-lg border border-red-200 bg-red-50 text-red-600 transition-colors hover:bg-red-100"
                          title="Désactiver l'utilisateur"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Stats bas de page */}
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4">
            <Building2 className="h-5 w-5 text-blue-700" />
            <p className="mt-2 text-sm font-semibold text-blue-950">
              {organizations.length.toLocaleString("fr")} organisations
            </p>
          </div>
          <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
            <Users className="h-5 w-5 text-emerald-700" />
            <p className="mt-2 text-sm font-semibold text-emerald-950">
              {organizations.filter((o: any) => o.plan_slug !== "free").length.toLocaleString("fr")} payants
            </p>
          </div>
          <div className="rounded-2xl border border-amber-100 bg-amber-50 p-4">
            <AlertTriangle className="h-5 w-5 text-amber-700" />
            <p className="mt-2 text-sm font-semibold text-amber-950">
              {organizations.filter((o: any) => o.limits_reached?.length).length.toLocaleString("fr")} limites atteintes
            </p>
          </div>
        </div>

        {/* ── Modale : Attribution de plan ── */}
        {assignTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm">
            <div className="w-full max-w-md rounded-[28px] border border-slate-200 bg-white p-6 shadow-2xl">
              <div className="mb-5 flex items-start justify-between">
                <div>
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary-50 text-primary-700">
                    <Crown className="h-5 w-5" />
                  </div>
                  <h2 className="mt-3 text-lg font-semibold text-slate-950">Attribuer un abonnement</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    Organisation : <span className="font-semibold text-slate-800">{assignTarget.name}</span>
                  </p>
                  <p className="text-xs text-slate-400">
                    Plan actuel : {assignTarget.plan || assignTarget.plan_slug || "Free"}
                  </p>
                </div>
                <button onClick={() => setAssignTarget(null)} className="text-slate-400 hover:text-slate-700">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="mb-4">
                <label className="label">Nouveau plan</label>
                <select
                  className="input"
                  value={assignSlug}
                  onChange={(e) => setAssignSlug(e.target.value)}
                >
                  {plans.length === 0 ? (
                    <option value="free">Free</option>
                  ) : (
                    plans.map((p) => (
                      <option key={p.slug} value={p.slug}>
                        {p.name}{p.price_monthly_eur > 0 ? ` — ${p.price_monthly_eur} EUR/mois` : " — Gratuit"}
                      </option>
                    ))
                  )}
                </select>
                <p className="mt-1.5 text-xs text-slate-400">
                  Changement immédiat, sans passer par Stripe. Aucun paiement déclenché.
                </p>
              </div>

              {assignMsg && (
                <p className={clsx(
                  "mb-4 rounded-xl px-3 py-2 text-sm",
                  assignMsg.type === "ok" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
                )}>
                  {assignMsg.text}
                </p>
              )}

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handleAssignPlan}
                  disabled={assignLoading || !assignSlug}
                  className="btn-primary flex-1 justify-center disabled:opacity-50"
                >
                  {assignLoading
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <ShieldCheck className="h-4 w-4" />}
                  Confirmer
                </button>
                <button type="button" onClick={() => setAssignTarget(null)} className="btn-secondary">
                  Annuler
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Modale : Confirmation suppression ── */}
        {deleteTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm">
            <div className="w-full max-w-md rounded-[28px] border border-red-200 bg-white p-6 shadow-2xl">
              <div className="mb-5 flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-red-50 text-red-600">
                  <Trash2 className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-slate-950">Désactiver ce compte ?</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    L'utilisateur{" "}
                    <span className="font-semibold text-slate-800">
                      {deleteTarget.owners?.[0]?.email || "inconnu"}
                    </span>{" "}
                    ne pourra plus se connecter. L'organisation et ses données sont conservées.
                  </p>
                  <p className="mt-2 text-xs text-slate-400">
                    Cette action est réversible depuis la base de données.
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handleDeleteUser}
                  disabled={deleteLoading}
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteLoading
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <Trash2 className="h-4 w-4" />}
                  Désactiver le compte
                </button>
                <button type="button" onClick={() => setDeleteTarget(null)} className="btn-secondary">
                  Annuler
                </button>
              </div>
            </div>
          </div>
        )}
      </AppLayout>
    </RoleGate>
  );
}
