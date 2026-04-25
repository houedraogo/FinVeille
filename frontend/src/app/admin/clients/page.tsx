"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Building2, Filter, RefreshCw, Search, Users } from "lucide-react";
import clsx from "clsx";

import AppLayout from "@/components/AppLayout";
import RoleGate from "@/components/RoleGate";
import { admin } from "@/lib/api";
import { formatDateRelative } from "@/lib/utils";

const METRIC_LABELS: Record<string, string> = {
  users: "utilisateurs",
  alerts: "alertes",
  saved_searches: "recherches",
  pipeline_projects: "suivi",
};

function usageText(org: any) {
  return Object.entries(org.usage || {})
    .map(([key, value]) => `${METRIC_LABELS[key] || key}: ${Number(value || 0)}/${org.limits?.[key] ?? "∞"}`)
    .join(" · ");
}

export default function AdminClientsPage() {
  const [operations, setOperations] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "paid" | "free" | "limited" | "inactive">("all");
  const [query, setQuery] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      setOperations(await admin.operations());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const organizations = operations?.organizations || [];
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

  return (
    <RoleGate allow={["admin"]} title="Clients reserve" message="Cette page est reservee au super admin." backHref="/admin/workspace">
      <AppLayout>
        <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-primary-600">Super admin</p>
            <h1 className="mt-1 text-2xl font-bold text-slate-950">Clients</h1>
            <p className="mt-2 text-sm text-slate-500">Organisations, plans, propriétaires, statut Stripe, usage et limites.</p>
          </div>
          <button onClick={load} disabled={loading} className="btn-secondary text-xs">
            <RefreshCw className={clsx("h-3.5 w-3.5", loading && "animate-spin")} />
            Actualiser
          </button>
        </div>

        <div className="mb-4 rounded-[26px] border border-slate-200 bg-white p-4 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative max-w-md flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input value={query} onChange={(event) => setQuery(event.target.value)} className="input pl-9" placeholder="Rechercher client, owner, email..." />
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
                    filter === key ? "border-primary-600 bg-primary-600 text-white" : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-primary-50",
                  )}
                >
                  <Filter className="h-3 w-3" />
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
          <div className="grid grid-cols-[1.2fr_0.7fr_1fr_0.8fr_1.3fr_0.75fr_0.5fr] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
            <span>Organisation</span>
            <span>Plan</span>
            <span>Proprietaire</span>
            <span>Stripe</span>
            <span>Usage</span>
            <span>Creation</span>
            <span />
          </div>
          <div className="divide-y divide-slate-100">
            {loading ? (
              <div className="flex items-center justify-center py-14 text-sm text-slate-400">
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Chargement clients...
              </div>
            ) : filtered.length === 0 ? (
              <p className="py-12 text-center text-sm text-slate-400">Aucun client ne correspond au filtre.</p>
            ) : (
              filtered.map((org: any) => {
                const owner = org.owners?.[0];
                return (
                  <div key={org.id} className="grid grid-cols-[1.2fr_0.7fr_1fr_0.8fr_1.3fr_0.75fr_0.5fr] gap-3 px-4 py-4 text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-slate-950">{org.name}</p>
                      <p className="truncate text-xs text-slate-400">{org.slug}</p>
                    </div>
                    <div>
                      <span className={org.plan_slug === "free" ? "rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600" : "rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700"}>
                        {org.plan}
                      </span>
                      <p className="mt-1 text-xs text-slate-400">{org.subscription_status}</p>
                    </div>
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-800">{owner?.full_name || owner?.email || "Non renseigne"}</p>
                      <p className="truncate text-xs text-slate-400">{owner?.email || org.billing_email || "Email absent"}</p>
                    </div>
                    <div>
                      <p className="truncate text-xs text-slate-500">{org.stripe_customer_id || "Aucun"}</p>
                      <p className="mt-1 truncate text-xs text-slate-400">{org.stripe_subscription_id || "Sans abonnement"}</p>
                    </div>
                    <div>
                      <p className="line-clamp-2 text-xs leading-5 text-slate-600">{usageText(org)}</p>
                      {org.limits_reached?.length > 0 && (
                        <p className="mt-1 inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                          <AlertTriangle className="h-3 w-3" />
                          Limite atteinte
                        </p>
                      )}
                    </div>
                    <div className="text-xs text-slate-500">{org.created_at ? formatDateRelative(org.created_at) : "N/A"}</div>
                    <Link href={`/admin/clients/${org.id}`} className="btn-secondary justify-center text-xs">
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4">
            <Building2 className="h-5 w-5 text-blue-700" />
            <p className="mt-2 text-sm font-semibold text-blue-950">{organizations.length.toLocaleString("fr")} organisations</p>
          </div>
          <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
            <Users className="h-5 w-5 text-emerald-700" />
            <p className="mt-2 text-sm font-semibold text-emerald-950">{organizations.filter((org: any) => org.plan_slug !== "free").length.toLocaleString("fr")} payants</p>
          </div>
          <div className="rounded-2xl border border-amber-100 bg-amber-50 p-4">
            <AlertTriangle className="h-5 w-5 text-amber-700" />
            <p className="mt-2 text-sm font-semibold text-amber-950">{organizations.filter((org: any) => org.limits_reached?.length).length.toLocaleString("fr")} limites atteintes</p>
          </div>
        </div>
      </AppLayout>
    </RoleGate>
  );
}
