"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Bell, CreditCard, RefreshCw, ShieldCheck, Users } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import RoleGate from "@/components/RoleGate";
import { admin } from "@/lib/api";
import { formatDateRelative } from "@/lib/utils";

const METRIC_LABELS: Record<string, string> = {
  users: "Utilisateurs",
  alerts: "Alertes",
  saved_searches: "Recherches",
  pipeline_projects: "Suivi",
};

function UsageCard({ metric, used, limit }: { metric: string; used: number; limit: number }) {
  const unlimited = limit < 0;
  const percent = unlimited ? 15 : Math.min(100, Math.round((used / Math.max(limit, 1)) * 100));
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">{METRIC_LABELS[metric] || metric}</p>
      <p className="mt-2 text-xl font-semibold text-slate-950">{used.toLocaleString("fr")} <span className="text-sm text-slate-400">/ {unlimited ? "∞" : limit.toLocaleString("fr")}</span></p>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className={percent >= 100 ? "h-full rounded-full bg-red-500" : "h-full rounded-full bg-primary-500"} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export default function AdminClientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      setDetail(await admin.organizationOperations(id));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [id]);

  const org = detail?.organization;

  return (
    <RoleGate allow={["admin"]} title="Client reserve" message="Cette page est reservee au super admin." backHref="/admin/clients">
      <AppLayout>
        <div className="mb-6">
          <Link href="/admin/clients" className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-primary-700">
            <ArrowLeft className="h-4 w-4" />
            Retour aux clients
          </Link>
          {loading ? (
            <div className="flex items-center justify-center rounded-[28px] border border-slate-200 bg-white py-16 text-sm text-slate-400">
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              Chargement organisation...
            </div>
          ) : !org ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">Organisation introuvable.</div>
          ) : (
            <>
              <div className="mb-6 overflow-hidden rounded-[34px] border border-slate-200 bg-[radial-gradient(circle_at_top_left,#dbeafe,transparent_34%),linear-gradient(135deg,#ffffff_0%,#f8fafc_54%,#eef2ff_100%)] p-6">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                  <div>
                    <p className="text-sm font-medium text-primary-600">Detail organisation</p>
                    <h1 className="mt-1 text-3xl font-bold text-slate-950">{org.name}</h1>
                    <p className="mt-2 text-sm text-slate-500">{org.slug} · creee {formatDateRelative(org.created_at)}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link href="/admin/billing" className="btn-secondary text-xs">
                      <CreditCard className="h-3.5 w-3.5" />
                      Abonnements
                    </Link>
                    <Link href="/admin/data-quality" className="btn-secondary text-xs">
                      <ShieldCheck className="h-3.5 w-3.5" />
                      Logs / qualite
                    </Link>
                  </div>
                </div>
              </div>

              <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-[24px] border border-primary-100 bg-primary-50 p-5">
                  <CreditCard className="h-5 w-5 text-primary-700" />
                  <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-primary-700">Plan</p>
                  <p className="mt-1 text-2xl font-semibold text-primary-950">{org.plan}</p>
                  <p className="mt-1 text-sm text-primary-700">{org.subscription_status}</p>
                </div>
                <div className="rounded-[24px] border border-slate-200 bg-white p-5">
                  <Users className="h-5 w-5 text-slate-700" />
                  <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Membres</p>
                  <p className="mt-1 text-2xl font-semibold text-slate-950">{detail.members.length}</p>
                </div>
                <div className="rounded-[24px] border border-emerald-100 bg-emerald-50 p-5">
                  <Bell className="h-5 w-5 text-emerald-700" />
                  <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Alertes</p>
                  <p className="mt-1 text-2xl font-semibold text-emerald-950">{org.usage.alerts || 0}</p>
                </div>
                <div className="rounded-[24px] border border-slate-200 bg-white p-5">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Stripe</p>
                  <p className="mt-3 truncate text-sm font-medium text-slate-800">{org.stripe_customer_id || "Aucun customer"}</p>
                  <p className="mt-1 truncate text-xs text-slate-400">{org.stripe_subscription_id || "Aucune subscription"}</p>
                </div>
              </div>

              <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-4">
                {Object.entries(org.usage || {}).map(([metric, used]: any) => (
                  <UsageCard key={metric} metric={metric} used={Number(used || 0)} limit={Number(org.limits?.[metric] ?? -1)} />
                ))}
              </div>

              <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                <section className="rounded-[28px] border border-slate-200 bg-white p-5">
                  <h2 className="text-lg font-semibold text-slate-950">Membres</h2>
                  <div className="mt-4 divide-y divide-slate-100">
                    {detail.members.map((member: any) => (
                      <div key={member.id} className="flex items-center justify-between gap-3 py-3">
                        <div className="min-w-0">
                          <p className="truncate font-medium text-slate-900">{member.full_name || member.email}</p>
                          <p className="truncate text-xs text-slate-400">{member.email} · {member.role}</p>
                        </div>
                        <span className={member.is_active ? "rounded-full bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700" : "rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500"}>
                          {member.is_active ? "Actif" : "Inactif"}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="rounded-[28px] border border-slate-200 bg-white p-5">
                  <h2 className="text-lg font-semibold text-slate-950">Alertes creees</h2>
                  <div className="mt-4 space-y-2">
                    {detail.alerts.length === 0 ? (
                      <p className="rounded-2xl border border-dashed border-slate-200 py-8 text-center text-sm text-slate-400">Aucune veille active.</p>
                    ) : (
                      detail.alerts.map((alert: any) => (
                        <div key={alert.id} className="rounded-2xl border border-slate-100 px-4 py-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate font-medium text-slate-900">{alert.name}</p>
                              <p className="mt-1 text-xs text-slate-400">{alert.owner_email} · {alert.frequency}</p>
                            </div>
                            <span className={alert.is_active ? "rounded-full bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700" : "rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500"}>
                              {alert.is_active ? "Active" : "Inactive"}
                            </span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </section>

                <section className="rounded-[28px] border border-slate-200 bg-white p-5">
                  <h2 className="text-lg font-semibold text-slate-950">Activite usage</h2>
                  <div className="mt-4 space-y-2">
                    {detail.usage_events.length === 0 ? (
                      <p className="rounded-2xl border border-dashed border-slate-200 py-8 text-center text-sm text-slate-400">Aucun evenement usage.</p>
                    ) : (
                      detail.usage_events.map((event: any) => (
                        <div key={event.id} className="rounded-2xl border border-slate-100 px-4 py-3">
                          <p className="font-medium text-slate-900">{event.event_type}</p>
                          <p className="mt-1 text-xs text-slate-400">{event.quantity} · {formatDateRelative(event.created_at)}</p>
                        </div>
                      ))
                    )}
                  </div>
                </section>

                <section className="rounded-[28px] border border-slate-200 bg-white p-5">
                  <h2 className="text-lg font-semibold text-slate-950">Audit logs</h2>
                  <div className="mt-4 space-y-2">
                    {detail.audit_logs.length === 0 ? (
                      <p className="rounded-2xl border border-dashed border-slate-200 py-8 text-center text-sm text-slate-400">Aucun audit log.</p>
                    ) : (
                      detail.audit_logs.map((log: any) => (
                        <div key={log.id} className="rounded-2xl border border-slate-100 px-4 py-3">
                          <p className="font-medium text-slate-900">{log.action}</p>
                          <p className="mt-1 text-xs text-slate-400">{log.resource_type || "system"} · {formatDateRelative(log.created_at)}</p>
                        </div>
                      ))
                    )}
                  </div>
                </section>
              </div>
            </>
          )}
        </div>
      </AppLayout>
    </RoleGate>
  );
}
