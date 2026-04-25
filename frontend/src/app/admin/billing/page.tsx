"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CreditCard, RefreshCw, TrendingDown, TrendingUp, Users } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import RoleGate from "@/components/RoleGate";
import { admin } from "@/lib/api";
import { formatDateRelative } from "@/lib/utils";

function money(value: number) {
  return `${value.toLocaleString("fr")} EUR`;
}

export default function AdminBillingPage() {
  const [operations, setOperations] = useState<any>(null);
  const [loading, setLoading] = useState(true);

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

  const subscribers = operations?.subscribers || [];
  const stats = useMemo(() => {
    const mrr = subscribers.reduce((sum: number, item: any) => sum + Number(item.price_monthly_eur || 0), 0);
    return {
      mrr,
      active: subscribers.filter((item: any) => item.subscription_status === "active").length,
      trialing: subscribers.filter((item: any) => item.subscription_status === "trialing").length,
      pastDue: subscribers.filter((item: any) => item.subscription_status === "past_due").length,
      churn: subscribers.filter((item: any) => ["canceled", "unpaid"].includes(item.subscription_status)).length,
      byPlan: subscribers.reduce((acc: Record<string, number>, item: any) => {
        acc[item.plan] = (acc[item.plan] || 0) + 1;
        return acc;
      }, {}),
    };
  }, [subscribers]);

  return (
    <RoleGate allow={["admin"]} title="Abonnements reserve" message="Cette page est reservee au super admin." backHref="/admin/workspace">
      <AppLayout>
        <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-primary-600">Super admin</p>
            <h1 className="mt-1 text-2xl font-bold text-slate-950">Abonnements</h1>
            <p className="mt-2 text-sm text-slate-500">MRR, plans actifs, essais, past_due et churn.</p>
          </div>
          <button onClick={load} disabled={loading} className="btn-secondary text-xs">
            <RefreshCw className={loading ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />
            Actualiser
          </button>
        </div>

        <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-[24px] border border-emerald-200 bg-emerald-50 p-5">
            <TrendingUp className="h-5 w-5 text-emerald-700" />
            <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">MRR</p>
            <p className="mt-1 text-2xl font-semibold text-emerald-950">{money(stats.mrr)}</p>
          </div>
          <div className="rounded-[24px] border border-blue-200 bg-blue-50 p-5">
            <Users className="h-5 w-5 text-blue-700" />
            <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-blue-700">Actifs</p>
            <p className="mt-1 text-2xl font-semibold text-blue-950">{stats.active}</p>
          </div>
          <div className="rounded-[24px] border border-violet-200 bg-violet-50 p-5">
            <CreditCard className="h-5 w-5 text-violet-700" />
            <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-violet-700">Essais</p>
            <p className="mt-1 text-2xl font-semibold text-violet-950">{stats.trialing}</p>
          </div>
          <div className="rounded-[24px] border border-amber-200 bg-amber-50 p-5">
            <AlertTriangle className="h-5 w-5 text-amber-700" />
            <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-amber-700">Past due</p>
            <p className="mt-1 text-2xl font-semibold text-amber-950">{stats.pastDue}</p>
          </div>
          <div className="rounded-[24px] border border-red-200 bg-red-50 p-5">
            <TrendingDown className="h-5 w-5 text-red-700" />
            <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-red-700">Churn</p>
            <p className="mt-1 text-2xl font-semibold text-red-950">{stats.churn}</p>
          </div>
        </div>

        <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[0.8fr_1.2fr]">
          <section className="rounded-[28px] border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-slate-950">Plans actifs</h2>
            <div className="mt-4 space-y-3">
              {Object.entries(stats.byPlan).length === 0 ? (
                <p className="rounded-2xl border border-dashed border-slate-200 py-8 text-center text-sm text-slate-400">Aucun abonnement payant.</p>
              ) : (
                Object.entries(stats.byPlan).map(([plan, count]) => (
                  <div key={plan} className="flex items-center justify-between rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
                    <span className="font-medium text-slate-900">{plan}</span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-slate-600">{String(count)}</span>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-5 py-4">
              <h2 className="text-lg font-semibold text-slate-950">Abonnements clients</h2>
              <p className="text-sm text-slate-500">Suivi Stripe et renouvellements.</p>
            </div>
            {loading ? (
              <div className="flex items-center justify-center py-14 text-sm text-slate-400">
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Chargement abonnements...
              </div>
            ) : subscribers.length === 0 ? (
              <p className="py-12 text-center text-sm text-slate-400">Aucun abonnement payant pour le moment.</p>
            ) : (
              <div className="divide-y divide-slate-100">
                {subscribers.map((item: any) => (
                  <div key={item.organization_id} className="grid grid-cols-[1.2fr_0.7fr_0.7fr_1fr_0.6fr] gap-3 px-5 py-4 text-sm">
                    <Link href={`/admin/clients/${item.organization_id}`} className="min-w-0">
                      <p className="truncate font-semibold text-slate-950 hover:text-primary-700">{item.organization_name}</p>
                      <p className="truncate text-xs text-slate-400">{item.billing_email || item.owners?.[0]?.email || "Email absent"}</p>
                    </Link>
                    <div>
                      <span className="rounded-full bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-700">{item.plan}</span>
                      <p className="mt-1 text-xs text-slate-400">{money(Number(item.price_monthly_eur || 0))}/mois</p>
                    </div>
                    <span className={item.subscription_status === "active" ? "text-emerald-700" : item.subscription_status === "past_due" ? "text-amber-700" : "text-slate-600"}>
                      {item.subscription_status}
                    </span>
                    <p className="truncate text-xs text-slate-500">{item.stripe_subscription_id || "Sans subscription id"}</p>
                    <p className="text-xs text-slate-500">{item.current_period_end ? formatDateRelative(item.current_period_end) : "N/A"}</p>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </AppLayout>
    </RoleGate>
  );
}
