"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { TrendingUp, Clock, AlertTriangle, CheckCircle, Database, RefreshCw, Flame, ArrowRight } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { dashboard, relevance } from "@/lib/api";
import { DashboardStats, DEVICE_TYPE_LABELS, RecommendationItem } from "@/lib/types";
import { formatDateRelative } from "@/lib/utils";
import {
  listPipelineDevices,
  syncWorkspace,
  type DevicePipelineEntry,
  type DevicePipelineStatus,
} from "@/lib/workspace";

const CHART_COLORS = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#84cc16", "#f97316"];

const PIPELINE_STATUS_ORDER: Record<DevicePipelineStatus, number> = {
  candidature_en_cours: 0,
  interessant: 1,
  a_etudier: 2,
  soumis: 3,
  refuse: 4,
  non_pertinent: 5,
};

const PIPELINE_STATUS_LABELS: Record<DevicePipelineStatus, string> = {
  a_etudier: "À étudier",
  interessant: "Prioritaire",
  candidature_en_cours: "En cours",
  soumis: "Soumis",
  refuse: "Refusé",
  non_pertinent: "Non pertinent",
};

const PIPELINE_STATUS_COLORS: Record<DevicePipelineStatus, string> = {
  a_etudier: "bg-amber-100 text-amber-700",
  interessant: "bg-violet-100 text-violet-700",
  candidature_en_cours: "bg-blue-100 text-blue-700",
  soumis: "bg-indigo-100 text-indigo-700",
  refuse: "bg-red-100 text-red-700",
  non_pertinent: "bg-slate-100 text-slate-600",
};

const PRIORITY_ORDER = { haute: 0, moyenne: 1, faible: 2 };

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [pipelineDevices, setPipelineDevices] = useState<DevicePipelineEntry[]>([]);

  useEffect(() => {
    dashboard.get()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));

    relevance.recommendations({ page_size: 4 })
      .then((data) => setRecommendations(Array.isArray(data?.items) ? data.items : []))
      .catch(() => setRecommendations([]));

    // Sync workspace to get pipeline for "Tes 3 priorités"
    syncWorkspace()
      .catch(() => false)
      .finally(() => setPipelineDevices(listPipelineDevices()));
  }, []);

  // Top 3 priorities: active statuses only, sorted by (status urgency, priority, deadline proximity)
  const topPriorities = useMemo(() => {
    const now = Date.now();
    return [...pipelineDevices]
      .filter((d) => !["refuse", "non_pertinent", "soumis"].includes(d.pipelineStatus))
      .sort((a, b) => {
        // 1. Status urgency
        const statusDiff =
          (PIPELINE_STATUS_ORDER[a.pipelineStatus] ?? 9) -
          (PIPELINE_STATUS_ORDER[b.pipelineStatus] ?? 9);
        if (statusDiff !== 0) return statusDiff;
        // 2. Priority (haute > moyenne > faible)
        const priorityDiff =
          (PRIORITY_ORDER[a.priority] ?? 9) -
          (PRIORITY_ORDER[b.priority] ?? 9);
        if (priorityDiff !== 0) return priorityDiff;
        // 3. Closest deadline first
        const aDeadline = a.closeDate ? new Date(a.closeDate).getTime() : Infinity;
        const bDeadline = b.closeDate ? new Date(b.closeDate).getTime() : Infinity;
        return aDeadline - bDeadline;
      })
      .slice(0, 3);
  }, [pipelineDevices]);

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
      label: "Opportunités actives",
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

  const smartHighlights = [
    stats.last_collection.items_new > 0
      ? {
          title: `Bonne nouvelle : ${stats.last_collection.items_new} nouvelles opportunités détectées`,
          detail: "Passe-les en revue maintenant pour ne pas laisser filer les plus pertinentes.",
          icon: TrendingUp,
          className: "border-emerald-200 bg-emerald-50 text-emerald-800",
        }
      : {
          title: "Astuce : garde ta veille active",
          detail: "Plus tes sources tournent régulièrement, plus Kafundo repère vite les bons financements.",
          icon: CheckCircle,
          className: "border-slate-200 bg-slate-50 text-slate-700",
        },
    stats.closing_soon_7d > 0
      ? {
          title: `Attention : ${stats.closing_soon_7d} deadline(s) proche(s)`,
          detail: "Priorise ces opportunités cette semaine avant d'explorer de nouvelles pistes.",
          icon: Clock,
          className: "border-orange-200 bg-orange-50 text-orange-800",
        }
      : {
          title: "Aucune urgence cette semaine",
          detail: "Profite-en pour enrichir ton suivi et préparer les prochaines candidatures.",
          icon: Clock,
          className: "border-blue-200 bg-blue-50 text-blue-800",
        },
    stats.pending_validation > 0
      ? {
          title: `Conseil : ${stats.pending_validation} opportunité(s) à vérifier`,
          detail: "Les fiches à valider peuvent cacher de bonnes pistes, mais demande une confirmation avant décision.",
          icon: AlertTriangle,
          className: "border-amber-200 bg-amber-50 text-amber-800",
        }
      : {
          title: "Catalogue propre",
          detail: "Les opportunités publiées sont mieux qualifiées et plus faciles à exploiter.",
          icon: CheckCircle,
          className: "border-emerald-200 bg-emerald-50 text-emerald-800",
      },
  ];

  const weeklyActionItems = [
    ...topPriorities.map((device) => ({
      id: `pipeline-${device.id}`,
      href: `/devices/${device.id}`,
      title: device.title,
      meta: `${PIPELINE_STATUS_LABELS[device.pipelineStatus]}${device.closeDate ? ` · ${formatDateRelative(device.closeDate)}` : ""}`,
      tone: device.closeDate ? "bg-orange-50 text-orange-700" : "bg-primary-50 text-primary-700",
      badge: device.closeDate ? "À traiter" : "À suivre",
    })),
    ...recommendations.slice(0, Math.max(0, 4 - topPriorities.length)).map((item) => ({
      id: `recommendation-${item.device.id}`,
      href: `/devices/${item.device.id}?from=recommendations`,
      title: item.device.title,
      meta: item.relevance.relevance_label,
      tone: "bg-emerald-50 text-emerald-700",
      badge: "Recommandée",
    })),
  ].slice(0, 4);

  const marketSignals = [
    {
      label: "Pays les plus actifs",
      value: stats.by_country.slice(0, 3).map((item) => item.country).join(" · ") || "À préciser",
      helper: "Zones où le volume d'opportunités est actuellement le plus fort.",
    },
    {
      label: "Formats les plus présents",
      value: stats.by_type
        .slice(0, 3)
        .map((item) => DEVICE_TYPE_LABELS[item.type] || item.type)
        .join(" · ") || "À préciser",
      helper: "Types de financement les plus visibles dans la veille récente.",
    },
    {
      label: "Rythme de détection",
      value: stats.new_last_7_days > 0
        ? `${stats.new_last_7_days} nouvelle${stats.new_last_7_days > 1 ? "s" : ""} opportunité${stats.new_last_7_days > 1 ? "s" : ""} en 7 jours`
        : "Aucune nouveauté récente",
      helper: "Pour savoir si la veille accélère ou si elle mérite d'être élargie.",
    },
    {
      label: "Pression calendrier",
      value: stats.closing_soon_30d > 0
        ? `${stats.closing_soon_30d} clôture${stats.closing_soon_30d > 1 ? "s" : ""} dans 30 jours`
        : "Aucune échéance proche",
      helper: "Un bon repère pour arbitrer entre exploration et exécution.",
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
            {stats.last_collection.items_new > 0 && ` - ${stats.last_collection.items_new} nouvelles opportunités`}
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

      <div className="mb-6 grid grid-cols-1 gap-3 lg:grid-cols-3">
        {smartHighlights.map(({ title, detail, icon: Icon, className }) => (
          <div key={title} className={clsx("rounded-2xl border px-4 py-3", className)}>
            <div className="flex items-start gap-3">
              <Icon className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="text-sm font-semibold">{title}</p>
                <p className="mt-1 text-xs leading-5 opacity-85">{detail}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Tes 3 priorités du moment ── */}
      {topPriorities.length > 0 && (
        <div className="mb-6">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Flame className="h-4 w-4 text-orange-500" />
              <h2 className="text-sm font-semibold text-gray-900">Tes 3 priorités du moment</h2>
            </div>
            <Link href="/workspace" className="text-xs text-primary-600 hover:underline">
              Voir tout le pipeline
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {topPriorities.map((device, idx) => {
              const now = Date.now();
              const deadline = device.closeDate ? new Date(device.closeDate).getTime() : null;
              const daysLeft = deadline ? Math.ceil((deadline - now) / (1000 * 60 * 60 * 24)) : null;
              const urgent = daysLeft !== null && daysLeft <= 14;
              return (
                <Link
                  key={device.id}
                  href={`/devices/${device.id}`}
                  className={clsx(
                    "group block rounded-2xl border px-4 py-4 transition-colors hover:border-primary-200 hover:bg-primary-50/40",
                    urgent ? "border-orange-200 bg-orange-50/50" : "border-slate-200 bg-white"
                  )}
                >
                  <div className="mb-2 flex items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-bold text-primary-700">
                      {idx + 1}
                    </span>
                    <span className={clsx(
                      "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                      PIPELINE_STATUS_COLORS[device.pipelineStatus]
                    )}>
                      {PIPELINE_STATUS_LABELS[device.pipelineStatus]}
                    </span>
                    {urgent && daysLeft !== null && (
                      <span className="ml-auto shrink-0 rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-semibold text-orange-700">
                        ⚡ J-{daysLeft}
                      </span>
                    )}
                  </div>
                  <p className="line-clamp-2 text-sm font-semibold text-slate-900 group-hover:text-primary-700">
                    {device.title}
                  </p>
                  <p className="mt-1 line-clamp-1 text-xs text-slate-500">
                    {device.organism} · {device.country}
                  </p>
                  {device.note && (
                    <p className="mt-2 line-clamp-1 text-xs italic text-slate-400">"{device.note}"</p>
                  )}
                  <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                    {device.closeDate && !urgent ? (
                      <span>{formatDateRelative(device.closeDate)}</span>
                    ) : <span />}
                    <ArrowRight className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

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
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">Recommandées pour vous</h2>
            <Link href="/recommendations" className="text-xs text-primary-600 hover:underline">
              Voir plus
            </Link>
          </div>
          {recommendations.length === 0 ? (
            <p className="py-8 text-center text-xs text-gray-400">
              Complète ton profil pour afficher des opportunités plus ciblées.
            </p>
          ) : (
            <div className="space-y-3">
              {recommendations.map((item) => (
                <Link
                  key={item.device.id}
                  href={`/devices/${item.device.id}`}
                  className="block rounded-2xl border border-slate-200 px-4 py-3 transition-colors hover:border-primary-200 hover:bg-primary-50/40"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="line-clamp-2 text-sm font-semibold text-slate-900">{item.device.title}</p>
                      <p className="mt-1 text-xs text-slate-500">{item.device.organism} · {item.device.country}</p>
                    </div>
                    <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                      {item.relevance.priority_level}
                    </span>
                  </div>
                  <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] text-primary-600">
                    {item.relevance.relevance_label}
                  </p>
                  {item.relevance.reason_texts?.length ? (
                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      {item.relevance.reason_texts.slice(0, 2).join(" ")}
                    </p>
                  ) : null}
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="card p-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Repartition par pays</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stats.by_country.slice(0, 8)} layout="vertical" margin={{ left: 60 }}>
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="country" tick={{ fontSize: 11 }} width={60} />
              <Tooltip formatter={(v) => [v, "Opportunités"]} />
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
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-700">À lancer cette semaine</h2>
              <p className="mt-1 text-xs text-gray-400">
                Les opportunités sur lesquelles tu peux agir tout de suite.
              </p>
            </div>
            <Link href="/workspace" className="text-xs text-primary-600 hover:underline">
              Voir mon suivi
            </Link>
          </div>
          {weeklyActionItems.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
              <p className="text-sm font-medium text-slate-700">Ton espace est encore vide</p>
              <p className="mt-1 text-sm text-slate-500">
                Ajoute des favoris, crée une veille ou complète ton profil pour faire remonter des priorités utiles.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {weeklyActionItems.map((item) => (
                <Link
                  key={item.id}
                  href={item.href}
                  className="flex items-start gap-3 rounded-2xl border border-slate-200 px-3 py-3 transition-colors hover:border-primary-200 hover:bg-primary-50/40"
                >
                  <span className={clsx("rounded-full px-2.5 py-1 text-[10px] font-semibold", item.tone)}>
                    {item.badge}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-sm font-medium text-slate-900">{item.title}</p>
                    <p className="mt-1 text-xs text-slate-500">{item.meta}</p>
                  </div>
                  <ArrowRight className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-300" />
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="card p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-700">Où concentrer ta veille</h2>
              <p className="mt-1 text-xs text-gray-400">
                Une lecture simple du marché pour décider plus vite.
              </p>
            </div>
            <Link href="/devices" className="text-xs text-primary-600 hover:underline">
              Explorer les opportunités
            </Link>
          </div>
          <div className="space-y-3">
            {marketSignals.map((signal) => (
              <div key={signal.label} className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                  {signal.label}
                </p>
                <p className="mt-1 text-sm font-semibold text-slate-900">{signal.value}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">{signal.helper}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
