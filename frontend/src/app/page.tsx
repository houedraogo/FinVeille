"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { TrendingUp, Clock, AlertTriangle, CheckCircle, Database, RefreshCw } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { dashboard } from "@/lib/api";
import { DashboardStats, DEVICE_TYPE_LABELS } from "@/lib/types";
import { formatDate, formatDateRelative } from "@/lib/utils";

const CHART_COLORS = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#84cc16", "#f97316"];

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboard.get()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
        </div>
      </AppLayout>
    );
  }

  if (!stats) {
    return (
      <AppLayout>
        <div className="text-center py-20 text-gray-400">Impossible de charger le dashboard</div>
      </AppLayout>
    );
  }

  const kpis = [
    {
      label: "Dispositifs actifs",
      value: stats.total_active.toLocaleString("fr"),
      sub: `${stats.total} au total`,
      icon: CheckCircle,
      color: "text-green-600",
      bg: "bg-green-50",
    },
    {
      label: "Nouveaux (7 jours)",
      value: stats.new_last_7_days.toLocaleString("fr"),
      sub: "ajoutes recemment",
      icon: TrendingUp,
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
    {
      label: "Cloturent dans 30j",
      value: stats.closing_soon_30d.toLocaleString("fr"),
      sub: `dont ${stats.closing_soon_7d} dans 7j`,
      icon: Clock,
      color: "text-orange-600",
      bg: "bg-orange-50",
    },
    {
      label: "En attente validation",
      value: stats.pending_validation.toLocaleString("fr"),
      sub: `confiance moy. ${stats.avg_confidence}%`,
      icon: AlertTriangle,
      color: "text-yellow-600",
      bg: "bg-yellow-50",
    },
  ];

  return (
    <AppLayout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {stats.last_collection.at
              ? `Derniere collecte ${formatDateRelative(stats.last_collection.at)}`
              : "Aucune collecte effectuee"}
            {stats.last_collection.items_new > 0 && ` - ${stats.last_collection.items_new} nouveaux dispositifs`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={clsx(
            "badge text-xs",
            stats.sources.in_error > 0 ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
          )}>
            <Database className="w-3 h-3 mr-1" />
            {stats.sources.active} sources actives
            {stats.sources.in_error > 0 && ` · ${stats.sources.in_error} en erreur`}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {kpis.map(({ label, value, sub, icon: Icon, color, bg }) => (
          <div key={label} className="card p-4">
            <div className="flex items-center gap-3">
              <div className={clsx("p-2 rounded-lg", bg)}>
                <Icon className={clsx("w-5 h-5", color)} />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">{value}</div>
                <div className="text-xs font-medium text-gray-500">{label}</div>
                <div className="text-xs text-gray-400">{sub}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div className="card p-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Repartition par pays</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stats.by_country.slice(0, 8)} layout="vertical" margin={{ left: 60 }}>
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="country" tick={{ fontSize: 11 }} width={60} />
              <Tooltip formatter={(v) => [v, "Dispositifs"]} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {stats.by_country.slice(0, 8).map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Repartition par type d'aide</h2>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width="50%" height={200}>
              <PieChart>
                <Pie data={stats.by_type} dataKey="count" nameKey="type" cx="50%" cy="50%" outerRadius={80} innerRadius={40}>
                  {stats.by_type.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v, _, p) => [v, DEVICE_TYPE_LABELS[p.payload.type] || p.payload.type]} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-1.5">
              {stats.by_type.slice(0, 6).map((item, i) => (
                <div key={item.type} className="flex items-center gap-2 text-xs">
                  <div
                    className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                    style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                  />
                  <span className="text-gray-600 truncate">{DEVICE_TYPE_LABELS[item.type] || item.type}</span>
                  <span className="ml-auto font-medium text-gray-900">{item.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">Derniers dispositifs</h2>
            <Link href="/devices" className="text-xs text-primary-600 hover:underline">Voir tout</Link>
          </div>
          <div className="space-y-2">
            {stats.recent_devices.map((d: any) => (
              <Link
                key={d.id}
                href={`/devices/${d.id}`}
                className="flex items-start gap-3 py-2 hover:bg-gray-50 rounded-lg px-2 -mx-2 transition-colors"
              >
                <span className="badge bg-blue-50 text-blue-700 text-xs mt-0.5 flex-shrink-0">
                  {DEVICE_TYPE_LABELS[d.device_type] || d.device_type}
                </span>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-gray-900 line-clamp-1">{d.title}</p>
                  <p className="text-xs text-gray-400">{d.organism} · {d.country}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">Clotures dans 7 jours</h2>
            <Link href="/devices?closing_soon_days=7" className="text-xs text-primary-600 hover:underline">
              Voir tout
            </Link>
          </div>
          {stats.closing_soon.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-8">Aucune cloture imminente</p>
          ) : (
            <div className="space-y-2">
              {stats.closing_soon.map((d) => (
                <Link
                  key={d.id}
                  href={`/devices/${d.id}`}
                  className="flex items-center gap-3 py-2 hover:bg-gray-50 rounded-lg px-2 -mx-2 transition-colors"
                >
                  <div
                    className={clsx(
                      "text-center rounded-lg px-2 py-1 flex-shrink-0 min-w-10",
                      d.days_left <= 3 ? "bg-red-50 text-red-700" : "bg-orange-50 text-orange-700"
                    )}
                  >
                    <div className="text-lg font-bold leading-none">{d.days_left}</div>
                    <div className="text-xs">jours</div>
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-gray-900 line-clamp-1">{d.title}</p>
                    <p className="text-xs text-gray-400">{d.country} · {formatDate(d.close_date)}</p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="card p-4 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">Sources en erreur</h2>
            <Link href="/sources" className="text-xs text-primary-600 hover:underline">Voir les sources</Link>
          </div>
          {stats.sources.errors.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-8">Aucune source en erreur</p>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
              {stats.sources.errors.map((source) => (
                <Link
                  key={source.id}
                  href={`/sources/${source.id}`}
                  className="block rounded-lg px-3 py-3 hover:bg-gray-50 transition-colors border border-gray-100"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 line-clamp-1">{source.name}</p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {source.country} · {source.consecutive_errors} erreur{source.consecutive_errors > 1 ? "s" : ""}
                        {source.last_checked_at && ` · ${formatDateRelative(source.last_checked_at)}`}
                      </p>
                      <p className="text-xs text-red-600 mt-2 line-clamp-2">
                        {source.last_error || "Aucun detail disponible"}
                      </p>
                    </div>
                    <span
                      className={clsx(
                        "badge text-[10px] flex-shrink-0",
                        source.is_active ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-600"
                      )}
                    >
                      {source.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
