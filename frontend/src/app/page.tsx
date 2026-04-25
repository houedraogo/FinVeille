"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie,
} from "recharts";
import {
  TrendingUp, Clock, AlertTriangle, CheckCircle, Database,
  RefreshCw, Flame, ArrowRight, Globe, Sparkles, Building2,
  Users, LayoutGrid,
} from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { dashboard, relevance } from "@/lib/api";
import { DEVICE_TYPE_LABELS, RecommendationItem } from "@/lib/types";
import { formatDateRelative } from "@/lib/utils";
import {
  listPipelineDevices, syncWorkspace,
  type DevicePipelineEntry, type DevicePipelineStatus,
} from "@/lib/workspace";

// ── Palettes ─────────────────────────────────────────────────────────────────

const CHART_COLORS = [
  "#2563eb", "#10b981", "#f59e0b", "#ef4444",
  "#8b5cf6", "#06b6d4", "#84cc16", "#f97316",
];

const PIPELINE_STATUS_ORDER: Record<DevicePipelineStatus, number> = {
  candidature_en_cours: 0, interessant: 1, a_etudier: 2,
  soumis: 3, refuse: 4, non_pertinent: 5,
};
const PIPELINE_STATUS_LABELS: Record<DevicePipelineStatus, string> = {
  a_etudier: "À étudier", interessant: "Prioritaire",
  candidature_en_cours: "En cours", soumis: "Soumis",
  refuse: "Refusé", non_pertinent: "Non pertinent",
};
const PIPELINE_STATUS_COLORS: Record<DevicePipelineStatus, string> = {
  a_etudier: "bg-amber-100 text-amber-700",
  interessant: "bg-violet-100 text-violet-700",
  candidature_en_cours: "bg-blue-100 text-blue-700",
  soumis: "bg-indigo-100 text-indigo-700",
  refuse: "bg-red-100 text-red-700",
  non_pertinent: "bg-slate-100 text-slate-600",
};
const PRIORITY_ORDER: Record<string, number> = { haute: 0, moyenne: 1, faible: 2 };

// ── Scope config ──────────────────────────────────────────────────────────────

type FinancingScope = "public" | "private" | "both" | null;

const SCOPE_CONFIG = {
  private: {
    heroGradient: "from-violet-950 via-violet-900 to-indigo-700",
    heroBadgeBg: "bg-violet-500/20",
    heroBadgeText: "text-violet-200",
    badgeLabel: "Financement Privé",
    heroTitle: "Prospection Investisseurs",
    heroSubtitle:
      "Suivez les fonds d'investissement, business angels et investisseurs actifs dans vos zones prioritaires.",
    catalogHref: "/devices/private",
    catalogLabel: "Explorer les fonds",
    kpis: (s: any, pipeline: DevicePipelineEntry[]) => [
      {
        label: "Fonds & investisseurs actifs",
        value: s.total_active.toLocaleString("fr"),
        sub: `${s.total} au total`,
        icon: TrendingUp,
        color: "text-violet-600",
        bg: "bg-violet-50",
      },
      {
        label: "Nouveaux cette semaine",
        value: s.new_last_7_days.toLocaleString("fr"),
        sub: "détectés récemment",
        icon: Sparkles,
        color: "text-indigo-600",
        bg: "bg-indigo-50",
      },
      {
        label: "Pays couverts",
        value: s.countries_count.toLocaleString("fr"),
        sub: "géographies actives",
        icon: Globe,
        color: "text-emerald-600",
        bg: "bg-emerald-50",
      },
      {
        label: "Dans ton pipeline",
        value: pipeline
          .filter((d) => !["refuse", "non_pertinent"].includes(d.pipelineStatus))
          .length.toLocaleString("fr"),
        sub: "fonds suivis activement",
        icon: LayoutGrid,
        color: "text-amber-600",
        bg: "bg-amber-50",
      },
    ],
    highlights: (s: any) => [
      s.new_last_7_days > 0
        ? {
            title: `${s.new_last_7_days} nouveau${s.new_last_7_days > 1 ? "x" : ""} fonds détecté${s.new_last_7_days > 1 ? "s" : ""} cette semaine`,
            detail: "Passe-les en revue pour identifier les plus pertinents pour ton projet.",
            icon: Sparkles,
            className: "border-violet-200 bg-violet-50 text-violet-900",
          }
        : {
            title: "Veille investisseurs active",
            detail: "Les nouvelles levées et fonds sont collectés en continu. Configure tes alertes pour ne rien manquer.",
            icon: CheckCircle,
            className: "border-slate-200 bg-slate-50 text-slate-700",
          },
      {
        title: "Astuce : complète ton profil investisseur",
        detail: "Plus ton profil est précis (stade, secteur, ticket), mieux les recommandations sont ciblées.",
        icon: Users,
        className: "border-indigo-200 bg-indigo-50 text-indigo-900",
      },
      {
        title: `${s.countries_count} géographie${s.countries_count > 1 ? "s" : ""} dans la base`,
        detail: "Filtre par pays pour concentrer ta prospection sur tes marchés cibles.",
        icon: Globe,
        className: "border-emerald-200 bg-emerald-50 text-emerald-900",
      },
    ],
    marketSignals: (s: any) => [
      {
        label: "Géographies les plus actives",
        value: s.by_country.slice(0, 3).map((i: any) => i.country).join(" · ") || "À préciser",
        helper: "Pays où le plus de fonds et investisseurs sont référencés.",
      },
      {
        label: "Nouveaux fonds (7 jours)",
        value: s.new_last_7_days > 0
          ? `${s.new_last_7_days} nouveau${s.new_last_7_days > 1 ? "x" : ""} fonds`
          : "Aucune nouveauté récente",
        helper: "Rythme de détection — un bon indicateur de la vitalité de la veille.",
      },
      {
        label: "Couverture géographique",
        value: `${s.countries_count} pays référencés`,
        helper: "Étends ta recherche à de nouvelles zones pour diversifier les pistes.",
      },
      {
        label: "Confiance des fiches",
        value: s.avg_confidence > 0 ? `${s.avg_confidence}% de confiance moyenne` : "À enrichir",
        helper: "Les fiches avec un score élevé sont plus fiables pour la prise de décision.",
      },
    ],
  },
  public: {
    heroGradient: "from-primary-950 via-primary-900 to-blue-700",
    heroBadgeBg: "bg-white/10",
    heroBadgeText: "text-white/85",
    badgeLabel: "Financement Public",
    heroTitle: "Veille Financement Public",
    heroSubtitle:
      "Subventions, appels à projets, concours et prêts correspondant à votre profil et vos zones prioritaires.",
    catalogHref: "/devices",
    catalogLabel: "Explorer les opportunités",
    kpis: (s: any, _pipeline: DevicePipelineEntry[]) => [
      {
        label: "Opportunités actives",
        value: s.total_active.toLocaleString("fr"),
        sub: `${s.total} au total`,
        icon: CheckCircle,
        color: "text-green-600",
        bg: "bg-green-50",
      },
      {
        label: "Nouvelles (7 jours)",
        value: s.new_last_7_days.toLocaleString("fr"),
        sub: "ajoutées récemment",
        icon: TrendingUp,
        color: "text-blue-600",
        bg: "bg-blue-50",
      },
      {
        label: "Clôturent dans 30j",
        value: s.closing_soon_30d.toLocaleString("fr"),
        sub: `dont ${s.closing_soon_7d} dans 7j`,
        icon: Clock,
        color: "text-orange-600",
        bg: "bg-orange-50",
      },
      {
        label: "En attente validation",
        value: s.pending_validation.toLocaleString("fr"),
        sub: `confiance moy. ${s.avg_confidence}%`,
        icon: AlertTriangle,
        color: "text-yellow-600",
        bg: "bg-yellow-50",
      },
    ],
    highlights: (s: any) => [
      s.last_collection?.items_new > 0
        ? {
            title: `${s.last_collection.items_new} nouvelles opportunités détectées`,
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
      s.closing_soon_7d > 0
        ? {
            title: `${s.closing_soon_7d} deadline(s) dans 7 jours`,
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
      s.pending_validation > 0
        ? {
            title: `${s.pending_validation} opportunité(s) à vérifier`,
            detail: "Les fiches à valider peuvent cacher de bonnes pistes — confirme avant décision.",
            icon: AlertTriangle,
            className: "border-amber-200 bg-amber-50 text-amber-800",
          }
        : {
            title: "Catalogue propre",
            detail: "Les opportunités publiées sont bien qualifiées et plus faciles à exploiter.",
            icon: CheckCircle,
            className: "border-emerald-200 bg-emerald-50 text-emerald-800",
          },
    ],
    marketSignals: (s: any) => [
      {
        label: "Pays les plus actifs",
        value: s.by_country.slice(0, 3).map((i: any) => i.country).join(" · ") || "À préciser",
        helper: "Zones où le volume d'opportunités est actuellement le plus fort.",
      },
      {
        label: "Formats les plus présents",
        value: s.by_type.slice(0, 3).map((i: any) => DEVICE_TYPE_LABELS[i.type] || i.type).join(" · ") || "À préciser",
        helper: "Types de financement les plus visibles dans la veille récente.",
      },
      {
        label: "Rythme de détection",
        value: s.new_last_7_days > 0
          ? `${s.new_last_7_days} nouvelle${s.new_last_7_days > 1 ? "s" : ""} opportunité${s.new_last_7_days > 1 ? "s" : ""} en 7 jours`
          : "Aucune nouveauté récente",
        helper: "Pour savoir si la veille accélère ou si elle mérite d'être élargie.",
      },
      {
        label: "Pression calendrier",
        value: s.closing_soon_30d > 0
          ? `${s.closing_soon_30d} clôture${s.closing_soon_30d > 1 ? "s" : ""} dans 30 jours`
          : "Aucune échéance proche",
        helper: "Un bon repère pour arbitrer entre exploration et exécution.",
      },
    ],
  },
} as const;

// "both" = mêmes config que public
const getScopeConfig = (scope: FinancingScope) =>
  scope === "private" ? SCOPE_CONFIG.private : SCOPE_CONFIG.public;

// ── Composant ─────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [stats, setStats]                   = useState<any | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [loading, setLoading]               = useState(true);
  const [pipelineDevices, setPipelineDevices] = useState<DevicePipelineEntry[]>([]);
  const [scope, setScope]                   = useState<FinancingScope>(null);

  useEffect(() => {
    const savedScope = (localStorage.getItem("kafundo_financing_scope") || null) as FinancingScope;
    setScope(savedScope);

    dashboard.get(savedScope ?? undefined)
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));

    relevance.recommendations({ page_size: 4 })
      .then((data) => setRecommendations(Array.isArray(data?.items) ? data.items : []))
      .catch(() => setRecommendations([]));

    syncWorkspace()
      .catch(() => false)
      .finally(() => setPipelineDevices(listPipelineDevices()));
  }, []);

  // Top 3 priorités pipeline
  const topPriorities = useMemo(() => {
    return [...pipelineDevices]
      .filter((d) => !["refuse", "non_pertinent", "soumis"].includes(d.pipelineStatus))
      .sort((a, b) => {
        const sd = (PIPELINE_STATUS_ORDER[a.pipelineStatus] ?? 9) - (PIPELINE_STATUS_ORDER[b.pipelineStatus] ?? 9);
        if (sd !== 0) return sd;
        const pd = (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9);
        if (pd !== 0) return pd;
        const aD = a.closeDate ? new Date(a.closeDate).getTime() : Infinity;
        const bD = b.closeDate ? new Date(b.closeDate).getTime() : Infinity;
        return aD - bD;
      })
      .slice(0, 3);
  }, [pipelineDevices]);

  const weeklyActionItems = useMemo(() => [
    ...topPriorities.map((device) => ({
      id: `pipeline-${device.id}`,
      href: `/devices/${device.id}`,
      title: device.title,
      meta: `${PIPELINE_STATUS_LABELS[device.pipelineStatus]}${device.closeDate ? ` · ${formatDateRelative(device.closeDate)}` : ""}`,
      tone: device.closeDate ? "bg-orange-50 text-orange-700" : "bg-primary-50 text-primary-700",
      badge: device.closeDate ? "À traiter" : "À suivre",
    })),
    ...recommendations.slice(0, Math.max(0, 4 - topPriorities.length)).map((item) => ({
      id: `rec-${item.device.id}`,
      href: `/devices/${item.device.id}?from=recommendations`,
      title: item.device.title,
      meta: item.relevance.relevance_label,
      tone: "bg-emerald-50 text-emerald-700",
      badge: "Recommandée",
    })),
  ].slice(0, 4), [topPriorities, recommendations]);

  // ── Loading ────────────────────────────────────────────────────────────────

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

  const cfg = getScopeConfig(scope);
  const kpis = cfg.kpis(stats, pipelineDevices);
  const highlights = cfg.highlights(stats);
  const marketSignals = cfg.marketSignals(stats);
  const isPrivate = scope === "private";

  return (
    <AppLayout>

      {/* ── Hero banner ──────────────────────────────────────────────────────── */}
      <section className={clsx(
        "mb-6 overflow-hidden rounded-[28px] border border-white/10 px-6 py-6 text-white",
        "bg-gradient-to-br shadow-[0_20px_60px_-30px_rgba(37,99,235,0.45)]",
        cfg.heroGradient,
      )}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <span className={clsx(
              "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-widest",
              cfg.heroBadgeBg, cfg.heroBadgeText,
            )}>
              {isPrivate ? <TrendingUp className="h-3.5 w-3.5" /> : <Building2 className="h-3.5 w-3.5" />}
              {cfg.badgeLabel}
            </span>
            <h1 className="mt-3 text-2xl font-bold tracking-tight text-white md:text-3xl">
              {cfg.heroTitle}
            </h1>
            <p className="mt-2 text-sm leading-6 text-white/75">{cfg.heroSubtitle}</p>
          </div>

          {/* Mini KPIs hero */}
          <div className="flex flex-wrap gap-4 lg:shrink-0">
            <div className="rounded-2xl border border-white/15 bg-white/10 px-5 py-3 text-center backdrop-blur-sm">
              <p className="text-2xl font-bold">{stats.total_active.toLocaleString("fr")}</p>
              <p className="mt-0.5 text-[11px] text-white/70">
                {isPrivate ? "Fonds actifs" : "Opportunités actives"}
              </p>
            </div>
            <div className="rounded-2xl border border-white/15 bg-white/10 px-5 py-3 text-center backdrop-blur-sm">
              <p className="text-2xl font-bold">{stats.new_last_7_days.toLocaleString("fr")}</p>
              <p className="mt-0.5 text-[11px] text-white/70">Nouveaux (7j)</p>
            </div>
            <div className="rounded-2xl border border-white/15 bg-white/10 px-5 py-3 text-center backdrop-blur-sm">
              <p className="text-2xl font-bold">{stats.countries_count.toLocaleString("fr")}</p>
              <p className="mt-0.5 text-[11px] text-white/70">Pays couverts</p>
            </div>
          </div>
        </div>

        {/* Source health */}
        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-white/60">
            <Database className="h-3.5 w-3.5" />
            <span>
              {stats.sources.active} sources actives
              {stats.sources.in_error > 0 && (
                <span className="ml-1 text-red-300">· {stats.sources.in_error} en erreur</span>
              )}
            </span>
            {stats.last_collection.at && (
              <span className="ml-2 border-l border-white/20 pl-2">
                Dernière collecte {formatDateRelative(stats.last_collection.at)}
              </span>
            )}
          </div>
          <Link
            href={cfg.catalogHref}
            className="inline-flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-xs font-semibold text-white transition hover:bg-white/20"
          >
            {cfg.catalogLabel}
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </section>

      {/* ── Smart highlights ─────────────────────────────────────────────────── */}
      <div className="mb-6 grid grid-cols-1 gap-3 lg:grid-cols-3">
        {highlights.map(({ title, detail, icon: Icon, className }) => (
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

      {/* ── KPIs ─────────────────────────────────────────────────────────────── */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {kpis.map(({ label, value, sub, icon: Icon, color, bg }) => (
          <div key={label} className="card p-4">
            <div className="flex items-center gap-3">
              <div className={clsx("rounded-xl p-2.5", bg)}>
                <Icon className={clsx("h-5 w-5", color)} />
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

      {/* ── Pipeline priorités ───────────────────────────────────────────────── */}
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
              const deadline = device.closeDate ? new Date(device.closeDate).getTime() : null;
              const daysLeft = deadline ? Math.ceil((deadline - Date.now()) / 86_400_000) : null;
              const urgent = daysLeft !== null && daysLeft <= 14;
              return (
                <Link
                  key={device.id}
                  href={`/devices/${device.id}`}
                  className={clsx(
                    "group block rounded-2xl border px-4 py-4 transition-colors hover:border-primary-200 hover:bg-primary-50/40",
                    urgent ? "border-orange-200 bg-orange-50/50" : "border-slate-200 bg-white",
                  )}
                >
                  <div className="mb-2 flex items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-bold text-primary-700">
                      {idx + 1}
                    </span>
                    <span className={clsx("rounded-full px-2 py-0.5 text-[10px] font-semibold", PIPELINE_STATUS_COLORS[device.pipelineStatus])}>
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
                    {device.closeDate && !urgent ? <span>{formatDateRelative(device.closeDate)}</span> : <span />}
                    <ArrowRight className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Recommandations + Graphique pays ─────────────────────────────────── */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">

        {/* Recommandées */}
        <div className="card p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-700">Recommandées pour vous</h2>
              <p className="mt-0.5 text-xs text-gray-400">
                {isPrivate ? "Fonds sélectionnés selon votre profil investisseur." : "Opportunités triées selon votre profil."}
              </p>
            </div>
            <Link href="/recommendations" className="text-xs text-primary-600 hover:underline">
              Voir plus
            </Link>
          </div>
          {recommendations.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-10 text-center">
              <Sparkles className="mx-auto mb-2 h-6 w-6 text-slate-300" />
              <p className="text-sm font-medium text-slate-600">Complète ton profil</p>
              <p className="mt-1 text-xs text-slate-400">
                {isPrivate
                  ? "Renseigne tes secteurs et zones cibles pour voir les fonds recommandés."
                  : "Renseigne tes secteurs et pays pour voir des opportunités ciblées."}
              </p>
              <Link href="/onboarding" className="mt-3 inline-block text-xs font-semibold text-primary-600 hover:underline">
                Configurer mon profil →
              </Link>
            </div>
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
                    <span className={clsx(
                      "shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold",
                      isPrivate ? "bg-violet-100 text-violet-700" : "bg-emerald-100 text-emerald-700",
                    )}>
                      {item.relevance.priority_level}
                    </span>
                  </div>
                  <p className={clsx(
                    "mt-3 text-xs font-semibold uppercase tracking-[0.16em]",
                    isPrivate ? "text-violet-600" : "text-primary-600",
                  )}>
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

        {/* Graphique pays */}
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">
            {isPrivate ? "Géographie des fonds" : "Répartition par pays"}
          </h2>
          {stats.by_country.length === 0 ? (
            <div className="flex h-48 items-center justify-center text-xs text-slate-400">
              Aucune donnée disponible
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={stats.by_country.slice(0, 8)} layout="vertical" margin={{ left: 60 }}>
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="country" tick={{ fontSize: 11 }} width={60} />
                <Tooltip formatter={(v) => [v, isPrivate ? "Fonds" : "Opportunités"]} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {stats.by_country.slice(0, 8).map((_: any, i: number) => (
                    <Cell key={i} fill={isPrivate
                      ? ["#7c3aed","#6d28d9","#5b21b6","#4c1d95","#8b5cf6","#a78bfa","#c4b5fd","#ddd6fe"][i % 8]
                      : CHART_COLORS[i % CHART_COLORS.length]
                    } />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ── Type chart (public only) ──────────────────────────────────────────── */}
      {!isPrivate && stats.by_type.length > 0 && (
        <div className="mb-6 card p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">Répartition par type d'aide</h2>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width="40%" height={180}>
              <PieChart>
                <Pie data={stats.by_type} dataKey="count" nameKey="type" cx="50%" cy="50%" outerRadius={80} innerRadius={40}>
                  {stats.by_type.map((_: any, i: number) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v, _, p) => [v, DEVICE_TYPE_LABELS[p.payload.type] || p.payload.type]} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-2">
              {stats.by_type.slice(0, 7).map((item: any, i: number) => (
                <div key={item.type} className="flex items-center gap-2 text-xs">
                  <div className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }} />
                  <span className="flex-1 truncate text-gray-600">{DEVICE_TYPE_LABELS[item.type] || item.type}</span>
                  <span className="font-semibold text-gray-900">{item.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── À lancer cette semaine + Signaux marché ──────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

        {/* Actions de la semaine */}
        <div className="card p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-700">
                {isPrivate ? "Fonds à traiter cette semaine" : "À lancer cette semaine"}
              </h2>
              <p className="mt-1 text-xs text-gray-400">
                {isPrivate
                  ? "Les fonds dans ton pipeline qui méritent une action rapide."
                  : "Les opportunités sur lesquelles tu peux agir tout de suite."}
              </p>
            </div>
            <Link href="/workspace" className="text-xs text-primary-600 hover:underline">
              Voir mon suivi
            </Link>
          </div>
          {weeklyActionItems.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
              <p className="text-sm font-medium text-slate-700">
                {isPrivate ? "Ton pipeline investisseurs est vide" : "Ton espace est encore vide"}
              </p>
              <p className="mt-1 text-sm text-slate-500">
                {isPrivate
                  ? "Explore les fonds disponibles et ajoute-les à ton suivi."
                  : "Ajoute des favoris ou complète ton profil pour faire remonter des priorités."}
              </p>
              <Link
                href={cfg.catalogHref}
                className={clsx(
                  "mt-3 inline-block text-xs font-semibold hover:underline",
                  isPrivate ? "text-violet-600" : "text-primary-600",
                )}
              >
                {cfg.catalogLabel} →
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {weeklyActionItems.map((item) => (
                <Link
                  key={item.id}
                  href={item.href}
                  className="flex items-start gap-3 rounded-2xl border border-slate-200 px-3 py-3 transition-colors hover:border-primary-200 hover:bg-primary-50/40"
                >
                  <span className={clsx("shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold", item.tone)}>
                    {item.badge}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-sm font-medium text-slate-900">{item.title}</p>
                    <p className="mt-1 text-xs text-slate-500">{item.meta}</p>
                  </div>
                  <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-300" />
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Signaux marché */}
        <div className="card p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-700">
                {isPrivate ? "Concentrer ta prospection" : "Où concentrer ta veille"}
              </h2>
              <p className="mt-1 text-xs text-gray-400">
                {isPrivate
                  ? "Signaux clés pour orienter ta recherche d'investisseurs."
                  : "Une lecture simple du marché pour décider plus vite."}
              </p>
            </div>
            <Link href={cfg.catalogHref} className="text-xs text-primary-600 hover:underline">
              {cfg.catalogLabel}
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
