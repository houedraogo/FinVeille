"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Building2,
  Clock,
  Database,
  Gauge,
  Mail,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Users,
} from "lucide-react";

import AppLayout from "@/components/AppLayout";
import RoleGate from "@/components/RoleGate";
import { admin } from "@/lib/api";
import { formatDateRelative } from "@/lib/utils";

const METRIC_LABELS: Record<string, string> = {
  users: "utilisateurs",
  alerts: "alertes",
  saved_searches: "recherches",
  pipeline_projects: "pipeline",
};

function KpiCard({
  label,
  value,
  sub,
  tone = "slate",
}: {
  label: string;
  value: string;
  sub: string;
  tone?: "slate" | "blue" | "green" | "amber" | "red";
}) {
  const tones = {
    slate: "border-slate-200 bg-white text-slate-950",
    blue: "border-blue-200 bg-blue-50 text-blue-950",
    green: "border-emerald-200 bg-emerald-50 text-emerald-950",
    amber: "border-amber-200 bg-amber-50 text-amber-950",
    red: "border-red-200 bg-red-50 text-red-950",
  };
  return (
    <div className={`rounded-[24px] border p-5 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)] ${tones[tone]}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.16em] opacity-60">{label}</p>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      <p className="mt-1 text-sm opacity-70">{sub}</p>
    </div>
  );
}

function Panel({
  title,
  description,
  icon: Icon,
  children,
}: {
  title: string;
  description: string;
  icon: typeof ShieldCheck;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
      <div className="mb-4 flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary-50 text-primary-700">
          <Icon className="h-5 w-5" />
        </span>
        <div>
          <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
          <p className="text-sm text-slate-500">{description}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function UsageBar({ used, limit }: { used: number; limit: number }) {
  const unlimited = limit < 0;
  const percent = unlimited ? 15 : Math.min(100, Math.round((used / Math.max(limit, 1)) * 100));
  return (
    <div>
      <div className="mb-1 flex justify-between text-[11px] text-slate-400">
        <span>{used.toLocaleString("fr")}</span>
        <span>{unlimited ? "illimite" : limit.toLocaleString("fr")}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div className={percent >= 100 ? "h-full rounded-full bg-red-500" : "h-full rounded-full bg-primary-500"} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export default function SuperAdminWorkspacePage() {
  const [operations, setOperations] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await admin.operations();
        if (!cancelled) setOperations(data);
      } catch (e: any) {
        if (!cancelled) setError(e.message || "Impossible de charger le cockpit exploitation.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const totals = operations?.totals || {};
  const organizations = operations?.organizations || [];
  const paidOrganizations = useMemo(
    () => organizations.filter((item: any) => item.plan_slug && item.plan_slug !== "free").length,
    [organizations],
  );

  return (
    <RoleGate
      allow={["admin"]}
      title="Espace super admin reserve"
      message="Cet espace pilote l'exploitation, les clients, les limites SaaS et les traces d'audit."
      backHref="/workspace"
    >
      <AppLayout>
        <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-primary-600">Espace super admin</p>
            <h1 className="mt-1 text-2xl font-bold text-slate-950">Cockpit exploitation SaaS</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Suivi clients, abonnements, usages, limites atteintes, audit trail, emails, RGPD et erreurs recentes.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link href="/admin" className="btn-secondary text-xs">
              <Gauge className="h-3.5 w-3.5" />
              Qualite donnees
            </Link>
            <Link href="/billing" className="btn-primary text-xs">
              <ShieldCheck className="h-3.5 w-3.5" />
              Plans SaaS
            </Link>
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center rounded-[28px] border border-slate-200 bg-white py-16 text-sm text-slate-400">
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            Chargement du cockpit exploitation...
          </div>
        )}

        {error && <div className="rounded-[24px] border border-red-200 bg-red-50 p-5 text-sm text-red-700">{error}</div>}

        {!loading && !error && operations && (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6">
              <KpiCard label="Organisations" value={(totals.organizations || 0).toLocaleString("fr")} sub={`${paidOrganizations} client(s) payant(s)`} tone="blue" />
              <KpiCard label="Utilisateurs" value={(totals.users || 0).toLocaleString("fr")} sub="Comptes actifs ou invites" tone="slate" />
              <KpiCard label="Abonnements" value={(totals.active_subscriptions || 0).toLocaleString("fr")} sub="Actifs, trialing ou past_due" tone="green" />
              <KpiCard label="Limites atteintes" value={(totals.limits_reached || 0).toLocaleString("fr")} sub="Clients a surveiller" tone={totals.limits_reached ? "amber" : "green"} />
              <KpiCard label="Demandes RGPD" value={(totals.pending_deletions || 0).toLocaleString("fr")} sub="Suppressions en attente" tone={totals.pending_deletions ? "red" : "slate"} />
              <KpiCard label="Erreurs recentes" value={(operations.recent_errors?.length || 0).toLocaleString("fr")} sub="Collectes failed/partial" tone={operations.recent_errors?.length ? "red" : "green"} />
            </div>

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[1.35fr_0.65fr]">
              <Panel title="Clients et usage" description="Plan actuel, statut abonnement et consommation des limites." icon={Building2}>
                <div className="overflow-hidden rounded-2xl border border-slate-200">
                  <div className="grid grid-cols-[1.2fr_0.7fr_1.4fr_0.6fr] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                    <span>Client</span>
                    <span>Plan</span>
                    <span>Usage</span>
                    <span>Etat</span>
                  </div>
                  <div className="divide-y divide-slate-100">
                    {organizations.length === 0 ? (
                      <p className="px-4 py-8 text-center text-sm text-slate-400">Aucune organisation client pour le moment.</p>
                    ) : (
                      organizations.map((org: any) => (
                        <div key={org.id} className="grid grid-cols-[1.2fr_0.7fr_1.4fr_0.6fr] gap-3 px-4 py-4 text-sm">
                          <div className="min-w-0">
                            <p className="truncate font-semibold text-slate-950">{org.name}</p>
                            <p className="text-xs text-slate-400">{org.slug}</p>
                          </div>
                          <div>
                            <span className="rounded-full bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-700">{org.plan}</span>
                            <p className="mt-1 text-xs text-slate-400">{org.subscription_status}</p>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            {Object.entries(org.usage || {}).map(([metric, used]: any) => (
                              <div key={metric}>
                                <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{METRIC_LABELS[metric] || metric}</p>
                                <UsageBar used={Number(used || 0)} limit={Number(org.limits?.[metric] ?? -1)} />
                              </div>
                            ))}
                          </div>
                          <div>
                            {org.limits_reached?.length ? (
                              <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">Limite</span>
                            ) : (
                              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">OK</span>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </Panel>

              <Panel title="Limites atteintes" description="Clients qui doivent etre contactes ou upsell." icon={AlertTriangle}>
                <div className="space-y-3">
                  {(operations.limits_reached || []).length === 0 ? (
                    <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-4 text-sm text-emerald-800">Aucune limite atteinte.</div>
                  ) : (
                    operations.limits_reached.map((entry: any) => (
                      <div key={entry.organization_id} className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3">
                        <p className="text-sm font-semibold text-amber-950">{entry.organization_name}</p>
                        <p className="mt-1 text-xs text-amber-800">
                          {entry.items.map((item: any) => `${METRIC_LABELS[item.metric] || item.metric}: ${item.used}/${item.limit}`).join(" · ")}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </Panel>
            </div>

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              <Panel title="Derniers audit logs" description="Trace des actions sensibles et administratives." icon={ShieldCheck}>
                <div className="space-y-2">
                  {(operations.audit_logs || []).slice(0, 8).map((item: any) => (
                    <div key={item.id} className="rounded-2xl border border-slate-100 bg-slate-50/70 px-4 py-3">
                      <p className="text-sm font-semibold text-slate-900">{item.action}</p>
                      <p className="mt-1 text-xs text-slate-500">{item.resource_type || "system"} · {formatDateRelative(item.created_at)}</p>
                    </div>
                  ))}
                  {operations.audit_logs?.length === 0 && <p className="py-6 text-center text-sm text-slate-400">Aucun audit log pour le moment.</p>}
                </div>
              </Panel>

              <Panel title="Emails transactionnels" description="Invitations, reset password, notifications et erreurs SMTP." icon={Mail}>
                <div className="space-y-2">
                  {(operations.email_events || []).slice(0, 8).map((item: any) => (
                    <div key={item.id} className="flex items-start gap-3 rounded-2xl border border-slate-100 px-4 py-3">
                      <span className={item.status === "sent" ? "mt-1 h-2.5 w-2.5 rounded-full bg-emerald-400" : "mt-1 h-2.5 w-2.5 rounded-full bg-amber-400"} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-slate-900">{item.subject}</p>
                        <p className="mt-1 text-xs text-slate-500">{item.email} · {item.template} · {formatDateRelative(item.created_at)}</p>
                        {item.error_message && <p className="mt-1 text-xs text-red-600">{item.error_message}</p>}
                      </div>
                    </div>
                  ))}
                  {operations.email_events?.length === 0 && <p className="py-6 text-center text-sm text-slate-400">Aucun email transactionnel journalise.</p>}
                </div>
              </Panel>

              <Panel title="Demandes RGPD" description="Suppressions et exports de donnees utilisateur." icon={Trash2}>
                <div className="space-y-2">
                  {(operations.deletion_requests || []).slice(0, 6).map((item: any) => (
                    <div key={item.id} className="rounded-2xl border border-red-100 bg-red-50/60 px-4 py-3">
                      <p className="text-sm font-semibold text-red-950">Suppression · {item.status}</p>
                      <p className="mt-1 text-xs text-red-700">
                        Creee {formatDateRelative(item.created_at)}
                        {item.scheduled_for ? ` · prevue ${formatDateRelative(item.scheduled_for)}` : ""}
                      </p>
                    </div>
                  ))}
                  {(operations.data_exports || []).slice(0, 4).map((item: any) => (
                    <div key={item.id} className="rounded-2xl border border-blue-100 bg-blue-50/60 px-4 py-3">
                      <p className="text-sm font-semibold text-blue-950">Export donnees · {item.status}</p>
                      <p className="mt-1 text-xs text-blue-700">Cree {formatDateRelative(item.created_at)}</p>
                    </div>
                  ))}
                  {operations.deletion_requests?.length === 0 && operations.data_exports?.length === 0 && (
                    <p className="py-6 text-center text-sm text-slate-400">Aucune demande RGPD recente.</p>
                  )}
                </div>
              </Panel>

              <Panel title="Erreurs recentes" description="Collectes echouees ou partielles a diagnostiquer." icon={Database}>
                <div className="space-y-2">
                  {(operations.recent_errors || []).slice(0, 8).map((item: any) => (
                    <Link key={item.id} href={`/sources/${item.source_id}`} className="block rounded-2xl border border-red-100 bg-red-50/70 px-4 py-3 transition-colors hover:bg-red-50">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-semibold text-red-950">{item.source_name}</p>
                          <p className="mt-1 text-xs text-red-700">{item.status} · {formatDateRelative(item.started_at)}</p>
                          {item.error_message && <p className="mt-1 line-clamp-2 text-xs text-red-600">{item.error_message}</p>}
                        </div>
                      </div>
                    </Link>
                  ))}
                  {operations.recent_errors?.length === 0 && (
                    <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-4 text-sm text-emerald-800">Aucune erreur recente.</div>
                  )}
                </div>
              </Panel>
            </div>
          </>
        )}
      </AppLayout>
    </RoleGate>
  );
}
