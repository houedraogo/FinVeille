"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { TrendingUp, Clock, AlertTriangle, CheckCircle, Database, RefreshCw, Flame, Zap, BadgeCheck, Sparkles, ArrowRight } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import MagicAnalysis from "@/components/MagicAnalysis";
import { dashboard } from "@/lib/api";
import { DashboardStats, DEVICE_TYPE_LABELS } from "@/lib/types";
import { formatDate, formatDateRelative, formatAmount, avgEffortFromTypes } from "@/lib/utils";

interface PriorityItem {
  icon: React.ElementType;
  text: string;
  href: string;
  color: string;
  bg: string;
}

function buildPriorities(stats: DashboardStats): PriorityItem[] {
  const items: PriorityItem[] = [];

  if (stats.closing_soon_7d > 0) {
    items.push({
      icon: Flame,
      text: `${stats.closing_soon_7d} opportunité${stats.closing_soon_7d > 1 ? "s" : ""} à traiter cette semaine`,
      href: "/devices?closing_soon_days=7",
      color: "text-red-600",
      bg: "bg-red-50",
    });
  }

  const soonest = stats.closing_soon[0];
  if (soonest && soonest.days_left <= 5) {
    items.push({
      icon: Clock,
      text: `1 deadline dans ${soonest.days_left} jour${soonest.days_left > 1 ? "s" : ""} — ${soonest.title.slice(0, 50)}${soonest.title.length > 50 ? "…" : ""}`,
      href: `/devices/${soonest.id}`,
      color: "text-orange-600",
      bg: "bg-orange-50",
    });
  }

  if (stats.new_last_7_days > 0) {
    items.push({
      icon: Zap,
      text: `${stats.new_last_7_days} financement${stats.new_last_7_days > 1 ? "s" : ""} très pertinent${stats.new_last_7_days > 1 ? "s" : ""} détecté${stats.new_last_7_days > 1 ? "s" : ""}`,
      href: "/devices?sort=first_seen_at&order=desc",
      color: "text-blue-600",
      bg: "bg-blue-50",
    });
  }

  if (stats.pending_validation > 0) {
    items.push({
      icon: AlertTriangle,
      text: `${stats.pending_validation} dossier${stats.pending_validation > 1 ? "s" : ""} à compléter`,
      href: "/devices?validation_status=pending",
      color: "text-yellow-600",
      bg: "bg-yellow-50",
    });
  }

  return items;
}

function PrioritiesBlock({ stats }: { stats: DashboardStats }) {
  const items = buildPriorities(stats);

  if (items.length === 0) {
    return (
      <div className="card p-4 mb-6 flex items-center gap-3 border-l-4 border-green-400">
        <BadgeCheck className="w-5 h-5 text-green-500 flex-shrink-0" />
        <p className="text-sm text-gray-700 font-medium">Tout est à jour — aucune action urgente aujourd'hui.</p>
      </div>
    );
  }

  return (
    <div className="card p-4 mb-6 border-l-4 border-primary-500">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-900">Priorités du jour</h2>
        <Link
          href="/devices?closing_soon_days=7"
          className="text-xs font-medium text-primary-600 hover:text-primary-700 hover:underline"
        >
          Voir mes actions →
        </Link>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {items.map((item, i) => {
          const Icon = item.icon;
          return (
            <Link
              key={i}
              href={item.href}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-gray-50 transition-colors group"
            >
              <div className={clsx("p-1.5 rounded-md flex-shrink-0", item.bg)}>
                <Icon className={clsx("w-4 h-4", item.color)} />
              </div>
              <span className="text-xs text-gray-700 group-hover:text-gray-900 transition-colors line-clamp-1">
                {item.text}
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function ROIBanner({ stats }: { stats: DashboardStats }) {
  const effort = avgEffortFromTypes(stats.by_type);
  const funding = stats.potential_funding ?? 0;
  const highRoi = stats.high_roi_count ?? 0;

  if (funding === 0 && highRoi === 0) return null;

  const fundingLabel = funding >= 1_000_000
    ? `${(funding / 1_000_000).toFixed(1)} M€`
    : funding >= 1_000
    ? `${Math.round(funding / 1_000)} k€`
    : `${Math.round(funding)} €`;

  return (
    <div className="relative overflow-hidden rounded-xl mb-6 bg-gradient-to-r from-primary-600 to-blue-500 p-5 text-white shadow-md">
      {/* Cercle décoratif */}
      <div className="pointer-events-none absolute -right-10 -top-10 w-48 h-48 rounded-full bg-white/10" />
      <div className="pointer-events-none absolute -right-4 bottom-4 w-24 h-24 rounded-full bg-white/5" />

      <p className="text-xs font-semibold uppercase tracking-widest text-primary-100 mb-3">
        Votre potentiel de financement identifié
      </p>

      <div className="grid grid-cols-3 gap-4">
        {/* Financement potentiel */}
        <div>
          <div className="text-2xl font-bold tracking-tight">{fundingLabel}</div>
          <div className="text-xs text-primary-100 mt-0.5">
            💰 Financements potentiels
          </div>
          <div className="text-[10px] text-primary-200 mt-1">
            Montant cumulé des aides ouvertes
          </div>
        </div>

        {/* Fort ROI */}
        <div>
          <div className="text-2xl font-bold tracking-tight">{highRoi}</div>
          <div className="text-xs text-primary-100 mt-0.5">
            📈 Opportunités à fort ROI
          </div>
          <div className="text-[10px] text-primary-200 mt-1">
            Confiance ≥ 70% · montant ≥ 50k€
          </div>
        </div>

        {/* Effort estimé */}
        <div>
          <div className="text-2xl font-bold tracking-tight">{effort}</div>
          <div className="text-xs text-primary-100 mt-0.5">
            ⏱ Effort moyen de montage
          </div>
          <div className="text-[10px] text-primary-200 mt-1">
            Par dossier, selon le type d'aide
          </div>
        </div>
      </div>

      <Link
        href="/devices?status=open&sort=amount_max"
        className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-white/90 hover:text-white underline underline-offset-2 transition-colors"
      >
        Voir toutes les opportunités →
      </Link>
    </div>
  );
}

const CHART_COLORS = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#84cc16", "#f97316"];

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showMagic, setShowMagic] = useState(false);

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
      {/* Hero "Analyser mon projet" */}
      <div className="relative overflow-hidden rounded-2xl mb-6 bg-gradient-to-r from-gray-950 via-primary-950 to-gray-950 p-6 shadow-xl">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_rgba(37,99,235,0.25)_0%,_transparent_60%)]" />
        <div className="pointer-events-none absolute -bottom-8 -right-8 w-56 h-56 rounded-full bg-primary-500/10" />

        <div className="relative flex items-center justify-between gap-6">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-primary-300" />
              <span className="text-xs font-semibold uppercase tracking-widest text-primary-300">
                Analyse IA
              </span>
            </div>
            <h2 className="text-lg font-bold text-white">Analyser mon projet</h2>
            <p className="mt-1 text-sm text-gray-400 max-w-sm">
              Shortlist personnalisée · Plan de financement · Priorisation automatique — en 30 secondes.
            </p>
            <div className="flex flex-wrap gap-2 mt-3">
              {["Shortlist intelligente", "Plan de financement", "Priorisation auto"].map((tag) => (
                <span key={tag} className="text-[10px] font-medium text-primary-300 bg-primary-900/60 border border-primary-700/50 px-2 py-0.5 rounded-full">
                  ✓ {tag}
                </span>
              ))}
            </div>
          </div>
          <button
            onClick={() => setShowMagic(true)}
            className="flex-shrink-0 flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-bold text-primary-700 shadow-lg hover:bg-primary-50 transition-colors group"
          >
            <Sparkles className="w-4 h-4" />
            Lancer l'analyse
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </button>
        </div>
      </div>

      {showMagic && <MagicAnalysis onClose={() => setShowMagic(false)} />}

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

      <ROIBanner stats={stats} />

      <PrioritiesBlock stats={stats} />

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
            <h2 className="text-sm font-semibold text-gray-700">Nouvelles aides détectées</h2>
            <Link href="/devices?sort=first_seen_at&order=desc" className="text-xs font-medium text-primary-600 hover:underline">
              Découvrir toutes les aides →
            </Link>
          </div>
          <div className="space-y-1">
            {stats.recent_devices.map((d: any) => (
              <div key={d.id} className="flex items-center gap-3 py-2 px-2 -mx-2 rounded-lg hover:bg-gray-50 group">
                <span className="badge bg-blue-50 text-blue-700 text-xs flex-shrink-0">
                  {DEVICE_TYPE_LABELS[d.device_type] || d.device_type}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-gray-900 line-clamp-1">{d.title}</p>
                  <p className="text-xs text-gray-400">{d.organism} · {d.country}</p>
                </div>
                <Link
                  href={`/devices/${d.id}`}
                  className="flex-shrink-0 rounded-lg bg-primary-50 px-2.5 py-1 text-[10px] font-semibold text-primary-700 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-primary-100"
                >
                  Analyser →
                </Link>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">Clôtures dans 7 jours</h2>
            <Link href="/devices?closing_soon_days=7" className="text-xs font-medium text-primary-600 hover:underline">
              Gérer mes priorités →
            </Link>
          </div>
          {stats.closing_soon.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-8">Aucune clôture imminente</p>
          ) : (
            <div className="space-y-1">
              {stats.closing_soon.map((d) => (
                <div key={d.id} className="flex items-center gap-3 py-2 px-2 -mx-2 rounded-lg hover:bg-gray-50 group">
                  <div
                    className={clsx(
                      "text-center rounded-lg px-2 py-1 flex-shrink-0 min-w-10",
                      d.days_left <= 3 ? "bg-red-50 text-red-700" : "bg-orange-50 text-orange-700"
                    )}
                  >
                    <div className="text-lg font-bold leading-none">{d.days_left}</div>
                    <div className="text-xs">jours</div>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-gray-900 line-clamp-1">{d.title}</p>
                    <p className="text-xs text-gray-400">{d.country} · {formatDate(d.close_date)}</p>
                  </div>
                  <Link
                    href={`/devices/${d.id}`}
                    className={clsx(
                      "flex-shrink-0 rounded-lg px-2.5 py-1 text-[10px] font-semibold opacity-0 transition-opacity group-hover:opacity-100",
                      d.days_left <= 3
                        ? "bg-red-50 text-red-700 hover:bg-red-100"
                        : "bg-orange-50 text-orange-700 hover:bg-orange-100"
                    )}
                  >
                    Prioriser →
                  </Link>
                </div>
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
